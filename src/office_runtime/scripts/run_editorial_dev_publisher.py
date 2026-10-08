from __future__ import annotations

import argparse
import os
from pathlib import Path

from office_runtime.editorial.publisher.config import PublisherConfig
from office_runtime.editorial.publisher.manual_intake import GoogleManualSheet
from office_runtime.editorial.publisher.pilot import PilotPublisher
from office_runtime.editorial.staging.sheets import GoogleSheetsGateway


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded Editorial X publisher")
    parser.add_argument("--profile", default="dev", choices=("dev", "argentina_econ"))
    parser.add_argument("--candidate-id", required=True, help="one explicitly authorized pilot candidate")
    parser.add_argument("--apply", action="store_true", help="perform the one authorized X mutation")
    parser.add_argument("--allow-manual-seed", action="store_true", help="allow explicitly marked manual seed rows")
    parser.add_argument("--artifacts-dir", type=Path, default=Path("artifacts/editorial/publisher"))
    args = parser.parse_args()
    if args.apply and not args.candidate_id:
        parser.error("--apply requires an explicit --candidate-id")
    config = PublisherConfig.from_profile(args.profile)
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
        args.candidate_id, apply=args.apply, allow_manual_seed=args.allow_manual_seed
    )
    print(result.as_dict())
    return 0 if result.state in {"DRY_RUN", "PUBLISHED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
