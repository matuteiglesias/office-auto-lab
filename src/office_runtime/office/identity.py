from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class IdentityResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class WorkspaceResolution:
    repo_id: str
    workspace_id: str | None
    local_path: str | None
    status: str
    reason: str
    binding_id: str | None = None
    binding_role: str | None = None


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y", "x"}


def _table_rows(snapshot: dict, table: str) -> list[dict]:
    try:
        rows = snapshot["tables"][table]["rows"]
    except (KeyError, TypeError) as exc:
        raise IdentityResolutionError(f"snapshot is missing table {table!r}") from exc
    if not isinstance(rows, list):
        raise IdentityResolutionError(f"snapshot table {table!r} rows must be a list")
    return [dict(row) for row in rows]


def _index_unique(rows: list[dict], key: str, table: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if not value:
            continue
        if value in out:
            raise IdentityResolutionError(f"duplicate {key}={value!r} in {table}")
        out[value] = row
    return out


class IdentityResolver:
    """Resolve execution identity from the Control Tower v2 snapshot.

    The resolver deliberately ignores ``front_registry_v2.repo_path`` and
    ``front_registry_v2.workdir``. Concrete paths are observations owned by
    ``repo_workspaces_v2`` and can only be reached through a repo binding.
    """

    def __init__(self, snapshot: dict):
        self.snapshot = snapshot
        self.fronts = _index_unique(_table_rows(snapshot, "front_registry_v2"), "front_id", "front_registry_v2")
        self.workspaces = _index_unique(_table_rows(snapshot, "repo_workspaces_v2"), "workspace_id", "repo_workspaces_v2")
        self.bindings = _table_rows(snapshot, "REPO MONITOR_v2")

    def front(self, front_id: str) -> dict:
        key = str(front_id).strip()
        if key not in self.fronts:
            raise IdentityResolutionError(f"unknown front_id {key!r}")
        return dict(self.fronts[key])

    def repo_bindings(self, front_id: str, *, active_only: bool = True) -> list[dict]:
        self.front(front_id)
        rows = [row for row in self.bindings if str(row.get("front_id", "")).strip() == front_id]
        if active_only:
            rows = [row for row in rows if str(row.get("binding_status", "")).strip().upper() == "ACTIVE"]
        return sorted(
            rows,
            key=lambda row: (
                not _truthy(row.get("is_primary")),
                str(row.get("binding_role", "")),
                str(row.get("repo_id", "")),
                str(row.get("binding_id", "")),
            ),
        )

    def _workspace_candidates(self, repo_id: str) -> list[dict]:
        rows = [
            row
            for row in self.workspaces.values()
            if str(row.get("repo_id", "")).strip() == repo_id
            and str(row.get("workspace_status", "")).strip().upper() == "ACTIVE"
        ]
        return sorted(
            rows,
            key=lambda row: (
                not _truthy(row.get("is_preferred")),
                str(row.get("checkout_kind", "")) != "CHECKOUT",
                str(row.get("workspace_id", "")),
            ),
        )

    def workspace_for_binding(self, binding: dict) -> WorkspaceResolution:
        repo_id = str(binding.get("repo_id", "")).strip()
        if not repo_id:
            raise IdentityResolutionError("repo binding has blank repo_id")

        binding_id = str(binding.get("binding_id", "")).strip() or None
        binding_role = str(binding.get("binding_role", "")).strip() or None
        explicit_workspace = str(binding.get("workspace_id", "")).strip()

        if explicit_workspace:
            workspace = self.workspaces.get(explicit_workspace)
            if workspace is None:
                raise IdentityResolutionError(
                    f"binding {binding_id or '<unknown>'} references unknown workspace_id {explicit_workspace!r}"
                )
            if str(workspace.get("repo_id", "")).strip() != repo_id:
                raise IdentityResolutionError(
                    f"binding {binding_id or '<unknown>'} repo_id {repo_id!r} does not match workspace {explicit_workspace!r}"
                )
            if str(workspace.get("workspace_status", "")).strip().upper() != "ACTIVE":
                return WorkspaceResolution(
                    repo_id=repo_id,
                    workspace_id=explicit_workspace,
                    local_path=None,
                    status="UNAVAILABLE",
                    reason="explicit workspace is not ACTIVE",
                    binding_id=binding_id,
                    binding_role=binding_role,
                )
            path = str(workspace.get("local_path", "")).strip() or None
            return WorkspaceResolution(
                repo_id=repo_id,
                workspace_id=explicit_workspace,
                local_path=path,
                status="RESOLVED" if path else "UNAVAILABLE",
                reason="explicit binding workspace" if path else "workspace has no local_path observation",
                binding_id=binding_id,
                binding_role=binding_role,
            )

        candidates = self._workspace_candidates(repo_id)
        if not candidates:
            return WorkspaceResolution(
                repo_id=repo_id,
                workspace_id=None,
                local_path=None,
                status="UNRESOLVED",
                reason="no ACTIVE workspace observed for repo_id",
                binding_id=binding_id,
                binding_role=binding_role,
            )

        preferred = [row for row in candidates if _truthy(row.get("is_preferred"))]
        if len(preferred) > 1:
            raise IdentityResolutionError(
                f"repo_id {repo_id!r} has multiple ACTIVE preferred workspaces: "
                + ", ".join(str(row.get("workspace_id", "")) for row in preferred)
            )
        if len(preferred) == 1:
            chosen = preferred[0]
            reason = "preferred ACTIVE workspace for repo_id"
        elif len(candidates) == 1:
            chosen = candidates[0]
            reason = "only ACTIVE workspace for repo_id"
        else:
            return WorkspaceResolution(
                repo_id=repo_id,
                workspace_id=None,
                local_path=None,
                status="AMBIGUOUS",
                reason="multiple ACTIVE workspaces and none is uniquely preferred",
                binding_id=binding_id,
                binding_role=binding_role,
            )

        path = str(chosen.get("local_path", "")).strip() or None
        return WorkspaceResolution(
            repo_id=repo_id,
            workspace_id=str(chosen.get("workspace_id", "")).strip() or None,
            local_path=path,
            status="RESOLVED" if path else "UNAVAILABLE",
            reason=reason if path else "selected workspace has no local_path observation",
            binding_id=binding_id,
            binding_role=binding_role,
        )

    def execution_context(self, front_id: str) -> dict:
        front = self.front(front_id)
        bindings = self.repo_bindings(front_id)
        repositories = []
        for binding in bindings:
            resolution = self.workspace_for_binding(binding)
            repositories.append(
                {
                    "binding_id": resolution.binding_id,
                    "binding_role": resolution.binding_role,
                    "repo_id": resolution.repo_id,
                    "is_primary": _truthy(binding.get("is_primary")),
                    "workspace": {
                        "status": resolution.status,
                        "workspace_id": resolution.workspace_id,
                        "local_path": resolution.local_path,
                        "reason": resolution.reason,
                    },
                }
            )

        primary = [repo for repo in repositories if repo["is_primary"]]
        if len(primary) > 1:
            raise IdentityResolutionError(f"front_id {front_id!r} has multiple ACTIVE primary repository bindings")

        return {
            "front_id": front_id,
            "title": str(front.get("title", "")).strip(),
            "repositories": repositories,
            "primary_repository": primary[0] if primary else None,
            "path_authority": "repo_workspaces_v2",
        }
