from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from ..remote import RepositorySourceError
from .base import BasePlugin, PluginCapability, result


class RemoteActivityPlugin(BasePlugin):
    name = "activity_remote"
    version = "1.0.0"
    capability = PluginCapability.REMOTE_READ

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        project = ctx.get("project") or {}
        identity = str(project.get("repository_full_name") or "").strip()
        source = ctx.get("repository_source")
        if not identity or source is None:
            return result(status="NA", bucket="MISSING_METADATA:repository_full_name", message="remote repository identity or source missing", meta={"unsupported_facts": _unsupported()})
        now = ctx.get("now") or datetime.now(timezone.utc)
        stale_days = float(project.get("repo_stale_days") or 14)
        since = now - timedelta(days=stale_days)
        try:
            facts = source.get_repository(identity)
            commits = source.list_commits(identity, since=since)
        except RepositorySourceError as exc:
            return result(status="NA", bucket=f"REPOSITORY_SOURCE:{exc.category}", message=str(exc)[:200], meta={"repository_full_name": identity, "source_error": exc.category, "unsupported_facts": _unsupported()})
        meta = {
            "repository_full_name": facts.full_name,
            "default_branch": facts.default_branch,
            "head_sha": facts.head_sha,
            "archived": facts.archived,
            "private": facts.private,
            "commits_within_threshold": len(commits),
            "threshold_days": stale_days,
            "unsupported_facts": _unsupported(),
        }
        evidence = [f"{facts.default_branch}@{facts.head_sha[:12]}", f"commits_{stale_days:g}d={len(commits)}"]
        if facts.private:
            return result(status="NA", bucket="PRIVATE_REPOSITORY_UNSUPPORTED", message="private repositories are excluded from GCP v0.1", evidence=evidence, meta=meta)
        if facts.archived:
            return result(status="NA", bucket="REPOSITORY_ARCHIVED", message="repository is archived", evidence=evidence, meta=meta)
        if not commits:
            return result(status="WARN", bucket="STALE_REPO:older_than_threshold", message=f"no commits found within {stale_days:g} days", evidence=evidence, meta=meta)
        latest = max(commits, key=lambda item: item.committed_at)
        meta.update({"last_commit_sha": latest.sha, "last_commit_at": latest.committed_at.isoformat(), "last_commit_subject": latest.subject})
        evidence.append(f"last_commit={latest.committed_at.isoformat()}")
        return result(status="PASS", bucket="RECENT_OK", message="repository has recent commit activity", evidence=evidence, meta=meta)


def _unsupported() -> dict[str, str]:
    return {"dirty_worktree": "NA", "ahead_behind": "NA", "local_origin": "NA"}


PLUGIN = RemoteActivityPlugin()
