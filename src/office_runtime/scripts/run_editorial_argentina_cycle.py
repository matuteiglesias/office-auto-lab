"""One bounded, account-isolated Editorial Argentina Econ GitHub Actions cycle.

The scheduler may be delayed or duplicated. One invocation selects at most one
eligible due row and never performs catch-up. Cloud credentials are managed by
editorial_econ_oauth_store.py, not this entrypoint.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence

from office_runtime.editorial.publisher.config import PublisherConfig
from office_runtime.editorial.publisher.manual_intake import GoogleManualSheet, project_manual_drafts
from office_runtime.editorial.publisher.pilot import PilotPublisher
from office_runtime.editorial.publisher.xurl_adapter import XurlAdapter, XIdentity
from office_runtime.editorial.staging.sheets import GoogleSheetsGateway, QUEUE_HEADERS, CANDIDATES_HEADERS

PROFILE = "argentina_econ"
EXPECTED_SHEET_ID = "1LAVlYY3T7POA3IUydn3zy2MQBrxc-3c1w-iUq7oFtgo"
MAX_LATENESS = timedelta(minutes=75)


class CycleBlocked(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_utc(value: str, *, field: str) -> datetime:
    if not value:
        raise CycleBlocked(f"{field} is empty")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CycleBlocked(f"{field} is not ISO8601") from exc
    if parsed.tzinfo is None:
        raise CycleBlocked(f"{field} lacks UTC offset")
    return parsed.astimezone(timezone.utc)


def _records(raw: list[list[str]], headers: Sequence[str], *, label: str) -> list[dict[str, str]]:
    if not raw or tuple(raw[0]) != tuple(headers):
        raise CycleBlocked(f"{label} headers differ from publisher contract")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for values in raw[1:]:
        row = list(values[:len(headers)]) + [""] * max(0, len(headers) - len(values))
        if not any(row):
            continue
        record = dict(zip(headers, row))
        key = record[headers[0]]
        if not key or key in seen:
            raise CycleBlocked(f"{label} contains duplicate/missing identity")
        seen.add(key)
        result.append(record)
    return result


def _assert_account(x: XurlAdapter, config: PublisherConfig) -> XIdentity:
    actual = x.whoami()
    if actual.username.casefold() != config.expected_username.casefold() or actual.user_id != config.expected_user_id:
        raise CycleBlocked("X account mismatch; refuse all X and Sheet publication mutations")
    return actual


def _recent_account_publication(x: XurlAdapter, config: PublisherConfig, now: datetime) -> bool:
    # Conservative: any recent public X post by the authenticated account
    # counts, including posts authored outside this automation.
    posts = x.recent_posts(config.expected_username, 100)
    for post in posts:
        if not post.created_at:
            raise CycleBlocked("X recent post has no created_at; cannot establish account cadence")
        if _parse_utc(post.created_at, field="X.created_at") > now - timedelta(hours=config.min_post_gap_hours):
            return True
    return False


def select_candidate(
    candidates: list[dict[str, str]],
    queue: list[dict[str, str]],
    *,
    now: datetime,
    min_gap: timedelta = timedelta(hours=24),
    max_lateness: timedelta = MAX_LATENESS,
) -> tuple[str | None, str]:
    by_id = {item["candidate_id"]: item for item in candidates}
    if set(item["candidate_id"] for item in queue) - set(by_id):
        raise CycleBlocked("orphan QUEUE candidate")
    publishing = [item for item in queue if item["publisher_status"] == "PUBLISHING"]
    if len(publishing) > 1:
        raise CycleBlocked("multiple unresolved PUBLISHING rows")
    if publishing:
        return publishing[0]["candidate_id"], "reconcile"

    # This is account-wide, unlike legacy per-candidate receipt lookup.
    for item in queue:
        if item["publisher_status"] == "PUBLISHED":
            published_at = _parse_utc(item["updated_at"], field="QUEUE.published_at")
            if now - min_gap < published_at <= now:
                return None, "account cadence gate (Sheet history)"
    eligible: list[tuple[datetime, str]] = []
    for item in queue:
        candidate = by_id.get(item["candidate_id"])
        if candidate is None:
            continue
        if item["decision"] != "APPROVE" or item["target_surface"] != "X":
            continue
        if item["publisher_status"] or item["published_ref"]:
            continue
        if candidate["machine_disposition"] != "stage" or candidate["risk_class"] != "low":
            continue
        scheduled = item["scheduled_for"]
        if not scheduled:
            # Unscheduled drafts cannot trigger arbitrary publication.
            continue
        due = _parse_utc(scheduled, field="QUEUE.scheduled_for")
        if due <= now and now - due <= max_lateness:
            expires = candidate["expires_at"]
            if not expires or _parse_utc(expires, field="CANDIDATES.expires_at") > now:
                eligible.append((due, item["candidate_id"]))
    if not eligible:
        return None, "no approved due post within the non-catchup window"
    eligible.sort()
    return eligible[0][1], "publish"


def main() -> int:
    parser = argparse.ArgumentParser(description="One safe economics-account publishing cycle")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="no Sheet or X mutation")
    mode.add_argument("--apply", action="store_true", help="one authorized due X mutation")
    parser.add_argument("--verify-identity", action="store_true", help="read-only whoami even if no post is due")
    args = parser.parse_args()

    try:
        config = PublisherConfig.from_profile(PROFILE)
        if (config.profile_id, config.account_key, config.expected_user_id, config.xurl_app, config.xurl_auth) != (
            PROFILE, "x_argentina_econ", "57242581", "argentina-econ-editorial", "oauth1"
        ):
            raise CycleBlocked("unexpected economics publisher profile")
        sheet_id = os.environ.get(config.sheet_id_env, "")
        if sheet_id != EXPECTED_SHEET_ID:
            raise CycleBlocked("economics workbook mismatch")
        if args.apply:
            if os.environ.get("EDITORIAL_ECON_RUNTIME_PROMOTED") != "true":
                raise CycleBlocked("cloud economics cycle has not passed local promotion gates")
            if os.environ.get(config.kill_switch_env) != "0":
                raise CycleBlocked("economics publication kill switch is active")
        gateway = GoogleSheetsGateway.from_environment(spreadsheet_id=sheet_id)
        draft_sheet = GoogleManualSheet(gateway)
        x = XurlAdapter(app=config.xurl_app, auth=config.xurl_auth)
        if args.verify_identity:
            _assert_account(x, config)

        if args.apply:
            intake = project_manual_drafts(draft_sheet)
            if intake.blocked:
                raise CycleBlocked("manual intake reported blocked rows; inspect DRAFTS before publishing")
        candidates = _records(draft_sheet.read_rows("CANDIDATES"), CANDIDATES_HEADERS, label="CANDIDATES")
        queue = _records(draft_sheet.read_rows("QUEUE"), QUEUE_HEADERS, label="QUEUE")
        now = _now()
        candidate_id, mode = select_candidate(
            candidates, queue, now=now, min_gap=timedelta(hours=config.min_post_gap_hours)
        )
        if candidate_id is None:
            print(json.dumps({"state": "SKIP", "reason": mode, "profile": PROFILE}))
            return 0
        # Save paid X identity reads on the usual empty/no-due polls.
        # Bind identity before any publication or reconciliation attempt.
        _assert_account(x, config)
        if mode == "reconcile":
            if args.dry_run:
                print(json.dumps({"state": "HOLD", "reason": "unresolved PUBLISHING requires apply-mode reconciliation"}))
                return 0
        elif _recent_account_publication(x, config, now):
            print(json.dumps({"state": "SKIP", "reason": "account cadence gate (X history)", "profile": PROFILE}))
            return 0

        if args.dry_run:
            print(json.dumps({"state": "DRY_RUN", "candidate_id": candidate_id, "mode": mode, "profile": PROFILE}))
            return 0

        # The publisher still owns duplicate, identity, X readback, and Sheet writeback gates.
        # No temporary high-frequency pilot policy is passed in cloud operation.
        publisher = PilotPublisher(gateway, config=config, x=x, drafts_sheet=draft_sheet)
        result = publisher.run(candidate_id, apply=True)
        print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
        if result.state == "PUBLISHED":
            return 0
        raise CycleBlocked("publisher did not reconcile/publish the selected candidate")
    except Exception as exc:
        # Do not log credentials or source texts from exceptions.
        print(json.dumps({"state": "BLOCKED", "error_class": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
