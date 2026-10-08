from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from office_runtime.editorial.staging.sheets import (
    CANDIDATES_HEADERS,
    CANDIDATES_TAB,
    QUEUE_HEADERS,
    QUEUE_TAB,
    SheetGateway,
)
from office_runtime.editorial.publisher.config import PublisherConfig
from office_runtime.editorial.publisher.manual_intake import DRAFTS_HEADERS, DRAFTS_SCHEMA, DRAFTS_TAB
from office_runtime.editorial.publisher.xurl_adapter import XIdentity, XPost, XurlAdapter

PUBLISHER_SCHEMA = "office_runtime.editorial.publisher.pilot.v1"
MAX_POST_LENGTH = 280
_DEV_CONFIG = PublisherConfig.from_profile("dev")
EXPECTED_USERNAME = _DEV_CONFIG.expected_username
EXPECTED_USER_ID = _DEV_CONFIG.expected_user_id


class PublisherBlocked(RuntimeError):
    pass


class XTransport(Protocol):
    def whoami(self) -> XIdentity: ...
    def recent_posts(self, username: str, max_results: int = 100) -> list[XPost]: ...
    def create_post(self, text: str) -> XPost: ...
    def read_post(self, post_id: str) -> XPost: ...


@dataclass(frozen=True)
class PublisherResult:
    candidate_id: str
    eligible: bool
    applied: bool
    state: str
    reason: str
    post_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class PilotPolicy:
    candidate_ids: frozenset[str]
    window_start: datetime
    window_end: datetime
    cap: int = 10
    slot_minutes: int = 5

    def validate(self, config: PublisherConfig) -> None:
        if config.profile_id != "argentina_econ":
            raise PublisherBlocked("temporary pilot mode is restricted to argentina_econ")
        if not self.candidate_ids or len(self.candidate_ids) > self.cap:
            raise PublisherBlocked("pilot candidate allowlist must contain 1..cap IDs")
        if self.window_end <= self.window_start:
            raise PublisherBlocked("pilot window must end after it starts")
        if not 1 <= self.slot_minutes <= 60:
            raise PublisherBlocked("pilot slot must be between 1 and 60 minutes")

    def active(self, now: datetime) -> bool:
        return self.window_start <= now < self.window_end


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _rows(tab_rows: list[list[str]], headers: tuple[str, ...]) -> dict[str, dict[str, str]]:
    if not tab_rows or tuple(tab_rows[0]) != headers:
        raise PublisherBlocked(f"{tab_rows!r} has an incompatible {headers[0]} header")
    result: dict[str, dict[str, str]] = {}
    for row in tab_rows[1:]:
        values = list(row[: len(headers)]) + [""] * max(0, len(headers) - len(row))
        record = dict(zip(headers, values))
        if not any(values):
            continue
        key = record[headers[0]]
        if not key or key in result:
            raise PublisherBlocked(f"duplicate or missing {headers[0]} in Sheet")
        result[key] = record
    return result


def _row_numbers(tab_rows: list[list[str]], headers: tuple[str, ...]) -> dict[str, int]:
    return {row[0]: number for number, row in enumerate(tab_rows[1:], start=2) if row and row[0]}


def _replace_field(row: Mapping[str, str], headers: tuple[str, ...], **updates: str) -> list[str]:
    unknown = set(updates) - set(headers)
    if unknown:
        raise PublisherBlocked(f"unknown Sheet fields: {sorted(unknown)}")
    return [updates.get(column, row.get(column, "")) for column in headers]


def _quality(value: str) -> Mapping[str, Any]:
    try:
        decoded = json.loads(value or "{}")
    except json.JSONDecodeError as exc:
        raise PublisherBlocked("quality_summary is not valid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise PublisherBlocked("quality_summary is not an object")
    return decoded


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class PilotPublisher:
    def __init__(
        self,
        gateway: SheetGateway,
        *,
        config: PublisherConfig | None = None,
        x: XTransport | None = None,
        drafts_sheet: Any | None = None,
        artifacts_dir: Path = Path("artifacts/editorial/publisher"),
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self.gateway = gateway
        self.config = config or _DEV_CONFIG
        self.x = x or XurlAdapter(app=self.config.xurl_app, auth=self.config.xurl_auth)
        self.drafts_sheet = drafts_sheet
        self.artifacts_dir = artifacts_dir
        self.clock = clock

    def _snapshot(self) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], dict[str, int]]:
        candidates = _rows(self.gateway.read_rows(CANDIDATES_TAB), CANDIDATES_HEADERS)
        queue_raw = self.gateway.read_rows(QUEUE_TAB)
        queue = _rows(queue_raw, QUEUE_HEADERS)
        return candidates, queue, _row_numbers(queue_raw, QUEUE_HEADERS)

    def _all_receipt_paths(self) -> list[Path]:
        if not self.artifacts_dir.exists():
            return []
        return sorted(path for path in self.artifacts_dir.glob("*.json") if path.is_file())

    def _receipt_paths(self, candidate_id: str) -> list[Path]:
        return [
            path for path in self._all_receipt_paths()
            if path.read_text(encoding="utf-8", errors="ignore").find(candidate_id) >= 0
        ]

    def _write_receipt(self, path: Path, receipt: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(_safe_json(receipt) + "\n", encoding="utf-8")
        temporary.replace(path)

    def _eligibility(
        self,
        candidate_id: str,
        candidate: Mapping[str, str] | None,
        queue: Mapping[str, str] | None,
        *,
        allow_manual_seed: bool,
        now: datetime,
        pilot: PilotPolicy | None = None,
    ) -> str:
        if self.config.authorized_candidate_ids and candidate_id not in self.config.authorized_candidate_ids:
            return "candidate is outside the explicitly authorized pilot set"
        if candidate is None or queue is None:
            return "candidate or queue row is missing"
        if queue.get("decision") != "APPROVE":
            return "queue decision is not APPROVE"
        if queue.get("target_surface") != "X":
            return "queue target_surface is not X"
        if queue.get("publisher_status") == "PUBLISHED":
            return "candidate is already published"
        if queue.get("published_ref"):
            return "candidate already has published_ref"
        if candidate.get("machine_disposition") != "stage":
            return "candidate machine disposition is not stage"
        if candidate.get("risk_class") != "low":
            return "candidate risk is not low"
        expires = _parse_time(candidate.get("expires_at"))
        if expires is not None and expires <= now:
            return "candidate is expired"
        scheduled = _parse_time(queue.get("scheduled_for"))
        if scheduled is not None and scheduled > now:
            return "candidate is not due"
        if pilot is not None:
            if candidate_id not in pilot.candidate_ids:
                return "candidate is outside the temporary pilot allowlist"
            if not pilot.active(now):
                return "temporary pilot window is inactive"
            if scheduled is None:
                return "temporary pilot requires an explicit scheduled_for"
            if now >= scheduled + timedelta(minutes=pilot.slot_minutes):
                return "scheduled pilot slot was missed; reschedule instead of catching up"
        quality = _quality(candidate.get("quality_summary", ""))
        if quality.get("forced_pipeline_acceptance") is True:
            return "forced pipeline acceptance is never publishable"
        if self.config.require_manual_seed and quality.get("manual_seed") is not True:
            return "candidate is not an explicitly marked manual seed"
        if self.config.require_manual_seed and not allow_manual_seed:
            return "manual seed requires --allow-manual-seed"
        draft = queue.get("draft_editable", "")
        if not draft.strip():
            return "draft_editable is empty"
        if len(draft) > MAX_POST_LENGTH:
            return f"draft_editable exceeds {MAX_POST_LENGTH} characters"
        return "eligible"

    def _reconcile(
        self,
        candidate_id: str,
        candidate: Mapping[str, str],
        queue: Mapping[str, str],
        row_number: int,
        now: datetime,
    ) -> PublisherResult | None:
        if queue.get("publisher_status") != "PUBLISHING":
            return None
        intended = queue.get("draft_editable", "")
        matches = [post for post in self.x.recent_posts(self.config.expected_username, 100) if _normalize_text(post.text) == _normalize_text(intended)]
        if len(matches) != 1:
            return PublisherResult(candidate_id, False, False, "BLOCKED", "unresolved prior publication attempt")
        post = matches[0]
        self._write_sheet_publication(queue, row_number, post, now)
        self._sync_draft_publication(candidate_id, post, now)
        return PublisherResult(candidate_id, True, True, "PUBLISHED", "reconciled prior publication", post.post_id)

    def _write_sheet_publication(self, queue: Mapping[str, str], row_number: int, post: XPost, now: datetime) -> None:
        self.gateway.replace_row(
            QUEUE_TAB,
            row_number,
            _replace_field(
                queue,
                QUEUE_HEADERS,
                publisher_status="PUBLISHED",
                published_ref=f"https://x.com/{self.config.expected_username}/status/{post.post_id}",
                updated_at=now.isoformat().replace("+00:00", "Z"),
            ),
        )

    def _sync_draft_publication(self, candidate_id: str, post: XPost, now: datetime) -> None:
        if self.drafts_sheet is None:
            return
        rows = self.drafts_sheet.read_rows(DRAFTS_TAB)
        if not rows or tuple(rows[0]) != DRAFTS_HEADERS:
            raise PublisherBlocked("DRAFTS header mismatch during publication writeback")
        for row_number, raw in enumerate(rows[1:], start=2):
            values = list(raw[:len(DRAFTS_HEADERS)]) + [""] * max(0, len(DRAFTS_HEADERS) - len(raw))
            if values[8] != candidate_id:
                continue
            record = dict(zip(DRAFTS_HEADERS, values))
            record["sync_status"] = "PUBLISHED"
            record["published_ref"] = f"https://x.com/{self.config.expected_username}/status/{post.post_id}"
            record["updated_at"] = now.isoformat().replace("+00:00", "Z")
            record["schema_version"] = DRAFTS_SCHEMA
            self.drafts_sheet.replace_row(DRAFTS_TAB, row_number, [record[column] for column in DRAFTS_HEADERS])
            return

    def run(
        self,
        candidate_id: str,
        *,
        apply: bool,
        allow_manual_seed: bool = False,
        pilot: PilotPolicy | None = None,
    ) -> PublisherResult:
        if pilot is not None:
            try:
                pilot.validate(self.config)
            except PublisherBlocked as exc:
                return PublisherResult(candidate_id, False, False, "BLOCKED", str(exc))
        if apply and os.environ.get(self.config.kill_switch_env, "").strip().lower() in {"1", "true", "yes", "on"}:
            return PublisherResult(candidate_id, False, False, "BLOCKED", "profile kill switch is active")
        now = self.clock()
        candidates, queue_rows, row_numbers = self._snapshot()
        candidate = candidates.get(candidate_id)
        queue = queue_rows.get(candidate_id)
        if candidate is None or queue is None:
            return PublisherResult(candidate_id, False, False, "BLOCKED", "candidate or queue row is missing")
        if queue.get("publisher_status") == "PUBLISHING":
            # Reconciliation writes to Sheets, therefore never execute it in
            # dry-run. Verify X account identity before the readback/writeback.
            if not apply:
                return PublisherResult(candidate_id, False, False, "BLOCKED", "unresolved PUBLISHING; dry-run is read-only")
            identity = self.x.whoami()
            if identity.username.casefold() != self.config.expected_username.casefold() or identity.user_id != self.config.expected_user_id:
                return PublisherResult(candidate_id, False, False, "BLOCKED", "X account identity mismatch")
            reconciled = self._reconcile(candidate_id, candidate, queue, row_numbers[candidate_id], now)
            if reconciled is not None:
                return reconciled
        reason = self._eligibility(candidate_id, candidate, queue, allow_manual_seed=allow_manual_seed, now=now, pilot=pilot)
        if reason != "eligible":
            return PublisherResult(candidate_id, False, False, "BLOCKED", reason)
        receipts = self._receipt_paths(candidate_id)
        if any(json.loads(path.read_text(encoding="utf-8")).get("state") not in {"PUBLISHED", "FAILED_BEFORE_EXTERNAL_MUTATION"} for path in receipts):
            return PublisherResult(candidate_id, False, False, "BLOCKED", "unresolved local publication attempt")
        identity = self.x.whoami()
        if identity.username.casefold() != self.config.expected_username.casefold() or identity.user_id != self.config.expected_user_id:
            return PublisherResult(candidate_id, False, False, "BLOCKED", "X account identity mismatch")
        recent = self.x.recent_posts(self.config.expected_username, 100)
        draft = queue["draft_editable"]
        if any(_normalize_text(post.text) == _normalize_text(draft) for post in recent):
            return PublisherResult(candidate_id, False, False, "BLOCKED", "exact text already exists in recent X history")
        published_times = []
        pilot_receipts = []
        # Cadence is account-wide within the isolated receipt namespace.
        # The prior candidate-scoped scan failed to limit distinct candidates.
        for path in self._all_receipt_paths():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("profile_id", self.config.profile_id) != self.config.profile_id:
                continue
            if data.get("state") == "PUBLISHED":
                published_at = _parse_time(data.get("published_at")) or now
                published_times.append(published_at)
                if data.get("pilot_mode") is True:
                    pilot_receipts.append(data)
        if pilot is None:
            recent_pilot = [value for value in published_times if now - value < timedelta(hours=24)]
            if len(recent_pilot) >= self.config.max_posts_per_day:
                return PublisherResult(candidate_id, False, False, "BLOCKED", "pilot daily cadence limit reached")
            if any(now - value < timedelta(hours=self.config.min_post_gap_hours) for value in published_times):
                return PublisherResult(candidate_id, False, False, "BLOCKED", "pilot minimum post gap not met")
        else:
            window_posts = [item for item in pilot_receipts if pilot.window_start <= (_parse_time(item.get("published_at")) or now) < pilot.window_end]
            if len(window_posts) >= pilot.cap:
                return PublisherResult(candidate_id, False, False, "BLOCKED", "temporary pilot cap reached")
            scheduled_value = _parse_time(queue.get("scheduled_for"))
            slot = scheduled_value.isoformat() if scheduled_value else ""
            if any(item.get("pilot_slot") == slot for item in pilot_receipts):
                return PublisherResult(candidate_id, False, False, "BLOCKED", "pilot slot already published")
        if not apply:
            return PublisherResult(candidate_id, True, False, "DRY_RUN", "eligible")

        attempt_id = f"pilot-{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:10]}"
        receipt_path = self.artifacts_dir / f"{attempt_id}.json"
        receipt: dict[str, Any] = {
            "schema_version": PUBLISHER_SCHEMA,
            "attempt_id": attempt_id,
            "candidate_id": candidate_id,
            "draft_sha256": hashlib.sha256(draft.encode("utf-8")).hexdigest(),
            "profile_id": self.config.profile_id,
            "account_key": self.config.account_key,
            "expected_x_username": self.config.expected_username,
            "expected_x_user_id": self.config.expected_user_id,
            "started_at": now.isoformat().replace("+00:00", "Z"),
            "policy_result": "eligible",
            "state": "PUBLISHING",
            "events": [{"at": now.isoformat().replace("+00:00", "Z"), "state": "PUBLISHING"}],
        }
        if pilot is not None:
            scheduled_value = _parse_time(queue.get("scheduled_for"))
            receipt.update({
                "pilot_mode": True,
                "pilot_window_start": pilot.window_start.isoformat().replace("+00:00", "Z"),
                "pilot_window_end": pilot.window_end.isoformat().replace("+00:00", "Z"),
                "pilot_slot": scheduled_value.isoformat() if scheduled_value else "",
            })
        self._write_receipt(receipt_path, receipt)
        self.gateway.replace_row(QUEUE_TAB, row_numbers[candidate_id], _replace_field(queue, QUEUE_HEADERS, publisher_status="PUBLISHING", updated_at=now.isoformat().replace("+00:00", "Z")))
        try:
            post = self.x.create_post(draft)
            readback = self.x.read_post(post.post_id)
            if (
                readback.post_id != post.post_id
                or readback.text != draft
                or (readback.author_id is not None and readback.author_id != self.config.expected_user_id)
                or (readback.username is not None and readback.username.casefold() != self.config.expected_username.casefold())
            ):
                raise PublisherBlocked("X readback did not exactly match the submitted post")
            completed_at = self.clock()
            self._write_sheet_publication(queue | {"publisher_status": "PUBLISHING"}, row_numbers[candidate_id], readback, completed_at)
            self._sync_draft_publication(candidate_id, readback, completed_at)
            receipt.update({"state": "PUBLISHED", "published_at": completed_at.isoformat().replace("+00:00", "Z"), "post_id": readback.post_id, "post_url": f"https://x.com/{self.config.expected_username}/status/{readback.post_id}"})
            receipt["events"].append({"at": receipt["published_at"], "state": "PUBLISHED"})
            self._write_receipt(receipt_path, receipt)
            return PublisherResult(candidate_id, True, True, "PUBLISHED", "published and read back", readback.post_id)
        except Exception as exc:
            receipt.update({"state": "UNRESOLVED", "error": type(exc).__name__})
            receipt["events"].append({"at": self.clock().isoformat().replace("+00:00", "Z"), "state": "UNRESOLVED"})
            self._write_receipt(receipt_path, receipt)
            raise
