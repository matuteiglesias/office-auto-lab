# plugins/runbook_plugin.py
from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List

from .base import BasePlugin, result
from ._utils import (
    find_runbook_files,
    safe_read_text_prefix,
    snippet_sha256_of_file,
    file_stat,
    mtime_iso,
    days_since_epoch,
    score_runbook,
)


_SECTION_RX = {
    "has_acceptance": re.compile(r"(?im)^\s*acceptance\s*:", re.IGNORECASE),
    "has_prereqs": re.compile(r"(?im)^\s*(prereq|prerequisite|requirements?)\s*:", re.IGNORECASE),
    "has_troubleshooting": re.compile(r"(?im)^\s*(troubleshooting|debug|diagnostics?)\s*:", re.IGNORECASE),
    # Smoke/quickstart patterns: we want this to be robust without being too loose
    "has_smoke": re.compile(
        r"(?i)\b(make\s+smoke|run_smoke\.(sh|py)|scripts/run_smoke\.(sh|py)|reproduce\.(sh|py)|python\s+-m\s+\S*smoke\S*)\b"
    ),
}


class RunbookPlugin(BasePlugin):
    name = "runbook"
    version = "1.0.0"

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.time()

        project = ctx.get("project") or ctx  # tolerate either shape
        repo_root = project.get("repo_path") or project.get("workdir")  or project.get("path")
        repo_root = str(repo_root).strip()

        max_depth = int(ctx.get("runbook_max_depth", 6))
        max_files = int(ctx.get("runbook_max_files", 8000))
        stale_days = float(ctx.get("runbook_stale_days", 120))

        # Deterministic discovery
        abs_paths = find_runbook_files(repo_root, max_depth=max_depth, max_files=max_files, include_readme_fallback=True)
        relpaths = [os.path.relpath(p, repo_root) for p in abs_paths]

        per_file: Dict[str, Any] = {}
        scored: List[tuple] = []

        for abs_p, rel_p in zip(abs_paths, relpaths):
            size_b, mtime = file_stat(abs_p)
            text = safe_read_text_prefix(abs_p, max_chars=50000)
            signals = {k: bool(rx.search(text)) for k, rx in _SECTION_RX.items()}
            sha = snippet_sha256_of_file(abs_p, max_read=4000)

            days = days_since_epoch(mtime)
            info = {
                "relpath": rel_p,
                "size_bytes": size_b,
                "mtime_iso": mtime_iso(mtime),
                "days_since_mod": round(days, 2),
                "sha256_snip": sha,
                **signals,
            }
            per_file[rel_p] = info
            scored.append((score_runbook(rel_p, signals), rel_p))

        # Pick best deterministically
        best_rel = None
        if scored:
            scored.sort(key=lambda x: (x[0][0], x[0][1], x[0][2]))  # uses (-score, depth, rp)
            best_rel = scored[0][1]
            best = per_file[best_rel]
        else:
            best = None

        # Decide status
        if not best:
            return result(
                status="WARN",
                bucket="RUNBOOK_NOT_FOUND",
                message="no runbook.* (or README fallback) found under repo root",
                evidence=[],
                meta={
                    "repo_root": repo_root,
                    "searched_max_depth": max_depth,
                    "searched_max_files": max_files,
                    "found": 0,
                    "elapsed_ms": int((time.time() - t0) * 1000),
                },
            )

        # Classify quality
        buckets: List[str] = []
        if best["days_since_mod"] > stale_days:
            buckets.append("RUNBOOK_STALE")
        if not best["has_smoke"]:
            buckets.append("RUNBOOK_MISSING_SMOKE_SECTION")
        if not best["has_troubleshooting"]:
            buckets.append("RUNBOOK_MISSING_TROUBLESHOOTING")
        if not best["has_prereqs"]:
            buckets.append("RUNBOOK_MISSING_PREREQS")

        # Status heuristic
        if buckets:
            status = "WARN"
            bucket = buckets[0]
        else:
            status = "PASS"
            bucket = "RUNBOOK_OK"

        # Evidence: top 5 by score, stable
        top_rel = [r for _, r in sorted(scored, key=lambda x: (x[0][0], x[0][1], x[0][2]))][:5]
        evidence = []
        for r in top_rel:
            sha = per_file[r].get("sha256_snip")
            if sha:
                evidence.append(f"{r}:{sha[:12]}")
            else:
                evidence.append(r)

        msg = f"best={best_rel} found={len(per_file)} days={best['days_since_mod']} smoke={best['has_smoke']} prereqs={best['has_prereqs']} troubleshoot={best['has_troubleshooting']}"

        return result(
            status=status,
            bucket=bucket,
            message=msg[:200],
            evidence=evidence,
            meta={
                "repo_root": repo_root,
                "best": best,
                "all": {k: per_file[k] for k in top_rel},
                "stale_days_threshold": stale_days,
                "elapsed_ms": int((time.time() - t0) * 1000),
            },
        )



# TODO


# runbook_plugin.py

# What it covers well:

# Existence and some minimal structure for the runbook.

# Sharp corners to fix:

# It should validate that the runbook mentions your current reality:

# compiler module exists

# systemd timer exists

# “how to run live-cycle” exists

# Add a simple “runbook freshness” rule:

# if runbook last modified older than X days, WARN

# or require a “Last updated:” line inside the file and check it