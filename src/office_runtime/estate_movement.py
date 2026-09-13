"""Read-only, delta-oriented Estate Movement Digest producer.

The producer observes a caller-bounded local repository estate.  It never
fetches, pulls, commits, edits, or executes a participating repository.  Its
claims are deliberately modest: categories are evidence labels over commits,
materializations, and run receipts, not lifecycle or priority decisions.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


IGNORE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".cache", ".pytest_cache", ".ruff_cache", "dist", "build", ".next"}
MATERIALIZED_DIRS = {"artifacts", "reports", "generated", "builds", "runs", "exports"}
SAFE_SUFFIXES = {".md", ".json", ".jsonl", ".csv", ".html", ".yaml", ".yml"}
AUTHORITY_NAMES = {"SYSTEM.yaml", "AGENTS.md", "OWNERSHIP.md", "repositories.yaml", "systems.yaml", "lifecycle.yaml", "lifecycle-decisions-2026.yaml"}
MATERIALIZATION_NAME_RE = re.compile(r"(?:manifest|digest|summary|report|closure|receipt|showcase|qa|catalog|index)", re.I)


def _parse_start(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _parse_end(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if len(value) == 10:
        parsed += timedelta(days=1)
    return parsed.replace(tzinfo=timezone.utc)


def _date_in_window(value: datetime, start: datetime, end: datetime) -> bool:
    return start <= value < end


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:16]


def _git(repo: Path, args: list[str]) -> str:
    completed = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=False, timeout=10)
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout or "git error").strip()[:300])
    return completed.stdout


def discover_repos(roots: Iterable[Path], max_depth: int = 4) -> list[Path]:
    found: dict[str, Path] = {}

    def walk(path: Path, depth: int) -> None:
        if depth > max_depth or not path.is_dir():
            return
        if (path / ".git").exists():
            try:
                if _git(path, ["rev-parse", "--is-inside-work-tree"]).strip() == "true":
                    found[str(path.resolve())] = path.resolve()
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
        try:
            children = sorted(path.iterdir(), key=lambda child: child.name.casefold())
        except OSError:
            return
        for child in children:
            if child.is_dir() and child.name not in IGNORE_DIRS:
                walk(child, depth + 1)

    for root in roots:
        walk(root.expanduser().resolve(), 0)
    return [found[key] for key in sorted(found)]


def _commit_evidence(repo: Path, start: str, end: str) -> list[dict[str, Any]]:
    fmt = "%H%x1f%h%x1f%aI%x1f%s"
    try:
        raw = _git(repo, ["log", f"--since={start}", f"--until={end}", f"--format={fmt}"])
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return [{"kind": "git_error", "evidence_id": f"git-error:{repo.name}:{_sha(str(exc))}", "repo": repo.name, "error": type(exc).__name__}]
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        full, short, when, subject = (line.split("\x1f") + [""] * 4)[:4]
        if not full:
            continue
        try:
            files = [path for path in _git(repo, ["show", "--name-only", "--format=", full]).splitlines() if path]
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            files = []
        rows.append({
            "kind": "git_commit", "evidence_id": f"git:{repo.name}:{short}", "repo": repo.name,
            "sha": short, "timestamp": when, "subject": subject[:240], "files": sorted(files)[:80],
        })
    return rows


def _materialization_evidence(repos: Iterable[Path], start: datetime, end: datetime, limit: int = 400, exclude_root: Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for repo in repos:
        for directory in sorted(MATERIALIZED_DIRS):
            root = repo / directory
            if not root.is_dir():
                continue
            try:
                paths = sorted(root.rglob("*"), key=lambda item: str(item))
            except OSError:
                continue
            for path in paths:
                if len(rows) >= limit:
                    return rows
                if not path.is_file() or path.suffix.lower() not in SAFE_SUFFIXES or not MATERIALIZATION_NAME_RE.search(path.name) or any(part in IGNORE_DIRS for part in path.parts):
                    continue
                if exclude_root:
                    try:
                        path.resolve().relative_to(exclude_root.resolve())
                        continue
                    except ValueError:
                        pass
                try:
                    changed = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                except OSError:
                    continue
                if not _date_in_window(changed, start, end):
                    continue
                relative = path.relative_to(repo).as_posix()
                rows.append({
                    "kind": "materialization", "evidence_id": f"file:{repo.name}:{_sha(relative + changed.isoformat())}",
                    "repo": repo.name, "path": relative, "timestamp": changed.isoformat(),
                })
    return rows


def _receipt_evidence(repos: Iterable[Path], start: datetime, end: datetime, limit: int = 300) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for repo in repos:
        events = repo / "artifacts" / "logs" / "events"
        if not events.is_dir():
            continue
        for path in sorted(events.glob("*.jsonl")):
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines:
                if len(rows) >= limit:
                    return rows
                try:
                    item = json.loads(line)
                    timestamp = datetime.fromisoformat(str(item.get("ts", "")).replace("Z", "+00:00"))
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    if not _date_in_window(timestamp.astimezone(timezone.utc), start, end):
                        continue
                except (ValueError, TypeError, json.JSONDecodeError):
                    continue
                status = str(item.get("status", "")).lower()
                level = str(item.get("level", "")).lower()
                event = str(item.get("event", ""))[:160]
                # One terminal/exception observation per run is more useful
                # than every progress event in a movement digest.
                if event != "run.end" and status not in {"error", "failed", "blocked"} and level not in {"error", "warning"}:
                    continue
                module = str(item.get("module", "unknown"))[:100]
                run_id = str(item.get("run_id", "unknown"))[:100]
                # A digest should not manufacture movement merely because it
                # wrote its own observational log before collection.
                if module == "estate.movement":
                    continue
                rows.append({
                    "kind": "run_receipt", "evidence_id": f"receipt:{repo.name}:{module}:{run_id}",
                    "repo": repo.name, "timestamp": timestamp.isoformat(), "module": module, "run_id": run_id,
                    "status": status or level, "event": event,
                })
    return rows


def _authority_evidence(control_plane: Path | None, start: datetime, end: datetime) -> list[dict[str, Any]]:
    if not control_plane or not (control_plane / "estate").is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted((control_plane / "estate").rglob("*"), key=lambda item: str(item)):
        if not path.is_file() or path.name not in AUTHORITY_NAMES:
            continue
        try:
            changed = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if _date_in_window(changed, start, end):
            relative = path.relative_to(control_plane).as_posix()
            rows.append({"kind": "authority_file", "evidence_id": f"authority:{_sha(relative + changed.isoformat())}", "repo": control_plane.name, "path": relative, "timestamp": changed.isoformat()})
    return rows


def _load_previous(path: Path | None) -> set[str]:
    if not path or not path.is_file():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("evidence_ids", []))
    except (OSError, json.JSONDecodeError):
        return set()


def _matches(text: str, expression: str) -> bool:
    return bool(re.search(expression, text, re.I))


def classify(evidence: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {key: [] for key in ("NEW", "CLOSED", "BECAME TRUE", "FAILED", "AUTHORITY CHANGED", "RECOVERY IMPROVED", "STILL BLOCKED", "COMPOUNDING CROSSOVERS", "NEXT PULL")}
    for item in evidence:
        text = " ".join([str(item.get("subject", "")), " ".join(item.get("files", [])), str(item.get("event", "")), str(item.get("path", ""))])
        kind, status = item.get("kind"), str(item.get("status", "")).lower()
        if kind == "materialization" or _matches(text, r"\b(feat|add|new|create|introduce)\b"):
            groups["NEW"].append(item)
        if _matches(text, r"\b(close[ds]?|resolve[ds]?|complete[ds]?|finish(?:ed|es)?)\b"):
            groups["CLOSED"].append(item)
        if kind == "run_receipt" and status == "ok" or _matches(text, r"\b(prove[ds]?|validat(?:e|ed|ion)|materializ(?:e|ed|ation)|publish(?:ed)?)\b"):
            groups["BECAME TRUE"].append(item)
        if kind == "git_error" or status in {"error", "failed"} or _matches(text, r"\b(fail(?:ed|ure)?|error|broken)\b"):
            groups["FAILED"].append(item)
        if kind == "authority_file" or _matches(text, r"\b(authority|ownership|lifecycle|governance|SYSTEM\.yaml|AGENTS\.md)\b"):
            groups["AUTHORITY CHANGED"].append(item)
        if _matches(text, r"\b(recover(?:y|ed)?|rollback|retry|idempoten|resilien|repair)\b"):
            groups["RECOVERY IMPROVED"].append(item)
        if status == "blocked" or _matches(text, r"\b(blocked|blocker|waiting)\b"):
            groups["STILL BLOCKED"].append(item)
        if "capability-atlas" in text or _matches(text, r"\b(crossover|consumer|adapter|contract|reuse|integration)\b"):
            groups["COMPOUNDING CROSSOVERS"].append(item)
    for category in ("FAILED", "STILL BLOCKED", "AUTHORITY CHANGED"):
        for item in groups[category][:8]:
            groups["NEXT PULL"].append(item)
    for key in groups:
        groups[key] = sorted({item["evidence_id"]: item for item in groups[key]}.values(), key=lambda item: item["evidence_id"])
    return groups


def render_markdown(digest_id: str, manifest: dict[str, Any], groups: dict[str, list[dict[str, Any]]]) -> str:
    lines = [f"# Estate Movement Digest — {digest_id}", "", f"Window: `{manifest['window']['start']}` through `{manifest['window']['end']}` (end exclusive internally).", f"Delta mode: `{manifest['delta_mode']}`. New evidence: {manifest['new_evidence_count']} of {manifest['evidence_count']} observed rows.", "", "This is a read-only evidence delta. It does not alter lifecycle, authority, readiness, or priority.", ""]
    for category, items in groups.items():
        lines += [f"## {category}", ""]
        if not items:
            lines += ["No new evidence matched this category.", ""]
            continue
        for item in items:
            detail = item.get("subject") or item.get("event") or item.get("path") or item.get("status") or item["kind"]
            lines.append(f"- `{item['evidence_id']}` — `{item.get('repo', 'unknown')}`: {detail}")
        lines.append("")
    lines += ["## Evidence accounting", "", f"- Repositories observed: {manifest['repositories_observed']}", f"- Git commits: {manifest['counts'].get('git_commit', 0)}", f"- Materializations: {manifest['counts'].get('materialization', 0)}", f"- Run receipts: {manifest['counts'].get('run_receipt', 0)}", f"- Authority files: {manifest['counts'].get('authority_file', 0)}", f"- Observation errors: {manifest['counts'].get('git_error', 0)}", ""]
    return "\n".join(lines)


def produce(*, digest_id: str, roots: list[Path], start: str, end: str, out_root: Path, previous_manifest: Path | None = None, control_plane: Path | None = None, max_depth: int = 4) -> dict[str, Any]:
    start_dt, end_dt = _parse_start(start), _parse_end(end)
    repos = discover_repos(roots, max_depth=max_depth)
    # Git's --until is inclusive, while the producer represents an exclusive
    # upper bound internally. Passing the final representable instant keeps
    # date-only and datetime windows aligned with file/receipt collection.
    git_end = (end_dt - timedelta(microseconds=1)).isoformat()
    all_evidence = _commit_evidence_rows(repos, start_dt.isoformat(), git_end)
    all_evidence += _materialization_evidence(repos, start_dt, end_dt, exclude_root=out_root)
    all_evidence += _receipt_evidence(repos, start_dt, end_dt)
    all_evidence += _authority_evidence(control_plane, start_dt, end_dt)
    all_evidence = sorted({item["evidence_id"]: item for item in all_evidence}.values(), key=lambda item: item["evidence_id"])
    prior_ids = _load_previous(previous_manifest)
    delta = [item for item in all_evidence if item["evidence_id"] not in prior_ids]
    counts = {kind: sum(item["kind"] == kind for item in all_evidence) for kind in {item["kind"] for item in all_evidence}}
    manifest = {
        "schema_version": 1, "digest_id": digest_id, "producer": "ops.estate-movement@1",
        "window": {"start": start, "end": end}, "delta_mode": "baseline" if not previous_manifest else "against-previous",
        "previous_manifest": previous_manifest.name if previous_manifest else None,
        "repositories_observed": len(repos), "evidence_count": len(all_evidence), "new_evidence_count": len(delta),
        "evidence_ids": [item["evidence_id"] for item in all_evidence], "new_evidence_ids": [item["evidence_id"] for item in delta], "counts": counts,
        "root_labels": sorted({root.name for root in roots}), "control_plane_label": control_plane.name if control_plane else None,
    }
    groups = classify(delta)
    target = out_root / digest_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "evidence.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in all_evidence), encoding="utf-8")
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest_path = target / f"{digest_id}.md"
    digest_path.write_text(render_markdown(digest_id, manifest, groups), encoding="utf-8")
    return {
        "status": "ok", "digest_id": digest_id, "out": str(target), "manifest": str(target / "manifest.json"),
        "digest": str(digest_path), "repositories_observed": len(repos), "evidence_count": len(all_evidence),
        "new_evidence_count": len(delta), "delta_mode": manifest["delta_mode"], "counts": counts,
    }


def _commit_evidence_rows(repos: Iterable[Path], start: str, end: str) -> list[dict[str, Any]]:
    return [item for repo in repos for item in _commit_evidence(repo, start, end)]
