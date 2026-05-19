from __future__ import annotations
import numpy as np
import pandas as pd
from .config import OfficeConfig
from .io import coerce_bool, read_sheet_values, normalize, write_text, write_json, utc_ts, promote_latest
from .validate import validate_required, validate_rows
from .render import (
    render_principal_brief,
    render_support_queue,
    render_validation_report,
    render_today_compile,
    render_office_summary,
    render_clock_compile,
)

def _prep(df: pd.DataFrame) -> pd.DataFrame:
    return df.replace("", np.nan).dropna(subset=["project_id"]).copy()

def _merge(front: pd.DataFrame, carry: pd.DataFrame):
    front2 = _prep(front)
    carry2 = _prep(carry)

    front_ids = set(front2["project_id"].astype(str))
    carry_ids = set(carry2["project_id"].astype(str))

    unmatched_front = front2[~front2["project_id"].astype(str).isin(carry_ids)].copy()
    unmatched_carry = carry2[~carry2["project_id"].astype(str).isin(front_ids)].copy()

    df = front2.merge(carry2, on="project_id", how="inner", suffixes=("", "_carry"))
    if "Title_carry" in df.columns and "Title" not in df.columns:
        df["Title"] = df["Title_carry"]
    return df, unmatched_front, unmatched_carry



def _b(df: pd.DataFrame, col: str) -> pd.Series:
    """Safe boolean column reader. Missing columns default to False."""
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    return coerce_bool(df[col])


def _attention_routes(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Additive attention routing.

    expected=1 means a row is expressed in the current operating cycle.
    expected=0 rows may still be watched or forced into support/escalation,
    but they should not enter normal human MAINT/FOCUS queues.
    """
    expected = _b(df, "expected")
    human_maint = _b(df, "human_maint")
    human_focus = _b(df, "human_focus")
    staff_get = _b(df, "staff_get")
    staff_watch = _b(df, "staff_watch")
    staff_post = _b(df, "staff_post")

    forced = (
        df.get("carry", pd.Series("", index=df.index)).isin(["Support-needed", "Escalate"])
        | (
            (df.get("principal", pd.Series("", index=df.index)) == "Required")
            & df.get("horizon", pd.Series("", index=df.index)).isin(["Today", "This week"])
        )
    )

    expressed = df[expected | forced].copy()
    latent = df[~(expected | forced)].copy()

    maint_get = df[expected & human_maint & ~human_focus & staff_get].copy()
    focus_get = df[expected & human_focus & staff_get].copy()

    watch = df[~expected & staff_watch].copy()
    latent_staff_get = df[~expected & staff_get & staff_watch].copy()
    post_eligible = df[staff_post].copy()

    return {
        "expressed_state": _score(expressed),
        "latent_state": _score(latent),
        "maint_get_queue": _score(maint_get),
        "focus_get_queue": _score(focus_get),
        "watch_queue": _score(watch),
        "latent_staff_get_queue": _score(latent_staff_get),
        "post_eligible_queue": _score(post_eligible),
    }




def _score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    s = pd.Series(0, index=df.index, dtype="int64")
    s += (df.get("horizon", "") == "Today").astype(int) * 5
    s += (df.get("carry", "") == "Escalate").astype(int) * 3
    s += (df.get("carry", "") == "Active").astype(int) * 2
    s += (df.get("principal", "") == "Required").astype(int) * 1
    s += df.get("needs", pd.Series("", index=df.index)).astype(str).str.contains("Execution", case=False, na=False).astype(int) * 1
    s -= (df.get("horizon", "") == "Later").astype(int) * 2
    df["_score"] = s
    return df.sort_values(["_score", "project_id"], ascending=[False, True])



# 9. “Nullified if not expressed”

# This is the core compile rule.

# I would not literally delete rows. I would create two dataframes:

# watch queue: expected=0 and staff_watch=1
# expressed_df = df[expected | forced].copy()
# latent_df = df[~(expected | forced)].copy()
# forced = (
#     (df["carry"].isin(["Support-needed", "Escalate"])) |
#     ((df["principal"] == "Required") & df["horizon"].isin(["Today", "This week"]))
# )
# Then run the existing principal/block bucket mostly on expressed_df, not on df.

# But support should still catch unexpressed support rows if they are explicitly Support-needed.

# So:
# principal buckets: expressed or forced principal
# support buckets: carry=Support-needed, even if expected=0
# block candidates: expected=1 only
# watch queue: expected=0 and staff_watch=1

# def _attention_routes(df: pd.DataFrame):
#     expected = b(df, "expected")
#     human_maint = b(df, "human_maint")
#     human_focus = b(df, "human_focus")
#     staff_get = b(df, "staff_get")
#     staff_watch = b(df, "staff_watch")
#     staff_post = b(df, "staff_post")

#     expressed = df[expected].copy()

#     maint_get = df[expected & human_maint & ~human_focus & staff_get].copy()
#     focus_get = df[expected & human_focus & staff_get].copy()

#     watch_only = df[~expected & staff_watch].copy()

#     staff_get_dormant = df[~expected & staff_get & staff_watch].copy()

#     post_eligible = df[staff_post].copy()

#     return expressed, maint_get, focus_get, watch_only, staff_get_dormant, post_eligible


def _bucket(df: pd.DataFrame):
    principal_week = df[(df["principal"] == "Required") & (df["horizon"].isin(["Today", "This week"]))]
    principal_today = principal_week[(principal_week["horizon"] == "Today") | (principal_week["carry"] == "Escalate")]
    support = df[df["carry"] == "Support-needed"]
    escal = df[df["carry"] == "Escalate"]
    blocks = df[(df["carry"] == "Active") & (df["needs"].str.contains("Execution", case=False, na=False))]
    active_exec = df[df["carry"] == "Active"]
    return tuple(map(_score, [principal_week, principal_today, support, escal, blocks, active_exec]))

def run_compile(cfg: OfficeConfig) -> dict:
    run_id = utc_ts()
    run_dir = cfg.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    front = normalize(read_sheet_values(cfg.service_account_json, cfg.spreadsheet_id, cfg.front_gid))
    carry = normalize(read_sheet_values(cfg.service_account_json, cfg.spreadsheet_id, cfg.carry_gid))

    issues = validate_required(front, carry)
    if any(i["severity"] == "error" for i in issues):
        write_json(run_dir / "manifest.json", {"run_id": run_id, "status": "error", "issues": issues})
        return {"run_id": run_id, "status": "error", "issues": issues}

    df, unmatched_front, unmatched_carry = _merge(front, carry)
    issues += validate_rows(df, strict=cfg.strict)

    principal_week, principal_today, support, escal, blocks, active_exec = _bucket(df)
    routes = _attention_routes(df)

    principal_week.to_csv(run_dir / "principal_brief_week.csv", index=False)
    principal_today.to_csv(run_dir / "principal_brief_today.csv", index=False)
    support.to_csv(run_dir / "support_queue.csv", index=False)
    escal.to_csv(run_dir / "escalations.csv", index=False)
    blocks.to_csv(run_dir / "block_candidates.csv", index=False)
    active_exec.to_csv(run_dir / "active_execution_lanes.csv", index=False)
    unmatched_front.to_csv(run_dir / "unmatched_front_registry.csv", index=False)
    unmatched_carry.to_csv(run_dir / "unmatched_carry_state.csv", index=False)
    df.to_csv(run_dir / "merged_state.csv", index=False)
    for name, route_df in routes.items():
        route_df.to_csv(run_dir / f"{name}.csv", index=False)


    write_text(run_dir / "principal_brief_week.md", render_principal_brief(principal_week, "Principal Brief - Week"))
    write_text(run_dir / "principal_brief_today.md", render_principal_brief(principal_today, "Principal Brief - Today"))
    write_text(run_dir / "support_queue.md", render_support_queue(support))
    write_text(run_dir / "validation_report.md", render_validation_report(issues))
    write_text(run_dir / "today_compile.md", render_today_compile(principal_today, support, escal, blocks))
    write_text(
        run_dir / "clock_compile.md",
        render_clock_compile(
            routes["maint_get_queue"],
            routes["focus_get_queue"],
            support,
            routes["watch_queue"],
            routes["post_eligible_queue"],
        ),
    )

    manifest = {
        "run_id": run_id,
        "status": "ok",
        "row_counts": {
            "front_registry": int(len(front)),
            "carry_state": int(len(carry)),
            "merged": int(len(df)),
            "principal_brief_week": int(len(principal_week)),
            "principal_brief_today": int(len(principal_today)),
            "support_queue": int(len(support)),
            "escalations": int(len(escal)),
            "block_candidates": int(len(blocks)),
            "unmatched_front_registry": int(len(unmatched_front)),
            "unmatched_carry_state": int(len(unmatched_carry)),
            "expressed_state": int(len(routes["expressed_state"])),
            "latent_state": int(len(routes["latent_state"])),
            "maint_get_queue": int(len(routes["maint_get_queue"])),
            "focus_get_queue": int(len(routes["focus_get_queue"])),
            "watch_queue": int(len(routes["watch_queue"])),
            "latent_staff_get_queue": int(len(routes["latent_staff_get_queue"])),
            "post_eligible_queue": int(len(routes["post_eligible_queue"])),
        },
        "selected_ids": {
            "principal_brief_week": principal_week["project_id"].tolist() if "project_id" in principal_week.columns else [],
            "principal_brief_today": principal_today["project_id"].tolist() if "project_id" in principal_today.columns else [],
            "support_queue": support["project_id"].tolist() if "project_id" in support.columns else [],
            "escalations": escal["project_id"].tolist() if "project_id" in escal.columns else [],
            "block_candidates": blocks["project_id"].tolist() if "project_id" in blocks.columns else [],
            "maint_get_queue": routes["maint_get_queue"]["project_id"].tolist() if "project_id" in routes["maint_get_queue"].columns else [],
            "focus_get_queue": routes["focus_get_queue"]["project_id"].tolist() if "project_id" in routes["focus_get_queue"].columns else [],
            "watch_queue": routes["watch_queue"]["project_id"].tolist() if "project_id" in routes["watch_queue"].columns else [],
        },
        "warnings": [i for i in issues if i.get("severity") != "error"],
        "file_outputs": sorted([p.name for p in run_dir.iterdir() if p.is_file()]),
    }

    write_text(
        run_dir / "office_summary.md",
        render_office_summary(manifest, principal_today, support, active_exec, escal, unmatched_front, unmatched_carry, issues),
    )
    write_json(run_dir / "manifest.json", manifest)
    promote_latest(run_dir, cfg.latest_dir)
    return manifest
