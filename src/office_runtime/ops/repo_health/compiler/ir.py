from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set


@dataclass(frozen=True)
class IssueIR:
    project_id: str
    plugin: str
    bucket: str
    normalized_class: str
    severity: str
    issue_type: str
    signature: str
    short_diag: str = ""
    run_id: str = ""
    ts_started: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectIR:
    project_id: str
    issues: List[IssueIR] = field(default_factory=list)

    # derived
    blockers: Set[str] = field(default_factory=set)
    warnings: Set[str] = field(default_factory=set)

    repo_path_ok: bool = True
    is_git_ok: bool = True
    makefile_ok: bool = True
    plugin_ok: bool = True

    can_run_smoke: bool = False

    def derive(self) -> None:
        issue_types = {i.issue_type for i in self.issues}

        if "repo_path_missing" in issue_types:
            self.repo_path_ok = False
        if "repo_not_git" in issue_types:
            self.is_git_ok = False
        if "makefile_missing" in issue_types:
            self.makefile_ok = False
        if "plugin_not_loaded" in issue_types:
            self.plugin_ok = False

        blocker_types = {"repo_path_missing", "repo_not_git", "makefile_missing", "plugin_not_loaded"}
        self.blockers = set(t for t in issue_types if t in blocker_types)

        warn_types = {"runbook_missing", "worktree_dirty", "staleness_old_commit"}
        self.warnings = set(t for t in issue_types if t in warn_types)

        self.can_run_smoke = self.repo_path_ok and self.makefile_ok and self.plugin_ok


def issue_to_trigger(i: IssueIR) -> Dict[str, Any]:
    return {
        "project_id": i.project_id,
        "plugin": i.plugin,
        "severity": i.severity,
        "issue_type": i.issue_type,
        "signature": i.signature,
    }


def project_to_target(p: ProjectIR, issue_signatures: List[str]) -> Dict[str, Any]:
    return {"project_id": p.project_id, "issue_signatures": issue_signatures}


def as_jsonable(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj
