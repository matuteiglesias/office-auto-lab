from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable


CONSTRAINTS_PATH = Path("requirements/constraints.txt")
PROFILE_PATHS = {
    "office": Path("requirements/profiles/office.txt"),
    "capture": Path("requirements/profiles/capture.txt"),
    "repo-health": Path("requirements/profiles/repo-health.txt"),
    "full": Path("requirements/profiles/full.txt"),
    "legacy-auto-checker": Path("requirements/profiles/legacy-auto-checker.txt"),
}
ACTIVE_PROFILES = ("office", "capture", "repo-health", "full")
COMPATIBILITY_PROFILES = ("legacy-auto-checker",)
_EXACT_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s]+)$")
_BARE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


class DependencyProfileError(ValueError):
    pass


def normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _iter_lines(path: Path) -> Iterable[str]:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        yield line


def load_constraints(repo_root: Path) -> dict[str, str]:
    path = repo_root / CONSTRAINTS_PATH
    if not path.is_file():
        raise DependencyProfileError(f"missing constraints file: {path}")
    constraints: dict[str, str] = {}
    for line in _iter_lines(path):
        match = _EXACT_PIN.fullmatch(line)
        if not match:
            raise DependencyProfileError(f"constraint must be an exact == pin: {line!r}")
        name, version = normalize_name(match.group(1)), match.group(2)
        if name in constraints:
            raise DependencyProfileError(f"duplicate constraint for {name!r}")
        constraints[name] = version
    if not constraints:
        raise DependencyProfileError("constraints file is empty")
    return constraints


def load_profile(repo_root: Path, profile: str) -> list[str]:
    try:
        relative = PROFILE_PATHS[profile]
    except KeyError as exc:
        choices = ", ".join(PROFILE_PATHS)
        raise DependencyProfileError(f"unsupported dependency profile {profile!r}; choose one of: {choices}") from exc
    path = repo_root / relative
    if not path.is_file():
        raise DependencyProfileError(f"missing dependency profile: {path}")
    packages: list[str] = []
    seen: set[str] = set()
    for line in _iter_lines(path):
        if not _BARE_NAME.fullmatch(line):
            raise DependencyProfileError(
                f"profile entries must be bare package names; versions belong in constraints: {line!r}"
            )
        name = normalize_name(line)
        if name in seen:
            raise DependencyProfileError(f"duplicate package {name!r} in profile {profile!r}")
        seen.add(name)
        packages.append(name)
    if not packages:
        raise DependencyProfileError(f"dependency profile {profile!r} is empty")
    return packages


def validate_profiles(repo_root: Path) -> None:
    constraints = load_constraints(repo_root)
    loaded = {name: load_profile(repo_root, name) for name in PROFILE_PATHS}
    for profile, packages in loaded.items():
        unconstrained = sorted(set(packages) - set(constraints))
        if unconstrained:
            raise DependencyProfileError(
                f"profile {profile!r} has packages without canonical constraints: {unconstrained}"
            )

    expected_full = set(loaded["office"]) | set(loaded["capture"]) | set(loaded["repo-health"])
    actual_full = set(loaded["full"])
    if actual_full != expected_full:
        raise DependencyProfileError(
            "full profile must equal the union of office + capture + repo-health; "
            f"missing={sorted(expected_full - actual_full)} extra={sorted(actual_full - expected_full)}"
        )


def install_command(repo_root: Path, profile: str, python: str | None = None) -> list[str]:
    validate_profiles(repo_root)
    load_profile(repo_root, profile)
    python_bin = python or sys.executable
    return [
        python_bin,
        "-m",
        "pip",
        "install",
        "-c",
        str(repo_root / CONSTRAINTS_PATH),
        "-r",
        str(repo_root / PROFILE_PATHS[profile]),
    ]
