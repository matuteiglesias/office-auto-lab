from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def _log_estate_movement(summary: dict) -> None:
    from office_runtime.ledger import append_ledger

    append_ledger(
        "estate.movement",
        "ok" if summary.get("status") == "ok" else "error",
        metrics={
            "repos": summary.get("repositories_observed"),
            "evidence": summary.get("evidence_count"),
            "delta": summary.get("new_evidence_count"),
        },
        artifacts={"digest": str(summary.get("digest")), "manifest": str(summary.get("manifest"))},
    )


def _cmd_evidence_git(args: argparse.Namespace) -> int:
    from office_runtime.evidence import git_trace
    from office_runtime.run_logging import RunLogger

    run_id = _new_run_id()
    logger = RunLogger("evidence.git", run_id)
    logger.event("run.start", status="ok", start=args.start, end=args.end)
    logger.event("roots.scan", status="ok", roots=[str(x) for x in args.roots], max_depth=args.max_depth)

    repos = git_trace.discover_repos(args.roots, max_depth=args.max_depth)
    logger.event("repos.discovered", status="ok", repos_found=len(repos))
    rows_list = list(
        git_trace.iter_commit_rows(
            repos,
            start=args.start,
            end=args.end,
            limit_per_repo=args.limit_per_repo,
        )
    )
    n = git_trace.write_jsonl(args.out, rows_list)
    summary = {
        "status": "ok",
        "repos_found": len(repos),
        "rows_written": n,
        "commits": sum(1 for row in rows_list if row.get("kind") == "git_commit"),
        "errors": sum(1 for row in rows_list if str(row.get("kind", "")).endswith("_error")),
        "out": str(args.out),
    }
    logger.event(
        "commits.trace",
        status="ok",
        rows_written=n,
        commits=summary["commits"],
        errors=summary["errors"],
        out=str(args.out),
    )
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

    rows_list = list(
        fs_trace.iter_file_events(
            args.roots,
            start=fs_trace._parse_start(args.start),
            end_exclusive=fs_trace._parse_end_exclusive(args.end),
            max_depth=args.max_depth,
            include_hidden=args.include_hidden,
            limit=args.limit,
        )
    )
    n = fs_trace.write_jsonl(args.out, rows_list)
    summary = {
        "status": "ok",
        "rows_written": n,
        "max_depth": args.max_depth,
        "errors": sum(1 for row in rows_list if str(row.get("kind", "")).endswith("_error")),
        "out": str(args.out),
    }
    logger.event("files.trace", status="ok", rows_written=n, errors=summary["errors"], out=str(args.out))
    logger.event("run.end", status="ok")
    _log_evidence_files(summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _cmd_estate_movement(args: argparse.Namespace) -> int:
    from office_runtime.estate_movement import produce
    from office_runtime.run_logging import RunLogger

    run_id = _new_run_id()
    logger = RunLogger("estate.movement", run_id)
    logger.event("run.start", status="ok", digest_id=args.digest_id, start=args.start, end=args.end)
    logger.event("roots.scan", status="ok", roots=[root.name for root in args.roots], max_depth=args.max_depth)
    result = produce(
        digest_id=args.digest_id,
        roots=args.roots,
        start=args.start,
        end=args.end,
        out_root=args.out_root,
        previous_manifest=args.previous_manifest,
        control_plane=args.control_plane,
        max_depth=args.max_depth,
    )
    logger.event(
        "digest.written",
        status=result.get("status"),
        digest=result.get("digest"),
        manifest=result.get("manifest"),
        evidence=result.get("evidence_count"),
        delta=result.get("new_evidence_count"),
    )
    logger.event("run.end", status=result.get("status"))
    _log_estate_movement(result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


def _capture_root(args: argparse.Namespace) -> Path:
    root = Path(os.environ.get("OFFICE_ROOT", ".")).resolve()
    return args.inbox_root or (root / "inbox")


def _cmd_capture_transcribe(args: argparse.Namespace) -> int:
    from office_runtime.capture.transcription import transcribe_event

    result = transcribe_event(
        _capture_root(args),
        args.event_id,
        model=args.model,
        force=args.force,
        dry_run=args.dry_run,
        audio_root=args.audio_root,
        max_bytes=args.max_bytes,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


def _cmd_capture_transcribe_pending(args: argparse.Namespace) -> int:
    from office_runtime.capture.transcription import transcribe_pending

    result = transcribe_pending(
        _capture_root(args),
        limit=args.limit,
        model=args.model,
        force=args.force,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


def _cmd_capture_route(args: argparse.Namespace) -> int:
    from office_runtime.capture.processing import route_event

    result = route_event(
        _capture_root(args), args.event_id, model=args.model, force=args.force, dry_run=args.dry_run
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


def _cmd_capture_artifactize(args: argparse.Namespace) -> int:
    from office_runtime.capture.processing import artifactize_event

    result = artifactize_event(
        _capture_root(args), args.event_id, model=args.model, force=args.force, dry_run=args.dry_run
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


def _cmd_capture_propose_reingest(args: argparse.Namespace) -> int:
    from office_runtime.capture.processing import propose_reingest_event

    result = propose_reingest_event(
        _capture_root(args), args.event_id, model=args.model, force=args.force, dry_run=args.dry_run
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


def _cmd_capture_process(args: argparse.Namespace) -> int:
    from office_runtime.capture.processing import process_event

    result = process_event(
        _capture_root(args),
        args.event_id,
        transcription_model=args.transcription_model,
        model=args.model,
        force=args.force,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


def _cmd_capture_lifecycle(args: argparse.Namespace) -> int:
    from office_runtime.capture.lifecycle import compile_and_write
    from office_runtime.office.config import load_config

    cfg = load_config()
    out_dir = args.out or cfg.latest_dir
    result = compile_and_write(_capture_root(args), out_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="office_runtime.cli",
        description="Office sidecar CLI. Canonical Office v2 generation is run_generation_v2.py.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="Capture processing surfaces.")
    capture_sub = capture.add_subparsers(dest="capture_cmd", required=True)

    lifecycle = capture_sub.add_parser("lifecycle", help="Compile non-mutating capture lifecycle artifacts.")
    lifecycle.add_argument("--inbox-root", type=Path, default=None)
    lifecycle.add_argument("--out", type=Path, default=None)
    lifecycle.set_defaults(handler=_cmd_capture_lifecycle)

    transcribe = capture_sub.add_parser("transcribe", help="Transcribe one raw capture audio event.")
    transcribe.add_argument("--event-id", required=True)
    transcribe.add_argument("--inbox-root", type=Path, default=None)
    transcribe.add_argument("--model", default=None)
    transcribe.add_argument("--audio-root", type=Path, default=None)
    transcribe.add_argument("--max-bytes", type=int, default=None)
    transcribe.add_argument("--force", action="store_true")
    transcribe.add_argument("--dry-run", action="store_true")
    transcribe.set_defaults(handler=_cmd_capture_transcribe)

    pending = capture_sub.add_parser("transcribe-pending", help="Transcribe pending raw capture audio events.")
    pending.add_argument("--limit", type=int, default=5)
    pending.add_argument("--inbox-root", type=Path, default=None)
    pending.add_argument("--model", default=None)
    pending.add_argument("--force", action="store_true")
    pending.add_argument("--dry-run", action="store_true")
    pending.set_defaults(handler=_cmd_capture_transcribe_pending)

    route = capture_sub.add_parser("route", help="Route one transcribed capture using Structured Outputs.")
    route.add_argument("--event-id", required=True)
    route.add_argument("--inbox-root", type=Path, default=None)
    route.add_argument("--model", default=None)
    route.add_argument("--force", action="store_true")
    route.add_argument("--dry-run", action="store_true")
    route.set_defaults(handler=_cmd_capture_route)

    artifactize = capture_sub.add_parser("artifactize", help="Create one artifact candidate from a routed capture.")
    artifactize.add_argument("--event-id", required=True)
    artifactize.add_argument("--inbox-root", type=Path, default=None)
    artifactize.add_argument("--model", default=None)
    artifactize.add_argument("--force", action="store_true")
    artifactize.add_argument("--dry-run", action="store_true")
    artifactize.set_defaults(handler=_cmd_capture_artifactize)

    reingest = capture_sub.add_parser("propose-reingest", help="Create one pending reingest candidate without applying it.")
    reingest.add_argument("--event-id", required=True)
    reingest.add_argument("--inbox-root", type=Path, default=None)
    reingest.add_argument("--model", default=None)
    reingest.add_argument("--force", action="store_true")
    reingest.add_argument("--dry-run", action="store_true")
    reingest.set_defaults(handler=_cmd_capture_propose_reingest)

    process = capture_sub.add_parser("process", help="Run missing capture processing steps.")
    process.add_argument("--event-id", required=True)
    process.add_argument("--inbox-root", type=Path, default=None)
    process.add_argument("--model", default=None)
    process.add_argument("--transcription-model", default=None)
    process.add_argument("--force", action="store_true")
    process.add_argument("--dry-run", action="store_true")
    process.set_defaults(handler=_cmd_capture_process)

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

    estate = subparsers.add_parser("estate", help="Read-only estate evidence projections.")
    estate_sub = estate.add_subparsers(dest="estate_cmd", required=True)
    movement = estate_sub.add_parser("movement", help="Produce a delta-oriented Estate Movement Digest.")
    movement.add_argument("--digest-id", required=True)
    movement.add_argument("--roots", nargs="+", required=True, type=Path)
    movement.add_argument("--start", required=True)
    movement.add_argument("--end", required=True)
    movement.add_argument("--out-root", type=Path, default=Path("artifacts/estate-movement"))
    movement.add_argument("--previous-manifest", type=Path, default=None)
    movement.add_argument("--control-plane", type=Path, default=None)
    movement.add_argument("--max-depth", type=int, default=4)
    movement.set_defaults(handler=_cmd_estate_movement)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
