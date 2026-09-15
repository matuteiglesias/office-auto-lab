#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from office_runtime.office.battletest_projection import render_battletest_projection


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a lineage-safe battle-test review projection.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--out-root", required=True, type=Path)
    parser.add_argument("--generated-at", default=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
    args = parser.parse_args()
    print(json.dumps(render_battletest_projection(args.run_dir, args.out_root, generated_at=args.generated_at), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
