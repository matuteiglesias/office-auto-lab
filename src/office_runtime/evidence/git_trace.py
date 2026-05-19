from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator


IGNORE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    ".next",
    ".cache",
}


@dataclass(frozen=True)
class GitRepo:
    path: Path
    name: str


def _parse_date_start(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def _parse_date_end_exclusive(s: str) -> datetime:
    # Treat --end YYYY-MM-DD as inclusive local/date intent by making it next-day exclusive.
    d = datetime.fromisoformat(s)
    if len(s) == 10:
        d = d + timedelta(days=1)
    return d.replace(tzinfo=timezone.utc)


def _run_git(repo: Path, args: list[str]) -> str:
    cmd = ["git", "-C", str(repo), *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "").strip())
    return r.stdout


def _is_git_repo(path: Path) -> bool:
    try:
        out = _run_git(path, ["rev-parse", "--is-inside-work-tree"]).strip()
        return out == "true"
    except Exception:
        return False


def discover_repos(roots: Iterable[Path], *, max_depth: int = 4) -> list[GitRepo]:
    repos: dict[str, GitRepo] = {}

    def walk(root: Path, depth: int) -> None:
        if depth > max_depth:
            return
        if not root.exists() or not root.is_dir():
            return

        if (root / ".git").exists() and _is_git_repo(root):
            real = root.resolve()
            repos[str(real)] = GitRepo(path=real, name=real.name)
            return

        try:
            children = list(root.iterdir())
        except PermissionError:
            return

        for child in children:
            if not child.is_dir():
                continue
            if child.name in IGNORE_DIR_NAMES:
                continue
            walk(child, depth + 1)

    for root in roots:
        walk(root.expanduser().resolve(), 0)

    return sorted(repos.values(), key=lambda r: str(r.path))


def _commit_shas(repo: Path, start: str, end: str, *, limit: int | None = None) -> list[str]:
    args = [
        "log",
        f"--since={start}",
        f"--until={end}",
        "--format=%H",
    ]
    if limit:
        args.insert(1, f"-n{limit}")
    out = _run_git(repo, args)
    return [x.strip() for x in out.splitlines() if x.strip()]


def _commit_metadata(repo: Path, sha: str) -> dict:
    fmt = "%H%x1f%h%x1f%aI%x1f%an%x1f%s"
    out = _run_git(repo, ["show", "-s", f"--format={fmt}", sha]).strip()
    parts = out.split("\x1f")
    full_sha, short_sha, commit_time, author, subject = (parts + [""] * 5)[:5]
    return {
        "commit_sha": short_sha or full_sha[:12],
        "commit_sha_full": full_sha,
        "commit_time": commit_time,
        "author": author,
        "subject": subject,
    }


def _commit_files(repo: Path, sha: str) -> list[str]:
    out = _run_git(repo, ["show", "--name-only", "--format=", sha])
    return [x.strip() for x in out.splitlines() if x.strip()]


def _commit_numstat(repo: Path, sha: str) -> tuple[int, int]:
    out = _run_git(repo, ["show", "--numstat", "--format=", sha])
    insertions = 0
    deletions = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins, dele = parts[0], parts[1]
        if ins.isdigit():
            insertions += int(ins)
        if dele.isdigit():
            deletions += int(dele)
    return insertions, deletions


def iter_commit_rows(repos: Iterable[GitRepo], *, start: str, end: str, limit_per_repo: int | None = None) -> Iterator[dict]:
    for repo in repos:
        try:
            shas = _commit_shas(repo.path, start, end, limit=limit_per_repo)
        except Exception as e:
            yield {
                "kind": "git_repo_error",
                "repo_path": str(repo.path),
                "repo_name": repo.name,
                "error": type(e).__name__,
                "message": str(e)[:500],
            }
            continue

        for sha in shas:
            try:
                meta = _commit_metadata(repo.path, sha)
                files = _commit_files(repo.path, sha)
                insertions, deletions = _commit_numstat(repo.path, sha)
                yield {
                    "kind": "git_commit",
                    "repo_path": str(repo.path),
                    "repo_name": repo.name,
                    **meta,
                    "files_changed": files,
                    "insertions": insertions,
                    "deletions": deletions,
                }
            except Exception as e:
                yield {
                    "kind": "git_commit_error",
                    "repo_path": str(repo.path),
                    "repo_name": repo.name,
                    "commit_sha": sha[:12],
                    "error": type(e).__name__,
                    "message": str(e)[:500],
                }


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            n += 1
    return n


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Trace git commits across repos within a date range.")
    p.add_argument("--roots", nargs="+", required=True, help="Root folders to search for git repos.")
    p.add_argument("--start", required=True, help="Start date/datetime, e.g. 2026-05-12.")
    p.add_argument("--end", required=True, help="End date/datetime. YYYY-MM-DD is treated as inclusive date.")
    p.add_argument("--out", required=True, help="Output JSONL path.")
    p.add_argument("--max-depth", type=int, default=4, help="Max folder depth for repo discovery.")
    p.add_argument("--limit-per-repo", type=int, default=None, help="Optional max commits per repo.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    roots = [Path(x).expanduser() for x in args.roots]
    repos = discover_repos(roots, max_depth=args.max_depth)

    rows = iter_commit_rows(
        repos,
        start=args.start,
        end=args.end,
        limit_per_repo=args.limit_per_repo,
    )
    n = write_jsonl(Path(args.out), rows)

    print(
        json.dumps(
            {
                "status": "ok",
                "repos_found": len(repos),
                "rows_written": n,
                "out": args.out,
                "start": args.start,
                "end": args.end,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())