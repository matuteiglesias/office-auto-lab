#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from office_runtime.office.config import load_config
from office_runtime.office.run_records import compile_runtime_health, load_run_records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile runtime_health_v2 projection from canonical Office run records.")
    parser.add_argument(
        "--stale-after-seconds",
        type=int,
        default=int(os.environ.get("OFFICE_V2_HEALTH_STALE_SECONDS", str(14 * 60 * 60))),
        help="Age after which the last successful non-shadow generation becomes stale.",
    )
    parser.add_argument(
        "--out",
        help="Optional output path; defaults to <OFFICE_OUT_ROOT>/v2/runtime_health.json.",
    )
    args = parser.parse_args(argv)

    cfg = load_config()
    projection = compile_runtime_health(
        load_run_records(cfg.out_root),
        stale_after_seconds=args.stale_after_seconds,
    )
    out = Path(args.out).expanduser().resolve() if args.out else cfg.out_root / "v2" / "runtime_health.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(projection, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({"status": "ok", "out": str(out), "rows": len(projection.get("rows", [])), "projection_digest": projection.get("projection_digest", "")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
