from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd

from .config import OfficeConfig
from .io import normalize, read_sheet_values, write_json


SCHEMA_VERSION = "ops.control-state-snapshot.v2"


@dataclass(frozen=True)
class TableSpec:
    name: str
    gid_env: str
    default_gid: str
    key: str
    required: tuple[str, ...]
    front_fk: bool = False


TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        "front_registry_v2",
        "OFFICE_V2_FRONT_GID",
        "1428476550",
        "front_id",
        ("front_id", "slug", "title", "group_key", "lifecycle_status"),
    ),
    TableSpec(
        "carry_state_v2",
        "OFFICE_V2_CARRY_GID",
        "27157683",
        "front_id",
        ("front_id", "carry_status", "horizon", "priority_mode", "needs", "principal_mode"),
        front_fk=True,
    ),
    TableSpec(
        "Capabilities_v2",
        "OFFICE_V2_CAPABILITIES_GID",
        "1779330064",
        "front_id",
        ("front_id",),
        front_fk=True,
    ),
    TableSpec(
        "operator_contract_v2",
        "OFFICE_V2_OPERATOR_CONTRACT_GID",
        "1747453443",
        "contract_id",
        ("contract_id", "front_id", "operator_name", "operator_class", "contract_status", "contract_version"),
        front_fk=True,
    ),
    TableSpec(
        "front_aliases_v2",
        "OFFICE_V2_FRONT_ALIASES_GID",
        "1657847512",
        "alias_id",
        ("alias_id", "front_id", "alias_namespace", "alias_value", "resolution_status"),
        front_fk=True,
    ),
    TableSpec(
        "support_artifacts_v2",
        "OFFICE_V2_SUPPORT_ARTIFACTS_GID",
        "432491750",
        "artifact_id",
        ("artifact_id", "front_id", "artifact_role", "artifact_kind", "authority_class", "status"),
        front_fk=True,
    ),
    TableSpec(
        "REPO MONITOR_v2",
        "OFFICE_V2_REPO_MONITOR_GID",
        "1165460743",
        "binding_id",
        ("binding_id", "front_id", "repo_id", "binding_role", "binding_status"),
        front_fk=True,
    ),
    TableSpec(
        "repo_workspaces_v2",
        "OFFICE_V2_REPO_WORKSPACES_GID",
        "915945555",
        "workspace_id",
        ("workspace_id", "repo_id", "local_path", "checkout_kind", "workspace_status"),
    ),
    TableSpec(
        "runtime_health_v2",
        "OFFICE_V2_RUNTIME_HEALTH_GID",
        "1528387812",
        "front_id",
        ("front_id", "health_status", "health_bucket", "source_run_id", "generated_at"),
        front_fk=True,
    ),
)


class ControlSnapshotError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _gid(spec: TableSpec) -> str:
    return os.environ.get(spec.gid_env, "").strip() or spec.default_gid


def _clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    # Sheets ranges may materialize trailing blank cells as NaN. Replace
    # missing scalars before normalize() stringifies them as the literal
    # value "nan", which would look like a real primary key.
    out = normalize(frame.where(pd.notna(frame), ""))
    if out.empty:
        return out

    def has_value(value: object) -> bool:
        if value is None or pd.isna(value):
            return False
        return bool(str(value).strip())

    default_false_columns = {"is_primary", "enabled", "cap_repo"}

    def is_material_row(row: pd.Series) -> bool:
        values = [(str(column), value) for column, value in row.items() if has_value(value)]
        if not values:
            return False
        return not all(
            column in default_false_columns and str(value).upper() == "FALSE"
            for column, value in values
        )

    nonempty = out.apply(is_material_row, axis=1)
    return out.loc[nonempty].reset_index(drop=True)


def _records(frame: pd.DataFrame) -> list[dict[str, str]]:
    return [
        {str(key): str(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _issue(severity: str, table: str, code: str, message: str, **extra: str) -> dict[str, str]:
    out = {"severity": severity, "table": table, "code": code, "message": message}
    out.update({key: str(value) for key, value in extra.items()})
    return out


def validate_tables(frames: Mapping[str, pd.DataFrame]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    by_name = {spec.name: spec for spec in TABLE_SPECS}

    for name, spec in by_name.items():
        if name not in frames:
            issues.append(_issue("error", name, "missing_table", "table was not supplied"))
            continue
        frame = _clean_frame(frames[name])
        missing = [column for column in spec.required if column not in frame.columns]
        for column in missing:
            issues.append(_issue("error", name, "missing_column", "required column is missing", field=column))
        if missing or frame.empty:
            if frame.empty:
                issues.append(_issue("warning", name, "empty_table", "table has no materialized rows"))
            continue

        keys = frame[spec.key].astype(str).str.strip()
        blank = frame[keys.eq("")]
        for index in blank.index:
            issues.append(_issue("error", name, "blank_primary_key", "primary key is blank", row=str(index + 2), field=spec.key))

        duplicated = keys.ne("") & keys.duplicated(keep=False)
        for value in sorted(set(keys[duplicated])):
            issues.append(_issue("error", name, "duplicate_primary_key", "primary key is duplicated", field=spec.key, value=value))

    front_frame = _clean_frame(frames.get("front_registry_v2", pd.DataFrame()))
    front_ids = set(front_frame.get("front_id", pd.Series(dtype=str)).astype(str).str.strip()) - {""}

    for spec in TABLE_SPECS:
        if not spec.front_fk or spec.name not in frames:
            continue
        frame = _clean_frame(frames[spec.name])
        if "front_id" not in frame.columns:
            continue
        unknown = sorted(set(frame["front_id"].astype(str).str.strip()) - {""} - front_ids)
        for front_id in unknown:
            issues.append(_issue("error", spec.name, "unknown_front_id", "front_id does not resolve in front_registry_v2", front_id=front_id))

    repo_monitor = _clean_frame(frames.get("REPO MONITOR_v2", pd.DataFrame()))
    workspaces = _clean_frame(frames.get("repo_workspaces_v2", pd.DataFrame()))
    workspace_ids = set(workspaces.get("workspace_id", pd.Series(dtype=str)).astype(str).str.strip()) - {""}
    if "workspace_id" in repo_monitor.columns:
        referenced = set(repo_monitor["workspace_id"].astype(str).str.strip()) - {""}
        for workspace_id in sorted(referenced - workspace_ids):
            issues.append(_issue("error", "REPO MONITOR_v2", "unknown_workspace_id", "workspace_id does not resolve in repo_workspaces_v2", workspace_id=workspace_id))

    # Alias collisions are an explicit migration state, not a validation error.
    aliases = _clean_frame(frames.get("front_aliases_v2", pd.DataFrame()))
    if "resolution_status" in aliases.columns:
        collisions = aliases[aliases["resolution_status"].astype(str).str.upper().eq("COLLISION")]
        if not collisions.empty:
            issues.append(_issue("observation", "front_aliases_v2", "declared_alias_collisions", "alias collisions remain explicit and are not coerced", count=str(len(collisions))))

    return issues


def build_snapshot(
    frames: Mapping[str, pd.DataFrame],
    *,
    observed_at: str | None = None,
    spreadsheet_id: str | None = None,
    gids: Mapping[str, str] | None = None,
) -> dict:
    cleaned = {name: _clean_frame(frame) for name, frame in frames.items()}
    issues = validate_tables(cleaned)
    errors = [issue for issue in issues if issue["severity"] == "error"]
    if errors:
        summary = "; ".join(f"{issue['table']}:{issue['code']}" for issue in errors[:8])
        raise ControlSnapshotError(f"Control Tower v2 validation failed: {summary}")

    tables = {
        spec.name: {
            "gid": str((gids or {}).get(spec.name, _gid(spec))),
            "key": spec.key,
            "row_count": int(len(cleaned[spec.name])),
            "rows": _records(cleaned[spec.name]),
        }
        for spec in TABLE_SPECS
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "observed_at": observed_at or _now_iso(),
        "source": {
            "kind": "google_sheets",
            "spreadsheet_id": spreadsheet_id or "",
        },
        "tables": tables,
        "validation": {
            "status": "ok",
            "issues": issues,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload["snapshot_digest"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    return payload


def read_control_tower_v2(cfg: OfficeConfig) -> dict[str, pd.DataFrame]:
    return {
        spec.name: read_sheet_values(
            cfg.service_account_json,
            cfg.spreadsheet_id,
            _gid(spec),
        )
        for spec in TABLE_SPECS
    }


def compile_control_snapshot(cfg: OfficeConfig, out: Path) -> dict:
    frames = read_control_tower_v2(cfg)
    snapshot = build_snapshot(
        frames,
        spreadsheet_id=cfg.spreadsheet_id,
        gids={spec.name: _gid(spec) for spec in TABLE_SPECS},
    )
    write_json(out, snapshot)
    return snapshot
