# plugins/smoke_plugin.py
from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Dict, Optional, List

from .base import BasePlugin, result
from ._utils import snippet_sha256_of_file


class SmokeRunPlugin(BasePlugin):
    """
    Portfolio contract:
      - repo root contains a Makefile
      - Makefile exposes:
          * make smoke     (cheap, offline, bounded)
          * make run_all   (full integration run)
    """

    # If you want to avoid changing policy sheets right now, set this to "smoke".
    name = "smoke"
    version = "2.0.0"

    DEFAULT_SMOKE_TARGET = "smoke"
    DEFAULT_RUN_ALL_TARGET = "run_all"

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.time()
        project = ctx.get("project") or ctx

        dry_run = bool(ctx.get("dry_run", True))
        timeouts = ctx.get("timeouts") or {}

        # target selection
        target = (
            project.get("make_target")
            or ctx.get("make_target")
            or ctx.get("target")
            or self.DEFAULT_SMOKE_TARGET
        )
        target = str(target).strip() or self.DEFAULT_SMOKE_TARGET

        # timeouts per mode: smoke short, run_all longer
        if target == self.DEFAULT_RUN_ALL_TARGET:
            timeout_s = int(timeouts.get("run_all", timeouts.get("shell", 1800)))
        else:
            timeout_s = int(timeouts.get("smoke", timeouts.get("shell", 180)))

        artifact_root = ctx.get("artifact_root") or "artifacts"
        pid = str(project.get("project_id") or "unknown").strip() or "unknown"

        repo_root = self._detect_repo_root(project)
        if not repo_root:
            return result(
                status="NA",
                bucket="MISSING_METADATA:repo_path|workdir",
                message="repo_root missing (need repo_path or workdir)",
                evidence=[],
                meta={"timeout_s": timeout_s, "target": target},
            )

        # Enforce Makefile-at-root contract
        if not self._has_makefile(repo_root):
            return result(
                status="NA",
                bucket="MAKEFILE_NOT_FOUND",
                message="No Makefile found at repo root (expected Makefile/makefile)",
                evidence=[],
                meta={"repo_root": repo_root, "timeout_s": timeout_s, "target": target},
            )

        cmd = ["make", "-s", "-C", repo_root, target]

        try:
            env = os.environ.copy()
            env["SMOKE_DRY_RUN"] = "1" if dry_run else "0"
            env["PROJECT_ID"] = pid
            env["ARTIFACT_ROOT"] = os.path.abspath(os.path.expanduser(str(artifact_root)))

            proc = subprocess.run(
                cmd,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=env,
            )
            out = (proc.stdout or "") + "\n" + (proc.stderr or "")

            # Persist bounded log
            adir = os.path.join(artifact_root, pid)
            os.makedirs(adir, exist_ok=True)
            logname = f"{target}.log"
            logpath = os.path.join(adir, logname)
            with open(logpath, "w", encoding="utf-8", errors="ignore") as fh:
                fh.write(out[:200000])
            sha = snippet_sha256_of_file(logpath, max_read=4000)

            meta = {
                "cmd": cmd,
                "repo_root": repo_root,
                "rc": proc.returncode,
                "timeout_s": timeout_s,
                "dry_run": dry_run,
                "target": target,
                "elapsed_ms": int((time.time() - t0) * 1000),
            }

            # Special case: distinguish “target missing” from “target failed”
            if proc.returncode != 0 and "No rule to make target" in out:
                return result(
                    status="NA",
                    bucket=f"MAKE_TARGET_NOT_FOUND:{target}",
                    message=f"Makefile present but target not defined: {target}",
                    evidence=[f"log:{os.path.relpath(logpath)}:{(sha or '')[:12]}"],
                    meta=meta,
                )

            if proc.returncode == 0:
                return result(
                    status="PASS",
                    bucket="MAKE_OK",
                    message=f"ok rc=0 log={os.path.relpath(logpath)}",
                    evidence=[f"log:{os.path.relpath(logpath)}:{(sha or '')[:12]}"],
                    meta=meta,
                )

            return result(
                status="FAIL",
                bucket=f"CMD_NONZERO:{proc.returncode}",
                message=f"nonzero rc={proc.returncode} log={os.path.relpath(logpath)}",
                evidence=[f"log:{os.path.relpath(logpath)}:{(sha or '')[:12]}"],
                meta=meta,
            )

        except subprocess.TimeoutExpired:
            return result(
                status="ERROR",
                bucket="TIMEOUT:shell",
                message=f"timeout after {timeout_s}s",
                evidence=[],
                meta={
                    "cmd": cmd,
                    "repo_root": repo_root,
                    "timeout_s": timeout_s,
                    "dry_run": dry_run,
                    "target": target,
                    "elapsed_ms": int((time.time() - t0) * 1000),
                },
            )
        except Exception as e:
            return result(
                status="ERROR",
                bucket=f"EXCEPTION:{type(e).__name__}",
                message=f"{type(e).__name__}: {e}"[:200],
                evidence=[],
                meta={
                    "cmd": cmd,
                    "repo_root": repo_root,
                    "dry_run": dry_run,
                    "target": target,
                    "elapsed_ms": int((time.time() - t0) * 1000),
                },
            )

    def _detect_repo_root(self, project: Dict[str, Any]) -> str:
        repo_root = project.get("repo_path") or project.get("workdir") or project.get("path") or ""
        repo_root = str(repo_root).strip()
        if not repo_root:
            return ""
        return os.path.abspath(os.path.expanduser(repo_root))

    def _has_makefile(self, repo_root: str) -> bool:
        print('Makefile lookup in:', os.path.join(repo_root, "Makefile"))
        return (
            os.path.isfile(os.path.join(repo_root, "Makefile"))
            or os.path.isfile(os.path.join(repo_root, "makefile"))
        )
