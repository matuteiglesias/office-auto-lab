"""Unattended, one-post-per-day ModernAIDev publisher.

The existing Sheet holds publication authority. No candidate is approved here.
An explicit APPLY plus two repo gates and the profile kill switch are required
for an X mutation. X account identity and recent history are verified on each run.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import timedelta, datetime, timezone

from office_runtime.editorial.publisher.config import PublisherConfig
from office_runtime.editorial.publisher.pilot import PilotPublisher
from office_runtime.editorial.publisher.xurl_adapter import XurlAdapter
from office_runtime.editorial.staging.sheets import GoogleSheetsGateway, CANDIDATES_HEADERS, QUEUE_HEADERS
from office_runtime.scripts.run_editorial_argentina_cycle import (
    CycleBlocked, _assert_account, _records, _recent_account_publication, select_candidate,
)

PROFILE = "dev"
EXPECTED_ID = "1927563136636243968"
# Several-hour GitHub schedule delays are observed. No indefinite backlog catch-up.
DEV_MAX_LATENESS = timedelta(hours=12)
DEV_CADENCE = timedelta(hours=24)


def main() -> int:
    parser = argparse.ArgumentParser(description="One bounded ModernAIDev Sheet-to-X cycle")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        config = PublisherConfig.from_profile(PROFILE)
        if (config.expected_username.lower(), config.expected_user_id, config.xurl_app, config.xurl_auth) != (
            "modernaidev", EXPECTED_ID, "modernai-editorial", "oauth1"
        ):
            raise CycleBlocked("ModernAIDev binding mismatch")
        sheet_id = os.environ.get(config.sheet_id_env, "")
        if not sheet_id:
            raise CycleBlocked("missing developer workbook binding")
        if args.apply and (
            os.environ.get("EDITORIAL_DEV_RUNTIME_PROMOTED") != "true"
            or os.environ.get("EDITORIAL_DEV_PUBLISH_ENABLED") != "true"
            or os.environ.get(config.kill_switch_env) != "0"
        ):
            raise CycleBlocked("developer publication is not promoted or is disabled")

        gateway = GoogleSheetsGateway.from_environment(spreadsheet_id=sheet_id)
        x = XurlAdapter(app=config.xurl_app, auth=config.xurl_auth)
        _assert_account(x, config)
        candidates = _records(gateway.read_rows("CANDIDATES"), CANDIDATES_HEADERS, label="CANDIDATES")
        queue = _records(gateway.read_rows("QUEUE"), QUEUE_HEADERS, label="QUEUE")
        now = datetime.now(timezone.utc)
        candidate_id, action = select_candidate(
            candidates, queue, now=now,
            min_gap=DEV_CADENCE, max_lateness=DEV_MAX_LATENESS,
        )
        if not candidate_id:
            print(json.dumps({"state": "NO_ELIGIBLE_CONTENT", "reason": action, "profile": PROFILE}))
            return 0
        if action != "reconcile" and _recent_account_publication(x, config, now, min_gap=DEV_CADENCE):
            print(json.dumps({"state": "CADENCE_HOLD", "reason": "recent X account post", "profile": PROFILE}))
            return 0
        if args.dry_run:
            print(json.dumps({"state": "DRY_RUN", "candidate_id": candidate_id, "action": action}))
            return 0
        publisher = PilotPublisher(gateway, config=config, x=x, artifacts_dir=__import__("pathlib").Path("artifacts/editorial/publisher/dev"))
        result = publisher.run(candidate_id, apply=True, allow_manual_seed=True)
        print(json.dumps(result.as_dict(), sort_keys=True))
        return 0 if result.state == "PUBLISHED" else 2
    except Exception as exc:
        # Do not log raw X or Sheet responses or credentials.
        print(json.dumps({"state": "FAILED", "error_class": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
