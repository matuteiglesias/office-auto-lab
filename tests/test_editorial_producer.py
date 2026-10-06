from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from office_runtime.editorial import producer
from office_runtime.editorial.contracts import ActivityEvidence
from office_runtime.editorial.intelligence.interfaces import IntelligenceResult
from office_runtime.editorial.run_bundle import validate_run_bundle


class _FakeGitHub:
    def __init__(self, transport) -> None:
        self.transport = transport

    def fetch_pull_request(self, repository_ref, number, *, observed_at=None):
        return ActivityEvidence(
            evidence_id=f"github:{repository_ref}:pr:{number}:merge:abc123",
            source_kind="github_pr",
            source_ref=f"https://github.com/{repository_ref}/pull/{number}",
            observed_at=observed_at,
            event_at="2026-10-06T10:00:00Z",
            status="merged",
            title="Preserve failure provenance across retries",
            summary="A completed change keeps upstream and internal failures distinct.",
            repository_ref=repository_ref,
            visibility="public",
            public_eligibility="eligible",
            artifact_refs=(f"https://github.com/{repository_ref}/pull/{number}",),
        )


class _FakeIntelligence:
    def run_story(self, *, story, evidence_by_id, context, policy, generated_at):
        evidence_id = story["evidence_refs"][0]
        angle = {
            "schema_version": "office_runtime.editorial.angle.v1",
            "angle_id": "angle:failure-provenance",
            "story_id": story["story_id"],
            "angle_type": "lesson",
            "claim": "Retries need failure provenance, not just another attempt.",
            "tension_or_hook": "Retrying everything hides the actual fault boundary.",
            "transferable_lesson": "Classify failure before retrying.",
            "evidence_refs": [evidence_id],
            "audience": ["software engineers"],
            "career_signals": ["reliability"],
            "why_interesting": "Recovery semantics depend on the failure boundary.",
            "risk_class": "low",
            "proof_object_refs": [],
            "required_status_wording": [],
            "counterpoint": None,
            "expiry_hint": None,
        }
        candidate = {
            "schema_version": "office_runtime.editorial.candidate.v1",
            "candidate_id": "cand:failure-provenance",
            "profile_id": "dev",
            "text": "Retries need failure provenance, not just another attempt.",
            "risk_class": "low",
            "evidence_refs": [evidence_id],
            "work_refs": [f"https://github.com/{story['repository_refs'][0]}/pull/123"],
            "story_id": story["story_id"],
            "angle_id": angle["angle_id"],
            "candidate_family": "LESSON",
            "semantic_fingerprint": "sem:failure-provenance",
            "language": "en",
            "topic_tags": ["reliability"],
            "career_signals": ["reliability"],
            "proof_object_refs": [],
            "freshness_class": "recent",
            "generated_at": generated_at,
            "expires_at": None,
            "machine_disposition": "stage",
            "quality": {
                "evidence": 4,
                "specificity": 4,
                "external_usefulness": 4,
                "novelty": 3,
                "professional_signal": 4,
            },
            "disclosure_risk": "pass",
            "repetition_risk": "pass",
            "status_truth_risk": "pass",
            "claim": angle["claim"],
            "source_event_refs": [evidence_id],
            "repository_refs": list(story["repository_refs"]),
        }
        return IntelligenceResult(
            angles=(angle,),
            judgments=(),
            candidates=(candidate,),
            provider_runs=({
                "stage": "angle_producer",
                "provider": "fake",
                "model": "fixture",
                "duration_ms": 1,
            },),
        )


class EditorialProducerTests(unittest.TestCase):
    def test_exact_pr_composes_valid_bundle_without_reimplementing_staging(self) -> None:
        env = {
            "EDITORIAL_ANGLE_MODEL": "fixture-model",
            "EDITORIAL_JUDGE_MODEL": "fixture-model",
        }
        with patch.dict(os.environ, env, clear=False), \
                patch.object(producer, "GitHubEvidenceClient", _FakeGitHub), \
                patch.object(producer, "build_adk_editorial_intelligence", lambda **_: _FakeIntelligence()):
            bundle = producer.produce_bundle({
                "profile_id": "dev",
                "pr_ref": "example/project#123",
                "since": None,
                "until": None,
                "date": None,
                "lookback_hours": None,
            })

        validated = validate_run_bundle(bundle)
        self.assertEqual(validated["retrieval"]["mode"], "exact_pr")
        self.assertEqual(validated["retrieval"]["pr_ref"], "example/project#123")
        self.assertEqual(validated["policy"]["authority"], "weekly-ops-governance")
        self.assertEqual(validated["batch"]["candidate_ids"], ["cand:failure-provenance"])
        self.assertEqual(validated["status"], "DEGRADED_INVENTORY")


if __name__ == "__main__":
    unittest.main()
