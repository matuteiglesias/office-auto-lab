#!/usr/bin/env python3
"""Compile a quiet job follow-up/deadline watch from normalized packets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from office_runtime.jobs import JobWatchError, compile_followup_watch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    try:
        payload = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        packet = compile_followup_watch(
            action_packets=payload.get("action_packets", []),
            prep_packets=payload.get("prep_packets", []),
            previous_fingerprints=payload.get("previous_fingerprints", {}),
            as_of=args.as_of,
        )
    except (OSError, json.JSONDecodeError, JobWatchError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2

    rendered = json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
