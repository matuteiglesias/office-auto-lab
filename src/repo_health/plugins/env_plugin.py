# plugins/env_plugin.py
from __future__ import annotations

import importlib
import os
import platform
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from .base import BasePlugin, result


def _run(cmd: List[str], cwd: Optional[str] = None, timeout_s: float = 2.0) -> Dict[str, Any]:
    try:
        p = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return {
            "rc": p.returncode,
            "out": (p.stdout or "").strip(),
            "err": (p.stderr or "").strip(),
        }
    except Exception as e:
        return {"rc": 999, "out": "", "err": f"{type(e).__name__}: {e}"}


def _sanitize_remote(url: str) -> str:
    # strip credentials in urls like https://user:pass@host/path
    import re
    return re.sub(r"^(https?://)([^/@]+)@", r"\1", (url or "").strip())


class EnvPlugin(BasePlugin):
    """
    Env plugin (v1):
      - rich but bounded snapshot of interpreter + deps + (optional) repo git facts
      - returns standard {status,message,bucket,evidence,meta}
      - offline by default (no network/DNS)
    """
    name = "env"
    version = "1.0.0"

    DEFAULT_CRITICAL_PKGS = [
        "pandas", "numpy", "requests", "gspread", "google.auth", "openpyxl"
    ]

    # Only surface these if present; do NOT dump all env.
    KEYS_OF_INTEREST = [
        "PATH", "HOME", "PYTHONPATH",
        "PROJECT_DIR", "DATA_DIR",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ]

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.time()
        project = ctx.get("project") or {}
        repo_root = str(project.get("repo_path") or project.get("workdir") or project.get("path") or "").strip()

        # knobs
        cfg = (ctx.get("config") or {}).get("env") or {}
        timeouts = ctx.get("timeouts") or {}
        timeout_git = float(cfg.get("timeout_git_s") or timeouts.get("git_s") or 2.0)
        # keep offline by default
        do_network = bool(cfg.get("check_network", False))

        evidence: List[str] = []
        meta: Dict[str, Any] = {}

        # ---- python / platform ----
        meta["python"] = {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "platform": platform.platform(),
            "cwd": os.getcwd(),
            "venv_active": bool(os.environ.get("VIRTUAL_ENV")),
            "venv_path": os.environ.get("VIRTUAL_ENV", ""),
        }

        # ---- env vars (high-signal only) ----
        meta["env_vars"] = {k: os.environ[k] for k in self.KEYS_OF_INTEREST if k in os.environ}

        # ---- packages ----
        critical = list(cfg.get("critical_packages") or self.DEFAULT_CRITICAL_PKGS)
        missing: List[str] = []
        present: List[str] = []
        for pkg in critical:
            try:
                importlib.import_module(pkg)
                present.append(pkg)
            except Exception:
                missing.append(pkg)
        meta["packages"] = {"critical": critical, "missing": missing, "present_count": len(present)}
        if missing:
            evidence.append("deps_missing:" + ",".join(missing))

        # ---- repo/git facts (optional) ----
        if repo_root:
            meta["repo_root"] = repo_root
            if not os.path.isdir(repo_root):
                # Important: env plugin can still report python/deps even if repo_root bad.
                evidence.append("repo_root_not_dir")
                meta["git"] = {"ok": False, "reason": "repo_root_not_a_directory"}
            else:
                # is it a git repo?
                r = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root, timeout_s=timeout_git)
                inside = (r["rc"] == 0 and r["out"].lower() == "true")
                git_meta: Dict[str, Any] = {"ok": bool(inside)}
                if not inside:
                    evidence.append("git_not_repo")
                    git_meta["reason"] = (r["err"] or r["out"] or "not a git work tree")[:200]
                else:
                    evidence.append("git_ok")
                    head = _run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, timeout_s=timeout_git)
                    br = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, timeout_s=timeout_git)
                    st = _run(["git", "status", "--porcelain"], cwd=repo_root, timeout_s=timeout_git)
                    dirty = bool(st["out"].strip()) if st["rc"] == 0 else None

                    git_meta.update({
                        "head": head["out"] if head["rc"] == 0 else "",
                        "branch": br["out"] if br["rc"] == 0 else "",
                        "dirty": dirty,
                    })

                    # origin remote (sanitized)
                    origin = _run(["git", "remote", "get-url", "origin"], cwd=repo_root, timeout_s=timeout_git)
                    if origin["rc"] == 0 and origin["out"]:
                        git_meta["origin"] = _sanitize_remote(origin["out"])

                    if dirty:
                        evidence.append("git_dirty")

                meta["git"] = git_meta
        else:
            evidence.append("repo_root_missing")

        # ---- network (optional, keep OFF by default) ----
        if do_network:
            import socket
            hosts = cfg.get("hosts") or ["google.com", "github.com", "pypi.org"]
            net: Dict[str, str] = {}
            for h in hosts:
                try:
                    socket.gethostbyname(h)
                    net[h] = "reachable"
                except Exception:
                    net[h] = "unreachable"
            meta["network"] = net
            if any(v == "unreachable" for v in net.values()):
                evidence.append("net_unreachable")

        meta["elapsed_ms"] = int((time.time() - t0) * 1000)

        # ---- status decision ----
        # Principle: env plugin is about environment readiness.
        # - Missing deps => FAIL (actionable)
        # - Network failures only matter if enabled => WARN/FAIL depending on policy (here WARN)
        # - Missing repo_root is NOT a failure (env can still be OK)
        if missing:
            return result(
                status="FAIL",
                bucket="MISSING_DEPS",
                message=f"missing python packages: {', '.join(missing)}",
                evidence=evidence,
                meta=meta,
            )

        if do_network and any(v == "unreachable" for v in meta.get("network", {}).values()):
            return result(
                status="WARN",
                bucket="NETWORK_DNS_ISSUES",
                message="dns lookup failed for at least one host",
                evidence=evidence,
                meta=meta,
            )

        return result(
            status="PASS",
            bucket="ENV_OK",
            message="env ok: python + deps present",
            evidence=evidence,
            meta=meta,
        )


PLUGIN = EnvPlugin()

def get_plugin():
    return PLUGIN