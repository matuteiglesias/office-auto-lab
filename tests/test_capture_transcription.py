from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from office_runtime.capture.lifecycle import compile_lifecycle
from office_runtime.capture.transcription import transcribe_event, transcribe_pending


class _FakeTranscriptions:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        return SimpleNamespace(text="Audio transcript", usage={"type": "duration", "seconds": 41.2})


class _FailingTranscriptions:
    def create(self, **kwargs):
        raise RuntimeError("api unavailable")


class _FailingClient:
    def __init__(self) -> None:
        self.audio = SimpleNamespace(transcriptions=_FailingTranscriptions())


class _FakeClient:
    def __init__(self) -> None:
        self.audio = SimpleNamespace(transcriptions=_FakeTranscriptions())


class CaptureTranscriptionTests(unittest.TestCase):
    def test_transcribes_one_event_to_processing_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            (inbox / "human_feedback").mkdir(parents=True)
            (inbox / "human_feedback_audio" / "2026-06-22").mkdir(parents=True)
            (inbox / "human_feedback" / "2026-06-22.jsonl").write_text(
                json.dumps({"event_id": "cap_001", "created_at": "2026-06-22T00:00:00Z"}) + "\n",
                encoding="utf-8",
            )
            (inbox / "human_feedback_audio" / "2026-06-22" / "cap_001.webm").write_bytes(b"webm")

            client = _FakeClient()
            result = transcribe_event(inbox, "cap_001", client=client, now="2026-06-22T00:01:00Z")

            self.assertEqual(result["status"], "ok")
            self.assertEqual(client.audio.transcriptions.calls, 1)
            out = inbox / "capture_processing" / "2026-06-22.jsonl"
            row = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(row["event_type"], "capture.transcribed")
            self.assertEqual(row["source_event_id"], "cap_001")
            self.assertEqual(row["status"], "transcribed")
            self.assertEqual(row["transcript"]["text"], "Audio transcript")
            self.assertEqual(row["transcript"]["model"], "gpt-4o-mini-transcribe")
            self.assertEqual(row["usage"], {"type": "duration", "seconds": 41.2})

            lifecycle = compile_lifecycle(inbox, generated_at="2026-06-22T00:02:00Z")
            self.assertEqual(lifecycle["captures"][0]["status"], "transcribed")
            self.assertEqual(lifecycle["captures"][0]["transcript"]["text"], "Audio transcript")

    def test_transcribe_pending_skips_already_transcribed_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            (inbox / "human_feedback").mkdir(parents=True)
            (inbox / "human_feedback_audio" / "2026-06-22").mkdir(parents=True)
            rows = [
                {"event_id": "cap_001", "created_at": "2026-06-22T00:00:00Z"},
                {"event_id": "cap_002", "created_at": "2026-06-22T00:01:00Z"},
            ]
            (inbox / "human_feedback" / "2026-06-22.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
            )
            for event_id in ("cap_001", "cap_002"):
                (inbox / "human_feedback_audio" / "2026-06-22" / f"{event_id}.webm").write_bytes(b"webm")
            (inbox / "capture_processing").mkdir()
            (inbox / "capture_processing" / "2026-06-22.jsonl").write_text(
                json.dumps({"event_type": "capture.transcribed", "source_event_id": "cap_001"}) + "\n",
                encoding="utf-8",
            )

            client = _FakeClient()
            result = transcribe_pending(inbox, limit=5, client=client, now="2026-06-22T00:02:00Z")

            self.assertEqual(result["processed"], 1)
            self.assertEqual(result["results"][0]["event_id"], "cap_002")
            self.assertEqual(client.audio.transcriptions.calls, 1)


    def test_transcribe_event_skips_duplicate_unless_forced(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            (inbox / "human_feedback").mkdir(parents=True)
            (inbox / "human_feedback_audio" / "2026-06-22").mkdir(parents=True)
            (inbox / "human_feedback" / "2026-06-22.jsonl").write_text(
                json.dumps({"event_id": "cap_003", "created_at": "2026-06-22T00:00:00Z"}) + "\n",
                encoding="utf-8",
            )
            (inbox / "human_feedback_audio" / "2026-06-22" / "cap_003.webm").write_bytes(b"webm")
            (inbox / "capture_processing").mkdir()
            (inbox / "capture_processing" / "2026-06-22.jsonl").write_text(
                json.dumps({"event_type": "capture.transcribed", "source_event_id": "cap_003"}) + "\n",
                encoding="utf-8",
            )

            client = _FakeClient()
            skipped = transcribe_event(inbox, "cap_003", client=client)
            forced = transcribe_event(inbox, "cap_003", client=client, force=True)

            self.assertEqual(skipped["status"], "skipped")
            self.assertEqual(forced["status"], "ok")
            self.assertEqual(client.audio.transcriptions.calls, 1)

    def test_rejects_unsupported_or_oversized_audio_before_api_call(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            (inbox / "human_feedback").mkdir(parents=True)
            (inbox / "human_feedback_audio" / "2026-06-22").mkdir(parents=True)
            (inbox / "human_feedback" / "2026-06-22.jsonl").write_text(
                json.dumps({"event_id": "cap_004", "created_at": "2026-06-22T00:00:00Z"}) + "\n",
                encoding="utf-8",
            )
            (inbox / "human_feedback_audio" / "2026-06-22" / "cap_004.txt").write_bytes(b"not audio")

            client = _FakeClient()
            unsupported = transcribe_event(inbox, "cap_004", client=client)
            (inbox / "human_feedback_audio" / "2026-06-22" / "cap_004.txt").unlink()
            (inbox / "human_feedback_audio" / "2026-06-22" / "cap_004.webm").write_bytes(b"too large")
            oversized = transcribe_event(inbox, "cap_004", client=client, max_bytes=3)

            self.assertEqual(unsupported["status"], "error")
            self.assertIn("unsupported audio extension", unsupported["error"])
            self.assertEqual(oversized["status"], "error")
            self.assertIn("audio too large", oversized["error"])
            self.assertEqual(client.audio.transcriptions.calls, 0)

    def test_appends_failure_event_on_transcription_api_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            (inbox / "human_feedback").mkdir(parents=True)
            (inbox / "human_feedback_audio" / "2026-06-22").mkdir(parents=True)
            (inbox / "human_feedback" / "2026-06-22.jsonl").write_text(
                json.dumps({"event_id": "cap_005", "created_at": "2026-06-22T00:00:00Z"}) + "\n",
                encoding="utf-8",
            )
            (inbox / "human_feedback_audio" / "2026-06-22" / "cap_005.webm").write_bytes(b"webm")

            result = transcribe_event(inbox, "cap_005", client=_FailingClient(), now="2026-06-22T00:01:00Z")

            self.assertEqual(result["status"], "error")
            row = json.loads((inbox / "capture_processing" / "2026-06-22.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(row["event_type"], "capture.transcription_failed")
            self.assertEqual(row["source_event_id"], "cap_005")


if __name__ == "__main__":
    unittest.main()
