from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from office_runtime.editorial.publisher.config import PublisherConfig
from office_runtime.editorial.publisher.manual_intake import GoogleManualSheet
from office_runtime.editorial.publisher.pilot import PilotPolicy, PilotPublisher
from office_runtime.editorial.staging.sheets import GoogleSheetsGateway


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded Editorial X publisher")
    parser.add_argument("--profile", default="dev", choices=("dev", "argentina_econ"))
    parser.add_argument("--candidate-id", required=True, help="one explicitly authorized pilot candidate")
    parser.add_argument("--apply", action="store_true", help="perform the one authorized X mutation")
    parser.add_argument("--allow-manual-seed", action="store_true", help="allow explicitly marked manual seed rows")
    parser.add_argument("--artifacts-dir", type=Path, default=Path("artifacts/editorial/publisher"))
    parser.add_argument("--pilot-mode", action="store_true", help="bounded argentina_econ pilot exception")
    parser.add_argument("--pilot-candidate-ids", help="comma-separated exact pilot allowlist")
    parser.add_argument("--pilot-window-start", help="UTC ISO-8601 pilot start")
    parser.add_argument("--pilot-window-end", help="UTC ISO-8601 pilot end")
    args = parser.parse_args()
    if args.apply and not args.candidate_id:
        parser.error("--apply requires an explicit --candidate-id")
    config = PublisherConfig.from_profile(args.profile)
    pilot = None
    if args.pilot_mode:
        if not all((args.pilot_candidate_ids, args.pilot_window_start, args.pilot_window_end)):
            parser.error("pilot mode requires --pilot-candidate-ids, --pilot-window-start, and --pilot-window-end")

        def parse_utc(value: str) -> datetime:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parser.error("pilot timestamps must include UTC timezone")
            return parsed.astimezone(timezone.utc)

        pilot = PilotPolicy(
            candidate_ids=frozenset(item.strip() for item in args.pilot_candidate_ids.split(",") if item.strip()),
            window_start=parse_utc(args.pilot_window_start),
            window_end=parse_utc(args.pilot_window_end),
        )
    sheet_id = os.environ.get(config.sheet_id_env)
    if not sheet_id:
        parser.error(f"{config.sheet_id_env} must be set for profile {args.profile}")
    gateway = GoogleSheetsGateway.from_environment(spreadsheet_id=sheet_id)
    result = PilotPublisher(
        gateway,
        config=config,
        drafts_sheet=GoogleManualSheet(gateway) if args.profile == "argentina_econ" else None,
        artifacts_dir=args.artifacts_dir if args.profile == "dev" else args.artifacts_dir / config.receipt_namespace,
    ).run(
        args.candidate_id, apply=args.apply, allow_manual_seed=args.allow_manual_seed, pilot=pilot
    )
    print(result.as_dict())
    return 0 if result.state in {"DRY_RUN", "PUBLISHED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
