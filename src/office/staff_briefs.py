from __future__ import annotations
import csv
import json
from pathlib import Path
import pandas as pd
from .io import write_text

def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def _read_text(path: Path, max_lines: int = 80) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[:max_lines]).strip()

def _read_tsv_first_row(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            return dict(row)
    return {}

def _s(x) -> str:
    if x is None:
        return ""
    x = str(x).strip()
    return "" if x.lower() == "nan" else x

def _first(*vals) -> str:
    for v in vals:
        sv = _s(v)
        if sv:
            return sv
    return ""

def _bundle_note(bundle: dict) -> str:
    h = bundle.get("human_context", {})
    return _first(
        h.get("Context Brief (next unlock)"),
        h.get("Decision (why)"),
        h.get("Narrative (thinking)"),
    )

def _scan_context(bundle: dict) -> tuple[dict, str]:
    sp = bundle.get("scan_paths", {}) or {}
    prereqs = _read_tsv_first_row(Path(sp["repo_prereqs_tsv"])) if sp.get("repo_prereqs_tsv") else {}
    srp = _read_text(Path(sp["repo_srp_txt"]), max_lines=70) if sp.get("repo_srp_txt") else ""
    return prereqs, srp

def render_unlocker(bundle: dict) -> str:
    p = bundle.get("project", {})
    r = bundle.get("runtime_context", {})
    prereqs, srp = _scan_context(bundle)
    title = _first(p.get("Title"), p.get("title"), p.get("project_id"))
    pid = _s(p.get("project_id"))
    repo = _first(p.get("workdir"), p.get("repo_path"))
    runbook = _first(prereqs.get("runbook_path"), p.get("runbook_path"))
    smoke = _first(prereqs.get("smoke_cmd"))
    note = _bundle_note(bundle)

    lines = [
        f"# Unlocker Brief - {pid} - {title}",
        "",
        "## Current posture",
        f"- Carry: {_s(p.get('carry'))}",
        f"- Horizon: {_s(p.get('horizon'))}",
        f"- Needs: {_s(p.get('needs'))}",
        "",
        "## What already exists",
    ]
    if note:
        lines.append(f"- Context: {note}")
    if repo:
        lines.append(f"- Repo/workdir: {repo}")
    if runbook:
        lines.append(f"- Runbook: {runbook}")
    if smoke:
        lines.append(f"- Smoke path hint: {smoke}")
    if _s(r.get("last_agg_status")):
        lines.append(f"- Runtime status: {_s(r.get('last_agg_status'))} / {_s(r.get('last_agg_bucket'))}")
    lines += [
        "",
        "## Cheapest next unlock",
    ]
    if smoke and repo:
        lines.append(f"- Run the bounded smoke path from `{repo}` using `{smoke}` and capture the result.")
    elif runbook:
        lines.append(f"- Read `{runbook}` and extract the exact first runnable or verifiable path.")
    elif repo:
        lines.append(f"- Use the repo snapshot to identify one entrypoint or one canonical file to inspect first in `{repo}`.")
    else:
        lines.append("- Create the minimum context stub: canonical purpose, current bottleneck, next bounded unlock.")
    lines += [
        "",
        "## What not to do now",
        "- Do not redesign the whole front.",
        "- Do not widen scope beyond one bounded unlock.",
        "- Do not mix diagnosis, rebuild, and new features in the same step.",
    ]
    if srp:
        lines += ["", "## Repo snapshot excerpt", "```text", srp[:3000], "```"]
    lines.append("")
    return "\n".join(lines)

def render_healthcheck(bundle: dict) -> str:
    p = bundle.get("project", {})
    r = bundle.get("runtime_context", {})
    prereqs, srp = _scan_context(bundle)
    title = _first(p.get("Title"), p.get("title"), p.get("project_id"))
    pid = _s(p.get("project_id"))
    repo = _first(p.get("workdir"), p.get("repo_path"))
    runbook = _first(prereqs.get("runbook_path"), p.get("runbook_path"))
    smoke = _first(prereqs.get("smoke_cmd"))
    note = _bundle_note(bundle)

    lines = [
        f"# Health Check Brief - {pid} - {title}",
        "",
        "## Known signals",
    ]
    if _s(r.get("last_update_ts")):
        lines.append(f"- Last update: {_s(r.get('last_update_ts'))} by {_s(r.get('last_update_by'))}")
    if _s(r.get("last_agg_status")):
        lines.append(f"- Aggregate runtime: {_s(r.get('last_agg_status'))} / {_s(r.get('last_agg_bucket'))}")
    if note:
        lines.append(f"- Context note: {note}")
    if repo:
        lines.append(f"- Repo/workdir: {repo}")
    if runbook:
        lines.append(f"- Runbook: {runbook}")
    if smoke:
        lines.append(f"- Smoke path: {smoke}")

    lines += [
        "",
        "## Recommended check order",
    ]
    if runbook:
        lines.append(f"1. Read `{runbook}` and confirm the canonical path still matches reality.")
    if smoke and repo:
        lines.append(f"2. Run `{smoke}` from `{repo}` and capture output.")
    elif repo:
        lines.append(f"2. Run a bounded repo snapshot / entrypoint inspection in `{repo}`.")
    lines.append("3. Compare result against current carry state and runtime status.")
    lines += [
        "",
        "## Healthy means",
        "- The front has one obvious entry path.",
        "- The expected artifact or smoke output can be produced.",
        "- The next step after diagnosis is clear.",
    ]
    if srp:
        lines += ["", "## Repo snapshot excerpt", "```text", srp[:3000], "```"]
    lines.append("")
    return "\n".join(lines)

def render_decision(bundle: dict) -> str:
    p = bundle.get("project", {})
    h = bundle.get("human_context", {})
    title = _first(p.get("Title"), p.get("title"), p.get("project_id"))
    pid = _s(p.get("project_id"))

    why = _first(h.get("Decision (why)"), h.get("Context Brief (next unlock)"), h.get("Narrative (thinking)"))
    needs = _s(p.get("needs"))

    default = "Approve one bounded next step that reduces ambiguity without broad redesign."
    if "health check" in needs.lower():
        default = "Approve a health check first, and postpone broader redesign until the health result is visible."
    if "execution" in needs.lower():
        default = "Approve one focused execution block with explicit stop rule and evidence expectation."

    lines = [
        f"# Decision Brief - {pid} - {title}",
        "",
        "## Decision needed now",
        f"- Carry: {_s(p.get('carry'))}",
        f"- Horizon: {_s(p.get('horizon'))}",
        f"- Needs: {needs}",
        "",
        "## Why this is surfacing",
        f"- {why or 'This item reached escalation or principal-required status and needs explicit direction.'}",
        "",
        "## Recommended default",
        f"- {default}",
        "",
        "## Cost of delay",
        "- The item stays cognitively open.",
        "- It continues to occupy principal attention without resolution.",
        "- Follow-up work cannot be cleanly delegated.",
        "",
        "## Acceptable outcomes",
        "- Approve the default.",
        "- Replace it with a narrower alternative.",
        "- Defer explicitly with a named review point.",
        "",
    ]
    return "\n".join(lines)

def render_execution(row: dict, prereqs: dict | None = None) -> str:
    prereqs = prereqs or {}
    pid = _s(row.get("project_id"))
    title = _s(row.get("Title"))
    repo = _first(row.get("workdir"), row.get("repo_path"))
    runbook = _first(prereqs.get("runbook_path"), row.get("runbook_path"))
    smoke = _first(prereqs.get("smoke_cmd"))
    note = _first(
        row.get("Context Brief (next unlock)"),
        row.get("Decision (why)"),
        row.get("Narrative (thinking)"),
        row.get("text"),
    )

    lines = [
        f"# Execution Brief - {pid} - {title}",
        "",
        "## Block objective",
        f"- Carry: {_s(row.get('carry'))}",
        f"- Horizon: {_s(row.get('horizon'))}",
        f"- Needs: {_s(row.get('needs'))}",
    ]
    if note:
        lines.append(f"- Context: {note}")
    lines += ["", "## Entry path"]
    if runbook:
        lines.append(f"- Read `{runbook}` first.")
    if smoke and repo:
        lines.append(f"- Preferred first action: run `{smoke}` from `{repo}`.")
    elif repo:
        lines.append(f"- Preferred first action: enter `{repo}` and inspect the canonical entrypoint or main runnable path.")
    else:
        lines.append("- Preferred first action: read the row context and define one bounded next action.")
    lines += [
        "",
        "## Evidence expected",
        "- A command output, note, diff, updated artifact, or explicit diagnosis.",
        "",
        "## Stop rule",
        "- Stop when one bounded step is completed and the next touch is clearer than before.",
        "- Do not widen scope mid-block.",
        "",
    ]
    return "\n".join(lines)

def build_staff_briefs(latest_dir: Path, top_execution: int = 9) -> dict:
    latest_dir = Path(latest_dir)
    briefs_dir = latest_dir / "briefs"
    scans_dir = latest_dir / "scans"
    bundles_dir = latest_dir / "bundles"
    briefs_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    jobs_csv = latest_dir / "ai_jobs.csv"
    if jobs_csv.exists():
        jobs = pd.read_csv(jobs_csv, dtype=str).fillna("")
        for _, jr in jobs.iterrows():
            bundle_path = Path(jr["bundle_path"])
            bundle = _load_json(bundle_path)
            btype = _s(jr["bundle_type"])
            pid = _s(jr["project_id"])

            if btype == "unlocker_brief":
                md = render_unlocker(bundle)
                out = briefs_dir / f"unlocker__{pid}.md"
                write_text(out, md)
                rows.append({"project_id": pid, "brief_type": btype, "brief_path": str(out)})
            elif btype == "healthcheck_brief":
                md = render_healthcheck(bundle)
                out = briefs_dir / f"healthcheck__{pid}.md"
                write_text(out, md)
                rows.append({"project_id": pid, "brief_type": btype, "brief_path": str(out)})
            elif btype == "decision_brief":
                md = render_decision(bundle)
                out = briefs_dir / f"decision__{pid}.md"
                write_text(out, md)
                rows.append({"project_id": pid, "brief_type": btype, "brief_path": str(out)})

    merged = pd.read_csv(latest_dir / "merged_state.csv", dtype=str).fillna("")
    
    # blocks = pd.read_csv(latest_dir / "block_candidates.csv", dtype=str).fillna("")
    focus_queue = latest_dir / "focus_get_queue.csv"
    if focus_queue.exists():
        blocks = pd.read_csv(focus_queue, dtype=str).fillna("")
    else:
        blocks = pd.read_csv(latest_dir / "block_candidates.csv", dtype=str).fillna("")

    merged_ix = {str(r["project_id"]).strip(): r.to_dict() for _, r in merged.iterrows()}

    for _, br in blocks.head(top_execution).iterrows():
        pid = _s(br["project_id"])
        row = merged_ix.get(pid, br.to_dict())
        prereqs = _read_tsv_first_row(scans_dir / f"repo_prereqs__{pid}.tsv")
        md = render_execution(row, prereqs)
        out = briefs_dir / f"execution__{pid}.md"
        write_text(out, md)
        rows.append({"project_id": pid, "brief_type": "execution_brief", "brief_path": str(out)})

    idx = pd.DataFrame(rows)
    if not idx.empty:
        idx.to_csv(latest_dir / "brief_index.csv", index=False)
    else:
        pd.DataFrame(columns=["project_id","brief_type","brief_path"]).to_csv(latest_dir / "brief_index.csv", index=False)

    return {"briefs_built": len(rows), "briefs_dir": str(briefs_dir)}
