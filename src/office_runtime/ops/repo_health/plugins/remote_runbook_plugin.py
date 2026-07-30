from __future__ import annotations

import hashlib
import re
from typing import Any, Dict

from ..remote import RepositorySourceError
from .base import BasePlugin, PluginCapability, result

_SECTION_RX = {
    "has_acceptance": re.compile(r"(?im)^\s*acceptance\s*:"),
    "has_prereqs": re.compile(r"(?im)^\s*(prereq|prerequisites?|requirements?)\s*:"),
    "has_troubleshooting": re.compile(r"(?im)^\s*(troubleshooting|debug|diagnostics?)\s*:"),
    "has_smoke": re.compile(r"(?i)\b(make\s+smoke|run_smoke\.(sh|py)|reproduce\.(sh|py))\b"),
}


class RemoteRunbookPlugin(BasePlugin):
    name = "runbook_remote"
    version = "1.0.0"
    capability = PluginCapability.REMOTE_READ

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        project = ctx.get("project") or {}
        identity = str(project.get("repository_full_name") or "").strip()
        source = ctx.get("repository_source")
        if not identity or source is None:
            return result(status="NA", bucket="MISSING_METADATA:repository_full_name", message="remote repository identity or source missing")
        try:
            facts = source.get_repository(identity)
            if facts.private:
                return result(status="NA", bucket="PRIVATE_REPOSITORY_UNSUPPORTED", message="private repositories are excluded from GCP v0.1", meta={"repository_full_name": identity})
            entries = source.list_tree(identity, facts.head_sha)
            blobs = {entry.path for entry in entries if entry.kind == "blob"}
            candidates = sorted(path for path in blobs if _is_candidate(path))[:5]
            if not candidates:
                hygiene = _hygiene(blobs)
                return result(status="WARN", bucket="RUNBOOK_NOT_FOUND", message="no bounded runbook or README candidate found", evidence=[], meta={"repository_full_name": identity, "hygiene": hygiene, "runbook_freshness": "NA"})
            scored = []
            details = {}
            for path in candidates:
                text = source.read_text(identity, path, facts.head_sha)
                signals = {key: bool(regex.search(text)) for key, regex in _SECTION_RX.items()}
                score = (50 if path.lower().endswith("runbook.md") else 10) + sum((20, 10, 10, 5)[i] for i, value in enumerate(signals.values()) if value)
                details[path] = {**signals, "sha256_snip": hashlib.sha256(text[:4000].encode()).hexdigest(), "freshness": "NA"}
                scored.append((-score, path))
        except (RepositorySourceError, KeyError) as exc:
            category = exc.category if isinstance(exc, RepositorySourceError) else "content_missing"
            return result(status="NA", bucket=f"REPOSITORY_SOURCE:{category}", message=str(exc)[:200], meta={"repository_full_name": identity, "source_error": category})
        best_path = sorted(scored)[0][1]
        best = details[best_path]
        missing = [name for name in ("has_smoke", "has_prereqs", "has_troubleshooting") if not best[name]]
        bucket = "RUNBOOK_OK" if not missing else f"RUNBOOK_MISSING_{missing[0][4:].upper()}"
        status = "PASS" if not missing else "WARN"
        evidence = [f"{path}:{details[path]['sha256_snip'][:12]}" for _, path in sorted(scored)]
        return result(status=status, bucket=bucket, message=f"best={best_path} found={len(details)}", evidence=evidence, meta={"repository_full_name": identity, "best": best, "hygiene": _hygiene(blobs), "runbook_freshness": "NA", "unsupported_facts": {"filesystem_mtime": "NA"}})


def _is_candidate(path: str) -> bool:
    normalized = path.lower()
    if normalized.count("/") > 2:
        return False
    base = normalized.rsplit("/", 1)[-1]
    return base.startswith("runbook.") or base in {"runbook", "runbooks.md", "readme.md", "readme.txt", "readme"}


def _hygiene(paths: set[str]) -> dict[str, bool]:
    lowered = {path.lower() for path in paths}
    return {"readme": any(path in lowered for path in {"readme", "readme.md", "readme.txt"}), "gitignore": ".gitignore" in lowered, "runbook": any("runbook" in path.rsplit("/", 1)[-1] for path in lowered)}


PLUGIN = RemoteRunbookPlugin()
