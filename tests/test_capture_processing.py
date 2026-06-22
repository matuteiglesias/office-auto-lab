from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from office_runtime.capture.lifecycle import compile_lifecycle
from office_runtime.capture.processing import (
    ARTIFACT_SCHEMA,
    REINGEST_SCHEMA,
    ROUTING_SCHEMA,
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


def seed_transcribed_capture(inbox: Path, transcript_text: str = "Reply to recruiter. Do not redesign the CRM.") -> None:
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
            "transcript": {"text": transcript_text, "model": "fixture"},
        }) + "\n",
        encoding="utf-8",
    )


class CaptureProcessingTests(unittest.TestCase):
    def test_schemas_are_strict_recursively(self) -> None:
        for schema in (ROUTING_SCHEMA, ARTIFACT_SCHEMA, REINGEST_SCHEMA):
            assert_strict_object_schema(self, schema)

    def test_semantic_fields_are_enum_constrained(self) -> None:
        self.assertIn("enum", ROUTING_SCHEMA["properties"]["capture_mode"])
        self.assertNotIn("Capture", ROUTING_SCHEMA["properties"]["capture_mode"]["enum"])
        self.assertIn("enum", ROUTING_SCHEMA["properties"]["artifact_type"])
        self.assertNotIn("Note", ROUTING_SCHEMA["properties"]["artifact_type"]["enum"])
        self.assertIn("enum", ARTIFACT_SCHEMA["properties"]["type"])
        self.assertNotIn("object", ARTIFACT_SCHEMA["properties"]["type"]["enum"])
        self.assertIn("enum", REINGEST_SCHEMA["properties"]["target_surface"])
        self.assertNotIn("queue", REINGEST_SCHEMA["properties"]["target_surface"]["enum"])
        self.assertEqual(ROUTING_SCHEMA["properties"]["routing_sentence"]["minLength"], 1)

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
                    "target_id": "cap_001",
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
                    "target_id": "cap_001",
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
            self.assertEqual(capture["reingest_candidate"]["target_id"], "52.3")
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

    def test_empty_routing_sentence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            seed_transcribed_capture(inbox)
            client = FakeClient([{
                "capture_mode": "Re-entry",
                "lane": "Projects / Ops",
                "artifact_type": "Next Pointer",
                "routing_sentence": "",
                "confidence": "medium",
            }])

            result = route_event(inbox, "cap_001", client=client)

            self.assertEqual(result["status"], "error")
            self.assertIn("routing_sentence", result["error"])

    def test_invalid_artifact_candidate_type_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            seed_transcribed_capture(inbox)
            client = FakeClient([
                {"capture_mode": "Re-entry", "lane": "Projects / Ops", "artifact_type": "Next Pointer", "routing_sentence": "Route to next pointer.", "confidence": "medium"},
                {"type": "object", "text": "Reply to recruiter.", "confidence": "medium", "evidence_excerpt": "Reply"},
            ])

            self.assertEqual(route_event(inbox, "cap_001", client=client)["status"], "ok")
            result = artifactize_event(inbox, "cap_001", client=client)

            self.assertEqual(result["status"], "error")
            self.assertIn("$.type", result["error"])

    def test_realistic_capture_examples_map_to_specific_ontology(self) -> None:
        scenarios = [
            (
                "For this job search project, next block is reply to CloudX about the interview window.",
                {"capture_mode": "Re-entry", "lane": "Projects / Ops", "artifact_type": "Next Pointer", "routing_sentence": "This updates the linked project next pointer with a reply action.", "confidence": "high"},
                {"type": "next_pointer", "text": "Reply to CloudX about the interview window.", "confidence": "high", "evidence_excerpt": "reply to CloudX"},
                {"target_surface": "carry_state", "target_id": "wrong", "proposed_delta": {"next": "Reply to CloudX about the interview window", "needs": "Execution time to draft and send the reply"}, "requires_human_approval": True},
                "carry_state",
                "next_pointer",
            ),
            (
                "This project should be parked until Friday because Eric has not replied yet.",
                {"capture_mode": "Correction", "lane": "Projects / Ops", "artifact_type": "Correction", "routing_sentence": "This corrects the linked project state by parking it until Friday.", "confidence": "high"},
                {"type": "correction", "text": "Park this project until Friday because Eric has not replied.", "confidence": "high", "evidence_excerpt": "parked until Friday"},
                {"target_surface": "front_registry", "target_id": "wrong", "proposed_delta": {"next": "Park project until Friday", "needs": "Human review of parked status/date"}, "requires_human_approval": True},
                "front_registry",
                "correction",
            ),
            (
                "Remember that this requires reading Eric's email first before drafting the response.",
                {"capture_mode": "Context Note", "lane": "Projects / Ops", "artifact_type": "Support Context", "routing_sentence": "This adds support context needed before executing the reply.", "confidence": "high"},
                {"type": "support_context", "text": "Read Eric's email before drafting the response.", "confidence": "high", "evidence_excerpt": "reading Eric's email first"},
                {"target_surface": "support_context", "target_id": "wrong", "proposed_delta": {"next": "Read Eric's email before drafting the response", "needs": "Access to Eric's email context"}, "requires_human_approval": True},
                "support_context",
                "support_context",
            ),
            (
                "Make a 25 minute block to send the reply and log the follow-up.",
                {"capture_mode": "Work Block Request", "lane": "Projects / Ops", "artifact_type": "Work Block Candidate", "routing_sentence": "This asks for a bounded work block on the linked project.", "confidence": "high"},
                {"type": "work_block_candidate_stub", "text": "25 minute block to send the reply and log the follow-up.", "confidence": "high", "evidence_excerpt": "25 minute block"},
                {"target_surface": "work_block_candidate_stub", "target_id": "wrong", "proposed_delta": {"next": "Send the reply and log the follow-up", "needs": "25 minute focus block"}, "requires_human_approval": True},
                "work_block_candidate_stub",
                "work_block_candidate_stub",
            ),
        ]
        for transcript, routing, artifact, reingest, target_surface, candidate_type in scenarios:
            with self.subTest(transcript=transcript), tempfile.TemporaryDirectory() as td:
                inbox = Path(td) / "inbox"
                seed_transcribed_capture(inbox, transcript)
                client = FakeClient([routing, artifact, reingest])

                self.assertEqual(route_event(inbox, "cap_001", client=client)["status"], "ok")
                self.assertEqual(artifactize_event(inbox, "cap_001", client=client)["status"], "ok")
                self.assertEqual(propose_reingest_event(inbox, "cap_001", client=client)["status"], "ok")

                capture = compile_lifecycle(inbox)["captures"][0]
                self.assertEqual(capture["artifact_candidate"]["candidate_type"], candidate_type)
                self.assertEqual(capture["reingest_candidate"]["target_surface"], target_surface)
                self.assertEqual(capture["reingest_candidate"]["target_id"], "52.3")
                self.assertNotEqual(capture["reingest_candidate"]["proposed_delta"]["next"], "52.3")

    def test_low_information_capture_uses_none_target_and_null_delta(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            seed_transcribed_capture(inbox)
            client = FakeClient([
                {"capture_mode": "Low Information", "lane": "Unknown", "artifact_type": "Discard Suggestion", "routing_sentence": "This is a microphone test with no actionable office update.", "confidence": "high"},
                {"type": "discard_suggestion", "text": "No actionable office update was found.", "confidence": "high", "evidence_excerpt": "Prueba, prueba, 1, 2, 3"},
                {"target_surface": "none", "target_id": "52.3", "proposed_delta": {"next": "52.3", "needs": "none"}, "requires_human_approval": True},
            ])

            self.assertEqual(route_event(inbox, "cap_001", client=client)["status"], "ok")
            self.assertEqual(artifactize_event(inbox, "cap_001", client=client)["status"], "ok")
            self.assertEqual(propose_reingest_event(inbox, "cap_001", client=client)["status"], "ok")

            capture = compile_lifecycle(inbox)["captures"][0]
            self.assertEqual(capture["routing"]["capture_mode"], "Low Information")
            self.assertEqual(capture["artifact_candidate"]["candidate_type"], "discard_suggestion")
            self.assertEqual(capture["reingest_candidate"]["target_surface"], "none")
            self.assertEqual(capture["reingest_candidate"]["target_id"], "")
            self.assertIsNone(capture["reingest_candidate"]["proposed_delta"]["next"])
            self.assertIsNone(capture["reingest_candidate"]["proposed_delta"]["needs"])


if __name__ == "__main__":
    unittest.main()
