from __future__ import annotations
import pandas as pd
from .io import head_link_candidates

def _row_note(r: dict) -> str:
    for k in ["text", "Decision (why)", "Context Brief (next unlock)", "Narrative (thinking)"]:
        v = str(r.get(k, "")).strip()
        if v and v.lower() != "nan":
            return v.replace("\n", " ")[:220]
    return ""



def _render_rows(df: pd.DataFrame, limit: int = 8) -> list[str]:
    if df.empty:
        return ["(none)", ""]
    out = []
    for _, r in df.head(limit).iterrows():
        out.append(
            f"- {r.get('project_id','')} - {r.get('Title','')} "
            f"| {r.get('Priority','')} | {r.get('carry','')} | "
            f"{r.get('horizon','')} | {r.get('needs','')}"
        )
    out.append("")
    return out


def render_clock_compile(
    maint_get: pd.DataFrame,
    focus_get: pd.DataFrame,
    support_df: pd.DataFrame,
    watch_df: pd.DataFrame,
    post_eligible: pd.DataFrame,
) -> str:
    out = [
        "# Clock Compile",
        "",
        "This is a clock-facing routing surface. It does not replace the principal brief, support queue, or today compile.",
        "",
        "## Human MAINT candidates",
        "",
        "Rows expressed for bounded upkeep. These should become checklist items, not rich briefs.",
        "",
    ]
    out += _render_rows(maint_get, limit=10)

    out += [
        "## Human FOCUS candidates",
        "",
        "Rows expressed for deep work where staff_get can prepare a usable focus packet.",
        "",
    ]
    out += _render_rows(focus_get, limit=10)

    out += [
        "## Staff SUPPORT packets",
        "",
        "Rows needing health checks, unlockers, decision briefs, or other staff-preparable diagnostics.",
        "",
    ]
    out += _render_rows(support_df, limit=8)

    out += [
        "## Watch-only / dormant pathways",
        "",
        "Rows not currently expressed, but still watchable. These should stay quiet unless a trigger fires.",
        "",
    ]
    out += _render_rows(watch_df, limit=12)

    out += [
        "## Post-eligible rows",
        "",
        "Rows that should be reingested if touched. This is an eligibility surface, not a command to post-process everything.",
        "",
    ]
    out += _render_rows(post_eligible, limit=12)

    return "\n".join(out) + "\n"


    


def render_principal_brief(df: pd.DataFrame, title: str = "Principal Brief") -> str:
    out = [f"# {title}", ""]
    if df.empty:
        return f"# {title}\n\n(no items)\n"
    for _, r in df.iterrows():
        row = r.to_dict()
        out += [
            f"## {row.get('project_id','')} - {row.get('Title','')}",
            f"- Horizon: {row.get('horizon','')}",
            f"- Needs: {row.get('needs','')}",
            f"- Why now: {row.get('carry','')} / {row.get('principal','')}",
        ]
        note = _row_note(row)
        if note:
            out.append(f"- Quick note: {note}")
        links = head_link_candidates(row)
        if links:
            out.append("- Links:")
            out += [f"  - {x}" for x in links]
        out.append("")
    return "\n".join(out) + "\n"

def render_support_queue(df: pd.DataFrame) -> str:
    if df.empty:
        return "# Support Queue\n\n(no items)\n"
    out = ["# Support Queue", ""]
    groups = {}
    for _, r in df.iterrows():
        need = str(r.get("needs", "")).strip() or "Unspecified"
        groups.setdefault(need, []).append(r.to_dict())
    for need, rows in groups.items():
        out += [f"## {need}", ""]
        for row in rows:
            out.append(f"- {row.get('project_id','')} - {row.get('Title','')} ({row.get('horizon','')})")
        out.append("")
    return "\n".join(out) + "\n"

def render_validation_report(issues: list[dict]) -> str:
    out = ["# Validation Report", ""]
    if not issues:
        return "# Validation Report\n\n(no issues)\n"
    for i in issues:
        out.append(f"- [{i.get('severity','')}] {i.get('project_id','')} {i.get('sheet','')} {i.get('field','')}: {i.get('message','')}")
    out.append("")
    return "\n".join(out)

def render_today_compile(principal_today: pd.DataFrame, support_df: pd.DataFrame, escal_df: pd.DataFrame, blocks_df: pd.DataFrame) -> str:
    out = ["# Today Compile", ""]
    sections = [
        ("Today: Principal", principal_today.head(6)),
        ("Today: Staff-preparable", support_df.head(6)),
        ("Today: Escalations", escal_df.head(6)),
        ("Today: Block candidates", blocks_df.head(6)),
    ]
    for title, df in sections:
        out += [f"## {title}", ""]
        if df.empty:
            out += ["(none)", ""]
            continue
        for _, r in df.iterrows():
            out.append(f"- {r.get('project_id','')} - {r.get('Title','')} | {r.get('carry','')} | {r.get('horizon','')} | {r.get('needs','')}")
        out.append("")
    return "\n".join(out) + "\n"

def render_office_summary(manifest: dict, principal_today: pd.DataFrame, support_df: pd.DataFrame, active_df: pd.DataFrame, escal_df: pd.DataFrame, unmatched_front: pd.DataFrame, unmatched_carry: pd.DataFrame, issues: list[dict]) -> str:
    rc = manifest.get("row_counts", {})
    out = [
        "# Office Summary",
        "",
        "## Counts",
        "",
        f"- front_registry: {rc.get('front_registry', 0)}",
        f"- carry_state: {rc.get('carry_state', 0)}",
        f"- merged: {rc.get('merged', 0)}",
        f"- principal_brief_week: {rc.get('principal_brief_week', 0)}",
        f"- principal_brief_today: {rc.get('principal_brief_today', 0)}",
        f"- support_queue: {rc.get('support_queue', 0)}",
        f"- escalations: {rc.get('escalations', 0)}",
        f"- block_candidates: {rc.get('block_candidates', 0)}",
        "",
        "## Top 3 Principal Today",
        "",
    ]
    if principal_today.empty:
        out += ["(none)", ""]
    else:
        for _, r in principal_today.head(6).iterrows():
            out.append(f"- {r.get('project_id','')} - {r.get('Title','')} ({r.get('horizon','')} / {r.get('needs','')})")
        out.append("")

    out += ["## Top 3 Staff-preparable", ""]
    if support_df.empty:
        out += ["(none)", ""]
    else:
        for _, r in support_df.head(6).iterrows():
            out.append(f"- {r.get('project_id','')} - {r.get('Title','')} ({r.get('needs','')})")
        out.append("")

    out += ["## Active Execution Lanes", ""]
    if active_df.empty:
        out += ["(none)", ""]
    else:
        for _, r in active_df.head(6).iterrows():
            out.append(f"- {r.get('project_id','')} - {r.get('Title','')}")
        out.append("")

    out += ["## Current Escalations", ""]
    if escal_df.empty:
        out += ["(none)", ""]
    else:
        for _, r in escal_df.iterrows():
            out.append(f"- {r.get('project_id','')} - {r.get('Title','')}")
        out.append("")

    out += [
        "## Drift Note",
        "",
        f"- unmatched_front_registry: {len(unmatched_front)}",
        f"- unmatched_carry_state: {len(unmatched_carry)}",
        f"- validation_warnings_or_errors: {len(issues)}",
        "",
    ]
    return "\n".join(out) + "\n"
