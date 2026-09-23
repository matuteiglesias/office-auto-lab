from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from office_runtime.office.config import OfficeConfig
from office_runtime.office.frontier_view import (
    FrontierViewError,
    compile_relationship_agenda_view,
    publish_relationship_agenda_view,
)


COLUMNS = [
    "agenda_id",
    "relation_id",
    "person",
    "agenda_type",
    "state",
    "priority",
    "agenda_item",
    "why_it_matters",
    "origin_date",
    "trigger_or_due",
    "evidence",
    "last_refreshed",
    "resolution_note",
]


def frame(*rows: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=COLUMNS)


def fixture() -> pd.DataFrame:
    return frame(
        [
            "ag_ready",
            "rel_a",
            "Ada Example",
            "PROMISE",
            "READY",
            "P1",
            "Offer two call windows.",
            "Explicit mutual scheduling loop.",
            "2026-09-18",
            "Now.",
            "Thread A",
            "2026-09-22",
            "",
        ],
        [
            "ag_wait",
            "rel_b",
            "Beto Example",
            "OFFER",
            "WAIT",
            "P2",
            "Choose one pilot after ideas arrive.",
            "Keeps the collaboration bounded.",
            "2026-09-18",
            "After reply.",
            "Thread B",
            "2026-09-21",
            "",
        ],
        [
            "ag_done",
            "rel_c",
            "Cora Example",
            "ASK",
            "DONE",
            "P1",
            "Answer the question.",
            "Closes conversational debt.",
            "2026-09-11",
            "Completed.",
            "Thread C",
            "2026-09-21",
            "Answered.",
        ],
        [
            "ag_drop",
            "rel_d",
            "Dani Example",
            "WATCH",
            "DROP",
            "P3",
            "Do not pursue this agenda item.",
            "The source explicitly closed the loop.",
            "2026-09-20",
            "Dropped.",
            "Thread D",
            "2026-09-22",
            "Dropped by source judgment.",
        ],
    )


class FrontierViewTests(unittest.TestCase):
    def test_compiler_preserves_source_state_and_derives_only_bucket(self) -> None:
        view = compile_relationship_agenda_view(
            fixture(),
            generated_at="2026-09-22T23:00:00Z",
            spreadsheet_id="sheet",
        )
        self.assertEqual(view["schema_version"], "frontier.view.v1")
        self.assertEqual(view["counts"]["items"], 2)
        self.assertEqual([item["id"] for item in view["items"]], ["agenda:ag_ready", "agenda:ag_wait"])
        self.assertEqual(view["items"][0]["source_state"], "READY")
        self.assertEqual(view["items"][0]["bucket"], "ACTION")
        self.assertEqual(view["items"][1]["source_state"], "WAIT")
        self.assertEqual(view["items"][1]["bucket"], "WAITING")
        self.assertTrue(view["policy"]["bucket_is_projection_only"])

    def test_closed_rows_stay_in_source_but_are_excluded_from_active_view_by_default(self) -> None:
        active = compile_relationship_agenda_view(fixture(), generated_at="2026-09-22T23:00:00Z")
        full = compile_relationship_agenda_view(
            fixture(),
            generated_at="2026-09-22T23:00:00Z",
            include_closed=True,
        )
        active_ids = {item["id"] for item in active["items"]}
        self.assertNotIn("agenda:ag_done", active_ids)
        self.assertNotIn("agenda:ag_drop", active_ids)
        done = next(item for item in full["items"] if item["id"] == "agenda:ag_done")
        dropped = next(item for item in full["items"] if item["id"] == "agenda:ag_drop")
        self.assertEqual(done["bucket"], "CLOSED")
        self.assertEqual(done["resolution_note"], "Answered.")
        self.assertEqual(dropped["source_state"], "DROP")
        self.assertEqual(dropped["bucket"], "CLOSED")

    def test_duplicate_ids_fail_closed(self) -> None:
        bad = pd.concat([fixture(), fixture().iloc[[0]]], ignore_index=True)
        with self.assertRaises(FrontierViewError):
            compile_relationship_agenda_view(bad)

    def test_unknown_source_state_is_preserved_and_visible_as_warning(self) -> None:
        data = fixture().iloc[[0]].copy()
        data.loc[data.index[0], "state"] = "MAYBE"
        view = compile_relationship_agenda_view(data, generated_at="2026-09-22T23:00:00Z")
        self.assertEqual(view["items"][0]["source_state"], "MAYBE")
        self.assertEqual(view["items"][0]["bucket"], "OTHER")
        self.assertEqual(len(view["warnings"]), 1)

    def test_failed_publish_does_not_replace_last_known_good(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = OfficeConfig("creds.json", "sheet", root)
            with patch("office_runtime.office.frontier_view.read_sheet_values", return_value=fixture()):
                first = publish_relationship_agenda_view(
                    cfg,
                    run_id="run-1",
                    generated_at="2026-09-22T23:00:00Z",
                )
            before = (root / "frontier" / "v1" / "current.json").read_text(encoding="utf-8")
            export = root / "render" / "frontier.view.v1.json"
            with patch("office_runtime.office.frontier_view.read_sheet_values", side_effect=RuntimeError("sheet unavailable")):
                with self.assertRaises(RuntimeError):
                    publish_relationship_agenda_view(cfg, run_id="run-2", export_path=export)
            self.assertEqual((root / "frontier" / "v1" / "current.json").read_text(encoding="utf-8"), before)
            self.assertFalse(export.exists())
            self.assertTrue(Path(first["view_path"]).is_file())

    def test_successful_publish_can_atomically_export_renderer_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = OfficeConfig("creds.json", "sheet", root)
            export = root / "render" / "frontier.view.v1.json"
            with patch("office_runtime.office.frontier_view.read_sheet_values", return_value=fixture()):
                publish_relationship_agenda_view(
                    cfg,
                    run_id="run-1",
                    export_path=export,
                    generated_at="2026-09-22T23:00:00Z",
                )
            view = json.loads(export.read_text(encoding="utf-8"))
            self.assertEqual(view["schema_version"], "frontier.view.v1")
            self.assertEqual(view["counts"]["items"], 2)


if __name__ == "__main__":
    unittest.main()
