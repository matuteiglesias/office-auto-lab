from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from office_runtime.capture.lifecycle import compile_and_write, compile_lifecycle


class CaptureLifecycleTests(unittest.TestCase):
    def test_merges_raw_processing_and_reingest_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = root / "inbox"
            (inbox / "human_feedback").mkdir(parents=True)
            (inbox / "capture_processing").mkdir(parents=True)
            (inbox / "reingest_candidates").mkdir(parents=True)

            (inbox / "human_feedback" / "2026-06-22.jsonl").write_text(
                json.dumps({
                    "event_id": "cap_001",
                    "created_at": "2026-06-22T00:00:00Z",
                    "project_id": "52.3",
                    "project_title": "Job Search Management",
                    "queue_key": "focus",
                    "audio_path": "inbox/human_feedback_audio/2026-06-22/cap_001.webm",
                    "human_note": "Please turn this into a bounded follow-up.",
                }) + "\n",
                encoding="utf-8",
            )
            (inbox / "capture_processing" / "2026-06-22.jsonl").write_text(
                "\n".join([
                    json.dumps({
                        "source_event_id": "cap_001",
                        "stage": "capture.transcribed",
                        "ts": "2026-06-22T00:01:00Z",
                        "status": "ok",
                        "transcript": "Create a small follow-up block for the job search queue.",
                        "model": "dry-run-fixture",
                    }),
                    json.dumps({
                        "source_event_id": "cap_001",
                        "stage": "capture.routed",
                        "ts": "2026-06-22T00:02:00Z",
                        "status": "ok",
                        "route": "work_block_candidate_stub",
                        "rationale": "The capture asks for bounded work attached to a row.",
                    }),
                ]) + "\n",
                encoding="utf-8",
            )
            (inbox / "reingest_candidates" / "2026-06-22.jsonl").write_text(
                json.dumps({
                    "source_event_id": "cap_001",
                    "ts": "2026-06-22T00:03:00Z",
                    "candidate_type": "work_block_candidate_stub",
                    "candidate_ref": "inbox/capture_artifacts/2026-06-22/cap_001.md",
                    "reingest_candidate_id": "reingest_cap_001",
                    "summary": "Review a possible work block stub.",
                }) + "\n",
                encoding="utf-8",
            )

            lifecycle = compile_lifecycle(inbox, generated_at="2026-06-22T00:04:00Z")

            self.assertEqual(lifecycle["status_counts"]["pending_reingest"], 1)
            self.assertEqual(len(lifecycle["captures"]), 1)
            capture = lifecycle["captures"][0]
            self.assertEqual(capture["event_id"], "cap_001")
            self.assertEqual(capture["status"], "pending_reingest")
            self.assertEqual(capture["target"]["project_id"], "52.3")
            self.assertEqual(capture["transcript"]["text"], "Create a small follow-up block for the job search queue.")
            self.assertEqual(capture["routing"]["route"], "work_block_candidate_stub")
            self.assertEqual(capture["reingest_candidate"]["reingest_candidate_id"], "reingest_cap_001")
            self.assertEqual(capture["events"], [
                "capture.created",
                "capture.transcribed",
                "capture.routed",
                "capture.reingest_candidate.created",
            ])

    def test_writes_json_markdown_and_csv_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = root / "inbox"
            out = root / "artifacts" / "latest"
            (inbox / "human_feedback").mkdir(parents=True)
            (inbox / "human_feedback" / "2026-06-22.jsonl").write_text(
                json.dumps({"event_id": "cap_002", "created_at": "2026-06-22T01:00:00Z"}) + "\n",
                encoding="utf-8",
            )

            result = compile_and_write(inbox, out, generated_at="2026-06-22T01:01:00Z")

            self.assertEqual(result["status"], "ok")
            json_path = out / "capture_lifecycle.json"
            md_path = out / "capture_lifecycle.md"
            csv_path = out / "capture_lifecycle.csv"
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertIn("# Capture Lifecycle", md_path.read_text(encoding="utf-8"))
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["captures"][0]["event_id"], "cap_002")
            with csv_path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["status"], "pending_transcription")


if __name__ == "__main__":
    unittest.main()
