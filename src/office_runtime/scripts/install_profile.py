#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from office_runtime.dependencies import (
    ACTIVE_PROFILES,
    COMPATIBILITY_PROFILES,
    PROFILE_PATHS,
    DependencyProfileError,
    install_command,
    load_constraints,
    load_profile,
    validate_profiles,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install one declared Office Runtime dependency profile from canonical constraints."
    )
    parser.add_argument("profile", nargs="?", help="Profile to install.")
    parser.add_argument("--list", action="store_true", help="List supported profiles and exit.")
    parser.add_argument("--check", action="store_true", help="Validate all dependency contracts and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Print the pip command without installing.")
    args = parser.parse_args()

    root = _repo_root()
    try:
        validate_profiles(root)
        if args.list:
            payload = {
                "active": list(ACTIVE_PROFILES),
                "compatibility_only": list(COMPATIBILITY_PROFILES),
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.check:
            payload = {
                "status": "ok",
                "constraints": len(load_constraints(root)),
                "profiles": {name: load_profile(root, name) for name in PROFILE_PATHS},
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if not args.profile:
            parser.error("profile is required unless --list or --check is used")
        command = install_command(root, args.profile)
    except DependencyProfileError as exc:
        parser.error(str(exc))

    if args.dry_run:
        print(json.dumps({"profile": args.profile, "command": command}, indent=2))
        return 0

    subprocess.run(command, cwd=root, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
