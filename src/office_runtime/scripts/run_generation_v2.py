#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

from office_runtime.office.config import load_config
from office_runtime.office.generation_v2 import run_generation_v2


def _env_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "y"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile one coherent Office v2 generation.")
    parser.add_argument("--run-id", help="Optional filesystem-safe run id; defaults to current UTC timestamp.")
    parser.add_argument(
        "--max-deep",
        type=int,
        default=int(os.environ.get("OFFICE_V2_MAX_DEEP", "6")),
        help="Maximum number of Staff items receiving deep preparation.",
    )
    parser.add_argument(
        "--local-repo-evidence",
        action="store_true",
        default=_env_true("OFFICE_V2_LOCAL_REPO_EVIDENCE"),
        help="Enable bounded local Git evidence adapters after governed workspace resolution.",
    )
    parser.add_argument(
        "--shadow",
        action="store_true",
        help="Compile a complete run but do not replace the v2 current pointer.",
    )
    parser.add_argument(
        "--trigger",
        default=os.environ.get("OFFICE_V2_TRIGGER", "manual"),
        help="Run trigger label recorded as evidence, e.g. manual, scheduled, or shadow-check.",
    )
    args = parser.parse_args(argv)

    result = run_generation_v2(
        load_config(),
        run_id=args.run_id,
        max_deep=args.max_deep,
        include_local_repo_evidence=args.local_repo_evidence,
        publish=not args.shadow,
        trigger=args.trigger,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
