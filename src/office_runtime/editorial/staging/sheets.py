from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

RUNS_TAB = "RUNS"
CANDIDATES_TAB = "CANDIDATES"
QUEUE_TAB = "QUEUE"

RUNS_SCHEMA = "office_runtime.editorial.sheet.runs.v1"
CANDIDATES_SCHEMA = "office_runtime.editorial.sheet.candidates.v1"
QUEUE_SCHEMA = "office_runtime.editorial.sheet.queue.v1"

RUNS_HEADERS = (
    "run_id",
    "profile_id",
    "started_at",
    "finished_at",
    "inventory_status",
    "candidate_count",
    "policy_ref",
    "source_summary",
    "error_summary",
    "run_bundle_ref",
    "schema_version",
)

CANDIDATES_HEADERS = (
    "candidate_id",
    "batch_id",
    "run_id",
    "created_at",
    "source_date",
    "source_tier",
    "repo",
    "work_refs",
    "angle_type",
    "candidate_family",
    "claim",
    "evidence_refs",
    "proof_object_refs",
    "career_signals",
    "risk_class",
    "semantic_fingerprint",
    "draft_original",
    "machine_disposition",
    "quality_summary",
    "expires_at",
    "schema_version",
)

QUEUE_HEADERS = (
    "candidate_id",
    "draft_editable",
    "decision",
    "editor_note",
    "target_surface",
    "publisher_status",
    "scheduled_for",
    "published_ref",
    "updated_at",
    "schema_version",
)

_EXPECTED = {
    RUNS_TAB: (RUNS_HEADERS, RUNS_SCHEMA, "run_id"),
    CANDIDATES_TAB: (CANDIDATES_HEADERS, CANDIDATES_SCHEMA, "candidate_id"),
    QUEUE_TAB: (QUEUE_HEADERS, QUEUE_SCHEMA, "candidate_id"),
}

RUN_IDENTITY_FIELDS = ("run_id", "profile_id", "started_at", "policy_ref", "schema_version")


class SheetProjectionError(RuntimeError):
    pass


class SheetSchemaError(SheetProjectionError):
    pass


class SheetIdentityConflict(SheetProjectionError):
    pass


class SheetGateway(Protocol):
    def read_rows(self, tab: str) -> list[list[str]]:
        """Return rows including the header row."""

    def append_row(self, tab: str, row: Sequence[str]) -> None:
        """Append one complete data row."""

    def replace_row(self, tab: str, row_number: int, row: Sequence[str]) -> None:
        """Replace one complete 1-based data row, including the header offset."""


@dataclass(frozen=True)
class _TabState:
    tab: str
    headers: tuple[str, ...]
    rows: dict[str, dict[str, str]]
    row_numbers: dict[str, int]


@dataclass(frozen=True)
class ProjectionResult:
    run_id: str
    run_action: str
    candidates_created: int
    candidates_reused: int
    queue_created: int
    queue_preserved: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_action": self.run_action,
            "candidates_created": self.candidates_created,
            "candidates_reused": self.candidates_reused,
            "queue_created": self.queue_created,
            "queue_preserved": self.queue_preserved,
        }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict, tuple)):
        return _canonical(value)
    return str(value)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SheetProjectionError(f"{label} must be an object")
    return value


def _records(value: Any, label: str) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SheetProjectionError(f"{label} must be an array")
    out: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        out.append(_mapping(item, f"{label}[{index}]"))
    return out


def _index(records: list[Mapping[str, Any]], key: str, label: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        raw = record.get(key)
        if not isinstance(raw, str) or not raw.strip():
            raise SheetProjectionError(f"{label} record missing {key}")
        if raw in result:
            raise SheetProjectionError(f"duplicate {label} identity {raw!r}")
        result[raw] = record
    return result


def _safe_policy_ref(policy: Mapping[str, Any]) -> str:
    for key in ("policy_ref", "ref", "identity", "commit_ref"):
        value = policy.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    content_hash = policy.get("content_hash") or policy.get("sha256")
    if isinstance(content_hash, str) and content_hash.strip():
        return content_hash.strip()
    return _canonical(policy)


def _safe_retrieval_summary(retrieval: Mapping[str, Any]) -> str:
    keys = (
        "intended_sources",
        "actual_sources",
        "sources_attempted",
        "sources_reached",
        "time_windows",
        "access_failures",
        "unknown_scope",
        "incomplete_scope",
    )
    return _canonical({key: retrieval[key] for key in keys if key in retrieval})


def _safe_error_summary(errors: Any) -> str:
    safe: list[dict[str, Any]] = []
    for record in _records(errors, "errors"):
        item = {}
        for key in ("stage", "code", "kind", "status"):
            if key in record:
                item[key] = record[key]
        safe.append(item)
    return _canonical(safe)


def _normalize_row(row: Sequence[Any], width: int) -> list[str]:
    values = [_as_text(value) for value in row[:width]]
    values.extend("" for _ in range(width - len(values)))
    return values


def _load_tab(gateway: SheetGateway, tab: str) -> _TabState:
    expected_headers, expected_schema, key_field = _EXPECTED[tab]
    raw = gateway.read_rows(tab)
    if not raw:
        raise SheetSchemaError(f"{tab} is missing its header row")
    headers = tuple(_as_text(value) for value in raw[0])
    if headers != expected_headers:
        raise SheetSchemaError(
            f"{tab} header mismatch; expected {list(expected_headers)!r}, got {list(headers)!r}"
        )

    rows: dict[str, dict[str, str]] = {}
    row_numbers: dict[str, int] = {}
    for row_number, raw_row in enumerate(raw[1:], start=2):
        if len(raw_row) > len(headers) and any(_as_text(value) for value in raw_row[len(headers):]):
            raise SheetSchemaError(f"{tab} row {row_number} contains unexpected extra columns")
        row = _normalize_row(raw_row, len(headers))
        if not any(row):
            continue
        record = dict(zip(headers, row))
        key = record[key_field]
        if not key:
            raise SheetSchemaError(f"{tab} row {row_number} has no {key_field}")
        if record["schema_version"] != expected_schema:
            raise SheetSchemaError(
                f"{tab} row {row_number} has schema_version {record['schema_version']!r}; "
                f"expected {expected_schema!r}"
            )
        if key in rows:
            raise SheetSchemaError(f"{tab} has duplicate key {key!r}")
        rows[key] = record
        row_numbers[key] = row_number
    return _TabState(tab=tab, headers=headers, rows=rows, row_numbers=row_numbers)


def _row(headers: tuple[str, ...], values: Mapping[str, Any]) -> list[str]:
    unknown = set(values) - set(headers)
    if unknown:
        raise SheetProjectionError(f"row contains unknown columns: {sorted(unknown)}")
    return [_as_text(values.get(header, "")) for header in headers]


def _source_date(candidate: Mapping[str, Any], evidence: dict[str, Mapping[str, Any]]) -> str:
    direct = candidate.get("source_date")
    if isinstance(direct, str) and direct:
        return direct
    refs = candidate.get("evidence_refs")
    if isinstance(refs, list):
        for ref in refs:
            item = evidence.get(str(ref))
            if not item:
                continue
            for key in ("event_at", "observed_at"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    return value[:10]
    return ""


def _source_tier(candidate: Mapping[str, Any], evidence: dict[str, Mapping[str, Any]]) -> str:
    direct = candidate.get("source_tier")
    if direct is not None:
        return _as_text(direct)
    refs = candidate.get("evidence_refs")
    if isinstance(refs, list):
        for ref in refs:
            item = evidence.get(str(ref))
            if item and item.get("source_tier") is not None:
                return _as_text(item.get("source_tier"))
    return ""


def _candidate_repo(candidate: Mapping[str, Any], story: Mapping[str, Any]) -> str:
    for key in ("repo", "repository_ref"):
        value = candidate.get(key)
        if isinstance(value, str) and value:
            return value
    refs = story.get("repository_refs")
    if isinstance(refs, list):
        return ",".join(str(value) for value in refs)
    return ""


def _build_run_row(bundle: Mapping[str, Any], run_bundle_ref: str) -> dict[str, Any]:
    batch = _mapping(bundle.get("batch"), "batch")
    policy = _mapping(bundle.get("policy"), "policy")
    retrieval = _mapping(bundle.get("retrieval"), "retrieval")
    candidate_ids = batch.get("candidate_ids")
    if not isinstance(candidate_ids, list):
        raise SheetProjectionError("batch.candidate_ids must be an array")
    return {
        "run_id": bundle.get("run_id"),
        "profile_id": bundle.get("profile_id"),
        "started_at": bundle.get("started_at"),
        "finished_at": bundle.get("finished_at"),
        "inventory_status": batch.get("inventory_status") or bundle.get("status"),
        "candidate_count": len(candidate_ids),
        "policy_ref": _safe_policy_ref(policy),
        "source_summary": _safe_retrieval_summary(retrieval),
        "error_summary": _safe_error_summary(bundle.get("errors", [])),
        "run_bundle_ref": run_bundle_ref,
        "schema_version": RUNS_SCHEMA,
    }


def _build_candidate_rows(bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    batch = _mapping(bundle.get("batch"), "batch")
    batch_id = batch.get("batch_id")
    run_id = bundle.get("run_id")
    candidate_ids = batch.get("candidate_ids")
    if not isinstance(candidate_ids, list):
        raise SheetProjectionError("batch.candidate_ids must be an array")

    candidates = _index(_records(bundle.get("candidates"), "candidates"), "candidate_id", "candidate")
    angles = _index(_records(bundle.get("angles"), "angles"), "angle_id", "angle")
    stories = _index(_records(bundle.get("stories"), "stories"), "story_id", "story")
    evidence = _index(_records(bundle.get("evidence"), "evidence"), "evidence_id", "evidence")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_candidate_id in candidate_ids:
        candidate_id = str(raw_candidate_id)
        if candidate_id in seen:
            raise SheetProjectionError(f"batch contains duplicate candidate_id {candidate_id!r}")
        seen.add(candidate_id)
        candidate = candidates.get(candidate_id)
        if candidate is None:
            raise SheetProjectionError(f"batch candidate {candidate_id!r} missing from candidates")
        angle_id = candidate.get("angle_id")
        angle = angles.get(str(angle_id))
        if angle is None:
            raise SheetProjectionError(f"candidate {candidate_id!r} references unknown angle {angle_id!r}")
        story_id = candidate.get("story_id") or angle.get("story_id")
        story = stories.get(str(story_id))
        if story is None:
            raise SheetProjectionError(f"candidate {candidate_id!r} references unknown story {story_id!r}")

        evidence_refs = candidate.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            raise SheetProjectionError(f"candidate {candidate_id!r} requires evidence_refs")
        missing_refs = [str(ref) for ref in evidence_refs if str(ref) not in evidence]
        if missing_refs:
            raise SheetProjectionError(
                f"candidate {candidate_id!r} references missing evidence {missing_refs!r}"
            )

        rows.append(
            {
                "candidate_id": candidate_id,
                "batch_id": batch_id,
                "run_id": run_id,
                "created_at": candidate.get("generated_at") or bundle.get("finished_at"),
                "source_date": _source_date(candidate, evidence),
                "source_tier": _source_tier(candidate, evidence),
                "repo": _candidate_repo(candidate, story),
                "work_refs": candidate.get("work_refs", []),
                "angle_type": angle.get("angle_type"),
                "candidate_family": candidate.get("candidate_family"),
                "claim": angle.get("claim"),
                "evidence_refs": evidence_refs,
                "proof_object_refs": candidate.get("proof_object_refs", []),
                "career_signals": candidate.get("career_signals", []),
                "risk_class": candidate.get("risk_class"),
                "semantic_fingerprint": candidate.get("semantic_fingerprint"),
                "draft_original": candidate.get("text"),
                "machine_disposition": candidate.get("machine_disposition"),
                "quality_summary": candidate.get("quality", {}),
                "expires_at": candidate.get("expires_at"),
                "schema_version": CANDIDATES_SCHEMA,
            }
        )
    return rows


def _build_queue_row(candidate_row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate_row["candidate_id"],
        "draft_editable": candidate_row["draft_original"],
        "decision": "REVIEW",
        "editor_note": "",
        "target_surface": "X",
        "publisher_status": "",
        "scheduled_for": "",
        "published_ref": "",
        "updated_at": "",
        "schema_version": QUEUE_SCHEMA,
    }


def _assert_nonempty(record: Mapping[str, Any], *fields: str) -> None:
    for field in fields:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise SheetProjectionError(f"{field} must be a non-empty string")


def project_run_bundle(
    bundle: Mapping[str, Any],
    gateway: SheetGateway,
    *,
    run_bundle_ref: str,
) -> ProjectionResult:
    """Project a completed run bundle without overwriting human-owned queue state."""

    if bundle.get("schema_version") != "office_runtime.editorial.run_bundle.v1":
        raise SheetProjectionError("unsupported run bundle schema_version")
    _assert_nonempty(bundle, "run_id", "profile_id", "started_at")

    # Validate the entire workbook shape before the first mutation.
    runs_state = _load_tab(gateway, RUNS_TAB)
    candidates_state = _load_tab(gateway, CANDIDATES_TAB)
    queue_state = _load_tab(gateway, QUEUE_TAB)

    orphan_queue = sorted(set(queue_state.rows) - set(candidates_state.rows))
    if orphan_queue:
        raise SheetSchemaError(
            f"QUEUE contains candidate IDs missing from CANDIDATES: {orphan_queue!r}"
        )

    # Validate all payload referential invariants before the first write as well.
    run_record = _build_run_row(bundle, run_bundle_ref)
    candidate_rows = _build_candidate_rows(bundle)
    _assert_nonempty(run_record, "run_id", "profile_id", "started_at", "policy_ref")
    run_id = str(run_record["run_id"])
    run_values = _row(RUNS_HEADERS, run_record)

    existing_run = runs_state.rows.get(run_id)
    if existing_run is None:
        gateway.append_row(RUNS_TAB, run_values)
        run_action = "created"
    else:
        desired_run = dict(zip(RUNS_HEADERS, run_values))
        for field in RUN_IDENTITY_FIELDS:
            if existing_run[field] != desired_run[field]:
                raise SheetIdentityConflict(
                    f"run_id {run_id!r} identity conflict in field {field!r}"
                )
        if existing_run == desired_run:
            run_action = "reused"
        else:
            gateway.replace_row(RUNS_TAB, runs_state.row_numbers[run_id], run_values)
            run_action = "reconciled"

    created = reused = queue_created = queue_preserved = 0
    for record in candidate_rows:
        candidate_id = str(record["candidate_id"])
        candidate_values = _row(CANDIDATES_HEADERS, record)
        existing_candidate = candidates_state.rows.get(candidate_id)
        if existing_candidate is None:
            gateway.append_row(CANDIDATES_TAB, candidate_values)
            created += 1
        else:
            desired = dict(zip(CANDIDATES_HEADERS, candidate_values))
            if existing_candidate != desired:
                raise SheetIdentityConflict(
                    f"candidate_id {candidate_id!r} conflicts with append-only candidate state"
                )
            reused += 1

        existing_queue = queue_state.rows.get(candidate_id)
        if existing_queue is None:
            gateway.append_row(QUEUE_TAB, _row(QUEUE_HEADERS, _build_queue_row(record)))
            queue_created += 1
        else:
            # Queue state is human/publisher owned after creation. Never rewrite it here.
            queue_preserved += 1

    return ProjectionResult(
        run_id=run_id,
        run_action=run_action,
        candidates_created=created,
        candidates_reused=reused,
        queue_created=queue_created,
        queue_preserved=queue_preserved,
    )


class InMemorySheetGateway:
    """Small test adapter with the same append/replace semantics as Sheets."""

    def __init__(
        self,
        rows: Mapping[str, Sequence[Sequence[Any]]] | None = None,
        *,
        fail_after_writes: int | None = None,
    ) -> None:
        defaults = {
            RUNS_TAB: [list(RUNS_HEADERS)],
            CANDIDATES_TAB: [list(CANDIDATES_HEADERS)],
            QUEUE_TAB: [list(QUEUE_HEADERS)],
        }
        source = rows or defaults
        self.rows = {
            tab: [_normalize_row(row, len(_EXPECTED[tab][0])) for row in tab_rows]
            for tab, tab_rows in source.items()
        }
        self.fail_after_writes = fail_after_writes
        self.write_count = 0

    def _before_write(self) -> None:
        if self.fail_after_writes is not None and self.write_count >= self.fail_after_writes:
            raise SheetProjectionError("injected sheet write failure")
        self.write_count += 1

    def read_rows(self, tab: str) -> list[list[str]]:
        if tab not in self.rows:
            raise SheetSchemaError(f"missing required tab {tab}")
        return [list(row) for row in self.rows[tab]]

    def append_row(self, tab: str, row: Sequence[str]) -> None:
        self._before_write()
        self.rows[tab].append(list(row))

    def replace_row(self, tab: str, row_number: int, row: Sequence[str]) -> None:
        self._before_write()
        index = row_number - 1
        if index <= 0 or index >= len(self.rows[tab]):
            raise SheetProjectionError(f"invalid row replacement {tab}!{row_number}")
        self.rows[tab][index] = list(row)

    def set_cell(self, tab: str, key: str, column: str, value: str) -> None:
        headers, _, key_field = _EXPECTED[tab]
        key_index = headers.index(key_field)
        column_index = headers.index(column)
        for row in self.rows[tab][1:]:
            if row[key_index] == key:
                row[column_index] = value
                return
        raise KeyError(key)


class GoogleSheetsGateway:
    """Google Sheets values adapter. It never creates tabs or repairs schema."""

    SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)

    def __init__(self, service: Any, spreadsheet_id: str) -> None:
        if not spreadsheet_id:
            raise SheetProjectionError("spreadsheet_id is required")
        self.service = service
        self.spreadsheet_id = spreadsheet_id

    @classmethod
    def from_environment(cls, spreadsheet_id: str | None = None) -> "GoogleSheetsGateway":
        try:
            import google.auth
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover - exercised only in integration environments
            raise SheetProjectionError(
                "Google Sheets dependencies are unavailable; install the declared office profile"
            ) from exc

        raw = os.environ.get("EDITORIAL_GOOGLE_CREDENTIALS_JSON")
        if raw:
            try:
                info = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SheetProjectionError("EDITORIAL_GOOGLE_CREDENTIALS_JSON is not valid JSON") from exc
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=list(cls.SCOPES)
            )
        else:
            credentials, _ = google.auth.default(scopes=list(cls.SCOPES))

        target = spreadsheet_id or os.environ.get("EDITORIAL_DEV_SHEET_ID")
        if not target:
            raise SheetProjectionError(
                "sheet projection requires --sheet-id or EDITORIAL_DEV_SHEET_ID"
            )
        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        return cls(service, target)

    @staticmethod
    def _end_column(width: int) -> str:
        if width < 1 or width > 26:
            raise SheetProjectionError("Sheet adapter currently supports up to 26 columns")
        return chr(ord("A") + width - 1)

    @classmethod
    def _range(cls, tab: str, row_number: int | None = None) -> str:
        escaped = tab.replace("'", "''")
        width = len(_EXPECTED[tab][0])
        end = cls._end_column(width)
        if row_number is None:
            return f"'{escaped}'!A1:{end}10000"
        return f"'{escaped}'!A{row_number}:{end}{row_number}"

    def read_rows(self, tab: str) -> list[list[str]]:
        try:
            response = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=self._range(tab))
                .execute()
            )
        except Exception as exc:  # pragma: no cover - integration boundary
            raise SheetProjectionError(f"failed reading required Sheet tab {tab}") from exc
        return response.get("values", [])

    def append_row(self, tab: str, row: Sequence[str]) -> None:
        try:
            (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self.spreadsheet_id,
                    range=self._range(tab),
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [list(row)]},
                )
                .execute()
            )
        except Exception as exc:  # pragma: no cover - integration boundary
            raise SheetProjectionError(f"failed appending Sheet tab {tab}") from exc

    def replace_row(self, tab: str, row_number: int, row: Sequence[str]) -> None:
        try:
            (
                self.service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=self.spreadsheet_id,
                    range=self._range(tab, row_number),
                    valueInputOption="RAW",
                    body={"values": [list(row)]},
                )
                .execute()
            )
        except Exception as exc:  # pragma: no cover - integration boundary
            raise SheetProjectionError(f"failed reconciling Sheet tab {tab}") from exc
