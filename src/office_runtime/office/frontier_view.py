from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import OfficeConfig
from .io import normalize, read_sheet_values, write_json


SCHEMA_VERSION = "frontier.view.v1"
CURRENT_SCHEMA_VERSION = "frontier.current-pointer.v1"
DEFAULT_RELATIONSHIP_AGENDA_GID = "1489271881"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")

REQUIRED_COLUMNS = (
    "agenda_id",
    "relation_id",
    "person",
    "agenda_type",
    "state",
    "priority",
    "agenda_item",
    "why_it_matters",
    "origin_date",
    "trigger_or_due",
    "evidence",
    "last_refreshed",
    "resolution_note",
)

BUCKET_BY_STATE = {
    "READY": "ACTION",
    "OPEN": "OPEN",
    "WAIT": "WAITING",
    "HOLD": "HOLD",
    "DONE": "CLOSED",
    "DROP": "CLOSED",
}

BUCKET_ORDER = {
    "ACTION": 0,
    "OPEN": 1,
    "WAITING": 2,
    "HOLD": 3,
    "OTHER": 4,
    "CLOSED": 5,
}

PRIORITY_ORDER = {
    "P0": 0,
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4,
}


class FrontierViewError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_run_id(run_id: str) -> str:
    value = str(run_id or "").strip()
    if not RUN_ID_RE.fullmatch(value):
        raise FrontierViewError("run_id must be a short filesystem-safe identifier")
    return value


def _stable_digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = normalize(frame.where(pd.notna(frame), ""))
    if out.empty:
        return out
    nonempty = out.apply(lambda row: any(str(value).strip() for value in row), axis=1)
    return out.loc[nonempty].reset_index(drop=True)


def _records(frame: pd.DataFrame) -> list[dict[str, str]]:
    return [
        {str(key): str(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _priority_key(value: str) -> tuple[int, str]:
    clean = str(value or "").strip().upper()
    return PRIORITY_ORDER.get(clean, 99), clean


def _item_from_row(row: dict[str, str]) -> tuple[dict, str | None]:
    agenda_id = row["agenda_id"].strip()
    source_state = row["state"].strip().upper()
    bucket = BUCKET_BY_STATE.get(source_state, "OTHER")
    warning = None if bucket != "OTHER" else f"unmapped agenda state {source_state!r} for {agenda_id}"

    person = row["person"].strip()
    evidence = row["evidence"].strip()
    relation_id = row["relation_id"].strip()

    item = {
        "id": f"agenda:{agenda_id}",
        "kind": "relationship_agenda",
        "bucket": bucket,
        "source_state": source_state,
        "priority": row["priority"].strip().upper(),
        "title": person or row["agenda_item"].strip() or agenda_id,
        "type": row["agenda_type"].strip(),
        "summary": row["agenda_item"].strip(),
        "why": row["why_it_matters"].strip(),
        "next_move": row["agenda_item"].strip(),
        "trigger": row["trigger_or_due"].strip(),
        "origin_date": row["origin_date"].strip(),
        "people": [person] if person else [],
        "projects": [],
        "institution": "",
        "location": "",
        "modality": "",
        "event_at": "",
        "deadline_at": "",
        "evidence": [{"label": evidence}] if evidence else [],
        "source_updated_at": row["last_refreshed"].strip(),
        "source_refs": [
            {
                "system": "control_tower",
                "dataset": "relationship_agenda_v1",
                "key": "agenda_id",
                "value": agenda_id,
            }
        ],
    }
    if relation_id:
        item["relation_id"] = relation_id
    resolution = row["resolution_note"].strip()
    if resolution:
        item["resolution_note"] = resolution
    return item, warning


def compile_relationship_agenda_view(
    frame: pd.DataFrame,
    *,
    generated_at: str | None = None,
    spreadsheet_id: str = "",
    gid: str = DEFAULT_RELATIONSHIP_AGENDA_GID,
    include_closed: bool = False,
) -> dict:
    cleaned = _clean_frame(frame)
    missing = [column for column in REQUIRED_COLUMNS if column not in cleaned.columns]
    if missing:
        raise FrontierViewError(f"relationship_agenda_v1 missing required columns: {', '.join(missing)}")

    if cleaned.empty:
        records: list[dict[str, str]] = []
    else:
        keys = cleaned["agenda_id"].astype(str).str.strip()
        blank_rows = [str(index + 2) for index in cleaned.index[keys.eq("")]]
        if blank_rows:
            raise FrontierViewError(f"relationship_agenda_v1 has blank agenda_id at rows: {', '.join(blank_rows)}")
        duplicated = sorted(set(keys[keys.duplicated(keep=False)]))
        if duplicated:
            raise FrontierViewError(f"relationship_agenda_v1 has duplicate agenda_id: {', '.join(duplicated)}")
        records = _records(cleaned)

    items: list[dict] = []
    warnings: list[str] = []
    for row in records:
        item, warning = _item_from_row(row)
        if item["bucket"] == "CLOSED" and not include_closed:
            continue
        if warning:
            warnings.append(warning)
        items.append(item)

    items.sort(
        key=lambda item: (
            BUCKET_ORDER.get(item["bucket"], 99),
            *_priority_key(item["priority"]),
            item["title"].casefold(),
            item["id"],
        )
    )

    source_payload = {
        "spreadsheet_id": spreadsheet_id,
        "dataset": "relationship_agenda_v1",
        "gid": str(gid),
        "rows": records,
    }

    counts: dict[str, int] = {"items": len(items)}
    for bucket in BUCKET_ORDER:
        count = sum(1 for item in items if item["bucket"] == bucket)
        if count:
            counts[bucket.lower()] = count

    payload = {
        "schema_version": SCHEMA_VERSION,
        "view_id": "relationship_agenda",
        "generated_at": generated_at or _now_iso(),
        "source": {
            "kind": "google_sheets",
            "spreadsheet_id": spreadsheet_id,
            "datasets": [
                {
                    "name": "relationship_agenda_v1",
                    "gid": str(gid),
                    "row_count": len(records),
                    "source_digest": _stable_digest(source_payload),
                }
            ],
        },
        "policy": {
            "closed_items_included": bool(include_closed),
            "source_state_is_preserved": True,
            "bucket_is_projection_only": True,
        },
        "counts": counts,
        "warnings": warnings,
        "items": items,
    }
    payload["view_digest"] = _stable_digest(payload)
    return payload


def _publish_current(root: Path, run_id: str, view: dict) -> None:
    pointer = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "run_id": run_id,
        "view_path": f"runs/{run_id}/frontier.view.v1.json",
        "view_digest": view["view_digest"],
        "generated_at": view["generated_at"],
    }
    tmp = root / f".current.{run_id}.tmp"
    write_json(tmp, pointer)
    os.replace(tmp, root / "current.json")


def _atomic_export(path: Path, view: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    write_json(tmp, view)
    os.replace(tmp, path)


def publish_relationship_agenda_view(
    cfg: OfficeConfig,
    *,
    run_id: str,
    include_closed: bool = False,
    publish: bool = True,
    export_path: Path | None = None,
    generated_at: str | None = None,
) -> dict:
    run_id = _validate_run_id(run_id)
    gid = os.environ.get("FRONTIER_RELATIONSHIP_AGENDA_GID", "").strip() or DEFAULT_RELATIONSHIP_AGENDA_GID

    frame = read_sheet_values(
        cfg.service_account_json,
        cfg.spreadsheet_id,
        gid,
    )
    view = compile_relationship_agenda_view(
        frame,
        generated_at=generated_at,
        spreadsheet_id=cfg.spreadsheet_id,
        gid=gid,
        include_closed=include_closed,
    )

    root = cfg.out_root / "frontier" / "v1"
    staging = root / ".staging" / run_id
    final = root / "runs" / run_id
    if staging.exists() or final.exists():
        raise FrontierViewError(f"run_id {run_id!r} already exists")

    try:
        staging.mkdir(parents=True, exist_ok=False)
        write_json(staging / "frontier.view.v1.json", view)
        manifest = {
            "schema_version": "frontier.view-run.v1",
            "run_id": run_id,
            "generated_at": view["generated_at"],
            "view_digest": view["view_digest"],
            "item_count": view["counts"]["items"],
            "published": bool(publish),
        }
        manifest["manifest_digest"] = _stable_digest(manifest)
        write_json(staging / "manifest.json", manifest)

        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, final)

        if publish:
            root.mkdir(parents=True, exist_ok=True)
            _publish_current(root, run_id, view)
            if export_path is not None:
                _atomic_export(Path(export_path), view)

        return {
            "status": "ok",
            "run_id": run_id,
            "published": bool(publish),
            "run_dir": str(final),
            "view_path": str(final / "frontier.view.v1.json"),
            "export_path": str(export_path) if publish and export_path is not None else "",
            "view": view,
        }
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
