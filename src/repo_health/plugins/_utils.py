# plugins/_utils.py
from __future__ import annotations

import datetime
import hashlib
import os
from typing import Iterable, Optional, Sequence, Tuple, Dict, Any

def file_stat(path: str) -> Tuple[int, float]:
    """Return (size_bytes, mtime_epoch). Never raises; returns (0,0) on failure."""
    try:
        st = os.stat(path)
        return int(st.st_size), float(st.st_mtime)
    except Exception:
        return 0, 0.0


def mtime_iso(mtime_epoch: float) -> str:
    try:
        return datetime.datetime.fromtimestamp(mtime_epoch, tz=datetime.timezone.utc).isoformat()
    except Exception:
        return "1970-01-01T00:00:00+00:00"


def days_since_epoch(mtime_epoch: float) -> float:
    if not mtime_epoch:
        return 1e9
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    return (now - float(mtime_epoch)) / 86400.0


def iter_files_deterministic(
    root: str,
    *,
    max_depth: int = 6,
    exclude_dirs: Optional[set[str]] = None,
    follow_symlinks: bool = False,
    max_files: int = 8000,
) -> Iterable[str]:
    """Deterministic os.walk with depth + exclusions + cap."""
    exclude = exclude_dirs or DEFAULT_EXCLUDE_DIRS
    root = os.path.abspath(root)

    yielded = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=follow_symlinks):
        # depth control
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirnames[:] = []
            continue

        # exclude dirs deterministically
        dirnames[:] = sorted([d for d in dirnames if d not in exclude])

        # stable file order
        for fn in sorted(filenames):
            yielded += 1
            if yielded > max_files:
                return
            yield os.path.join(dirpath, fn)


def is_runbook_basename(name: str) -> bool:
    n = name.lower()
    if n == "runbook":
        return True
    if n.startswith("runbook."):
        return True
    # allow plural folder file name variations occasionally
    if n in {"runbooks.md", "runbooks.txt"}:
        return True
    return False


def find_runbook_files(
    root: str,
    *,
    max_depth: int = 6,
    max_files: int = 8000,
    include_readme_fallback: bool = True,
) -> list[str]:
    """Return absolute paths to runbook candidates, deterministically sorted."""
    root = os.path.abspath(root)
    candidates: list[str] = []

    for p in iter_files_deterministic(root, max_depth=max_depth, max_files=max_files):
        base = os.path.basename(p)
        if is_runbook_basename(os.path.splitext(base)[0]) or base.lower().startswith("runbook."):
            candidates.append(p)

    if not candidates and include_readme_fallback:
        # README fallback only if no runbook.* exists
        for p in iter_files_deterministic(root, max_depth=2, max_files=2000):
            base = os.path.basename(p).lower()
            if base in {"readme.md", "readme.txt", "readme"}:
                candidates.append(p)

    return sorted(set(candidates))


def score_runbook(relpath: str, signals: Dict[str, Any]) -> Tuple[int, int, str]:
    """Higher score first. Return a tuple usable for deterministic sorting."""
    rp = relpath.replace(os.sep, "/").lower()
    score = 0

    # name/location preference
    if rp.endswith("/runbook.md") or rp == "runbook.md":
        score += 50
    elif rp.endswith("/runbook.txt") or rp == "runbook.txt":
        score += 40
    elif "docs/" in rp:
        score += 10
    elif "notes/" in rp:
        score += 5

    # content signals
    if signals.get("has_smoke"):
        score += 20
    if signals.get("has_prereqs"):
        score += 10
    if signals.get("has_troubleshooting"):
        score += 10
    if signals.get("has_acceptance"):
        score += 5

    # prefer shorter paths (less nesting)
    depth = rp.count("/")
    return (-score, depth, rp)

# import datetime
# import hashlib
# import os
import time
import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional, List, Dict, Any, Tuple


DEFAULT_EXCLUDE_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules",
    ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", ".cache",
    ".idea", ".vscode",
}

DEFAULT_OUTPUT_DIR_HINTS = ["outputs", "output", "artifacts", "reports", "data", "results"]


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def snippet_sha256_of_file(path: str, max_read: int = 4000) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            b = f.read(max_read)
        return hashlib.sha256(b).hexdigest()
    except Exception:
        return None


def safe_read_text_prefix(path: str, max_chars: int = 40000) -> str:
    try:
        with open(path, "rb") as f:
            b = f.read(max_chars * 2)
        # reject binary-ish
        if b"\0" in b[:8000]:
            return ""
        return b.decode("utf-8", errors="replace")[:max_chars]
    except Exception:
        return ""


def bytes_human(n: int) -> str:
    try:
        n = int(n)
    except Exception:
        return str(n)
    if n < 1024:
        return f"{n}B"
    for unit in ["KB", "MB", "GB", "TB"]:
        n = n / 1024.0
        if n < 1024:
            return f"{n:.1f}{unit}"
    return f"{n:.1f}PB"


def age_human(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = seconds / 60.0
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60.0
    if hours < 48:
        return f"{hours:.1f}h"
    days = hours / 24.0
    return f"{days:.1f}d"


@dataclass(frozen=True)
class FileHit:
    relpath: str
    abspath: str
    size_bytes: int
    mtime_epoch: float


def _is_excluded_dir(dirname: str, extra_excludes: Optional[set[str]] = None) -> bool:
    if dirname in DEFAULT_EXCLUDE_DIRS:
        return True
    if extra_excludes and dirname in extra_excludes:
        return True
    return False


def walk_files_deterministic(
    root: str,
    *,
    max_depth: int = 6,
    exclude_dirs: Optional[set[str]] = None,
    followlinks: bool = False,
    deadline_epoch: Optional[float] = None,
    max_files_seen: Optional[int] = None,
) -> Iterator[Tuple[str, str]]:
    """Yield (abspath, relpath_from_root) deterministically.
    Deterministic means:
      - directory entries are sorted
      - directory pruning is stable
    """
    root = os.path.abspath(root)
    root_sep = root + os.sep

    files_seen = 0
    for cur, dirs, files in os.walk(root, topdown=True, followlinks=followlinks):
        if deadline_epoch and time.time() > deadline_epoch:
            return

        rel_dir = cur[len(root_sep):] if cur.startswith(root_sep) else ""
        depth = 0 if not rel_dir else rel_dir.count(os.sep) + 1
        # prune by depth
        if depth >= max_depth:
            dirs[:] = []
        # prune excluded dirs
        dirs[:] = [d for d in dirs if not _is_excluded_dir(d, exclude_dirs)]
        dirs.sort()
        files.sort()

        for fn in files:
            if deadline_epoch and time.time() > deadline_epoch:
                return
            abspath = os.path.join(cur, fn)
            relpath = os.path.relpath(abspath, root)
            yield abspath, relpath
            files_seen += 1
            if max_files_seen and files_seen >= max_files_seen:
                return


def best_effort_du_lines(paths: List[str], *, timeout_s: float = 2.0) -> List[str]:
    """Run `du -sh` if available, return lines like '12M\toutputs'. Best-effort."""
    if not paths:
        return []
    if shutil.which("du") is None:
        return []
    try:
        cmd = ["du", "-sh"] + paths
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        out = (p.stdout or "").strip().splitlines()
        # keep at most 10 lines deterministic order
        return out[:10]
    except Exception:
        return []


def split_list_field(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    s = str(val)
    # accept comma/semicolon/space separated
    parts = []
    for chunk in s.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts