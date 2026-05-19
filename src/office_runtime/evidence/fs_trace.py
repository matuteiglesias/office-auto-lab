from __future__ import annotations

import argparse
import json
import os
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


BUCKET_BY_EXT = {
    ".md": "markdown",
    ".txt": "text",
    ".csv": "data",
    ".json": "data",
    ".jsonl": "data",
    ".parquet": "data",
    ".xlsx": "spreadsheet",
    ".xls": "spreadsheet",
    ".pdf": "pdf",
    ".py": "code",
    ".sh": "code",
    ".js": "code",
    ".ts": "code",
    ".tsx": "code",
    ".html": "web",
    ".css": "web",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
}


def _parse_start(s: str) -> datetime:
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def _parse_end_exclusive(s: str) -> datetime:
    d = datetime.fromisoformat(s)
    if len(s) == 10:
        d = d + timedelta(days=1)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def _dt_from_ts(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _bucket(path: Path) -> str:
    return BUCKET_BY_EXT.get(path.suffix.lower(), "other")


def _should_ignore_dir(path: Path) -> bool:
    return path.name in IGNORE_DIR_NAMES


def iter_file_events(
    roots: Iterable[Path],
    *,
    start: datetime,
    end_exclusive: datetime,
    max_depth: int = 8,
    include_hidden: bool = False,
    limit: int | None = None,
) -> Iterator[dict]:
    emitted = 0

    for root in roots:
        root = root.expanduser().resolve()
        if not root.exists() or not root.is_dir():
            yield {
                "kind": "filesystem_root_error",
                "root": str(root),
                "error": "not_a_directory",
                "message": "Root does not exist or is not a directory.",
            }
            continue

        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath)

            rel_parts = current.relative_to(root).parts if current != root else ()
            depth = len(rel_parts)
            if depth > max_depth:
                dirnames[:] = []
                continue

            dirnames[:] = [
                d
                for d in dirnames
                if not _should_ignore_dir(Path(d)) and (include_hidden or not d.startswith("."))
            ]

            for name in filenames:
                if not include_hidden and name.startswith("."):
                    continue

                path = current / name
                try:
                    st = path.stat()
                except (FileNotFoundError, PermissionError, OSError):
                    continue

                modified_at = _dt_from_ts(st.st_mtime)
                if not (start <= modified_at < end_exclusive):
                    continue

                rel = path.relative_to(root)

                # Linux creation/birth time is not portable. We expose no created_at_observed
                # unless a future platform-specific implementation can support it reliably.
                row = {
                    "kind": "filesystem_event",
                    "root": str(root),
                    "path": str(path),
                    "relative_path": str(rel),
                    "event_type": "modified",
                    "modified_at": _iso(modified_at),
                    "created_at_observed": None,
                    "creation_reliable": False,
                    "size_bytes": int(st.st_size),
                    "extension": path.suffix.lower(),
                    "bucket": _bucket(path),
                }
                yield row
                emitted += 1

                if limit is not None and emitted >= limit:
                    return


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            n += 1
    return n


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Trace filesystem modifications within a date range.")
    p.add_argument("--roots", nargs="+", required=True, help="Root folders to scan.")
    p.add_argument("--start", required=True, help="Start date/datetime, e.g. 2026-05-12.")
    p.add_argument("--end", required=True, help="End date/datetime. YYYY-MM-DD is treated as inclusive date.")
    p.add_argument("--out", required=True, help="Output JSONL path.")
    p.add_argument("--max-depth", type=int, default=8, help="Max folder depth under each root.")
    p.add_argument("--include-hidden", action="store_true", help="Include hidden files/dirs except ignored heavy dirs.")
    p.add_argument("--limit", type=int, default=None, help="Optional max emitted rows.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    start = _parse_start(args.start)
    end_exclusive = _parse_end_exclusive(args.end)
    roots = [Path(x).expanduser() for x in args.roots]

    rows = iter_file_events(
        roots,
        start=start,
        end_exclusive=end_exclusive,
        max_depth=args.max_depth,
        include_hidden=args.include_hidden,
        limit=args.limit,
    )
    n = write_jsonl(Path(args.out), rows)

    print(
        json.dumps(
            {
                "status": "ok",
                "rows_written": n,
                "out": args.out,
                "start": args.start,
                "end": args.end,
                "max_depth": args.max_depth,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())