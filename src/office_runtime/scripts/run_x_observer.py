"""Explicit read-only O1 qualification; offline by default. No persistent mutation."""
from __future__ import annotations

import argparse
import json
import os
import sys

from office_runtime.x_observer.client import ReadOnlyXClient
from office_runtime.x_observer.contracts import ObserverContractError
from office_runtime.x_observer.qualification import qualify


def main() -> int:
    parser = argparse.ArgumentParser(description="X Observer Phase A — read-only qualification")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="offline capability report; no X requests")
    mode.add_argument("--qualify-live", action="store_true", help="bounded GET-only X identity/timeline probe")
    parser.add_argument("--handle", default="JMilei")
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--max-usd", type=float, default=0.25)
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps({
            "state": "DRY_RUN", "network_used": False, "x_mutation": False,
            "sheets_mutation": False, "account_enabled": False,
            "source": "docs/spec/x-observer-v0/PHASE_A_FREEZE.md",
        }, sort_keys=True))
        return 0
    token = os.environ.get("X_OBSERVER_BEARER_TOKEN", "")
    if not token:
        print(json.dumps({"state": "BLOCKED", "reason": "OBSERVER_BEARER_TOKEN_MISSING"}))
        return 2
    try:
        report = qualify(
            ReadOnlyXClient(token), handle=args.handle,
            max_pages=args.max_pages, max_results=args.max_results,
            max_usd=args.max_usd,
        )
    except Exception as exc:
        # Never print raw provider responses or bearer tokens.
        if isinstance(exc, ObserverContractError):
            reason = "PROVIDER_CONTRACT_OR_IDENTITY_UNVERIFIED"
        else:
            reason = type(exc).__name__
        print(json.dumps({"state": "BLOCKED", "reason": reason}))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["qualification_status"] in {
        "BOUNDED_READ_COMPLETE", "MAX_PAGES_STOP", "BUDGET_STOP",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
