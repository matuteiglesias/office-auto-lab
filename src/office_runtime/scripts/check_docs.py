#!/usr/bin/env python3
"""Validate canonical Markdown metadata and repository-relative links."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CANONICAL_DIRS = tuple(
    ROOT / "docs" / name
    for name in ("architecture", "case-studies", "components", "getting-started", "operations", "reference")
)
REQUIRED = ("Status", "Audience", "Owner", "Verified against")
LINK_RE = re.compile(r"(?<!!)\[[^]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*$", re.MULTILINE)


def markdown_files(exclude: set[Path] | None = None) -> list[Path]:
    excluded = exclude or set()
    files = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    return [path for path in files if path.is_file() and path.resolve() not in excluded]


def slug(text: str) -> str:
    value = re.sub(r"[^\w\- ]", "", text.strip().lower())
    return re.sub(r"\s+", "-", value)


def check_metadata(path: Path, text: str) -> list[str]:
    if not any(path.is_relative_to(directory) for directory in CANONICAL_DIRS):
        return []
    head = "\n".join(text.splitlines()[:12])
    return [f"{path.relative_to(ROOT)}: missing metadata field {name!r}" for name in REQUIRED if f"**{name}:**" not in head]


def check_links(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    for raw in LINK_RE.findall(text):
        if "://" in raw or raw.startswith(("mailto:", "#")):
            target_path, _, anchor = raw.partition("#")
            if not target_path and anchor:
                destination = path
            else:
                continue
        else:
            target_path, _, anchor = raw.partition("#")
            destination = (path.parent / target_path).resolve()
        try:
            destination.relative_to(ROOT)
        except ValueError:
            errors.append(f"{path.relative_to(ROOT)}: link escapes repository: {raw}")
            continue
        if not destination.exists():
            errors.append(f"{path.relative_to(ROOT)}: missing link target: {raw}")
            continue
        if anchor and destination.is_file() and destination.suffix.lower() == ".md":
            headings = {slug(value) for value in HEADING_RE.findall(destination.read_text(encoding="utf-8"))}
            if anchor not in headings:
                errors.append(f"{path.relative_to(ROOT)}: missing anchor: {raw}")
    return errors


def _resolve_excludes(values: list[str]) -> set[Path]:
    excludes: set[Path] = set()
    for value in values:
        candidate = (ROOT / value).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError as exc:
            raise ValueError(f"excluded documentation path escapes repository: {value}") from exc
        if not candidate.is_file():
            raise ValueError(f"excluded documentation path does not exist: {value}")
        excludes.add(candidate)
    return excludes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Repository-relative Markdown path to omit from this scoped validation run.",
    )
    args = parser.parse_args(argv)
    try:
        excludes = _resolve_excludes(args.exclude)
    except ValueError as exc:
        parser.error(str(exc))

    errors: list[str] = []
    files = markdown_files(excludes)
    for path in files:
        text = path.read_text(encoding="utf-8")
        errors.extend(check_metadata(path, text))
        errors.extend(check_links(path, text))
    if errors:
        print("documentation validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"documentation validation ok: {len(files)} Markdown files; excluded={len(excludes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
