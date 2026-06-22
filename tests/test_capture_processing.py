from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from office_runtime.capture.lifecycle import compile_lifecycle
from office_runtime.capture.processing import (
    REINGEST_SCHEMA,
    artifactize_event,
    process_event,
    propose_reingest_event,
    route_event,
)


class FakeResponses:
    def __init__(self, outputs: list[dict]):
        self.outputs = outputs
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {"output_text": json.dumps(self.outputs.pop(0))}


class FakeClient:
    def __init__(self, outputs: list[dict]):
        self.responses = FakeResponses(outputs)


class FakeTranscriptions:
    def create(self, **kwargs):
        return {"text": "Reply to recruiter. Do not redesign the CRM.", "duration": 2.5}


class FakeAudio:
    def __init__(self):
        self.transcriptions = FakeTranscriptions()


class FakeTranscriptionClient:
    def __init__(self):
        self.audio = FakeAudio()


def assert_strict_object_schema(testcase: unittest.TestCase, schema: dict, path: str = "$") -> None:
    if schema.get("type") == "object":
        testcase.assertIn("properties", schema, path)
        testcase.assertEqual(schema.get("additionalProperties"), False, path)
        properties = schema["properties"]
        testcase.assertEqual(set(schema.get("required", [])), set(properties), path)
        for key, child in properties.items():
            if isinstance(child, dict):
                assert_strict_object_schema(testcase, child, f"{path}.{key}")


class StrictSchemaFakeResponses(FakeResponses):
    def create(self, **kwargs):
        schema = kwargs["text"]["format"]["schema"]
        assert_strict_object_schema(unittest.TestCase(), schema)
        return super().create(**kwargs)


class StrictSchemaFakeClient(FakeClient):
    def __init__(self, outputs: list[dict]):
        self.responses = StrictSchemaFakeResponses(outputs)


def seed_transcribed_capture(inbox: Path) -> None:
    (inbox / "human_feedback").mkdir(parents=True)
    (inbox / "capture_processing").mkdir(parents=True)
    (inbox / "human_feedback" / "2026-06-22.jsonl").write_text(
        json.dumps({
            "event_id": "cap_001",
            "created_at": "2026-06-22T00:00:00Z",
            "project_id": "52.3",
            "project_title": "Job Search Management",
            "queue_key": "focus",
        }) + "\n",
        encoding="utf-8",
    )
    (inbox / "capture_processing" / "2026-06-22.jsonl").write_text(
        json.dumps({
            "event_type": "capture.transcribed",
            "source_event_id": "cap_001",
            "status": "transcribed",
            "ts": "2026-06-22T00:01:00Z",
            "transcript": {"text": "Reply to recruiter. Do not redesign the CRM.", "model": "fixture"},
        }) + "\n",
        encoding="utf-8",
    )


class CaptureProcessingTests(unittest.TestCase):
    def test_reingest_schema_is_strict_recursively(self) -> None:
        assert_strict_object_schema(self, REINGEST_SCHEMA)

    def test_propose_reingest_submits_strict_schema_to_responses_api(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            seed_transcribed_capture(inbox)
            client = FakeClient([
                {
                    "capture_mode": "Re-entry",
                    "lane": "Projects / Ops",
                    "artifact_type": "Next Pointer",
                    "routing_sentence": "This is Re-entry capture for Projects / Ops.",
                    "confidence": "medium",
                },
                {
                    "type": "next_pointer",
                    "text": "Reply to recruiter. Do not redesign the CRM.",
                    "confidence": "medium",
                    "evidence_excerpt": "Reply to recruiter",
                },
            ])
            self.assertEqual(route_event(inbox, "cap_001", client=client)["status"], "ok")
            self.assertEqual(artifactize_event(inbox, "cap_001", client=client)["status"], "ok")

            strict_client = StrictSchemaFakeClient([
                {
                    "target_surface": "carry_state",
                    "target_id": "52.3",
                    "proposed_delta": {"next": "Reply to recruiter", "needs": "Execution only"},
                    "requires_human_approval": True,
                }
            ])
            result = propose_reingest_event(inbox, "cap_001", client=strict_client, now="2026-06-22T00:04:00Z")

            self.assertEqual(result["status"], "ok")
            schema = strict_client.responses.calls[0]["text"]["format"]["schema"]
            self.assertIn("proposed_delta", schema["properties"])
            self.assertIn("proposed_delta", schema["required"])
            self.assertEqual(set(schema["properties"]["proposed_delta"]["required"]), {"next", "needs"})

    def test_routes_artifactizes_and_proposes_reingest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            seed_transcribed_capture(inbox)
            client = FakeClient([
                {
                    "capture_mode": "Re-entry",
                    "lane": "Projects / Ops",
                    "artifact_type": "Next Pointer",
                    "routing_sentence": "This is Re-entry capture for Projects / Ops; it should become a Next Pointer.",
                    "confidence": "medium",
                },
                {
                    "type": "next_pointer",
                    "text": "Reply to recruiter. Do not redesign the CRM.",
                    "confidence": "medium",
                    "evidence_excerpt": "Reply to recruiter",
                },
                {
                    "target_surface": "carry_state",
                    "target_id": "52.3",
                    "proposed_delta": {"next": "Reply to recruiter", "needs": "Execution only"},
                    "requires_human_approval": True,
                },
            ])

            self.assertEqual(route_event(inbox, "cap_001", client=client, now="2026-06-22T00:02:00Z")["status"], "ok")
            self.assertEqual(artifactize_event(inbox, "cap_001", client=client, now="2026-06-22T00:03:00Z")["status"], "ok")
            self.assertEqual(propose_reingest_event(inbox, "cap_001", client=client, now="2026-06-22T00:04:00Z")["status"], "ok")

            lifecycle = compile_lifecycle(inbox)
            capture = lifecycle["captures"][0]
            self.assertEqual(capture["status"], "pending_reingest")
            self.assertEqual(capture["routing"]["artifact_type"], "Next Pointer")
            self.assertEqual(capture["artifact_candidate"]["candidate_type"], "next_pointer")
            self.assertEqual(capture["reingest_candidate"]["proposed_delta"]["next"], "Reply to recruiter")
            self.assertEqual(len(client.responses.calls), 3)
            self.assertEqual(client.responses.calls[0]["text"]["format"]["type"], "json_schema")

    def test_process_runs_missing_steps_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            (inbox / "human_feedback").mkdir(parents=True)
            (inbox / "human_feedback_audio" / "2026-06-22").mkdir(parents=True)
            (inbox / "human_feedback" / "2026-06-22.jsonl").write_text(
                json.dumps({"event_id": "cap_002", "created_at": "2026-06-22T00:00:00Z"}) + "\n",
                encoding="utf-8",
            )
            (inbox / "human_feedback_audio" / "2026-06-22" / "cap_002.webm").write_bytes(b"audio")
            client = FakeClient([
                {"capture_mode": "Re-entry", "lane": "Projects / Ops", "artifact_type": "Next Pointer", "routing_sentence": "Route it.", "confidence": "medium"},
                {"type": "next_pointer", "text": "Reply to recruiter.", "confidence": "medium", "evidence_excerpt": "Reply"},
                {"target_surface": "carry_state", "target_id": "", "proposed_delta": {"next": "Reply to recruiter", "needs": None}, "requires_human_approval": True},
            ])

            result = process_event(
                inbox,
                "cap_002",
                transcription_client=FakeTranscriptionClient(),
                client=client,
                now="2026-06-22T00:01:00Z",
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual([step["step"] for step in result["steps"]], ["transcribe", "route", "artifactize", "propose_reingest"])

    def test_invalid_structured_output_appends_failure_event(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            seed_transcribed_capture(inbox)
            client = FakeClient([{
                "capture_mode": "Re-entry",
                "lane": "Projects / Ops",
                "artifact_type": "Next Pointer",
                "routing_sentence": "Missing confidence.",
            }])

            result = route_event(inbox, "cap_001", client=client, now="2026-06-22T00:02:00Z")

            self.assertEqual(result["status"], "error")
            lines = (inbox / "capture_processing" / "2026-06-22.jsonl").read_text(encoding="utf-8").strip().splitlines()
            failed = json.loads(lines[-1])
            self.assertEqual(failed["event_type"], "capture.failed")
            self.assertEqual(failed["failed_stage"], "capture.routed")

    def test_dry_run_does_not_append_processing_event(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            seed_transcribed_capture(inbox)
            before = (inbox / "capture_processing" / "2026-06-22.jsonl").read_text(encoding="utf-8")
            client = FakeClient([{
                "capture_mode": "Re-entry",
                "lane": "Projects / Ops",
                "artifact_type": "Next Pointer",
                "routing_sentence": "Route it.",
                "confidence": "medium",
            }])

            result = route_event(inbox, "cap_001", client=client, dry_run=True)

            self.assertEqual(result["status"], "ok")
            self.assertTrue(result["dry_run"])
            self.assertEqual((inbox / "capture_processing" / "2026-06-22.jsonl").read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
