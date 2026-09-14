from __future__ import annotations

from typing import Any

from .identity import IdentityResolutionError, IdentityResolver


SCHEMA_VERSION = "ops.work-item-set.v1"
ACTIVE_CARRY = frozenset({"ACTIVE", "ACTIVE_LIGHT"})
UNHEALTHY_RUNTIME = frozenset({"FAIL", "FAILED", "ERROR", "WARN", "WARNING", "DEGRADED", "STALE"})
KIND_ORDER = {"DECIDE": 0, "UNBLOCK": 1, "VERIFY": 2, "EXECUTE": 3, "MAINTAIN": 4}


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y", "x"}


def _explicit_false(value: Any) -> bool:
    return str(value or "").strip().lower() in {"false", "0", "no", "n"}


def _rows(snapshot: dict, table: str) -> list[dict]:
    return [dict(row) for row in snapshot.get("tables", {}).get(table, {}).get("rows", [])]


def _by_front(snapshot: dict, table: str) -> dict[str, dict]:
    return {
        str(row.get("front_id", "")).strip(): row
        for row in _rows(snapshot, table)
        if str(row.get("front_id", "")).strip()
    }


def _identity_summary(resolver: IdentityResolver, front_id: str, cap_repo: bool) -> tuple[dict, bool, str | None]:
    try:
        context = resolver.execution_context(front_id)
    except IdentityResolutionError as exc:
        return {
            "repo_ids": [],
            "workspace_states": [],
            "path_authority": "repo_workspaces_v2",
            "status": "ERROR",
        }, cap_repo, str(exc)

    repositories = context["repositories"]
    summary = {
        "repo_ids": [repo["repo_id"] for repo in repositories],
        "workspace_states": [
            {
                "repo_id": repo["repo_id"],
                "workspace_id": repo["workspace"]["workspace_id"],
                "status": repo["workspace"]["status"],
            }
            for repo in repositories
        ],
        "path_authority": context["path_authority"],
        "status": "RESOLVED" if (not cap_repo or any(repo["workspace"]["status"] == "RESOLVED" for repo in repositories)) else "NOT_READY",
    }
    blocked = cap_repo and summary["status"] != "RESOLVED"
    return summary, blocked, None


def _work_item(
    *,
    front_id: str,
    title: str,
    kind: str,
    carry: dict,
    front: dict,
    identity: dict,
    trigger_codes: list[str],
    snapshot_digest: str,
    identity_error: str | None = None,
) -> dict:
    return {
        "work_item_id": f"wi:{front_id}:{kind.lower()}",
        "front_id": front_id,
        "title": title,
        "kind": kind,
        "trigger_codes": trigger_codes,
        "carry_status": str(carry.get("carry_status", "")).strip(),
        "horizon": str(carry.get("horizon", "")).strip(),
        "priority_mode": str(carry.get("priority_mode", "")).strip(),
        "principal_mode": str(carry.get("principal_mode", "")).strip(),
        "principal_required": str(carry.get("principal_mode", "")).strip().upper() == "REQUIRED",
        "prep_mode": "STAFF_REQUIRED" if _truthy(front.get("staff_get")) else "NONE",
        "watch_enabled": _truthy(front.get("staff_watch")),
        "post_eligible": _truthy(front.get("staff_post")),
        "identity": identity,
        "context": {
            "needs": str(carry.get("needs", "")).strip(),
            "note": str(carry.get("note", "")).strip(),
        },
        "identity_error": identity_error,
        "source_snapshot_digest": snapshot_digest,
    }


def compile_work_items(snapshot: dict) -> dict:
    """Compile typed work from structured v2 state.

    ``needs`` is carried as human context only. It is never parsed to choose a
    work kind. Multiple typed work items may be emitted for one front because a
    front can simultaneously require Principal participation and executable or
    maintenance work.
    """

    fronts = _by_front(snapshot, "front_registry_v2")
    carry_rows = _rows(snapshot, "carry_state_v2")
    capabilities = _by_front(snapshot, "Capabilities_v2")
    runtime = _by_front(snapshot, "runtime_health_v2")
    resolver = IdentityResolver(snapshot)
    snapshot_digest = str(snapshot.get("snapshot_digest", "")).strip()

    items: list[dict] = []
    skipped: list[dict] = []

    for carry in carry_rows:
        front_id = str(carry.get("front_id", "")).strip()
        front = fronts.get(front_id)
        if not front:
            skipped.append({"front_id": front_id, "reason": "MISSING_FRONT"})
            continue

        carry_status = str(carry.get("carry_status", "")).strip().upper()
        lifecycle = str(front.get("lifecycle_status", "")).strip().upper()
        if carry_status not in ACTIVE_CARRY:
            skipped.append({"front_id": front_id, "reason": f"CARRY_{carry_status or 'BLANK'}"})
            continue
        if lifecycle and lifecycle != "ACTIVE":
            skipped.append({"front_id": front_id, "reason": f"LIFECYCLE_{lifecycle}"})
            continue
        if _explicit_false(front.get("enabled")):
            skipped.append({"front_id": front_id, "reason": "DISABLED"})
            continue

        cap = capabilities.get(front_id, {})
        cap_repo = _truthy(cap.get("cap_repo"))
        identity, repo_blocked, identity_error = _identity_summary(resolver, front_id, cap_repo)
        title = str(front.get("title", "")).strip() or front_id

        kinds: list[tuple[str, list[str]]] = []
        principal_mode = str(carry.get("principal_mode", "")).strip().upper()
        if principal_mode == "REQUIRED":
            kinds.append(("DECIDE", ["PRINCIPAL_REQUIRED"]))

        if repo_blocked:
            code = "IDENTITY_ERROR" if identity_error else "REPO_IDENTITY_NOT_READY"
            kinds.append(("UNBLOCK", [code]))

        health = runtime.get(front_id, {})
        health_status = str(health.get("health_status", "")).strip().upper()
        if health_status in UNHEALTHY_RUNTIME:
            kinds.append(("VERIFY", [f"RUNTIME_{health_status}"]))

        if _truthy(front.get("human_focus")) and not repo_blocked:
            kinds.append(("EXECUTE", ["HUMAN_FOCUS_ENABLED"]))

        if _truthy(front.get("human_maint")):
            kinds.append(("MAINTAIN", ["HUMAN_MAINT_ENABLED"]))

        if not kinds and _truthy(front.get("staff_get")):
            kinds.append(("UNBLOCK", ["STAFF_PREPARATION_REQUIRED"]))

        # One item per type/front. Merge trigger codes if two structured rules
        # produce the same type.
        merged: dict[str, list[str]] = {}
        for kind, trigger_codes in kinds:
            merged.setdefault(kind, [])
            merged[kind].extend(code for code in trigger_codes if code not in merged[kind])

        for kind, trigger_codes in merged.items():
            items.append(
                _work_item(
                    front_id=front_id,
                    title=title,
                    kind=kind,
                    carry=carry,
                    front=front,
                    identity=identity,
                    trigger_codes=trigger_codes,
                    snapshot_digest=snapshot_digest,
                    identity_error=identity_error,
                )
            )

    items.sort(key=lambda item: (item["front_id"], KIND_ORDER[item["kind"]]))
    skipped.sort(key=lambda row: (row["front_id"], row["reason"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "source_snapshot_digest": snapshot_digest,
        "work_items": items,
        "skipped_fronts": skipped,
        "counts": {
            "work_items": len(items),
            "fronts_with_work": len({item["front_id"] for item in items}),
            "skipped_fronts": len(skipped),
        },
    }
