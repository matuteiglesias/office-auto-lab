# runner.py
import argparse, sys, time, traceback
from datetime import date as Date
from typing import Dict, List, Any, Tuple
from repo_health.frontier_export import export_frontier_latest

from repo_health.sheets import (
    auth_gspread,
    read_tab_records,          # implement small helper
    write_tab_overwrite,       # implement small helper
    append_rows,               # implement small helper
    ensure_header_has_columns, # optional helper
    batch_update_cells_by_col, # optional helper for Projects summary
)
from repo_health.policy import compute_effective_runset, RunIntent
from repo_health.plugin_loader import load_plugins_from_folder

PROJECTS_SHEET = "front_registry"
CAPABILITIES_SHEET = "Capabilities"
PLUGIN_POLICY_SHEET = "PluginPolicy"
PLUGIN_PREREQS_SHEET = "PluginPrereqs"
EFFECTIVE_RUNSET_SHEET = "EffectiveRunSet"
PLUGIN_RESULTS_SHEET = "PluginResults"
RUNTIME_HEALTH_SHEET = "runtime_health"

SUMMARY_COLS = ["last_update_ts", "last_update_by", "last_agg_status", "last_agg_bucket"]


import logging
from pathlib import Path

LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s "
    "run=%(run_id)s project=%(project_id)s plugin=%(plugin)s bucket=%(bucket)s "
    "%(message)s"
)

class ContextFilter(logging.Filter):
    def __init__(self, run_id="-"):
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        # Provide defaults so formatting never crashes
        record.run_id = getattr(record, "run_id", self.run_id)
        record.project_id = getattr(record, "project_id", "-")
        record.plugin = getattr(record, "plugin", "-")
        record.bucket = getattr(record, "bucket", "-")
        return True

def setup_logging(run_id: str, log_dir: str = "logs") -> logging.Logger:
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("checkins")
    root.setLevel(logging.INFO)

    # Avoid duplicate handlers if setup is called twice
    root.handlers.clear()
    root.propagate = False

    formatter = logging.Formatter(LOG_FORMAT)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    ch.addFilter(ContextFilter(run_id))
    root.addHandler(ch)

    # File handler per run
    fh = logging.FileHandler(log_dir_path / f"run_{run_id}.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)  # keep more detail in file
    fh.setFormatter(formatter)
    fh.addFilter(ContextFilter(run_id))
    root.addHandler(fh)

    return root




def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--sheet-id", required=True)
    p.add_argument("--sa", required=True)
    p.add_argument("--subset", help="comma-separated project_ids to run (priority).")
    p.add_argument("--rows", help="comma-separated sheet row numbers to run (1-based; Projects data rows start at 2).")
    p.add_argument("--plugins", help="comma-separated plugin names to run.")
    p.add_argument("--date", default=Date.today().isoformat(), help="YYYY-MM-DD; default today")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--no-write", action="store_true", default=False)
    p.add_argument("--policy-only", action="store_true", help="compute EffectiveRunSet but do not execute intents")
    return p.parse_args(argv)

def normalize_project_id(x) -> str:
    return str(x).strip() if x is not None else ""

def build_project_index(projects: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx = {}
    for r in projects:
        pid = normalize_project_id(r.get("project_id"))
        if pid:
            idx[pid] = r
    return idx

def subset_project_ids_from_rows(projects: List[Dict[str, Any]], rows_arg: str) -> List[str]:
    # rows are 1-based sheet rows. data rows start at 2.
    # so data index = row-2
    idxs = [int(x.strip()) for x in rows_arg.split(",") if x.strip()]
    pids = []
    for r in idxs:
        data_i = r - 2
        if 0 <= data_i < len(projects):
            pid = normalize_project_id(projects[data_i].get("project_id"))
            if pid:
                pids.append(pid)
    return pids

# run_id = _sha1_12(f"{run_date_str}:{pid}:{plugin}")

# logger = setup_logging(run_id)?

# log = setup_logging(run_id)

# log.info("runner started")
# log_plan = logging.getLogger("checkins.plan")
# log_exec = logging.getLogger("checkins.execute.plugin.pipeline_output")

# log_exec.info(
#     "search completed",
#     extra={"project_id": pid, "plugin": "pipeline_output", "bucket": "FOUND_RECENT"}
# )


def filter_intents(
    intents: List[RunIntent],
    *,
    subset_pids: List[str] | None,
    subset_plugins: List[str] | None,
) -> List[RunIntent]:
    # logger.debug("filter_intents.start intents=%d subset_pids=%d subset_plugins=%d", len(intents), len(subset_pids or []), len(subset_plugins or []))

    out = intents
    if subset_pids:
        s = set(subset_pids)
        out = [i for i in out if i.project_id in s]
        # logger.debug("filter_intents.after_pids intents=%d kept=%d", len(intents), len(out))
    if subset_plugins:
        s = set(subset_plugins)
        out = [i for i in out if i.plugin in s]
        # logger.debug("filter_intents.after_plugins kept=%d", len(out))
    # v1: execute only scheduled intents
    out = [i for i in out if i.scheduled]
    # logger.info("filter_intents.done scheduled=%d", len(out))
    return out

def execute_intent(intent: RunIntent, project_ctx: Dict[str, Any], plugins: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    """
    Returns a single PLUGIN_RESULTS row dict (append-only).
    Keep plugin raw output, but normalize to short fields in runner.
    """
    t0 = time.time()
    plugin_name = intent.plugin




    if plugin_name not in plugins:
        # Treat as system error in v1, but record it
        return {
            "run_id": intent.run_id,
            "date": intent.run_date,
            "project_id": intent.project_id,
            "plugin": plugin_name,
            "executed": False,
            "normalized_class": "system_error",
            "bucket": "PLUGIN_NOT_FOUND",
            "short_diag": f"plugin {plugin_name} not loaded",
            "ts_started": int(t0),
            "duration_ms": int((time.time() - t0) * 1000),
        }

    try:


        #   plugin_ctx = {
        #       "run_id": intent.run_id,
        #       "run_date": intent.run_date,
        #       "project_id": intent.project_id,
        #       "plugin": plugin_name,
        #       "dry_run": dry_run,
        #       "project": project_ctx,
        #       "timeouts": {"search_s": 10.0, "shell_s": 60.0},  # fill from your config
        #       "artifact_root": "artifacts",                    # optional
        #       "config": {},                                    # optional
        #   }
        #   raw = plugins[plugin_name].run(plugin_ctx)

        plugin_ctx = {
            "run_id": intent.run_id,
            "run_date": intent.run_date,
            "project_id": intent.project_id,
            "plugin": plugin_name,
            "dry_run": dry_run,
            "artifact_root": "artifacts",
            "timeouts": {"shell": 18, "search_s": 18},
            "project": project_ctx,
            "config": {},                                    # optional
        }
        raw = plugins[plugin_name].run(plugin_ctx)  # plugin API: run(ctx) -> dict
        # Expect raw like: {"status": "PASS|FAIL|WARN|NA|ERROR", "message": "...", "bucket": "...", "evidence": [...], "meta": {...}}


        # raw = plugins[plugin_name].run(project_ctx, dry_run=dry_run)  # your plugin API
        # Expect raw like: {"status": "PASS|FAIL|WARN|NA|ERROR", "message": "...", "evidence": "...", "meta": {...}}
        status = str(raw.get("status", "")).upper().strip()
        msg = str(raw.get("message", "")).strip()

        # v1 normalization rules
        if status in {"PASS"}:
            norm = "ok"
            bucket = "PASS"
        elif status in {"WARN", "WARNING"}:
            norm = "warning"
            bucket = "WARN"
        elif status in {"NA", "SKIP"}:
            norm = "ineligible"
            bucket = str(raw.get("bucket") or "NA")
        elif status in {"FAIL"}:
            norm = "actionable_failure"
            bucket = str(raw.get("bucket") or "FAIL")
        else:
            norm = "system_error"
            bucket = str(raw.get("bucket") or "PLUGIN_ERROR")

        return {
            "run_id": intent.run_id,
            "date": intent.run_date,
            "project_id": intent.project_id,
            "plugin": plugin_name,
            "executed": True,
            "normalized_class": norm,
            "bucket": bucket,
            "short_diag": msg[:200],
            "ts_started": int(t0),
            "duration_ms": int((time.time() - t0) * 1000),
        }

    except Exception as e:
        return {
            "run_id": intent.run_id,
            "date": intent.run_date,
            "project_id": intent.project_id,
            "plugin": plugin_name,
            "executed": True,
            "normalized_class": "system_error",
            "bucket": "EXCEPTION",
            "short_diag": f"{type(e).__name__}: {e}",
            "ts_started": int(t0),
            "duration_ms": int((time.time() - t0) * 1000),
        }
    

import uuid

def _mk_run_id(args) -> str:
    """
    Make a run_id early so we can log immediately.
    Use date if provided so it's easy to grep.
    """
    date_part = getattr(args, "date", None) or "no-date"
    # short suffix keeps it unique without being annoying
    suffix = uuid.uuid4().hex[:8]
    return f"{date_part}_{suffix}"

def _log_counts(log: logging.Logger, name: str, rows: list) -> None:
    log.info("%s loaded rows=%d", name, len(rows), extra={"bucket": "LOAD"})

def main(argv):
    args = parse_args(argv)
    dry_run = not args.apply

    # Create run_id before anything else so logs always have it
    run_id = _mk_run_id(args)

    # Setup logging once at the top-level
    logger = setup_logging(run_id=run_id, log_dir="logs")
    log = logging.getLogger("checkins")
    log_plan = logging.getLogger("checkins.plan")
    log_exec = logging.getLogger("checkins.execute")

    log.info(
        "runner.start date=%s dry_run=%s no_write=%s policy_only=%s",
        args.date, dry_run, args.no_write, args.policy_only,
        extra={"bucket": "RUN_START"},
    )

    t0 = time.time()


    client = auth_gspread(args.sa)
    sh = client.open_by_key(args.sheet_id)

    # Read metadata tabs as list[dict]
    projects = read_tab_records(sh, PROJECTS_SHEET)
    capabilities = read_tab_records(sh, CAPABILITIES_SHEET)
    plugin_policy = read_tab_records(sh, PLUGIN_POLICY_SHEET)
    plugin_prereqs = read_tab_records(sh, PLUGIN_PREREQS_SHEET)


    _log_counts(log_plan, "projects", projects)
    _log_counts(log_plan, "capabilities", capabilities)
    _log_counts(log_plan, "plugin_policy", plugin_policy)
    _log_counts(log_plan, "plugin_prereqs", plugin_prereqs)


    projects_by_id = build_project_index(projects)


    # Compute intents
    log_plan.info("plan.compute_effective_runset start", extra={"bucket": "PLAN"})
    intents, debug_info = compute_effective_runset(
        projects=projects,
        capabilities=capabilities,
        plugin_policy=plugin_policy,
        plugin_prereqs=plugin_prereqs,
        run_date=args.date,
        debug=False,
        emit=log_plan.debug,     # instead of print
        return_debug=True,
        # If your function supports it, pass run_id through so intents carry it
        # run_id=run_id,
    )
    log_plan.info(
        "plan.compute_effective_runset done intents=%d",
        len(intents),
        extra={"bucket": "PLAN"},
    )


    # Optional: write EffectiveRunSet for debugging
    if not args.no_write:
        rows = []
        for i in intents:
            rows.append({
                "run_id": i.run_id,                 # if your intents already carry it
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
            })
        log_plan.info(
            "plan.write_effective_runset rows=%d sheet=%s",
            len(rows), EFFECTIVE_RUNSET_SHEET,
            extra={"bucket": "SHEET_WRITE"},
        )
        write_tab_overwrite(sh, EFFECTIVE_RUNSET_SHEET, rows)

    if args.policy_only:
        log.info(
            "runner.exit policy_only intents=%d",
            len(intents),
            extra={"bucket": "RUN_END"},
        )
        return
    


    # Load plugins
    plugins = load_plugins_from_folder("src/repo_health/plugins")
    if not plugins:
        log.warning("no plugins loaded", extra={"bucket": "PLUGINS_NONE"})
    else:
        # log.info("plugins.loaded count=%d", len(plugins), extra={"bucket": "PLUGINS"})
            # logger.info("plugins.loaded count=%d names=%s", len(plugins), ",".join(sorted(plugins.keys())))

        log.info(
            "plugins.loaded count=%d names=%s",
            len(plugins),
            ",".join(sorted(plugins.keys())),
            extra={"bucket": "PLUGINS"},
        )



    # CLI filters
    subset_pids = None
    if args.rows:
        subset_pids = subset_project_ids_from_rows(projects, args.rows)
        log.info("cli.filter rows=%s resolved_pids=%d", args.rows, len(subset_pids), extra={"bucket": "FILTER"})
    elif args.subset:
        subset_pids = [p.strip() for p in args.subset.split(",") if p.strip()]
        log.info("cli.filter subset_pids=%d", len(subset_pids), extra={"bucket": "FILTER"})

    subset_plugins = None
    if args.plugins:
        subset_plugins = [p.strip() for p in args.plugins.split(",") if p.strip()]
        log.info("cli.filter subset_plugins=%s", ",".join(subset_plugins), extra={"bucket": "FILTER"})

    run_intents = filter_intents(intents, subset_pids=subset_pids, subset_plugins=subset_plugins)
    log.info(
        "execute.start intents=%d dry_run=%s write=%s",
        len(run_intents), dry_run, (not args.no_write),
        extra={"bucket": "EXEC_START"},
    )

    results_rows = []
    project_summary: Dict[str, Tuple[str, str]] = {}  # pid -> (last_agg_status, last_agg_bucket)
    sev_rank = {"system_error": 3, "actionable_failure": 2, "warning": 1, "ok": 0, "ineligible": 0}

    for intent in run_intents:
        pid = intent.project_id
        plugin_name = intent.plugin
        ctx = projects_by_id.get(pid, {"project_id": pid})

        # Per-intent start log
        log_exec.info(
            "intent.start scheduled=%s due=%s prereq_ok=%s",
            intent.scheduled, intent.due, intent.prereq_ok,
            extra={"project_id": pid, "plugin": plugin_name, "bucket": "INTENT_START"},
        )

        # Execute intent (best-effort)
        try:
            res = execute_intent(intent, ctx, plugins, dry_run=dry_run)
        except Exception as e:
            # If execute_intent itself can throw, capture and normalize here
            log_exec.exception(
                "intent.exception",
                extra={"project_id": pid, "plugin": plugin_name, "bucket": f"EXCEPTION:{type(e).__name__}"},
            )
            # Minimal normalized result row fallback
            res = {
                "run_id": getattr(intent, "run_id", run_id),
                "run_date": getattr(intent, "run_date", args.date),
                "project_id": pid,
                "plugin": plugin_name,
                "executed": False,
                "raw_outcome": "fail",
                "normalized_class": "system_error",
                "bucket": f"EXCEPTION:{type(e).__name__}",
                "short_diag": f"execute_intent raised {type(e).__name__}",
            }

        results_rows.append(res)

        # Per-intent end log
        log_exec.info(
            "intent.done class=%s bucket=%s executed=%s",
            res.get("normalized_class"), res.get("bucket"), res.get("executed"),
            extra={"project_id": pid, "plugin": plugin_name, "bucket": "INTENT_DONE"},
        )

        # Minimal per-project summary
        new_status = res.get("normalized_class", "ok")
        new_bucket = res.get("bucket", "-")
        cur = project_summary.get(pid)
        if cur is None:
            project_summary[pid] = (new_status, new_bucket)
        else:
            cur_status, cur_bucket = cur
            if sev_rank.get(new_status, 0) > sev_rank.get(cur_status, 0):
                project_summary[pid] = (new_status, new_bucket)

    # Append results
    if results_rows:
        log.info(
            "execute.write_results rows=%d sheet=%s",
            len(results_rows), PLUGIN_RESULTS_SHEET,
            extra={"bucket": "SHEET_APPEND"},
        )
        append_rows(sh, PLUGIN_RESULTS_SHEET, results_rows)

        export_info = export_frontier_latest(results_rows, run_date=args.date)
        # run_date = getattr(intent, "run_date", args.date)
        logger.info("Wrote frontier csv: %s", export_info)

    # Optional: projects write-back (you said you might omit this, so gate it cleanly)
    if (not args.no_write) and (not getattr(args, "no_sync_back", False)):
        ts = Date.fromisoformat(args.date).strftime("%m/%d/%Y")
        runner_id = "runner_v1"

        updates = []
        for pid, (st, bucket) in project_summary.items():
            updates.append({
                "project_id": pid,
                "last_update_ts": ts,
                "last_update_by": runner_id,
                "last_agg_status": st,
                "last_agg_bucket": bucket,
            })

        log.info(
            "sync_back.start projects=%d sheet=%s",
            # len(updates), PROJECTS_SHEET,
            len(updates), RUNTIME_HEALTH_SHEET,
            extra={"bucket": "SYNC_BACK"},
        )
        try:
            # batch_update_cells_by_col(sh, PROJECTS_SHEET, updates, key_col="project_id", cols=SUMMARY_COLS)
            ensure_header_has_columns(sh, RUNTIME_HEALTH_SHEET, ["project_id"] + SUMMARY_COLS)
        except Exception as e:
            log.exception(
                "sync_back.failed",
                extra={"bucket": f"SYNC_BACK_ERROR:{type(e).__name__}"},
            )
        else:
            log.info("sync_back.done", extra={"bucket": "SYNC_BACK"})

    elapsed = time.time() - t0
    log.info(
        "runner.end elapsed_s=%.2f intents=%d results=%d",
        elapsed, len(intents), len(results_rows),
        extra={"bucket": "RUN_END"},
    )


if __name__ == "__main__":
    main(sys.argv[1:])
