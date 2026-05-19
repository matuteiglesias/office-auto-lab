# policy.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
import hashlib
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import pandas as pd 


Record = Dict[str, Any]
Table = Union[Sequence[Record], "pd.DataFrame"]


# ----------------------------
# Helpers: input normalization
# ----------------------------
def _to_records(table: Table) -> List[Record]:
    """
    Accepts either:
      - list[dict]
      - pandas.DataFrame
    Returns list[dict].
    """
    if table is None:
        return []
    if pd is not None and isinstance(table, pd.DataFrame):
        return table.to_dict(orient="records")
    # assume sequence of dicts
    return [dict(r) for r in table]


def _s(x: Any) -> str:
    """Stable string conversion used for IDs and joins."""
    if x is None:
        return ""
    return str(x).strip()


def _boolish(x: Any, default: bool = False) -> bool:
    if x is None:
        return default
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _parse_csvish_list(x: Any) -> List[str]:
    """
    Accepts:
      - "a,b,c"
      - ["a","b"]
      - None
    Returns list[str] trimmed and non-empty.
    """
    if x is None:
        return []
    if isinstance(x, (list, tuple, set)):
        return [s for s in (_s(v) for v in x) if s]
    s = _s(x)
    if not s:
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def _sha1_12(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


# ----------------------------
# Policy semantics (v1)
# ----------------------------
LANE_ACTIVE = "Sprint"
LANE_HEDGE = "Hedge"
LANE_HEDGE_B= "Hedge B"
LANE_ARCHIVE = "Archive"

CLASS_DEFAULT = "default"  # placeholder if you later support overrides


@dataclass(frozen=True)
class RunIntent:
    run_id: str
    run_date: str  # YYYY-MM-DD
    project_id: str
    plugin: str
    implied_by_tags: List[str]
    # lane: str
    priority: str
    due: bool
    prereq_ok: bool
    ineligible_bucket: str
    skip_reason: str
    scheduled: bool
    make_target: str


# def _detect_priority(p: Record) -> str:
#     """
#     v1 lane source:
#       - prefer explicit 'lane' / 'Lane'
#       - fallback to your 'Priority' column convention (Sprint/Hedge/Hedge B/Archive)
#     """
#     raw = _s(p.get("lane") or p.get("Lane") or p.get("Priority") or p.get("priority"))
#     s = raw.strip().lower()
#     if s in {"sprint"}:
#         return LANE_ACTIVE
#     if s in {"hedge"}:
#         return LANE_HEDGE
#     if s in {"hedge b", "hedge_b", "hedgeb"}:
#         return LANE_HEDGE_B
#     if s in {"archive"}:
#         return LANE_ARCHIVE
#     # default
#     return LANE_ACTIVE


def _detect_enabled(p: Record) -> bool:
    if "enabled" in p:
        return _boolish(p.get("enabled"), default=True)
    return True



from datetime import datetime, date as Date

def _detect_next_date(p: Record) -> Optional[Date]:
    """
    Read Projects.next and parse into a date.

    Expected common formats:
      - "12/27/2025"  (US m/d/yyyy)
      - "27/12/2025"  (d/m/yyyy)  <-- we'll handle if unambiguous
      - "2025-12-27"  (ISO)
      - datetime/date objects
    Returns:
      - date or None if missing/unparseable
    """
    raw = p.get("next")
    if raw is None:
        return None

    # already a date/datetime
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, Date) and not isinstance(raw, datetime):
        return raw

    s = _s(raw)
    if not s:
        return None

    s = s.strip()

    # ISO fast path: 2025-12-27
    try:
        return Date.fromisoformat(s)
    except Exception:
        pass

    # Try m/d/yyyy
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass

    # Try d/m/yyyy (only if it doesn't look like m/d with m>12 logic)
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            d = datetime.strptime(s, fmt).date()
            return d
        except Exception:
            pass

    return None


def _is_due_today(run_dt: Date, next_dt: Optional[Date]) -> bool:
    if next_dt is None:
        return False
    return next_dt <= run_dt



# def _compute_due_v1(run_dt: Date, lane: str, p: Record) -> bool:
#     """
#     v1 scheduling:
#       - active: due daily
#       - maintain: not due by default (can add weekly logic later)
#       - archive/delete: not due
#     If you later add cadence columns, extend here.
#     """
#     if lane == LANE_ACTIVE:
#         return True
#     return False


# def _missing_required_fields(p: Record, required_fields: List[str]) -> List[str]:
#     missing = []
#     for f in required_fields:
#         # treat empty string as missing
#         if not _s(p.get(f)):
#             missing.append(f)
#     return missing


# # ----------------------------
# # Public API
# # ----------------------------

from typing import Callable, Optional, Tuple, Union, List, Dict, Any

# ... keep your existing imports/types/RunIntent/helpers ...


import logging
from collections import Counter
from datetime import date as Date
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

# assumes you already have:
# - Table, Record, RunIntent
# - _to_records, _s, _boolish, _sha1_12, _intent_to_row, _compute_due_v1
# - lane constants: LANE_ACTIVE, LANE_HEDGE, LANE_HEDGE_B, LANE_ARCHIVE, LANE_DELETE
# - pd optional import handled elsewhere (pd may be None)

# ----------------------------
# Required-fields parsing (AND-of-ORs)
# ----------------------------
def _parse_required_fields_expr(x: Any) -> List[List[str]]:
    """
    Parse required_fields into AND-of-ORs.

    Examples:
      "repo_path"                  -> [["repo_path"]]
      "repo_path, env_path"        -> [["repo_path"], ["env_path"]]
      "repo_path OR runbook_path"  -> [["repo_path","runbook_path"]]
      "a OR b, c OR d, e"          -> [["a","b"], ["c","d"], ["e"]]
    """
    s = _s(x)
    if not s:
        return []
    parts = [p.strip() for p in s.split(",") if p.strip()]
    groups: List[List[str]] = []
    for part in parts:
        part = part.replace("|", " OR ")
        ors = [q.strip() for q in part.split(" OR ") if q.strip()]
        groups.append([_s(o) for o in ors if _s(o)])
    return groups


def _missing_required_fields_expr(p: Dict[str, Any], groups: List[List[str]]) -> List[str]:
    """
    Each group is satisfied if ANY field in the group is present (non-empty).
    Returns list of missing group labels ("a|b") for bucketing.
    """
    missing: List[str] = []
    for group in groups:
        if not group:
            continue
        ok = any(_s(p.get(f)) for f in group)
        if not ok:
            missing.append("|".join(group))
    return missing


# ----------------------------
# Capabilities: support wide or tall
# ----------------------------
def _extract_tags_from_capabilities_rows(cap_rows: List[Dict[str, Any]]) -> Tuple[Dict[str, List[str]], Dict[str, Any]]:
    """
    Supports:
      A) Tall: (project_id, capability_tag)
      B) Wide: (project_id, cap_repo, cap_pipeline, ...)
    Returns (tags_by_pid, debug_meta)
    """
    dbg = {
        "shape": None,
        "wide_cap_keys_count": 0,
        "wide_cap_keys_preview": [],
        "bad_rows": 0,
        "projects_with_tags": 0,
    }

    tags_by_pid: Dict[str, List[str]] = {}

    if not cap_rows:
        dbg["shape"] = "empty"
        return tags_by_pid, dbg

    # Detect wide keys
    wide_keys = []
    for k in cap_rows[0].keys():
        if isinstance(k, str) and k.startswith("cap_"):
            wide_keys.append(k)

    dbg["wide_cap_keys_count"] = len(wide_keys)
    dbg["wide_cap_keys_preview"] = wide_keys[:20]

    # Prefer tall mode if explicitly present
    tall_mode = any("capability_tag" in r for r in cap_rows)

    if tall_mode:
        dbg["shape"] = "tall"
        bad = 0
        for r in cap_rows:
            pid = _s(r.get("project_id"))
            tag = _s(r.get("capability_tag"))
            if not pid or not tag:
                bad += 1
                continue
            tags_by_pid.setdefault(pid, [])
            if tag not in tags_by_pid[pid]:
                tags_by_pid[pid].append(tag)
        dbg["bad_rows"] = bad
        dbg["projects_with_tags"] = len(tags_by_pid)
        return tags_by_pid, dbg

    # Otherwise wide mode if cap_* keys exist
    if wide_keys:
        dbg["shape"] = "wide"
        bad = 0
        for r in cap_rows:
            pid = _s(r.get("project_id"))
            if not pid:
                bad += 1
                continue
            for k, v in r.items():
                if isinstance(k, str) and k.startswith("cap_") and _boolish(v, default=False):
                    tags_by_pid.setdefault(pid, [])
                    if k not in tags_by_pid[pid]:
                        tags_by_pid[pid].append(k)
        dbg["bad_rows"] = bad
        dbg["projects_with_tags"] = len(tags_by_pid)
        return tags_by_pid, dbg

    # Fallback: no capability_tag and no cap_* columns
    dbg["shape"] = "unknown"
    dbg["bad_rows"] = len(cap_rows)
    return tags_by_pid, dbg



def compute_effective_runset(
    projects: Table,
    capabilities: Table,
    plugin_policy: Table,
    plugin_prereqs: Table,
    run_date: Union[Date, str],
    *,
    return_df: bool = False,
    debug: bool = False,  # <-- default ON (hardcoded convenience)
    logger: Optional[logging.Logger] = None,
    emit: Optional[Callable[[str], None]] = None,
    return_debug: bool = True,  # <-- default ON so you always get the debug dict
    debug_project_limit: int = 30,
    debug_intent_limit: int = 40,
) -> Union[List[RunIntent], "pd.DataFrame", Tuple[List[RunIntent], Dict[str, Any]]]:
    """
    Super-verbose, phase-logged version.

    - debug defaults to True
    - return_debug defaults to True (returns (intents, debug_info))
      If you need strict list return for runner compatibility, set return_debug=False,
      OR update runner to unpack tuples (recommended).
    """

    # ----------------------------
    # debug plumbing
    # ----------------------------
    def _say(msg: str) -> None:
        if not debug:
            return
        if emit is not None:
            emit(msg); return
        if logger is not None:
            logger.info(msg); return
        print(msg)

    def _preview_keys(rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return "[]"
        return str(list(rows[0].keys()))

    # ----------------------------
    # run_date normalization
    # ----------------------------
    if isinstance(run_date, str):
        run_dt = Date.fromisoformat(run_date)
        run_date_str = run_date
    else:
        run_dt = run_date
        run_date_str = run_dt.isoformat()

    _say(f"[policy] === compute_effective_runset ===")
    _say(f"[policy] run_date={run_date_str}")

    # ----------------------------
    # load/normalize tables
    # ----------------------------
    proj_rows = _to_records(projects)
    cap_rows = _to_records(capabilities)
    pol_rows = _to_records(plugin_policy)
    pre_rows = _to_records(plugin_prereqs)

    # logger.info("policy.inputs projects=%d capabilities=%d plugin_policy=%d plugin_prereqs=%d run_date=%s", len(projects), len(capabilities), len(plugin_policy), len(plugin_prereqs), run_date)

    debug_info: Dict[str, Any] = {
        "run_date": run_date_str,
        "counts": {},
        "drops": Counter(),
        "skip_reason": Counter(),
        "ineligible_bucket": Counter(),
        "intents_by_plugin": Counter(),
        "scheduled_by_plugin": Counter(),
        "projects_with_no_tags": 0,
        "projects_with_no_implied_plugins": 0,
        "header_preview": {
            "projects_keys": _preview_keys(proj_rows),
            "capabilities_keys": _preview_keys(cap_rows),
            "plugin_policy_keys": _preview_keys(pol_rows),
            "plugin_prereqs_keys": _preview_keys(pre_rows),
        },
        "capabilities_shape": {},
    }

    _say(f"[policy] loaded rows: projects={len(proj_rows)} capabilities={len(cap_rows)} "
         f"plugin_policy={len(pol_rows)} plugin_prereqs={len(pre_rows)}")
    _say(f"[policy] header preview: {debug_info['header_preview']}")

    # ----------------------------
    # index projects
    # ----------------------------
    proj_by_id: Dict[str, Dict[str, Any]] = {}
    missing_project_id_rows = 0
    dup_project_ids = 0

    for p in proj_rows:
        pid = _s(p.get("project_id"))
        if not pid:
            missing_project_id_rows += 1
            continue
        if pid in proj_by_id:
            dup_project_ids += 1
        proj_by_id[pid] = p

    debug_info["counts"]["projects_indexed"] = len(proj_by_id)
    debug_info["drops"]["projects_missing_project_id"] = missing_project_id_rows
    debug_info["drops"]["projects_duplicate_project_id_overwritten"] = dup_project_ids

    _say(f"[policy] projects indexed={len(proj_by_id)} "
         f"(missing project_id rows={missing_project_id_rows}, duplicate ids overwritten={dup_project_ids})")

    # ----------------------------
    # capabilities -> tags_by_pid (wide/tall)
    # ----------------------------
    tags_by_pid, cap_dbg = _extract_tags_from_capabilities_rows(cap_rows)
    debug_info["capabilities_shape"] = cap_dbg

    _say(f"[policy] capabilities shape={cap_dbg.get('shape')} "
         f"projects_with_tags={cap_dbg.get('projects_with_tags')} bad_rows={cap_dbg.get('bad_rows')}")
    if cap_dbg.get("shape") == "wide":
        _say(f"[policy] capabilities wide keys (preview)={cap_dbg.get('wide_cap_keys_preview')}")

    # ----------------------------
    # policy: capability -> plugin
    # ----------------------------
    pol_by_tag: Dict[str, List[Dict[str, Any]]] = {}
    bad_pol_rows = 0
    mode_off = 0

    for r in pol_rows:
        tag = _s(r.get("capability_tag") or r.get("capability"))
        plugin = _s(r.get("plugin"))
        if not tag or not plugin:
            bad_pol_rows += 1
            continue

        default_mode = _s(r.get("default_mode")).lower() or "on"

        # NEW
        make_target = _s(r.get("make_target")).strip()
        make_target = make_target.lower()  # optional, but helps normalize sheet noise

        r2 = dict(r)
        r2["default_mode"] = default_mode
        r2["make_target"] = make_target  # NEW
        pol_by_tag.setdefault(tag, []).append(r2)

        if default_mode != "on":
            mode_off += 1



    debug_info["counts"]["policy_tags_indexed"] = len(pol_by_tag)
    debug_info["drops"]["plugin_policy_rows_bad_missing_tag_or_plugin"] = bad_pol_rows
    debug_info["counts"]["plugin_policy_rows_mode_off"] = mode_off

    _say(f"[policy] policy indexed tags={len(pol_by_tag)} "
         f"(bad rows={bad_pol_rows}, mode_off_rows={mode_off})")
    if debug:
        _say(f"[policy] policy tags preview={list(pol_by_tag.keys())[:20]}")

    # ----------------------------
    # prereqs: plugin -> meta
    # ----------------------------
    prereq_by_plugin: Dict[str, Dict[str, Any]] = {}
    bad_pre_rows = 0
    for r in pre_rows:
        plugin = _s(r.get("plugin"))
        if not plugin:
            bad_pre_rows += 1
            continue
        meta = dict(r)
        meta["_required_groups"] = _parse_required_fields_expr(meta.get("required_fields"))
        prereq_by_plugin[plugin] = meta

    debug_info["counts"]["plugins_with_prereqs"] = len(prereq_by_plugin)
    debug_info["drops"]["plugin_prereqs_rows_bad_missing_plugin"] = bad_pre_rows

    _say(f"[policy] prereqs indexed plugins={len(prereq_by_plugin)} (bad rows={bad_pre_rows})")
    if debug:
        preview = {k: prereq_by_plugin[k].get("_required_groups") for k in list(prereq_by_plugin.keys())[:10]}
        _say(f"[policy] prereqs preview (required_groups)={preview}")

    # ----------------------------
    # main loop: build intents
    # ----------------------------
    intents: List[RunIntent] = []
    shown_projects = 0
    shown_intents = 0

    for pid, p in proj_by_id.items():
        if not _detect_enabled(p):
            debug_info["drops"]["projects_disabled"] += 1
            continue

        # lane = _detect_lane(p)
        # if lane == LANE_DELETE:
        #     debug_info["drops"]["projects_lane_delete"] += 1
        #     continue

        priority = _s(p.get("Priority") or p.get("priority") or "")  # keep your sheet string as-is
        project_tags = tags_by_pid.get(pid, [])
        if not project_tags:
            debug_info["projects_with_no_tags"] += 1

        # implied plugins
        implied_plugins: Dict[str, List[str]] = {}
        make_target_by_plugin: Dict[str, str] = {}  # NEW
        make_target_conflicts = 0  # NEW (optional debug)

        for tag in project_tags:
            for pol in pol_by_tag.get(tag, []):
                if _s(pol.get("default_mode")).lower() != "on":
                    continue

                plugin = _s(pol.get("plugin"))
                if not plugin:
                    continue

                implied_plugins.setdefault(plugin, [])
                if tag not in implied_plugins[plugin]:
                    implied_plugins[plugin].append(tag)

                # NEW: accumulate make_target for this plugin
                mt = _s(pol.get("make_target")).strip().lower()
                if mt:
                    prev = make_target_by_plugin.get(plugin, "")

                    # precedence rule for your use case:
                    # if any tag implies run_all, take run_all
                    if prev == "":
                        make_target_by_plugin[plugin] = mt
                    elif prev == "run_all":
                        pass
                    elif mt == "run_all":
                        make_target_by_plugin[plugin] = "run_all"
                    elif mt != prev:
                        # conflict: keep prev, but count it
                        make_target_conflicts += 1




        if project_tags and not implied_plugins:
            debug_info["projects_with_no_implied_plugins"] += 1

        if debug and shown_projects < debug_project_limit:
            shown_projects += 1
            # _say(f"[policy][project] pid={pid} lane={lane} Priority={priority} "
            #      f"tags={project_tags} implied_plugins={list(implied_plugins.keys())}")
            _say(f"[policy][project] pid={pid} Priority={priority} "
                 f"tags={project_tags} implied_plugins={list(implied_plugins.keys())}")

        for plugin, implied_by in implied_plugins.items():
            debug_info["intents_by_plugin"][plugin] += 1

            meta = prereq_by_plugin.get(plugin, {})
            required_groups = meta.get("_required_groups", [])
            missing = _missing_required_fields_expr(p, required_groups)
            prereq_ok = (len(missing) == 0)

            skip_reason = ""
            ineligible_bucket = ""

            if not prereq_ok:
                skip_reason = "missing_prereq"
                ineligible_bucket = f"MISSING_METADATA:{missing[0]}"
                debug_info["skip_reason"][skip_reason] += 1
                debug_info["ineligible_bucket"][ineligible_bucket] += 1

            # due = _compute_due_v1(run_dt, lane, p)
            # scheduled = bool(due and prereq_ok and lane != LANE_ARCHIVE)

            # if lane == LANE_ARCHIVE:
            #     scheduled = False
            #     if not skip_reason:
            #         skip_reason = "archived"
            #         debug_info["skip_reason"][skip_reason] += 1


            next_dt = _detect_next_date(p)
            due = _is_due_today(run_dt, next_dt)

            # prereq gating remains
            # scheduled = bool(due and prereq_ok)
            scheduled = bool(prereq_ok)

            # missing next -> not scheduled, but *auditable*
            if next_dt is None and prereq_ok:
                # You can decide whether missing next should be a skip_reason or just a bucket
                # skip_reason = skip_reason or "missing_next"
                debug_info["skip_reason"][skip_reason] += 1


            if scheduled:
                debug_info["scheduled_by_plugin"][plugin] += 1


            run_id = _sha1_12(f"{run_date_str}:{pid}:{plugin}")
            intent = RunIntent(
                run_id=run_id,
                run_date=run_date_str,
                project_id=pid,
                plugin=plugin,
                implied_by_tags=implied_by,
                # lane=lane,
                priority=priority,
                due=due,
                prereq_ok=prereq_ok,
                ineligible_bucket=ineligible_bucket,
                skip_reason=skip_reason,
                scheduled=scheduled,
                make_target=make_target_by_plugin.get(plugin, ""),  # NEW

                # make_target = , if smoke, target = smoke, if run_all, run_all...
            )
            # intent.make_target = row.make_target
            intents.append(intent)






            if debug and shown_intents < debug_intent_limit:
                shown_intents += 1
                _say(
                    "[policy][intent] "
                    f"pid={pid} plugin={plugin} implied_by={implied_by} "
                    f"required_groups={required_groups} missing={missing} "
                    f"next={next_dt} due={due} prereq_ok={prereq_ok} scheduled={scheduled} "
                    f"skip_reason={skip_reason} bucket={ineligible_bucket} run_id={run_id}"
                )

    debug_info["counts"]["intents_total"] = len(intents)
    debug_info["counts"]["projects_enabled_processed"] = (
        len(proj_by_id)
        - debug_info["drops"]["projects_disabled"]
        - debug_info["drops"]["projects_lane_delete"]
    )

    debug_info["counts"].setdefault("make_target_conflicts", 0)
    debug_info["counts"]["make_target_conflicts"] += make_target_conflicts


    # ----------------------------
    # summary log
    # ----------------------------
    _say(f"[policy] intents_total={len(intents)}")
    _say(f"[policy] drops={dict(debug_info['drops'])}")
    _say(f"[policy] skip_reason counts={dict(debug_info['skip_reason'])}")
    _say(f"[policy] ineligible_bucket top={debug_info['ineligible_bucket'].most_common(10)}")
    _say(f"[policy] intents_by_plugin={dict(debug_info['intents_by_plugin'])}")
    _say(f"[policy] scheduled_by_plugin={dict(debug_info['scheduled_by_plugin'])}")
    _say(f"[policy] projects_with_no_tags={debug_info['projects_with_no_tags']}, "
         f"projects_with_no_implied_plugins={debug_info['projects_with_no_implied_plugins']}")

    # ----------------------------
    # return
    # ----------------------------
    if return_df:
        if pd is None:
            raise RuntimeError("pandas is not installed, cannot return DataFrame")
        df = pd.DataFrame([_intent_to_row(i) for i in intents])
        return (df, debug_info) if return_debug else df

    # logger.info("policy.outputs intents=%d scheduled=%d ineligible=%d drops=%s", len(intents), sum(1 for i in intents if i.scheduled), sum(1 for i in intents if getattr(i, "ineligible_reason", None)), debug_info.get("drops"))

    return (intents, debug_info) if return_debug else intents


 
def _intent_to_row(i: RunIntent) -> Record:
    return {
        "run_id": i.run_id,
        "date": i.run_date,
        "project_id": i.project_id,
        "plugin": i.plugin,
        "implied_by_tags": ",".join(i.implied_by_tags),
        "priority": i.priority,
        "due": i.due,
        "prereq_ok": i.prereq_ok,
        "ineligible_bucket": i.ineligible_bucket,
        "skip_reason": i.skip_reason,
        "scheduled": i.scheduled,
    # make_target=make_target_by_plugin.get(plugin, ""),  # NEW
    }
