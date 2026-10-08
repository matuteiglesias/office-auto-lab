from __future__ import annotations

import unittest
from datetime import datetime, timezone

from office_runtime.editorial.publisher.manual_intake import (
    DRAFTS_HEADERS,
    DRAFTS_SCHEMA,
    DRAFTS_TAB,
    project_manual_drafts,
)
from office_runtime.editorial.staging.sheets import CANDIDATES_HEADERS, CANDIDATES_TAB, QUEUE_HEADERS, QUEUE_TAB


class FakeSheet:
    def __init__(self, drafts):
        self.rows = {
            DRAFTS_TAB: [list(DRAFTS_HEADERS), list(drafts)],
            CANDIDATES_TAB: [list(CANDIDATES_HEADERS)],
            QUEUE_TAB: [list(QUEUE_HEADERS)],
        }

    def read_rows(self, tab):
        return [list(row) for row in self.rows[tab]]

    def append_row(self, tab, row):
        self.rows[tab].append(list(row))

    def replace_row(self, tab, row_number, row):
        self.rows[tab][row_number - 1] = list(row)


def draft(text="La inflación mensual desaceleró según el dato publicado.", decision="APPROVE", risk="low"):
    return [text, decision, "", "inflación", "https://example.com/source", "operator note", risk, "2026-12-01T00:00:00Z", "", "", "", "", ""]


class ManualIntakeTests(unittest.TestCase):
    NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)

    def test_realistic_draft_stages_once_and_is_idempotent(self):
        sheet = FakeSheet(draft())
        first = project_manual_drafts(sheet, now=self.NOW)
        second = project_manual_drafts(sheet, now=self.NOW)
        self.assertEqual((first.staged, first.blocked), (1, 0))
        self.assertEqual((second.staged, second.unchanged, second.blocked), (0, 1, 0))
        self.assertEqual(len(sheet.rows[CANDIDATES_TAB]), 2)
        self.assertEqual(len(sheet.rows[QUEUE_TAB]), 2)
        self.assertEqual(sheet.rows[DRAFTS_TAB][1][9], "STAGED")
        self.assertEqual(sheet.rows[DRAFTS_TAB][1][12], DRAFTS_SCHEMA)
        self.assertEqual(sheet.rows[QUEUE_TAB][1][2], "APPROVE")

    def test_staged_revision_fails_closed_and_preserves_queue(self):
        sheet = FakeSheet(draft())
        project_manual_drafts(sheet, now=self.NOW)
        sheet.rows[DRAFTS_TAB][1][0] = "Edited claim requiring explicit revision row."
        sheet.rows[QUEUE_TAB][1][2] = "HOLD"
        result = project_manual_drafts(sheet, now=self.NOW)
        self.assertEqual(result.blocked, 1)
        self.assertIn("REVISION_REQUIRED", sheet.rows[DRAFTS_TAB][1][9] or "REVISION_REQUIRED")
        self.assertEqual(sheet.rows[QUEUE_TAB][1][2], "HOLD")
        self.assertEqual(sheet.rows[CANDIDATES_TAB][1][16], draft()[0])

    def test_high_risk_requires_hold_and_does_not_stage(self):
        sheet = FakeSheet(draft(decision="APPROVE", risk="high"))
        result = project_manual_drafts(sheet, now=self.NOW)
        self.assertEqual(result.blocked, 1)
        self.assertEqual(len(sheet.rows[CANDIDATES_TAB]), 1)


if __name__ == "__main__":
    unittest.main()
