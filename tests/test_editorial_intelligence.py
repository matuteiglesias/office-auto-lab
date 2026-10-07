from __future__ import annotations

import subprocess
import sys
import unittest

from office_runtime.editorial.contracts import (
    STORY_CLUSTER_SCHEMA,
    ActivityEvidence,
    StoryCluster,
    validate_dev_candidate,
)
from office_runtime.editorial.intelligence.interfaces import EditorialIntelligence, ModelStageOutput
from office_runtime.editorial.intelligence.validation import IntelligenceContractError


DEV_PROFILE = {"profile_id": "dev", "strategy": "dev_projection"}


def evidence(eid: str, *, status: str = "merged", source_ref: str | None = None) -> dict:
    return {
        "evidence_id": eid,
        "source_ref": source_ref or f"https://github.com/example/repo/pull/{eid[-1]}",
        "status": status,
    }


def story(*refs: str, eligibility: str = "eligible", freshness: str = "recent") -> dict:
    return {
        "schema_version": STORY_CLUSTER_SCHEMA,
        "story_id": "story:abc",
        "evidence_refs": list(refs),
        "cluster_kind": "related_work" if len(refs) > 1 else "single_event",
        "working_summary": "Bounded reliability work",
        "freshness_class": freshness,
        "repository_refs": ["example/repo"],
        "public_eligibility": eligibility,
        "related_context_refs": [],
        "measured_results": [],
        "open_questions": [],
        "status_language_constraints": [],
    }


def angle(*refs: str, angle_type: str = "lesson", required: list[str] | None = None) -> dict:
    return {
        "angle_id": "angle:1",
        "story_id": "story:abc",
        "angle_type": angle_type,
        "claim": "Retries should preserve failure provenance instead of flattening every failure.",
        "tension_or_hook": "Retrying can hide the distinction between upstream and internal faults.",
        "transferable_lesson": "Keep failure classes explicit across retry boundaries.",
        "evidence_refs": list(refs),
        "audience": ["data engineers", "backend engineers"],
        "career_signals": ["reliability", "production Python"],
        "why_interesting": "The recovery mechanism depends on knowing which boundary failed.",
        "risk_class": "low",
        "required_status_wording": required or [],
    }


def decision(
    *refs: str,
    disposition: str = "stage",
    gates: dict | None = None,
    draft: str | None = None,
    expires_at: str | None = None,
) -> dict:
    return {
        "angle_id": "angle:1",
        "machine_disposition": disposition,
        "rationale": "Specific, supported, and externally useful.",
        "draft_text": draft or "Retries work better when failure provenance stays explicit across system boundaries.",
        "candidate_family": "lesson",
        "evidence_refs": list(refs),
        "risk_class": "low",
        "quality": {
            "evidence": 4,
            "specificity": 4,
            "external_usefulness": 4,
            "novelty": 3,
            "professional_signal": 4,
        },
        "gates": gates or {
            "disclosure_risk": "PASS",
            "repetition_risk": "PASS",
            "status_truth_risk": "PASS",
        },
        "topic_tags": ["reliability"],
        "language": "en",
        "expires_at": expires_at,
    }


class FakeProducer:
    def __init__(self, angles: list[dict]) -> None:
        self.angles = angles

    def produce(self, request):
        return ModelStageOutput(
            payload={"angles": self.angles},
            provider_run={"stage": "angle_producer", "provider": "fake"},
        )


class FakeJudge:
    def __init__(self, decisions: list[dict]) -> None:
        self.decisions = decisions

    def judge(self, request):
        return ModelStageOutput(
            payload={"decisions": self.decisions},
            provider_run={"stage": "editor_judge", "provider": "fake"},
        )


class EditorialIntelligenceTests(unittest.TestCase):
    def test_core_path_does_not_import_adk(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "import office_runtime.editorial.intelligence.batch; "
                    "import office_runtime.editorial.intelligence.interfaces; "
                    "import office_runtime.editorial.intelligence.validation; "
                    "assert 'google.adk' not in sys.modules"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_strong_story_survives_as_canonical_transferable_candidate(self) -> None:
        ev = {"ev:1": evidence("ev:1")}
        engine = EditorialIntelligence(
            FakeProducer([angle("ev:1")]),
            FakeJudge([decision("ev:1")]),
        )
        result = engine.run_story(
            story=story("ev:1"),
            evidence_by_id=ev,
            policy={"policy_ref": "policy@test"},
            generated_at="2026-10-06T12:00:00Z",
        )
        self.assertEqual(len(result.angles), 1)
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(validate_dev_candidate(candidate, DEV_PROFILE), candidate)
        self.assertEqual(candidate["candidate_family"], "LESSON")
        self.assertEqual(candidate["disclosure_risk"], "pass")
        self.assertIn("ev:1", candidate["evidence_refs"])
        self.assertEqual(candidate["quality"]["external_usefulness"], 4)
        self.assertNotIn("Added retry handling", candidate["text"])

    def test_canonical_story_and_evidence_dataclasses_cross_local_interface(self) -> None:
        ev = ActivityEvidence(
            evidence_id="ev:1",
            source_kind="github_pr",
            source_ref="https://github.com/example/repo/pull/1",
            observed_at="2026-10-06T12:00:00Z",
            event_at="2026-10-06T11:00:00Z",
            status="merged",
            title="Preserve retry provenance",
            summary="A bounded reliability change.",
            repository_ref="example/repo",
            visibility="public",
            public_eligibility="eligible",
        )
        st = StoryCluster(
            story_id="story:abc",
            evidence_refs=("ev:1",),
            cluster_kind="single_event",
            working_summary="Bounded reliability work",
            freshness_class="recent",
            repository_refs=("example/repo",),
            public_eligibility="eligible",
        )
        engine = EditorialIntelligence(
            FakeProducer([angle("ev:1")]),
            FakeJudge([decision("ev:1")]),
        )
        result = engine.run_story(
            story=st,
            evidence_by_id={"ev:1": ev},
            policy={"policy_ref": "policy@test"},
            generated_at="2026-10-06T12:00:00Z",
        )
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0]["work_refs"], [ev.source_ref])

    def test_zero_angle_abstention_is_success(self) -> None:
        engine = EditorialIntelligence(FakeProducer([]), FakeJudge([]))
        result = engine.run_story(
            story=story("ev:1"),
            evidence_by_id={"ev:1": evidence("ev:1")},
            policy={"policy_ref": "policy@test"},
        )
        self.assertEqual(result.angles, ())
        self.assertEqual(result.candidates, ())
        self.assertEqual(len(result.provider_runs), 1)

    def test_unsupported_angle_evidence_is_rejected_deterministically(self) -> None:
        bad = angle("ev:other")
        engine = EditorialIntelligence(FakeProducer([bad]), FakeJudge([]))
        with self.assertRaises(IntelligenceContractError):
            engine.run_story(
                story=story("ev:1"),
                evidence_by_id={"ev:1": evidence("ev:1")},
                policy={"policy_ref": "policy@test"},
            )

    def test_security_sensitive_story_cannot_stage_even_if_model_requests_it(self) -> None:
        gates = {
            "disclosure_risk": "FAIL",
            "repetition_risk": "PASS",
            "status_truth_risk": "PASS",
        }
        engine = EditorialIntelligence(
            FakeProducer([angle("ev:1")]),
            FakeJudge([decision("ev:1", gates=gates)]),
        )
        result = engine.run_story(
            story=story("ev:1", eligibility="restricted"),
            evidence_by_id={"ev:1": evidence("ev:1")},
            policy={"policy_ref": "policy@test"},
        )
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.judgments[0]["machine_disposition"], "drop")
        self.assertIn(
            "hard_gate:disclosure_risk",
            result.judgments[0]["deterministic_rejection_reasons"],
        )

    def test_in_progress_completion_language_is_rejected_deterministically(self) -> None:
        judged = decision("ev:1", draft="This shipped a reliable retry boundary.")
        engine = EditorialIntelligence(
            FakeProducer([angle("ev:1")]),
            FakeJudge([judged]),
        )
        result = engine.run_story(
            story=story("ev:1"),
            evidence_by_id={"ev:1": evidence("ev:1", status="in_progress")},
            policy={"policy_ref": "policy@test"},
        )
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.judgments[0]["gates"]["status_truth_risk"], "fail")

    def test_timely_candidate_without_expiry_is_dropped_not_fabricated(self) -> None:
        engine = EditorialIntelligence(
            FakeProducer([angle("ev:1")]),
            FakeJudge([decision("ev:1")]),
        )
        result = engine.run_story(
            story=story("ev:1", freshness="timely"),
            evidence_by_id={"ev:1": evidence("ev:1")},
            policy={"policy_ref": "policy@test"},
        )
        self.assertEqual(result.candidates, ())
        self.assertIn(
            "timely_candidate_missing_expiry",
            result.judgments[0]["deterministic_rejection_reasons"],
        )

    def test_force_one_safe_candidate_promotes_only_soft_rejection(self) -> None:
        judged = decision("ev:1", disposition="drop")
        judged["rationale"] = "Useful but below the normal editorial bar."
        engine = EditorialIntelligence(
            FakeProducer([angle("ev:1")]),
            FakeJudge([judged]),
            force_one_safe_candidate=True,
        )
        result = engine.run_story(
            story=story("ev:1"),
            evidence_by_id={"ev:1": evidence("ev:1")},
            policy={"policy_ref": "policy@test"},
            generated_at="2026-10-06T12:00:00Z",
        )
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertTrue(candidate["forced_pipeline_acceptance"])
        self.assertIn("FORCED_PIPELINE_ACCEPTANCE", candidate["editorial_warning"])
        self.assertEqual(candidate["machine_disposition"], "stage")
        self.assertEqual(result.judgments[0]["machine_disposition"], "stage")
        self.assertIn(
            "forced_pipeline_acceptance_soft_override",
            result.judgments[0]["deterministic_rejection_reasons"],
        )

    def test_force_one_safe_candidate_derives_bounded_expiry_for_timely_story(self) -> None:
        judged = decision("ev:1", disposition="drop")
        engine = EditorialIntelligence(
            FakeProducer([angle("ev:1")]),
            FakeJudge([judged]),
            force_one_safe_candidate=True,
        )
        result = engine.run_story(
            story=story("ev:1", freshness="timely"),
            evidence_by_id={"ev:1": evidence("ev:1")},
            policy={"policy_ref": "policy@test"},
            generated_at="2026-10-06T12:00:00Z",
        )
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0]["expires_at"], "2026-10-07T12:00:00Z")

    def test_force_one_safe_candidate_handles_empty_judge_decision_set(self) -> None:
        engine = EditorialIntelligence(
            FakeProducer([angle("ev:1")]),
            FakeJudge([]),
            force_one_safe_candidate=True,
        )
        result = engine.run_story(
            story=story("ev:1"),
            evidence_by_id={"ev:1": evidence("ev:1")},
            policy={"policy_ref": "policy@test"},
        )
        self.assertEqual(len(result.candidates), 1)
        self.assertTrue(result.candidates[0]["forced_pipeline_acceptance"])

    def test_force_one_safe_candidate_never_overrides_hard_gate(self) -> None:
        judged = decision(
            "ev:1",
            disposition="drop",
            gates={
                "disclosure_risk": "FAIL",
                "repetition_risk": "PASS",
                "status_truth_risk": "PASS",
            },
        )
        engine = EditorialIntelligence(
            FakeProducer([angle("ev:1")]),
            FakeJudge([judged]),
            force_one_safe_candidate=True,
        )
        result = engine.run_story(
            story=story("ev:1"),
            evidence_by_id={"ev:1": evidence("ev:1")},
            policy={"policy_ref": "policy@test"},
        )
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.judgments[0]["machine_disposition"], "drop")

    def test_multi_evidence_synthesis_preserves_lineage(self) -> None:
        produced = angle("ev:1", "ev:2", angle_type="synthesis")
        judged = decision("ev:1", "ev:2")
        judged["candidate_family"] = "synthesis"
        engine = EditorialIntelligence(
            FakeProducer([produced]),
            FakeJudge([judged]),
        )
        result = engine.run_story(
            story=story("ev:1", "ev:2"),
            evidence_by_id={
                "ev:1": evidence("ev:1"),
                "ev:2": evidence("ev:2"),
            },
            policy={"policy_ref": "policy@test"},
        )
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0]["candidate_family"], "SYNTHESIS")
        self.assertEqual(result.candidates[0]["evidence_refs"], ["ev:1", "ev:2"])


if __name__ == "__main__":
    unittest.main()
