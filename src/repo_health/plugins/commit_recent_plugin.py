# plugins/commit_recent_plugin.py
"""
commit_recent plugin v1: repo observability
Goal: give a compact, deterministic health surface for a local git repo.

Inputs (ctx expected):
  ctx["project"]: dict with at least:
    - repo_path (preferred) or workdir: local path to repo root
    - optional: repo_stale_days (int) or repo_stale_hours (int)

Output (dict):
  - status: PASS|WARN|FAIL|NA|ERROR (or a bucket string for ineligible)
  - normalized_class: ok|warning|actionable_failure|ineligible|system_error
  - bucket: machine-friendly category
  - message: one sentence
  - evidence: list[str] (short)
  - meta: dict (structured)
  - duration_s: float
  - executed: bool
"""
from __future__ import annotations
import os, time, datetime, subprocess, re
from typing import Any, Dict, List, Optional, Tuple



DEFAULT_EXCLUDE_REMOTE_CREDS = True

def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

def _iso(dt: datetime.datetime) -> str:
    return dt.astimezone(datetime.timezone.utc).isoformat()

def _sanitize_remote(url: str) -> str:
    # strip credentials in urls like https://user:pass@host/path
    return re.sub(r'^(https?://)([^/@]+)@', r'\1', url.strip())

def _run(cmd: List[str], cwd: str, timeout_s: float) -> Tuple[int, str, str]:
    p = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_s,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def _git(cwd: str, args: List[str], timeout_s: float = 2.0) -> Tuple[int, str, str]:
    return _run(["git"] + args, cwd=cwd, timeout_s=timeout_s)

def _file_exists_any(cwd: str, candidates: List[str]) -> Optional[str]:
    for rel in candidates:
        p = os.path.join(cwd, rel)
        if os.path.isfile(p):
            return rel
    return None

def _has_runbook(cwd: str) -> bool:
    # quick: runbook.* in root or notes/ or docs/
    for rel_dir in ["", "notes", "docs"]:
        d = os.path.join(cwd, rel_dir)
        if not os.path.isdir(d):
            continue
        try:
            for name in os.listdir(d):
                if name.lower().startswith("runbook."):
                    return True
        except Exception:
            pass
    return False

def _parse_status_porcelain(lines: List[str]) -> Dict[str, int]:
    # git status --porcelain output, two-character status + path
    staged = 0
    unstaged = 0
    untracked = 0
    for ln in lines:
        if not ln:
            continue
        if ln.startswith("??"):
            untracked += 1
            continue
        x = ln[0]
        y = ln[1] if len(ln) > 1 else " "
        if x != " ":
            staged += 1
        if y != " ":
            unstaged += 1
    return {"staged": staged, "unstaged": unstaged, "untracked": untracked}


# compatible with 
# def execute_intent(intent: RunIntent, project_ctx: Dict[str, Any], plugins: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
#     """
#     Returns a single PLUGIN_RESULTS row dict (append-only).
#     Keep plugin raw output, but normalize to short fields in runner.
#     """
#     t0 = time.time()
#     plugin_name = intent.plugin

# ?


from .base import BasePlugin, result

class CommitRecentPlugin(BasePlugin):
    name = "commit_recent"
    version = "1.0.0"

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.time()
        project = ctx.get("project") or {}
        repo_root = project.get("repo_path") or project.get("workdir") or ""
        repo_root = str(repo_root).strip()

        def done(status: str, normalized_class: str, bucket: str, message: str,
                 evidence: List[str] | None = None, meta: Dict[str, Any] | None = None,
                 executed: bool = True) -> Dict[str, Any]:
            return {
                "status": status,
                "normalized_class": normalized_class,
                "bucket": bucket,
                "message": message,
                "evidence": evidence or [],
                "meta": meta or {},
                "duration_s": round(time.time() - t0, 3),
                "executed": executed,
            }


        if not repo_root or not os.path.isdir(repo_root):
            bucket = "MISSING_METADATA:repo_path"
            return done(bucket, "ineligible", bucket, "repo_path/workdir missing or not a directory", executed=True,
                        evidence = [repo_root] if repo_root else [],
            meta={"repo_root": repo_root},
            )

        # Is it a git repo?
        rc, out, err = _git(repo_root, ["rev-parse", "--is-inside-work-tree"])
        if rc != 0 or out.lower() != "true":
            return done("FAIL", "actionable_failure", "NOT_A_GIT_REPO",
                        "repo_root is not a git work tree", evidence=[repo_root], meta={"stderr": err[:200]})

        # Core git facts
        facts: Dict[str, Any] = {"repo_root": repo_root}

        rc, head, err = _git(repo_root, ["rev-parse", "--short", "HEAD"])
        if rc == 0:
            facts["head"] = head
        rc, branch, err2 = _git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
        if rc == 0:
            facts["branch"] = branch

        rc, ctime, err3 = _git(repo_root, ["log", "-1", "--format=%ct"])
        last_commit_dt: Optional[datetime.datetime] = None
        if rc == 0 and ctime.isdigit():
            last_commit_dt = datetime.datetime.fromtimestamp(int(ctime), tz=datetime.timezone.utc)
            facts["last_commit_ts"] = int(ctime)
            facts["last_commit_iso"] = _iso(last_commit_dt)

        rc, subj, _ = _git(repo_root, ["log", "-1", "--format=%s"])
        if rc == 0:
            facts["last_commit_subject"] = subj[:200]

        # Recent commit count (7 days)
        rc, cnt7, _ = _git(repo_root, ["rev-list", "--count", "--since=7 days ago", "HEAD"])
        if rc == 0 and cnt7.isdigit():
            facts["commits_7d"] = int(cnt7)

        # Status porcelain
        rc, st, _ = _git(repo_root, ["status", "--porcelain"])
        status_lines = st.splitlines() if rc == 0 and st else []
        st_counts = _parse_status_porcelain(status_lines)
        facts["changes"] = st_counts
        dirty = (st_counts["staged"] + st_counts["unstaged"] + st_counts["untracked"]) > 0

        # Upstream ahead/behind if available
        rc, ab, ab_err = _git(repo_root, ["rev-list", "--left-right", "--count", "@{u}...HEAD"])
        if rc == 0 and ab:
            parts = ab.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                facts["behind"] = int(parts[0])
                facts["ahead"] = int(parts[1])
        else:
            facts["upstream"] = None

        # Remote url (sanitized)
        rc, url, _ = _git(repo_root, ["remote", "get-url", "origin"])
        if rc == 0 and url:
            facts["origin"] = _sanitize_remote(url) if DEFAULT_EXCLUDE_REMOTE_CREDS else url

        # Repo hygiene checks
        readme = _file_exists_any(repo_root, ["README.md", "README.MD", "README.txt", "README.rst"])
        # license_f = _file_exists_any(repo_root, ["LICENSE", "LICENSE.txt", "LICENSE.md"])
        gitignore = _file_exists_any(repo_root, [".gitignore"])
        # pyproject = _file_exists_any(repo_root, ["pyproject.toml"])
        requirements = _file_exists_any(repo_root, ["requirements.txt"])
        runbook_present = _has_runbook(repo_root)

        hygiene = {
            "readme": bool(readme),
            # "license": bool(license_f),
            "gitignore": bool(gitignore),
            # "pyproject": bool(pyproject),
            # "requirements": bool(requirements),
            "runbook": bool(runbook_present),
        }
        facts["hygiene"] = hygiene

        missing = [k for k, v in hygiene.items() if not v]
        evidence: List[str] = []
        if facts.get("branch") and facts.get("head"):
            evidence.append(f'{facts["branch"]}@{facts["head"]}')
        if last_commit_dt:
            age_h = (_now_utc() - last_commit_dt).total_seconds() / 3600.0
            evidence.append(f'last_commit={facts.get("last_commit_iso")} age_h={age_h:.1f}')
        if facts.get("commits_7d") is not None:
            evidence.append(f'commits_7d={facts["commits_7d"]}')
        if dirty:
            evidence.append(f'dirty staged={st_counts["staged"]} unstaged={st_counts["unstaged"]} untracked={st_counts["untracked"]}')
        if "ahead" in facts and "behind" in facts:
            evidence.append(f'ahead={facts["ahead"]} behind={facts["behind"]}')
        if missing:
            evidence.append("missing=" + ",".join(missing))

        # Thresholds for "stale"
        stale_days = project.get("repo_stale_days")
        stale_hours = project.get("repo_stale_hours")
        if stale_hours is None and stale_days is None:
            stale_days = 14
        threshold_h = float(stale_hours) if stale_hours is not None else float(stale_days) * 24.0

        # Decision
        # Priority: system error -> actionable failure -> warning -> ok
        if last_commit_dt is None:
            return done("WARN", "warning", "NO_COMMIT_INFO", "could not read last commit timestamp", evidence=evidence, meta=facts)

        age_h = (_now_utc() - last_commit_dt).total_seconds() / 3600.0
        facts["last_commit_age_hours"] = age_h
        if age_h > threshold_h:
            return done("WARN", "warning", "STALE_REPO:older_than_threshold",
                        f"last commit is {age_h:.1f}h old (threshold {threshold_h:.1f}h)",
                        evidence=evidence, meta=facts)

        # Repo is active enough. Still warn on hygiene gaps or dirty worktree.
        if dirty:
            return done("WARN", "warning", "DIRTY_WORKTREE",
                        "repo has uncommitted changes", evidence=evidence, meta=facts)

        # if missing:
        #     return done("WARN", "warning", "REPO_HYGIENE_GAPS",
        #                 "repo is active but missing basic hygiene files", evidence=evidence, meta=facts)

        return done("PASS", "ok", "RECENT_OK", "repo looks healthy (recent commit, clean worktree)", evidence=evidence, meta=facts)

# Export patterns for different plugin loaders
PLUGIN = CommitRecentPlugin()
def get_plugin():
    return PLUGIN



# TODO

# commit_recent_plugin.py

# What it covers well:

# Checks repo has recent commit and/or clean worktree.

# Sharp corners to fix:

# Config should be per project, not implicitly global. Add optional fields in the sheet like:

# stale_days_warn, stale_days_fail, allow_dirty

# Treat “dirty worktree” as WARN by default, but allow FAIL for certain repos (infra repos).

# Add an “upstream divergence” check (cheap signal):

# git rev-list --count --left-right @{upstream}...HEAD