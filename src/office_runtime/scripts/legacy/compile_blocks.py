from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List


import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from office_runtime.ops.repo_health.compiler.generate import (
    parse_frontier_rows,
    rollup_projects,
    generate_candidate_blocks,
    candidate_to_prepared_block,
    write_jsonl,
)


def read_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontier", required=True, help="CSV with frontier rows")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD for output namespace")
    ap.add_argument("--out-dir", default="out/compiler", help="base output dir")
    ap.add_argument("--top", type=int, default=6, help="max blocks to emit")
    args = ap.parse_args()

    frontier_path = Path(args.frontier)
    rows = read_csv(frontier_path)

    issues = parse_frontier_rows(rows)
    projects = rollup_projects(issues)

    candidates = generate_candidate_blocks(args.date, projects, issues)

    prepared = [candidate_to_prepared_block(args.date, c) for c in candidates[: args.top]]

    # enforce v0 rule: PIPELINE blocks cannot include blockers
    for pb in prepared:
        if pb["mode"] == "PIPELINE":
            for t in pb["targets"]:
                pid = t["project_id"]
                p = projects.get(pid)
                if p and p.blockers:
                    raise RuntimeError(f"PIPELINE block includes blocker project {pid}: {sorted(p.blockers)}")

    out_dir = Path(args.out_dir) / args.date
    out_path = out_dir / "prepared_blocks.jsonl"
    write_jsonl(out_path, prepared)

    print(f"Wrote {len(prepared)} blocks -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
