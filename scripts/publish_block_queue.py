from __future__ import annotations
import argparse, json
from pathlib import Path

from repo_health.sheets import auth_gspread, write_tab_overwrite  # reuse what runner already uses

def _load_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out

def _flatten(block: dict, artifact_path: str) -> dict:
    targets = block.get("targets", []) or []
    target_ids = ",".join(str(t.get("project_id","")) for t in targets if "project_id" in t)

    op_ids = ",".join(str(op.get("op_id","")) for op in (block.get("operator_plan",[]) or []) if isinstance(op, dict))
    stop = " | ".join(block.get("stop_rules",[]) or [])

    return {
        "date": block.get("date",""),
        "block_id": block.get("block_id",""),
        "mode": block.get("mode",""),
        "archetype": block.get("archetype",""),
        "duration_min": block.get("duration_min",""),
        "title": block.get("title",""),
        "targets": target_ids,
        "operators": op_ids,
        "stop_rules": stop,
        "artifact_path": artifact_path,
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet-id", required=True)
    ap.add_argument("--sa", required=True)
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--tab", default="BlockQueue")
    args = ap.parse_args()

    jsonl_path = Path(args.jsonl)
    blocks = _load_jsonl(jsonl_path)
    rows = [_flatten(b, str(jsonl_path)) for b in blocks]

    # sc = SheetClient(args.sheet_url)

    client = auth_gspread(args.sa)
        # 1mImijqIwcbBqcO05xKzPWMITo-53ypjd1BEGicTp3jE 

    sc = client.open_by_key(args.sheet_id)

    write_tab_overwrite(sc, args.tab, rows)
    print(f"OK published {len(rows)} blocks to tab={args.tab}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
