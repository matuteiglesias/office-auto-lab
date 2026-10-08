from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlparse

from office_runtime.editorial.staging.sheets import (
    CANDIDATES_HEADERS,
    CANDIDATES_TAB,
    QUEUE_HEADERS,
    QUEUE_TAB,
    GoogleSheetsGateway,
)

DRAFTS_TAB = "DRAFTS"
DRAFTS_HEADERS = (
    "post_text", "decision", "scheduled_for_utc", "topic", "source_urls", "editor_note",
    "risk_class", "expires_at_utc", "candidate_id", "sync_status", "published_ref", "updated_at", "schema_version",
)
DRAFTS_SCHEMA = "office_runtime.editorial.manual_drafts.v1"
VALID_DECISIONS = frozenset({"DRAFT", "REVIEW", "APPROVE", "HOLD", "REJECT"})
VALID_RISKS = frozenset({"low", "medium", "high"})


class ManualIntakeError(RuntimeError):
    pass


class ManualSheet(Protocol):
    def read_rows(self, tab: str) -> list[list[str]]: ...
    def append_row(self, tab: str, row: Sequence[str]) -> None: ...
    def replace_row(self, tab: str, row_number: int, row: Sequence[str]) -> None: ...


class GoogleManualSheet:
    """Values adapter that reuses GoogleSheetsGateway authentication and service."""

    _WIDTHS = {DRAFTS_TAB: len(DRAFTS_HEADERS), CANDIDATES_TAB: len(CANDIDATES_HEADERS), QUEUE_TAB: len(QUEUE_HEADERS)}

    def __init__(self, gateway: GoogleSheetsGateway) -> None:
        self.gateway = gateway

    @classmethod
    def from_environment(cls, spreadsheet_id: str) -> "GoogleManualSheet":
        return cls(GoogleSheetsGateway.from_environment(spreadsheet_id=spreadsheet_id))

    @staticmethod
    def _end_column(width: int) -> str:
        return chr(ord("A") + width - 1)

    def _range(self, tab: str, row_number: int | None = None) -> str:
        end = self._end_column(self._WIDTHS[tab])
        return f"'{tab}'!A{row_number}:{end}{row_number}" if row_number else f"'{tab}'!A:{end}"

    def read_rows(self, tab: str) -> list[list[str]]:
        return self.gateway.service.spreadsheets().values().get(
            spreadsheetId=self.gateway.spreadsheet_id, range=self._range(tab)
        ).execute().get("values", [])

    def append_row(self, tab: str, row: Sequence[str]) -> None:
        self.gateway.service.spreadsheets().values().append(
            spreadsheetId=self.gateway.spreadsheet_id, range=self._range(tab),
            valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": [list(row)]}
        ).execute()

    def replace_row(self, tab: str, row_number: int, row: Sequence[str]) -> None:
        self.gateway.service.spreadsheets().values().update(
            spreadsheetId=self.gateway.spreadsheet_id, range=self._range(tab, row_number),
            valueInputOption="RAW", body={"values": [list(row)]}
        ).execute()


@dataclass(frozen=True)
class IntakeResult:
    staged: int
    unchanged: int
    blocked: int
    rows: tuple[dict[str, str], ...]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: str, label: str, *, future: bool = False, now: datetime) -> str:
    raw = value.strip()
    if not raw:
        return ""
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ManualIntakeError(f"{label} must be ISO-8601 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ManualIntakeError(f"{label} must include UTC timezone")
    parsed = parsed.astimezone(timezone.utc)
    if future and parsed <= now:
        raise ManualIntakeError(f"{label} must be in the future")
    return parsed.isoformat().replace("+00:00", "Z")


def _urls(value: str) -> list[str]:
    values = [item for item in re.split(r"[\s,]+", value.strip()) if item]
    for item in values:
        parsed = urlparse(item)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ManualIntakeError(f"source_urls contains an invalid URL: {item}")
    return values


def _records(rows: list[list[str]], headers: tuple[str, ...], tab: str) -> tuple[list[dict[str, str]], dict[str, int]]:
    if not rows or tuple(rows[0]) != headers:
        raise ManualIntakeError(f"{tab} header mismatch")
    result: list[dict[str, str]] = []
    numbers: dict[str, int] = {}
    for number, raw in enumerate(rows[1:], start=2):
        values = list(raw[:len(headers)]) + [""] * max(0, len(headers) - len(raw))
        if not any(values):
            continue
        record = dict(zip(headers, values))
        result.append(record)
        numbers[str(number)] = number
    return result, numbers


def _index(records: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for record in records:
        value = record.get(key, "")
        if value:
            if value in output:
                raise ManualIntakeError(f"duplicate {key}: {value}")
            output[value] = record
    return output


def _candidate_id(record: Mapping[str, str]) -> str:
    canonical = "\n".join((record.get("post_text", ""), record.get("topic", ""), record.get("source_urls", "")))
    return "cand:argentina-econ-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def _row(headers: tuple[str, ...], record: Mapping[str, Any]) -> list[str]:
    return [str(record.get(header, "")) for header in headers]


def project_manual_drafts(sheet: ManualSheet, *, now: datetime | None = None) -> IntakeResult:
    current = (now or _utc_now()).astimezone(timezone.utc)
    draft_rows, _ = _records(sheet.read_rows(DRAFTS_TAB), DRAFTS_HEADERS, DRAFTS_TAB)
    candidate_rows, _ = _records(sheet.read_rows(CANDIDATES_TAB), CANDIDATES_HEADERS, CANDIDATES_TAB)
    queue_raw = sheet.read_rows(QUEUE_TAB)
    queue_rows, _ = _records(queue_raw, QUEUE_HEADERS, QUEUE_TAB)
    candidates = _index(candidate_rows, "candidate_id")
    queues = _index(queue_rows, "candidate_id")
    results: list[dict[str, str]] = []
    staged = unchanged = blocked = 0

    for row_number, source in ((number, record) for number, record in enumerate(draft_rows, start=2)):
        if not source.get("post_text", "").strip():
            continue
        candidate_id = source.get("candidate_id", "").strip() or _candidate_id(source)
        updated = dict(source)
        try:
            decision = source.get("decision", "DRAFT").strip().upper() or "DRAFT"
            risk = source.get("risk_class", "low").strip().lower() or "low"
            if decision not in VALID_DECISIONS:
                raise ManualIntakeError("decision must be DRAFT, REVIEW, APPROVE, HOLD, or REJECT")
            if risk not in VALID_RISKS:
                raise ManualIntakeError("risk_class must be low, medium, or high")
            if risk == "high" and decision != "HOLD":
                raise ManualIntakeError("high-risk drafts must be HOLD")
            scheduled = _timestamp(source.get("scheduled_for_utc", ""), "scheduled_for_utc", future=True, now=current)
            expires = _timestamp(source.get("expires_at_utc", ""), "expires_at_utc", future=True, now=current)
            urls = _urls(source.get("source_urls", ""))
            if candidate_id in candidates:
                existing = candidates[candidate_id]
                if existing.get("draft_original") != source.get("post_text", "") or existing.get("risk_class") != risk:
                    raise ManualIntakeError("REVISION_REQUIRED: staged draft changed; create a new DRAFTS row for an explicit revision")
                queue = queues.get(candidate_id)
                if queue is None:
                    raise ManualIntakeError("candidate exists without QUEUE row")
                updated["sync_status"] = "PUBLISHED" if queue.get("publisher_status") == "PUBLISHED" else "STAGED"
                updated["candidate_id"] = candidate_id
                updated["published_ref"] = queue.get("published_ref", "")
                updated["updated_at"] = current.isoformat().replace("+00:00", "Z")
                updated["schema_version"] = DRAFTS_SCHEMA
                unchanged += 1
            else:
                effective_decision = "REVIEW" if decision == "DRAFT" else decision
                fingerprint = "sha256:" + hashlib.sha256(source.get("post_text", "").encode("utf-8")).hexdigest()
                candidate = {
                    "candidate_id": candidate_id,
                    "batch_id": f"manual:argentina_econ:{current.date().isoformat()}",
                    "run_id": f"manual-intake:{candidate_id}",
                    "created_at": current.isoformat().replace("+00:00", "Z"),
                    "source_date": current.date().isoformat(),
                    "source_tier": "manual_sheet",
                    "repo": "",
                    "work_refs": json.dumps(urls, ensure_ascii=False, separators=(",", ":")),
                    "angle_type": "field_note",
                    "candidate_family": "MANUAL_DRAFT",
                    "claim": source.get("post_text", ""),
                    "evidence_refs": "[]",
                    "proof_object_refs": json.dumps(urls, ensure_ascii=False, separators=(",", ":")),
                    "career_signals": "[]",
                    "risk_class": risk,
                    "semantic_fingerprint": fingerprint,
                    "draft_original": source.get("post_text", ""),
                    "machine_disposition": "stage",
                    "quality_summary": json.dumps({"intake": "manual_sheet", "source_urls": urls, "model": None}, ensure_ascii=False, separators=(",", ":")),
                    "expires_at": expires,
                    "schema_version": "office_runtime.editorial.sheet.candidates.v1",
                }
                queue = {
                    "candidate_id": candidate_id,
                    "draft_editable": source.get("post_text", ""),
                    "decision": effective_decision,
                    "editor_note": source.get("editor_note", ""),
                    "target_surface": "X",
                    "publisher_status": "",
                    "scheduled_for": scheduled,
                    "published_ref": "",
                    "updated_at": current.isoformat().replace("+00:00", "Z"),
                    "schema_version": "office_runtime.editorial.sheet.queue.v1",
                }
                sheet.append_row(CANDIDATES_TAB, _row(CANDIDATES_HEADERS, candidate))
                sheet.append_row(QUEUE_TAB, _row(QUEUE_HEADERS, queue))
                updated["candidate_id"] = candidate_id
                updated["sync_status"] = "STAGED"
                updated["published_ref"] = ""
                updated["updated_at"] = current.isoformat().replace("+00:00", "Z")
                updated["schema_version"] = DRAFTS_SCHEMA
                staged += 1
        except ManualIntakeError as exc:
            updated["candidate_id"] = candidate_id if candidate_id in candidates else ""
            updated["sync_status"] = f"ERROR: {exc}"
            updated["updated_at"] = current.isoformat().replace("+00:00", "Z")
            updated["schema_version"] = DRAFTS_SCHEMA
            blocked += 1
        updated_values = _row(DRAFTS_HEADERS, updated)
        sheet.replace_row(DRAFTS_TAB, row_number, updated_values)
        results.append({"row": str(row_number), "candidate_id": updated.get("candidate_id", ""), "sync_status": updated.get("sync_status", "")})
    return IntakeResult(staged=staged, unchanged=unchanged, blocked=blocked, rows=tuple(results))
