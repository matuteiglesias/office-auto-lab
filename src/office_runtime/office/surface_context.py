from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT = "registry:estate-surfaces@1"


def load_surface_context(path: Path | None) -> dict[str, Any] | None:
    """Load optional estate-surface governance context.

    Absence is valid. If configured, malformed or wrong-contract context fails closed
    so Office never silently compiles against ambiguous governance input.
    """
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract") != CONTRACT:
        raise ValueError(
            f"unexpected surface context contract: {payload.get('contract')!r}; expected {CONTRACT!r}"
        )
    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, list):
        raise ValueError("surface context must contain a list-valued 'surfaces' field")
    ids = [surface.get("id") for surface in surfaces]
    if any(not isinstance(surface_id, str) or not surface_id for surface_id in ids):
        raise ValueError("surface context contains invalid surface id")
    if len(ids) != len(set(ids)):
        raise ValueError("surface context contains duplicate surface ids")
    return payload


def summarize_surface_context(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return bounded advisory governance diagnostics without changing Office routing."""
    if payload is None:
        return {
            "contract": None,
            "configured": False,
            "surface_count": 0,
            "active_count": 0,
            "promoted_count": 0,
            "candidate_count": 0,
            "remediation_count": 0,
            "projection_count": 0,
            "canonical_count": 0,
            "candidate_ids": [],
            "remediation_ids": [],
        }

    surfaces = payload.get("surfaces", [])
    promotion_state = {
        surface.get("id"): surface.get("promotion", {}).get("state")
        for surface in surfaces
    }
    candidate_ids = sorted(
        surface_id for surface_id, state in promotion_state.items() if state == "candidate"
    )
    remediation_ids = sorted(
        surface_id for surface_id, state in promotion_state.items() if state == "remediation"
    )

    return {
        "contract": payload.get("contract"),
        "configured": True,
        "surface_count": len(surfaces),
        "active_count": sum(surface.get("lifecycle") == "active" for surface in surfaces),
        "promoted_count": sum(state == "promoted" for state in promotion_state.values()),
        "candidate_count": len(candidate_ids),
        "remediation_count": len(remediation_ids),
        "projection_count": sum(surface.get("kind") == "projection" for surface in surfaces),
        "canonical_count": sum(
            surface.get("lifecycle") == "active"
            and surface.get("authority", {}).get("state") == "canonical"
            for surface in surfaces
        ),
        "candidate_ids": candidate_ids,
        "remediation_ids": remediation_ids,
    }
