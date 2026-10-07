#!/usr/bin/env python3
"""Compile deterministic application-asset readiness from normalized JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from office_runtime.jobs import JobPrepError, compile_application_prep


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, help="JSON containing job_ref, requirements, and asset_registry.")
    parser.add_argument("--as-of", required=True, help="Explicit YYYY-MM-DD evaluation date.")
    parser.add_argument("--out", help="Optional output JSON path. Stdout is always emitted.")
    args = parser.parse_args()

    try:
        payload = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        packet = compile_application_prep(
            job_ref=str(payload.get("job_ref") or ""),
            requirements=payload.get("requirements", []),
            asset_registry=payload.get("asset_registry", []),
            as_of=args.as_of,
        )
    except (OSError, json.JSONDecodeError, JobPrepError) as exc:
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
