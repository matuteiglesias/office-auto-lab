from __future__ import annotations

import argparse
import importlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from office_runtime.editorial.contracts import ContractError, RUN_BUNDLE_SCHEMA
from office_runtime.editorial.run_bundle import atomic_write_run_bundle, validate_run_bundle
from office_runtime.editorial.staging.sheets import (
    GoogleSheetsGateway,
    ProjectionResult,
    SheetGateway,
    SheetProjectionError,
    project_run_bundle,
)

DEFAULT_LOOKBACK_HOURS = 96
MAX_WINDOW_HOURS = 24 * 14
_PROVIDER_ENV = "EDITORIAL_DEV_BUNDLE_PROVIDER"
_PR_RE = re.compile(r"^[^/ #]+/[^# ]+#[1-9][0-9]*$")


class EditorialStagingError(RuntimeError):
    pass


@dataclass(frozen=True)
class StageRequest:
    profile_id: str
    pr_ref: str | None = None
    since: str | None = None
    until: str | None = None
    date_value: str | None = None
    lookback_hours: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "pr_ref": self.pr_ref,
            "since": self.since,
            "until": self.until,
            "date": self.date_value,
            "lookback_hours": self.lookback_hours,
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str, label: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise EditorialStagingError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_window(start: datetime, end: datetime) -> None:
    if end <= start:
        raise EditorialStagingError("window end must be after window start")
    if end - start > timedelta(hours=MAX_WINDOW_HOURS):
        raise EditorialStagingError(
            f"manual window exceeds the bounded {MAX_WINDOW_HOURS // 24}-day maximum"
        )


def resolve_request(
    *,
    profile_id: str = "dev",
    pr_ref: str | None = None,
    since: str | None = None,
    until: str | None = None,
    date_value: str | None = None,
    lookback_hours: int | None = None,
    now: datetime | None = None,
) -> StageRequest:
    selectors = [
        pr_ref is not None,
        since is not None,
        date_value is not None,
        lookback_hours is not None,
    ]
    if sum(selectors) != 1:
        raise EditorialStagingError(
            "choose exactly one source selector: --pr, --since, --date, or --lookback-hours"
        )
    if profile_id != "dev":
        raise EditorialStagingError("Editorial Dev Staging v1 only supports profile_id='dev'")

    if pr_ref is not None:
        if not _PR_RE.fullmatch(pr_ref.strip()):
            raise EditorialStagingError("--pr must use exact owner/repo#PR syntax")
        if until is not None:
            raise EditorialStagingError("--until is only valid with --since")
        return StageRequest(profile_id=profile_id, pr_ref=pr_ref.strip())

    current = (now or _utc_now()).astimezone(timezone.utc)

    if date_value is not None:
        if until is not None:
            raise EditorialStagingError("--until is only valid with --since")
        try:
            parsed_date = date.fromisoformat(date_value)
        except ValueError as exc:
            raise EditorialStagingError("--date must use YYYY-MM-DD") from exc
        start = datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return StageRequest(
            profile_id=profile_id,
            since=start.isoformat().replace("+00:00", "Z"),
            until=end.isoformat().replace("+00:00", "Z"),
            date_value=date_value,
        )

    if lookback_hours is not None:
        if until is not None:
            raise EditorialStagingError("--until is not valid with --lookback-hours")
        if lookback_hours < 1 or lookback_hours > MAX_WINDOW_HOURS:
            raise EditorialStagingError(
                f"--lookback-hours must be between 1 and {MAX_WINDOW_HOURS}"
            )
        start = current - timedelta(hours=lookback_hours)
        return StageRequest(
            profile_id=profile_id,
            since=start.isoformat().replace("+00:00", "Z"),
            until=current.isoformat().replace("+00:00", "Z"),
            lookback_hours=lookback_hours,
        )

    assert since is not None
    start = _parse_datetime(since, "--since")
    end = _parse_datetime(until, "--until") if until else current
    _validate_window(start, end)
    return StageRequest(
        profile_id=profile_id,
        since=start.isoformat().replace("+00:00", "Z"),
        until=end.isoformat().replace("+00:00", "Z"),
    )


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EditorialStagingError(f"run bundle not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EditorialStagingError(f"run bundle is not valid JSON: {path}") from exc
    if not isinstance(payload, Mapping):
        raise EditorialStagingError("run bundle must be a JSON object")
    return payload


def _validate_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    try:
        validated = validate_run_bundle(bundle)
    except ContractError as exc:
        raise EditorialStagingError(f"invalid canonical editorial run bundle: {exc}") from exc
    if validated.get("schema_version") != RUN_BUNDLE_SCHEMA:
        raise EditorialStagingError("unsupported editorial run-bundle schema_version")
    if validated.get("profile_id") != "dev":
        raise EditorialStagingError("run bundle profile_id must be 'dev'")
    return validated


def _load_provider(entrypoint: str) -> Callable[[Mapping[str, Any]], Mapping[str, Any]]:
    if ":" not in entrypoint:
        raise EditorialStagingError(
            "bundle provider must use module:function syntax, e.g. package.module:produce_bundle"
        )
    module_name, function_name = entrypoint.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise EditorialStagingError(f"cannot import bundle provider module {module_name!r}") from exc
    provider = getattr(module, function_name, None)
    if not callable(provider):
        raise EditorialStagingError(f"bundle provider {entrypoint!r} is not callable")
    return provider


def resolve_bundle(
    request: StageRequest | None,
    *,
    bundle_in: Path | None = None,
    provider_entrypoint: str | None = None,
) -> Mapping[str, Any]:
    if bundle_in is not None:
        if provider_entrypoint:
            raise EditorialStagingError("--bundle-in cannot be combined with --provider")
        bundle = _load_json(bundle_in)
        _validate_bundle(bundle)
        return bundle

    if request is None:
        raise EditorialStagingError("a source request is required when --bundle-in is not used")
    entrypoint = provider_entrypoint or os.environ.get(_PROVIDER_ENV)
    if not entrypoint:
        raise EditorialStagingError(
            f"no candidate-production adapter configured; set {_PROVIDER_ENV} or pass --provider"
        )
    provider = _load_provider(entrypoint)
    produced = provider(request.as_dict())
    if not isinstance(produced, Mapping):
        raise EditorialStagingError("bundle provider must return a mapping")
    _validate_bundle(produced)
    return produced


def _safe_run_id(bundle: Mapping[str, Any]) -> str:
    value = bundle.get("run_id")
    if not isinstance(value, str) or not value.strip():
        raise EditorialStagingError("run bundle run_id must be a non-empty string")
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    if not safe:
        raise EditorialStagingError("run_id cannot be converted into a safe artifact name")
    return safe


def write_bundle_artifact(bundle: Mapping[str, Any], out_dir: Path) -> Path:
    validated = _validate_bundle(bundle)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{_safe_run_id(validated)}.json"
    try:
        return atomic_write_run_bundle(target, validated)
    except ContractError as exc:
        raise EditorialStagingError(f"cannot write immutable canonical run bundle: {exc}") from exc


def _relative_artifact_ref(path: Path) -> str:
    if path.is_absolute():
        raise EditorialStagingError("Sheet run_bundle_ref must not contain an absolute local path")
    parts = path.parts
    if ".." in parts:
        raise EditorialStagingError("Sheet run_bundle_ref must not escape the repository")
    return path.as_posix()


def inventory_status(bundle: Mapping[str, Any]) -> str:
    batch = bundle.get("batch")
    if isinstance(batch, Mapping):
        status = batch.get("inventory_status")
        if isinstance(status, str) and status:
            return status
    status = bundle.get("status")
    return str(status) if status is not None else "FAILED"


def make_summary(
    bundle: Mapping[str, Any],
    *,
    projection: ProjectionResult | None,
    artifact_ref: str,
    apply_sheet: bool,
    projection_error: str | None = None,
) -> dict[str, Any]:
    retrieval = bundle.get("retrieval") if isinstance(bundle.get("retrieval"), Mapping) else {}
    batch = bundle.get("batch") if isinstance(bundle.get("batch"), Mapping) else {}
    candidate_ids = batch.get("candidate_ids")
    if not isinstance(candidate_ids, list):
        candidate_ids = []
    return {
        "run_id": bundle.get("run_id"),
        "profile_id": bundle.get("profile_id"),
        "policy_ref": (
            bundle.get("policy", {}).get("policy_ref")
            if isinstance(bundle.get("policy"), Mapping)
            else None
        ),
        "retrieval_sources_attempted": retrieval.get("sources_attempted")
        or retrieval.get("intended_sources")
        or [],
        "retrieval_sources_reached": retrieval.get("sources_reached")
        or retrieval.get("actual_sources")
        or [],
        "evidence_count": len(bundle.get("evidence", {}).get("items", []))
        if isinstance(bundle.get("evidence"), Mapping)
        and isinstance(bundle.get("evidence", {}).get("items"), list)
        else 0,
        "story_count": len(bundle.get("stories", []))
        if isinstance(bundle.get("stories"), list)
        else 0,
        "angle_count": len(bundle.get("angles", []))
        if isinstance(bundle.get("angles"), list)
        else 0,
        "candidate_count": len(candidate_ids),
        "inventory_status": inventory_status(bundle),
        "source_failures": retrieval.get("access_failures", []),
        "projection_status": (
            "failed"
            if projection_error is not None
            else "applied"
            if projection is not None
            else "not_requested"
        ),
        "projection": projection.as_dict() if projection is not None else None,
        "projection_error": projection_error,
        "run_bundle_ref": artifact_ref,
        "sheet_mutation_requested": apply_sheet,
    }


def write_summary_markdown(summary: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Editorial Dev Staging run",
        "",
        f"- run_id: `{summary.get('run_id')}`",
        f"- profile: `{summary.get('profile_id')}`",
        f"- inventory: `{summary.get('inventory_status')}`",
        f"- candidates: `{summary.get('candidate_count')}`",
        f"- evidence: `{summary.get('evidence_count')}`",
        f"- stories: `{summary.get('story_count')}`",
        f"- angles: `{summary.get('angle_count')}`",
        f"- projection: `{summary.get('projection_status')}`",
        f"- run bundle: `{summary.get('run_bundle_ref')}`",
    ]
    failures = summary.get("source_failures")
    if failures:
        lines.extend(["", "Source failures were recorded in the run bundle/retrieval summary."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def stage_bundle(
    bundle: Mapping[str, Any],
    *,
    out_dir: Path,
    summary_out: Path,
    apply_sheet: bool,
    sheet_id: str | None = None,
    gateway: SheetGateway | None = None,
) -> tuple[dict[str, Any], Path]:
    artifact_path = write_bundle_artifact(bundle, out_dir)
    try:
        artifact_ref = _relative_artifact_ref(artifact_path)
    except EditorialStagingError:
        # CLI defaults are repository-relative. An explicitly absolute out-dir is valid
        # for local evidence, but must not leak into the Sheet projection.
        artifact_ref = f"editorial-run:{_safe_run_id(bundle)}"

    projection: ProjectionResult | None = None
    projection_error: str | None = None
    try:
        if apply_sheet:
            target_gateway = gateway or GoogleSheetsGateway.from_environment(sheet_id)
            projection = project_run_bundle(bundle, target_gateway, run_bundle_ref=artifact_ref)
    except SheetProjectionError as exc:
        projection_error = type(exc).__name__
        summary = make_summary(
            bundle,
            projection=None,
            artifact_ref=artifact_ref,
            apply_sheet=apply_sheet,
            projection_error=projection_error,
        )
        write_summary_markdown(summary, summary_out)
        raise

    summary = make_summary(
        bundle,
        projection=projection,
        artifact_ref=artifact_ref,
        apply_sheet=apply_sheet,
        projection_error=projection_error,
    )
    write_summary_markdown(summary, summary_out)
    return summary, artifact_path


def add_stage_arguments(parser: argparse.ArgumentParser) -> None:
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--pr", dest="pr_ref", help="Process one exact owner/repo#PR source.")
    selector.add_argument("--since", help="Process an explicit ISO-8601 window start.")
    selector.add_argument("--date", dest="date_value", help="Process one UTC YYYY-MM-DD day.")
    selector.add_argument(
        "--lookback-hours",
        type=int,
        help=f"Process a bounded overlapping lookback (max {MAX_WINDOW_HOURS}h).",
    )
    parser.add_argument("--until", help="Optional ISO-8601 window end; valid only with --since.")
    parser.add_argument(
        "--bundle-in",
        type=Path,
        help="Projection-only mode: consume an already-generated editorial.run_bundle.v1.",
    )
    parser.add_argument(
        "--provider",
        help=f"Candidate producer adapter as module:function; defaults to {_PROVIDER_ENV}.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/editorial/runs"),
        help="Repository-local immutable run-bundle artifact directory.",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=Path("artifacts/editorial/run-summary.md"),
        help="Operator summary path.",
    )
    parser.add_argument(
        "--apply-sheet",
        action="store_true",
        help="Explicitly authorize projection into the configured staging workbook.",
    )
    parser.add_argument(
        "--sheet-id",
        default=None,
        help="Staging workbook ID; defaults to EDITORIAL_DEV_SHEET_ID.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force local-artifact-only mode. Cannot be combined with --apply-sheet.",
    )


def execute_stage_namespace(args: argparse.Namespace) -> int:
    if args.dry_run and args.apply_sheet:
        raise EditorialStagingError("--dry-run cannot be combined with --apply-sheet")
    if args.bundle_in is not None:
        if any((args.pr_ref, args.since, args.date_value, args.lookback_hours, args.until)):
            raise EditorialStagingError(
                "--bundle-in is projection-only and cannot be combined with source selectors"
            )
        request = None
    else:
        request = resolve_request(
            pr_ref=args.pr_ref,
            since=args.since,
            until=args.until,
            date_value=args.date_value,
            lookback_hours=args.lookback_hours,
        )
    bundle = resolve_bundle(
        request,
        bundle_in=args.bundle_in,
        provider_entrypoint=args.provider,
    )
    summary, _ = stage_bundle(
        bundle,
        out_dir=args.out_dir,
        summary_out=args.summary_out,
        apply_sheet=bool(args.apply_sheet and not args.dry_run),
        sheet_id=args.sheet_id,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 1 if inventory_status(bundle) == "FAILED" else 0


def build_standalone_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bounded Editorial Dev Staging v1 operator/runtime entrypoint."
    )
    add_stage_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_standalone_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return execute_stage_namespace(args)
    except (EditorialStagingError, SheetProjectionError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
