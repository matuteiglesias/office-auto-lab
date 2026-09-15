from __future__ import annotations


class PacketFreshnessError(ValueError):
    pass


def evaluate_packet_freshness(
    packet: dict,
    *,
    current_snapshot_digest: str,
    current_repo_revisions: dict[str, str] | None = None,
) -> dict:
    """Evaluate whether a prepared Staff packet is still reusable.

    Freshness is evidence-based. The function never refreshes or mutates a
    packet; callers decide whether a stale/unknown packet deserves new prep.
    """
    packet_snapshot = str(packet.get("source_snapshot_digest", "")).strip()
    current_snapshot = str(current_snapshot_digest or "").strip()
    if not packet_snapshot or not current_snapshot:
        raise PacketFreshnessError("packet and current snapshot digests are required")
    prepared_at = str(packet.get("prepared_at", "")).strip()
    if not prepared_at:
        return {
            "status": "UNKNOWN_FRESHNESS",
            "reusable": False,
            "reasons": ["packet is missing prepared_at"],
        }
    if packet_snapshot != current_snapshot:
        return {
            "status": "STALE_STATE",
            "reusable": False,
            "reasons": ["Control Tower snapshot changed since preparation"],
        }

    revisions = dict(current_repo_revisions or {})
    missing: list[str] = []
    changed: list[str] = []
    checked: list[str] = []
    for evidence in packet.get("evidence", []) or []:
        if str(evidence.get("adapter", "")) != "local_repo":
            continue
        if str(evidence.get("status", "")).lower() != "ok":
            continue
        repo_id = str(evidence.get("repo_id", "")).strip()
        old_revision = str(evidence.get("revision", "")).strip()
        if not repo_id or not old_revision:
            continue
        checked.append(repo_id)
        current_revision = str(revisions.get(repo_id, "")).strip()
        if not current_revision:
            missing.append(repo_id)
        elif current_revision != old_revision:
            changed.append(repo_id)

    if changed:
        return {
            "status": "STALE_REPOSITORY",
            "reusable": False,
            "reasons": [f"repository revision changed: {repo_id}" for repo_id in sorted(set(changed))],
            "checked_repo_ids": sorted(set(checked)),
        }
    if missing:
        return {
            "status": "UNKNOWN_EVIDENCE",
            "reusable": False,
            "reasons": [f"current repository revision unavailable: {repo_id}" for repo_id in sorted(set(missing))],
            "checked_repo_ids": sorted(set(checked)),
        }
    return {
        "status": "CURRENT",
        "reusable": True,
        "reasons": [],
        "checked_repo_ids": sorted(set(checked)),
    }
