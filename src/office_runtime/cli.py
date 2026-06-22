from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")



def _log_compile_manifest(manifest: dict) -> None:
    from office_runtime.ledger import append_ledger

    counts = manifest.get("row_counts", {}) or {}
    metrics = {
        "merged": counts.get("merged"),
        "expressed": counts.get("expressed_state"),
        "focus": counts.get("focus_get_queue"),
        "support": counts.get("support_queue"),
        "warnings": len(manifest.get("warnings", [])),
    }
    append_ledger("office.compile", "ok", run_id=manifest.get("run_id"), metrics=metrics)


def _log_staff_bundles(result: dict, run_id: str | None = None) -> None:
    from office_runtime.ledger import append_ledger

    append_ledger(
        "staff.bundles",
        "ok",
        run_id=run_id,
        metrics={"bundles": result.get("bundles_built"), "scan_mode": result.get("scan_mode")},
    )


def _log_staff_briefs(result: dict, run_id: str | None = None) -> None:
    from office_runtime.ledger import append_ledger

    append_ledger("staff.briefs", "ok", run_id=run_id, metrics={"briefs": result.get("briefs_built")})


def _log_evidence_git(summary: dict) -> None:
    from office_runtime.ledger import append_ledger

    append_ledger(
        "evidence.git",
        "ok",
        metrics={
            "repos": summary.get("repos_found"),
            "commits": summary.get("commits"),
            "errors": summary.get("errors"),
            "rows": summary.get("rows_written"),
        },
        artifacts={"out": str(summary.get("out"))},
    )


def _log_evidence_files(summary: dict) -> None:
    from office_runtime.ledger import append_ledger

    append_ledger(
        "evidence.files",
        "ok",
        metrics={
            "files": summary.get("rows_written"),
            "max_depth": summary.get("max_depth"),
            "errors": summary.get("errors"),
        },
        artifacts={"out": str(summary.get("out"))},
    )

def _cmd_daily(args: argparse.Namespace) -> int:
    from office_runtime.office.config import load_config
    from office_runtime.office.compile import run_compile
    from office_runtime.staff.bundles import build_bundles
    from office_runtime.staff.briefs import build_staff_briefs

    cfg = load_config()
    manifest = run_compile(cfg)
    if manifest.get("status") == "ok":
        _log_compile_manifest(manifest)
        manifest["bundle_build"] = build_bundles(cfg, scan_mode=args.scan_mode)
        manifest["bundle_build"]["scan_mode"] = args.scan_mode
        _log_staff_bundles(manifest["bundle_build"], run_id=manifest.get("run_id"))
        manifest["brief_build"] = build_staff_briefs(cfg.latest_dir)
        _log_staff_briefs(manifest["brief_build"], run_id=manifest.get("run_id"))
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest.get("status") == "ok" else 1


def _cmd_office_compile(_: argparse.Namespace) -> int:
    from office_runtime.office.config import load_config
    from office_runtime.office.compile import run_compile

    cfg = load_config()
    manifest = run_compile(cfg)
    if manifest.get("status") == "ok":
        _log_compile_manifest(manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest.get("status") == "ok" else 1


def _cmd_staff_bundles(args: argparse.Namespace) -> int:
    from office_runtime.office.config import load_config
    from office_runtime.staff.bundles import build_bundles

    cfg = load_config()
    result = build_bundles(cfg, scan_mode=args.scan_mode)
    result["scan_mode"] = args.scan_mode
    _log_staff_bundles(result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_staff_briefs(_: argparse.Namespace) -> int:
    from office_runtime.office.config import load_config
    from office_runtime.staff.briefs import build_staff_briefs

    cfg = load_config()
    result = build_staff_briefs(cfg.latest_dir)
    _log_staff_briefs(result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_ops_repo_health_policy(args: argparse.Namespace) -> int:
    from office_runtime.ops.repo_health import runner as repo_health_runner

    repo_health_runner.main(["--policy-only", *args.repo_health_args])
    return 0


def _cmd_ops_repo_health_run(args: argparse.Namespace) -> int:
    from office_runtime.ops.repo_health import runner as repo_health_runner

    repo_health_runner.main(args.repo_health_args)
    return 0


def _cmd_evidence_git(args: argparse.Namespace) -> int:
    from office_runtime.evidence import git_trace
    from office_runtime.run_logging import RunLogger

    run_id = _new_run_id()
    logger = RunLogger("evidence.git", run_id)
    logger.event("run.start", status="ok", start=args.start, end=args.end)
    logger.event("roots.scan", status="ok", roots=[str(x) for x in args.roots], max_depth=args.max_depth)

    repos = git_trace.discover_repos(args.roots, max_depth=args.max_depth)
    logger.event("repos.discovered", status="ok", repos_found=len(repos))
    rows = git_trace.iter_commit_rows(
        repos,
        start=args.start,
        end=args.end,
        limit_per_repo=args.limit_per_repo,
    )
    rows_list = list(rows)
    n = git_trace.write_jsonl(args.out, rows_list)
    summary = {
        "status": "ok",
        "repos_found": len(repos),
        "rows_written": n,
        "commits": sum(1 for r in rows_list if r.get("kind") == "git_commit"),
        "errors": sum(1 for r in rows_list if str(r.get("kind", "")).endswith("_error")),
        "out": str(args.out),
    }
    logger.event("commits.trace", status="ok", rows_written=n, commits=summary["commits"], errors=summary["errors"], out=str(args.out))
    logger.event("run.end", status="ok")
    _log_evidence_git(summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _cmd_evidence_files(args: argparse.Namespace) -> int:
    from office_runtime.evidence import fs_trace
    from office_runtime.run_logging import RunLogger

    run_id = _new_run_id()
    logger = RunLogger("evidence.files", run_id)
    logger.event("run.start", status="ok", start=args.start, end=args.end)
    logger.event("roots.scan", status="ok", roots=[str(x) for x in args.roots], max_depth=args.max_depth)

    rows = fs_trace.iter_file_events(
        args.roots,
        start=fs_trace._parse_start(args.start),
        end_exclusive=fs_trace._parse_end_exclusive(args.end),
        max_depth=args.max_depth,
        include_hidden=args.include_hidden,
        limit=args.limit,
    )
    rows_list = list(rows)
    n = fs_trace.write_jsonl(args.out, rows_list)
    summary = {
        "status": "ok",
        "rows_written": n,
        "max_depth": args.max_depth,
        "errors": sum(1 for r in rows_list if str(r.get("kind", "")).endswith("_error")),
        "out": str(args.out),
    }
    logger.event("files.trace", status="ok", rows_written=n, errors=summary["errors"], out=str(args.out))
    logger.event("run.end", status="ok")
    _log_evidence_files(summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0



def _cmd_capture_lifecycle(args: argparse.Namespace) -> int:
    from office_runtime.capture.lifecycle import compile_and_write
    from office_runtime.office.config import load_config

    cfg = load_config()
    root = Path(os.environ.get("OFFICE_ROOT", ".")).resolve()
    inbox_root = args.inbox_root or (root / "inbox")
    out_dir = args.out or cfg.latest_dir
    result = compile_and_write(inbox_root, out_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="office_runtime.cli")
    subparsers = parser.add_subparsers(dest="command")

    daily = subparsers.add_parser("daily", help="Run office compile + staff bundles + staff briefs.")
    daily.add_argument("--scan-mode", choices=["none", "existing", "refresh"], default="existing")
    daily.set_defaults(handler=_cmd_daily)

    office = subparsers.add_parser("office", help="Office surfaces.")
    office_sub = office.add_subparsers(dest="office_cmd", required=True)
    office_sub.add_parser("compile", help="Run office compile only.").set_defaults(handler=_cmd_office_compile)

    staff = subparsers.add_parser("staff", help="Staff surfaces.")
    staff_sub = staff.add_subparsers(dest="staff_cmd", required=True)
    staff_bundles = staff_sub.add_parser("bundles", help="Build staff bundles only.")
    staff_bundles.add_argument("--scan-mode", choices=["none", "existing", "refresh"], default="refresh")
    staff_bundles.set_defaults(handler=_cmd_staff_bundles)
    staff_sub.add_parser("briefs", help="Build staff briefs only.").set_defaults(handler=_cmd_staff_briefs)

    ops = subparsers.add_parser("ops", help="Ops surfaces.")
    ops_sub = ops.add_subparsers(dest="ops_cmd", required=True)
    repo_health = ops_sub.add_parser("repo-health", help="Repo health surfaces.")
    repo_health_sub = repo_health.add_subparsers(dest="repo_health_cmd", required=True)
    repo_health_sub.add_parser("policy", help="Run repo-health in policy-only mode.").add_argument(
        "repo_health_args", nargs=argparse.REMAINDER, help="Arguments passed through to repo-health runner."
    )
    repo_health_sub.choices["policy"].set_defaults(handler=_cmd_ops_repo_health_policy)
    repo_health_sub.add_parser("run", help="Run repo-health normally.").add_argument(
        "repo_health_args", nargs=argparse.REMAINDER, help="Arguments passed through to repo-health runner."
    )
    repo_health_sub.choices["run"].set_defaults(handler=_cmd_ops_repo_health_run)

    capture = subparsers.add_parser("capture", help="Capture processing surfaces.")
    capture_sub = capture.add_subparsers(dest="capture_cmd", required=True)
    cap_lifecycle = capture_sub.add_parser("lifecycle", help="Compile non-mutating capture lifecycle artifacts.")
    cap_lifecycle.add_argument("--inbox-root", type=Path, default=None, help="Inbox root containing human_feedback and capture_processing JSONL streams.")
    cap_lifecycle.add_argument("--out", type=Path, default=None, help="Output directory for capture_lifecycle artifacts. Defaults to OFFICE_OUT_ROOT/latest.")
    cap_lifecycle.set_defaults(handler=_cmd_capture_lifecycle)

    evidence = subparsers.add_parser("evidence", help="Evidence surfaces.")
    evidence_sub = evidence.add_subparsers(dest="evidence_cmd", required=True)
    ev_git = evidence_sub.add_parser("git", help="Trace git commits across repositories.")
    ev_git.add_argument("--roots", nargs="+", required=True, type=Path)
    ev_git.add_argument("--start", required=True)
    ev_git.add_argument("--end", required=True)
    ev_git.add_argument("--out", required=True, type=Path)
    ev_git.add_argument("--max-depth", type=int, default=4)
    ev_git.add_argument("--limit-per-repo", type=int, default=None)
    ev_git.set_defaults(handler=_cmd_evidence_git)

    ev_files = evidence_sub.add_parser("files", help="Trace filesystem modifications.")
    ev_files.add_argument("--roots", nargs="+", required=True, type=Path)
    ev_files.add_argument("--start", required=True)
    ev_files.add_argument("--end", required=True)
    ev_files.add_argument("--out", required=True, type=Path)
    ev_files.add_argument("--max-depth", type=int, default=8)
    ev_files.add_argument("--include-hidden", action="store_true")
    ev_files.add_argument("--limit", type=int, default=None)
    ev_files.set_defaults(handler=_cmd_evidence_files)

    parser.set_defaults(handler=_cmd_daily)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
