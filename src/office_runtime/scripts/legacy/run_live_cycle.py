from __future__ import annotations
import argparse, subprocess, sys
from datetime import datetime
from pathlib import Path

def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(r.returncode)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--sheet-id", required=True)
    ap.add_argument("--sa", required=True)
    ap.add_argument("--frontier-csv", default="out/frontier/latest.csv")
    args = ap.parse_args()

    Path("out/runs").mkdir(parents=True, exist_ok=True)
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    log_path = Path("out/runs") / f"live_cycle_{run_id}.log"

    with log_path.open("w", encoding="utf-8") as log:
        def _p(cmd: list[str]) -> None:
            log.write("+ " + " ".join(cmd) + "\n")
            log.flush()
            r = subprocess.run(cmd, stdout=log, stderr=log)
            if r.returncode != 0:
                raise SystemExit(r.returncode)

        # 1) frontier update (must write out/frontier/latest.csv)
        _p(["python3", "-m", "office_runtime.ops.repo_health.run_frontier", "--sa", args.sa, "--sheet-id", args.sheet_id])

        # 2) compile (reads frontier csv)
        _p(["python3", "scripts/compile_blocks.py", "--frontier", args.frontier_csv, "--date", args.date])

        jsonl = f"out/compiler/{args.date}/prepared_blocks.jsonl"

        # 3) publish queue
        _p(["python3", "scripts/publish_block_queue.py", "--sheet-id", args.sheet_id, "--sa", args.sa, "--jsonl", jsonl])

    print(f"OK live cycle done. log={log_path}")
    return 0

# # TODO
# B) Make the service produce an obvious artifact each run

# You already have logs/run_YYYY-MM-DD_<runid>.log. Good.

# Do one more: write “last_ok” and “last_run” markers so you can check health without reading logs:

# out/runs/last_run.txt containing timestamp and run_id

# out/runs/last_ok.txt updated only when the full cycle succeeds

# This takes 3 lines in scripts/run_live_cycle.py and makes debugging trivial.

if __name__ == "__main__":
    raise SystemExit(main())
