from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from office_runtime.office.generation_v2 import compile_generation_from_frames
from tests.test_generation_v2 import frames


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class GenerationRunRecordTests(unittest.TestCase):
    def test_published_generation_has_matching_run_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = compile_generation_from_frames(frames(), out_root=root, run_id="run-1", trigger="scheduled")
            record = read_json(root / "v2" / "run_records" / "run-1.json")
            current = read_json(root / "v2" / "current.json")
            self.assertEqual(record["status"], "SUCCEEDED")
            self.assertEqual(record["publication_status"], "PUBLISHED")
            self.assertEqual(record["trigger"], "scheduled")
            self.assertEqual(record["manifest_digest"], result["manifest"]["manifest_digest"])
            self.assertEqual(current["manifest_digest"], record["manifest_digest"])
            self.assertEqual(record["stage_results"]["invariants"]["status"], "OK")
            self.assertEqual(record["stage_results"]["publication"]["status"], "OK")

    def test_failed_generation_leaves_failed_record_without_replacing_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compile_generation_from_frames(frames(), out_root=root, run_id="run-1")
            current_before = read_json(root / "v2" / "current.json")
            with patch("office_runtime.office.generation_v2.compile_principal_brief", side_effect=RuntimeError("principal exploded")):
                with self.assertRaises(RuntimeError):
                    compile_generation_from_frames(frames(), out_root=root, run_id="run-2", trigger="scheduled")
            current_after = read_json(root / "v2" / "current.json")
            record = read_json(root / "v2" / "run_records" / "run-2.json")
            self.assertEqual(current_after, current_before)
            self.assertEqual(record["status"], "FAILED")
            self.assertEqual(record["publication_status"], "NOT_PUBLISHED")
            self.assertEqual(record["failures"][0]["stage"], "principal")
            self.assertIn("principal exploded", record["failures"][0]["message"])

    def test_shadow_run_is_recorded_but_does_not_create_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compile_generation_from_frames(frames(), out_root=root, run_id="shadow-1", publish=False, trigger="shadow-check")
            record = read_json(root / "v2" / "run_records" / "shadow-1.json")
            self.assertEqual(record["status"], "SUCCEEDED")
            self.assertEqual(record["publication_status"], "SHADOW")
            self.assertEqual(record["stage_results"]["publication"]["status"], "SKIPPED")
            self.assertFalse((root / "v2" / "current.json").exists())


if __name__ == "__main__":
    unittest.main()
