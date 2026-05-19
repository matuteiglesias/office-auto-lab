from __future__ import annotations
from pathlib import Path
import csv

REQUIRED_COLS_V0 = [
    "bucket",
    "date",
    "duration_ms",
    "executed",
    "normalized_class",
    "plugin",
    "project_id",
    "run_id",
    "short_diag",
    "ts_started",
]

class _LF(csv.excel):
    lineterminator = "\n"

def export_frontier_latest(rows: list[dict], *, run_date: str, out_root: str = "out/frontier") -> dict:
    out_root_p = Path(out_root)
    out_root_p.mkdir(parents=True, exist_ok=True)
    day_dir = out_root_p / run_date
    day_dir.mkdir(parents=True, exist_ok=True)

    # Normalize and keep only required columns. Unknown columns are ignored by design.
    norm = []
    for r in rows:
        rr = {k: r.get(k, "") for k in REQUIRED_COLS_V0}
        norm.append(rr)

    norm.sort(key=lambda r: (
        str(r.get("normalized_class","")),
        str(r.get("plugin","")),
        str(r.get("project_id","")),
        str(r.get("bucket","")),
        str(r.get("run_id","")),
    ))

    def _write_csv(path: Path) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=REQUIRED_COLS_V0, dialect=_LF, extrasaction="ignore")
            w.writeheader()
            w.writerows(norm)

    latest_path = out_root_p / "latest.csv"
    dated_path = day_dir / "frontier.csv"
    _write_csv(latest_path)
    _write_csv(dated_path)

    return {"latest_csv": str(latest_path), "dated_csv": str(dated_path), "rows": len(norm)}
