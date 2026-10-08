"""Deterministic application-asset selection over a human-owned registry."""

from __future__ import annotations

from typing import Any

CONTRACT = "artifact:ops.job-application-prep@1"


class JobPrepError(ValueError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _status_rank(status: str) -> int:
    return {
        "approved_current": 0,
        "candidate_needs_review": 1,
        "reference_only": 2,
        "missing": 3,
        "retired": 4,
    }.get(status, 99)


def _track_rank(asset_track: str, wanted_track: str, allow_general: bool) -> int | None:
    if asset_track == wanted_track:
        return 0
    if allow_general and asset_track.lower() in {"general", "data/ai general"}:
        return 1
    return None


def _validate_registry(registry: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for row in registry:
        asset_id = _text(row.get("asset_id"))
        if not asset_id:
            raise JobPrepError("asset_id is required")
        if asset_id in seen:
            raise JobPrepError(f"duplicate asset_id: {asset_id}")
        seen.add(asset_id)
        if _text(row.get("status")) not in {
            "approved_current",
            "candidate_needs_review",
            "reference_only",
            "missing",
            "retired",
        }:
            raise JobPrepError(f"unsupported asset status for {asset_id}")


def _match_requirement(
    requirement: dict[str, Any],
    registry: list[dict[str, Any]],
) -> dict[str, Any]:
    req_id = _text(requirement.get("requirement_id"))
    wanted_types = requirement.get("accepted_asset_types")
    if not req_id or not isinstance(wanted_types, list) or not wanted_types:
        raise JobPrepError("each requirement needs requirement_id and accepted_asset_types")
    wanted_types = {_text(item) for item in wanted_types if _text(item)}
    wanted_track = _text(requirement.get("track"))
    language = _text(requirement.get("language"))
    allow_general = bool(requirement.get("allow_general_base", False))

    matches: list[tuple[int, int, dict[str, Any]]] = []
    missing_markers: list[dict[str, Any]] = []
    for asset in registry:
        if _text(asset.get("asset_type")) not in wanted_types:
            continue
        if language and _text(asset.get("language")) != language:
            continue
        track_rank = _track_rank(_text(asset.get("track")), wanted_track, allow_general)
        if track_rank is None:
            continue
        status = _text(asset.get("status"))
        if status == "missing":
            missing_markers.append(asset)
            continue
        if status == "retired":
            continue
        matches.append((track_rank, _status_rank(status), asset))

    matches.sort(key=lambda item: (item[0], item[1], _text(item[2].get("asset_id"))))
    selected = matches[0][2] if matches else None

    if selected is None:
        state = "missing-known" if missing_markers else "missing-unregistered"
    else:
        status = _text(selected.get("status"))
        state = {
            "approved_current": "approved",
            "candidate_needs_review": "review-required",
            "reference_only": "draft-from-reference",
        }[status]

    return {
        "requirement_id": req_id,
        "label": requirement.get("label"),
        "state": state,
        "selected_asset": (
            {
                "asset_id": selected.get("asset_id"),
                "asset_type": selected.get("asset_type"),
                "track": selected.get("track"),
                "language": selected.get("language"),
                "status": selected.get("status"),
                "title": selected.get("title"),
                "url": selected.get("url"),
                "last_reviewed": selected.get("last_reviewed"),
            }
            if selected
            else None
        ),
        "known_missing_assets": sorted(
            _text(item.get("asset_id")) for item in missing_markers
        ),
    }


def compile_application_prep(
    *,
    job_ref: str,
    requirements: list[dict[str, Any]],
    asset_registry: list[dict[str, Any]],
    as_of: str,
) -> dict[str, Any]:
    if not job_ref.strip():
        raise JobPrepError("job_ref is required")
    if not isinstance(requirements, list) or not requirements:
        raise JobPrepError("requirements must be a non-empty list")
    if not isinstance(asset_registry, list):
        raise JobPrepError("asset_registry must be a list")

    _validate_registry(asset_registry)
    results = [_match_requirement(item, asset_registry) for item in requirements]
    states = {item["state"] for item in results}
    ready = states <= {"approved"}

    next_actions: list[str] = []
    for item in results:
        if item["state"] == "review-required":
            next_actions.append(
                f'Review/tailor {item["selected_asset"]["asset_id"]} for {item["requirement_id"]}.'
            )
        elif item["state"] == "draft-from-reference":
            next_actions.append(
                f'Draft {item["requirement_id"]} from reference {item["selected_asset"]["asset_id"]}; do not send the reference unchanged.'
            )
        elif item["state"] in {"missing-known", "missing-unregistered"}:
            next_actions.append(f'Create or resolve {item["requirement_id"]}.')

    return {
        "contract": CONTRACT,
        "as_of": as_of,
        "job_ref": job_ref,
        "ready_for_submission_materially": ready,
        "requirements": results,
        "next_actions": next_actions,
        "authority": {
            "asset_registry": "ATS 2026 / Assets (human-owned pointers and readiness)",
            "compiler": "office-auto-lab read-only SIDECAR",
        },
    }
