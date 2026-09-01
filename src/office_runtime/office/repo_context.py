from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

CONTRACT = "context:github-repositories@1"


def parse_repo_ids(value: Any) -> list[str]:
    """Parse optional front-owned repository associations.

    Sheet-friendly values may be comma/semicolon/whitespace separated. Empty values
    are valid and represent a front with no repository association.
    """
    if value is None:
        return []
    try:
        missing = pd.isna(value)
        if isinstance(missing, bool) and missing:
            return []
    except (TypeError, ValueError):
        pass
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part for part in re.split(r"[;,\s]+", text) if part]


def load_repo_context(path: Path | None) -> dict[str, Any] | None:
    """Load an optional repo-keyed context artifact.

    Absence is not an error. When a path exists but contains malformed content,
    fail explicitly rather than silently accepting ambiguous provenance.
    """
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract") != CONTRACT:
        raise ValueError(
            f"unexpected repository context contract: {payload.get('contract')!r}; expected {CONTRACT!r}"
        )
    repositories = payload.get("repositories")
    if not isinstance(repositories, dict):
        raise ValueError("repository context must contain an object-valued 'repositories' field")
    return payload


def enrich_with_repo_context(
    df: pd.DataFrame,
    payload: dict[str, Any] | None,
) -> tuple[pd.DataFrame, dict[str, int | str | None]]:
    """Attach advisory repository-context diagnostics to Office front rows.

    This function never changes carry, horizon, priority, principal posture, or
    selection fields. Front-to-repository associations remain owned by Office via
    the optional ``repo_ids`` column.
    """
    out = df.copy()
    repositories = payload.get("repositories", {}) if payload else {}

    known_values: list[str] = []
    unknown_values: list[str] = []
    statuses: list[str] = []
    total_refs = 0
    known_refs = 0
    unknown_refs = 0

    for value in out.get("repo_ids", pd.Series("", index=out.index)):
        repo_ids = parse_repo_ids(value)
        total_refs += len(repo_ids)
        known = [repo_id for repo_id in repo_ids if repo_id in repositories]
        unknown = [repo_id for repo_id in repo_ids if repo_id not in repositories]
        known_refs += len(known)
        unknown_refs += len(unknown)
        known_values.append(";".join(known))
        unknown_values.append(";".join(unknown))
        if not repo_ids:
            statuses.append("none")
        elif payload is None:
            statuses.append("context-unavailable")
        elif unknown and known:
            statuses.append("partial")
        elif unknown:
            statuses.append("unknown")
        else:
            statuses.append("known")

    out["repo_context_status"] = statuses
    out["repo_context_known_ids"] = known_values
    out["repo_context_unknown_ids"] = unknown_values

    summary: dict[str, int | str | None] = {
        "contract": payload.get("contract") if payload else None,
        "generated_at": payload.get("generated_at") if payload else None,
        "front_rows": int(len(out)),
        "repo_refs": total_refs,
        "known_repo_refs": known_refs,
        "unknown_repo_refs": unknown_refs,
    }
    return out, summary
