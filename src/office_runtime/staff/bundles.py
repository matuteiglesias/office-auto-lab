from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Literal
import pandas as pd
from office_runtime.office.config import OfficeConfig
from office_runtime.office.io import read_sheet_values, normalize, write_json, write_text

SUPPORT_COLS = [
    "project_id",
    "Decision (why)",
    "Context Brief (next unlock)",
    "Narrative (thinking)",
    "print_artifact",
    "memo_slug",
]

RUNTIME_COLS = [
    "project_id",
    "last_update_ts",
    "last_update_by",
    "last_agg_status",
    "last_agg_bucket",
]

def _prep(df: pd.DataFrame) -> pd.DataFrame:
    return df.replace("", pd.NA).dropna(subset=["project_id"]).copy()

def _pick_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    keep = [c for c in cols if c in df.columns]
    return df[keep].copy()

def load_enriched_state(cfg: OfficeConfig, merged_csv: Path | None = None) -> pd.DataFrame:
    front = normalize(read_sheet_values(cfg.service_account_json, cfg.spreadsheet_id, cfg.front_gid))
    carry = normalize(read_sheet_values(cfg.service_account_json, cfg.spreadsheet_id, cfg.carry_gid))
    runtime = normalize(read_sheet_values(cfg.service_account_json, cfg.spreadsheet_id, cfg.runtime_gid))
    support = normalize(read_sheet_values(cfg.service_account_json, cfg.spreadsheet_id, cfg.support_gid))

    front = _prep(front)
    carry = _prep(carry)
    runtime = _pick_cols(_prep(runtime), RUNTIME_COLS)
    support = _pick_cols(_prep(support), SUPPORT_COLS)

    df = front.merge(carry, on="project_id", how="inner", suffixes=("", "_carry"))
    if "Title_carry" in df.columns and "Title" not in df.columns:
        df["Title"] = df["Title_carry"]
    if not runtime.empty:
        df = df.merge(runtime, on="project_id", how="left")
    if not support.empty:
        df = df.merge(support, on="project_id", how="left")
    if merged_csv:
        merged_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(merged_csv, index=False)
    return df

def _row_to_bundle(row: dict, bundle_type: str, selected_from: str, scan_paths: dict) -> dict:
    def pick(keys):
        return {k: row.get(k, "") for k in keys if k in row}

    return {
        "bundle_type": bundle_type,
        "office": {
            "selected_from": selected_from,
            "question_to_answer": {
                "unlocker_brief": "What is the cheapest bounded next unlock for this front?",
                "healthcheck_brief": "Is this front healthy enough to proceed, and if not, what should be checked first?",
                "decision_brief": "What decision is actually needed now, and what is the recommended default?",
            }.get(bundle_type, ""),
            "allowed_output": "short_markdown_brief",
        },
        "project": pick([
            "project_id","Title","carry","horizon","needs","principal",
            "repo_path","workdir","runbook_path","output_paths",
            "uses_prompt","prompt","Priority","status"
        ]),
        "human_context": pick([
            "text","Decision (why)","Context Brief (next unlock)",
            "Narrative (thinking)","print_artifact","memo_slug"
        ]),
        "runtime_context": pick([
            "last_update_ts","last_update_by","last_agg_status","last_agg_bucket"
        ]),
        "scan_paths": scan_paths,
    }

def _safe(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    txt = (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
    return r.returncode, txt.strip()

def _existing_scan_paths(project_id: str, scans_dir: Path) -> dict:
    out = {}
    prereqs = scans_dir / f"repo_prereqs__{project_id}.tsv"
    srp = scans_dir / f"repo_srp__{project_id}.txt"
    if prereqs.exists():
        out["repo_prereqs_tsv"] = str(prereqs)
    if srp.exists():
        out["repo_srp_txt"] = str(srp)
    return out


def _refresh_scan_repo(cfg: OfficeConfig, project_id: str, repo_or_workdir: str, scans_dir: Path) -> dict:
    scans_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    target = str(repo_or_workdir or "").strip()
    if not target:
        return out

    prereqs = cfg.scripts_dir / "repo_contract_scan.sh"
    srp = cfg.scripts_dir / "repo_snapshot_protocol.sh"

    if prereqs.exists():
        code, txt = _safe(["bash", str(prereqs), target])
        p = scans_dir / f"repo_prereqs__{project_id}.tsv"
        write_text(p, txt + ("\n" if txt else ""))
        out["repo_prereqs_tsv"] = str(p)

    if srp.exists():
        # code, txt = _safe(["bash", str(srp), target, "--full"])
        code, txt = _safe(["bash", str(srp), target])
        p = scans_dir / f"repo_srp__{project_id}.txt"
        write_text(p, txt + ("\n" if txt else ""))
        out["repo_srp_txt"] = str(p)

    return out

def _bundle_type_for(row: dict, selected_from: str) -> str | None:
    carry = str(row.get("carry", "")).strip()
    needs = str(row.get("needs", "")).strip().lower()

    if selected_from == "support_queue":
        if "health check" in needs and "unlocker" in needs:
            return "healthcheck_brief"
        if "health check" in needs:
            return "healthcheck_brief"
        if "unlocker" in needs or "next unlock" in needs:
            return "unlocker_brief"
        if "decision" in needs:
            return "decision_brief"
        return "unlocker_brief"

    if selected_from == "principal_brief_today" and carry == "Escalate":
        return "decision_brief"

    return None

def build_bundles(
    cfg: OfficeConfig,
    out_dir: Path | None = None,
    scan_mode: Literal["none", "existing", "refresh"] = "refresh",
) -> dict:
    latest = out_dir or cfg.latest_dir
    bundles_dir = latest / "bundles"
    scans_dir = latest / "scans"
    bundles_dir.mkdir(parents=True, exist_ok=True)
    scans_dir.mkdir(parents=True, exist_ok=True)

    df = load_enriched_state(cfg)
    made = []

    support_ids = set()
    principal_today_ids = set()

    support_csv = latest / "support_queue.csv"
    if support_csv.exists():
        support_ids = set(pd.read_csv(support_csv, dtype=str).fillna("")["project_id"].tolist())

    principal_today_csv = latest / "principal_brief_today.csv"
    if principal_today_csv.exists():
        principal_today_ids = set(pd.read_csv(principal_today_csv, dtype=str).fillna("")["project_id"].tolist())

    for _, r in df.iterrows():
        row = r.to_dict()
        pid = str(row.get("project_id", "")).strip()
        if not pid:
            continue

        selected_from = None
        if pid in support_ids:
            selected_from = "support_queue"
        elif pid in principal_today_ids and str(row.get("carry", "")).strip() == "Escalate":
            selected_from = "principal_brief_today"
        else:
            continue

        bundle_type = _bundle_type_for(row, selected_from)
        if not bundle_type:
            continue

        repo_or_workdir = str(row.get("workdir", "")).strip() or str(row.get("repo_path", "")).strip()
        if scan_mode == "none":
            scan_paths = {}
        elif scan_mode == "existing":
            scan_paths = _existing_scan_paths(pid, scans_dir)
        elif scan_mode == "refresh":
            scan_paths = _refresh_scan_repo(cfg, pid, repo_or_workdir, scans_dir) if repo_or_workdir else {}
        else:
            raise ValueError(f"Unsupported scan_mode: {scan_mode}")
        bundle = _row_to_bundle(row, bundle_type, selected_from, scan_paths)

        out = bundles_dir / f"{bundle_type.split('_')[0]}__{pid}.json"
        write_json(out, bundle)
        made.append({
            "project_id": pid,
            "bundle_type": bundle_type,
            "selected_from": selected_from,
            "bundle_path": str(out),
        })

    jobs = pd.DataFrame(made)
    if not jobs.empty:
        jobs.to_csv(latest / "ai_jobs.csv", index=False)
    else:
        pd.DataFrame(columns=["project_id","bundle_type","selected_from","bundle_path"]).to_csv(latest / "ai_jobs.csv", index=False)

    return {"bundles_built": len(made), "bundles_dir": str(bundles_dir), "scans_dir": str(scans_dir)}
