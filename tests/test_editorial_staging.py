from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from office_runtime.editorial.contracts import (
    ActivityEvidence,
    AngleCard,
    DailyBatch,
    PolicyIdentity,
)
from office_runtime.editorial.run_bundle import build_run_bundle
from office_runtime.editorial.story import cluster_stories
from office_runtime.editorial.staging.runtime import (
    EditorialStagingError,
    inventory_status,
    resolve_request,
    stage_bundle,
)
from office_runtime.editorial.staging.sheets import (
    CANDIDATES_TAB,
    InMemorySheetGateway,
    QUEUE_HEADERS,
    QUEUE_TAB,
    RUNS_TAB,
    SheetIdentityConflict,
    SheetProjectionError,
    SheetSchemaError,
    project_run_bundle,
)


def _bundle(
    *,
    candidate_id: str = "candidate-1",
    text: str = "Retries need failure provenance, not just another attempt.",
    window_end: str = "2026-10-06T10:00:00Z",
) -> dict:
    evidence = ActivityEvidence(
        evidence_id=f"evidence:{candidate_id}",
        source_kind="github_pr",
        source_ref="https://github.com/matuteiglesias/office-auto-lab/pull/52",
        observed_at="2026-10-06T10:00:00Z",
        event_at="2026-10-06T09:30:00Z",
        status="merged",
        title="Fixture PR",
        summary="Fixture evidence.",
        repository_ref="matuteiglesias/office-auto-lab",
        visibility="public",
        public_eligibility="eligible",
        artifact_refs=("https://github.com/matuteiglesias/office-auto-lab/pull/52",),
        source_metadata={"source_tier": "1"},
    )
    story = cluster_stories([evidence], as_of="2026-10-06T10:00:00Z")[0]
    angle = AngleCard(
        angle_id=f"angle:{candidate_id}",
        story_id=story.story_id,
        angle_type="lesson",
        claim="Retries need failure provenance.",
        tension_or_hook="Retrying everything hides the actual fault boundary.",
        transferable_lesson="Classify failure before retrying.",
        evidence_refs=(evidence.evidence_id,),
        audience=("software engineers",),
        career_signals=("reliability",),
        why_interesting="It changes recovery semantics.",
        risk_class="low",
    )
    candidate = {
        "schema_version": "office_runtime.editorial.candidate.v1",
        "candidate_id": candidate_id,
        "profile_id": "dev",
        "text": text,
        "risk_class": "low",
        "evidence_refs": [evidence.evidence_id],
        "work_refs": ["matuteiglesias/office-auto-lab#52"],
        "story_id": story.story_id,
        "angle_id": angle.angle_id,
        "candidate_family": "LESSON",
        "semantic_fingerprint": f"fingerprint:{candidate_id}",
        "language": "en",
        "topic_tags": ["reliability"],
        "career_signals": ["reliability"],
        "proof_object_refs": [],
        "freshness_class": "timely",
        "generated_at": "2026-10-06T10:00:30Z",
        "expires_at": "2026-10-09T10:00:00Z",
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
        "claim": angle.claim,
        "source_event_refs": [evidence.evidence_id],
        "repository_refs": [evidence.repository_ref],
    }
    batch = DailyBatch.from_mapping(
        {
            "schema_version": "office_runtime.editorial.daily_batch.v1",
            "batch_id": f"batch:{candidate_id}",
            "profile_id": "dev",
            "batch_date": "2026-10-06",
            "target_count": 8,
            "floor_count": 5,
            "ceiling_count": 12,
            "inventory_status": "DEGRADED_INVENTORY",
            "candidate_ids": [candidate_id],
            "source_tier_counts": {"1": 1},
            "diversity_summary": {"repositories": 1, "families": 1},
            "shortage_reasons": ["fixture contains one defensible candidate"],
        }
    )
    policy = PolicyIdentity.from_mapping(
        {
            "authority": "weekly-ops-governance",
            "source_ref": "github:weekly-ops-governance:editorial-policy",
            "source_revision": "0123456789abcdef0123456789abcdef01234567",
            "content_sha256": "a" * 64,
        }
    )
    retrieval = {
        "intended_sources": ["github_pr"],
        "actual_sources": ["github_pr"],
        "time_windows": [
            {
                "scope": "matuteiglesias/office-auto-lab",
                "since": "2026-10-03T10:00:00Z",
                "until": window_end,
            }
        ],
        "failures": [],
        "scope_status": "complete",
    }
    return build_run_bundle(
        profile_id="dev",
        started_at="2026-10-06T10:00:00Z",
        finished_at="2026-10-06T10:01:00Z",
        policy=policy,
        retrieval=retrieval,
        evidence=[evidence],
        stories=[story],
        angles=[angle],
        candidates=[candidate],
        batch=batch,
        status="DEGRADED_INVENTORY",
    ).to_dict()


class EditorialSheetProjectionTests(unittest.TestCase):
    def test_first_projection_creates_run_candidate_and_queue(self) -> None:
        gateway = InMemorySheetGateway()
        result = project_run_bundle(_bundle(), gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        self.assertEqual(result.run_action, "created")
        self.assertEqual(result.candidates_created, 1)
        self.assertEqual(result.queue_created, 1)
        self.assertEqual(len(gateway.rows[RUNS_TAB]), 2)
        self.assertEqual(len(gateway.rows[CANDIDATES_TAB]), 2)
        self.assertEqual(len(gateway.rows[QUEUE_TAB]), 2)

        queue = dict(zip(QUEUE_HEADERS, gateway.rows[QUEUE_TAB][1]))
        self.assertEqual(queue["draft_editable"], _bundle()["candidates"][0]["text"])
        self.assertEqual(queue["decision"], "REVIEW")
        self.assertEqual(queue["target_surface"], "X")
        self.assertEqual(queue["publisher_status"], "")

    def test_retry_is_duplicate_safe(self) -> None:
        gateway = InMemorySheetGateway()
        first = project_run_bundle(_bundle(), gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        second = project_run_bundle(_bundle(), gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        self.assertEqual(first.candidates_created, 1)
        self.assertEqual(second.run_action, "reused")
        self.assertEqual(second.candidates_reused, 1)
        self.assertEqual(second.queue_preserved, 1)
        self.assertEqual(len(gateway.rows[RUNS_TAB]), 2)
        self.assertEqual(len(gateway.rows[CANDIDATES_TAB]), 2)
        self.assertEqual(len(gateway.rows[QUEUE_TAB]), 2)

    def test_human_edit_and_decision_survive_rerun(self) -> None:
        for decision in ("APPROVE", "HOLD", "REJECT"):
            with self.subTest(decision=decision):
                gateway = InMemorySheetGateway()
                bundle = _bundle()
                project_run_bundle(bundle, gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
                gateway.set_cell(QUEUE_TAB, "candidate-1", "draft_editable", "Human-edited draft")
                gateway.set_cell(QUEUE_TAB, "candidate-1", "decision", decision)
                gateway.set_cell(QUEUE_TAB, "candidate-1", "editor_note", "Keep this nuance.")
                gateway.set_cell(QUEUE_TAB, "candidate-1", "target_surface", "LONGFORM_SEED")
                project_run_bundle(bundle, gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
                queue = dict(zip(QUEUE_HEADERS, gateway.rows[QUEUE_TAB][1]))
                self.assertEqual(queue["draft_editable"], "Human-edited draft")
                self.assertEqual(queue["decision"], decision)
                self.assertEqual(queue["editor_note"], "Keep this nuance.")
                self.assertEqual(queue["target_surface"], "LONGFORM_SEED")

    def test_later_run_preserves_existing_human_queue_state(self) -> None:
        gateway = InMemorySheetGateway()
        first = _bundle(candidate_id="candidate-1", window_end="2026-10-06T10:00:00Z")
        project_run_bundle(first, gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        gateway.set_cell(QUEUE_TAB, "candidate-1", "draft_editable", "Edited after run one")
        gateway.set_cell(QUEUE_TAB, "candidate-1", "decision", "APPROVE")

        second = _bundle(candidate_id="candidate-2", window_end="2026-10-06T11:00:00Z")
        result = project_run_bundle(second, gateway, run_bundle_ref="artifacts/editorial/runs/run-2.json")
        self.assertEqual(result.queue_created, 1)

        first_queue = dict(zip(QUEUE_HEADERS, gateway.rows[QUEUE_TAB][1]))
        self.assertEqual(first_queue["draft_editable"], "Edited after run one")
        self.assertEqual(first_queue["decision"], "APPROVE")
        self.assertEqual(len(gateway.rows[QUEUE_TAB]), 3)

    def test_publisher_state_survives_rerun(self) -> None:
        gateway = InMemorySheetGateway()
        bundle = _bundle()
        project_run_bundle(bundle, gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        gateway.set_cell(QUEUE_TAB, "candidate-1", "publisher_status", "scheduled")
        gateway.set_cell(QUEUE_TAB, "candidate-1", "scheduled_for", "2026-10-08T12:00:00Z")
        gateway.set_cell(QUEUE_TAB, "candidate-1", "published_ref", "x:future:123")
        project_run_bundle(bundle, gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        queue = dict(zip(QUEUE_HEADERS, gateway.rows[QUEUE_TAB][1]))
        self.assertEqual(queue["publisher_status"], "scheduled")
        self.assertEqual(queue["scheduled_for"], "2026-10-08T12:00:00Z")
        self.assertEqual(queue["published_ref"], "x:future:123")

    def test_partial_projection_can_retry(self) -> None:
        gateway = InMemorySheetGateway(fail_after_writes=2)
        bundle = _bundle()
        with self.assertRaises(SheetProjectionError):
            project_run_bundle(bundle, gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        self.assertEqual(len(gateway.rows[RUNS_TAB]), 2)
        self.assertEqual(len(gateway.rows[CANDIDATES_TAB]), 2)
        self.assertEqual(len(gateway.rows[QUEUE_TAB]), 1)

        gateway.fail_after_writes = None
        result = project_run_bundle(bundle, gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        self.assertEqual(result.candidates_reused, 1)
        self.assertEqual(result.queue_created, 1)
        self.assertEqual(len(gateway.rows[QUEUE_TAB]), 2)

    def test_candidate_identity_conflict_fails_closed(self) -> None:
        gateway = InMemorySheetGateway()
        bundle = _bundle()
        project_run_bundle(bundle, gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        gateway.set_cell(CANDIDATES_TAB, "candidate-1", "draft_original", "mutated original")
        with self.assertRaises(SheetIdentityConflict):
            project_run_bundle(bundle, gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")

    def test_run_identity_conflict_fails_closed(self) -> None:
        gateway = InMemorySheetGateway()
        bundle = _bundle()
        project_run_bundle(bundle, gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        gateway.set_cell(RUNS_TAB, bundle["run_id"], "profile_id", "other")
        with self.assertRaises(SheetIdentityConflict):
            project_run_bundle(bundle, gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")

    def test_malformed_headers_and_row_versions_fail_before_mutation(self) -> None:
        gateway = InMemorySheetGateway()
        gateway.rows[QUEUE_TAB][0][0] = "wrong"
        with self.assertRaises(SheetSchemaError):
            project_run_bundle(_bundle(), gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        self.assertEqual(gateway.write_count, 0)

        gateway = InMemorySheetGateway()
        project_run_bundle(_bundle(), gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        gateway.set_cell(CANDIDATES_TAB, "candidate-1", "schema_version", "future.v2")
        before = gateway.write_count
        with self.assertRaises(SheetSchemaError):
            project_run_bundle(_bundle(), gateway, run_bundle_ref="artifacts/editorial/runs/run-1.json")
        self.assertEqual(gateway.write_count, before)


class EditorialStagingRuntimeTests(unittest.TestCase):
    def test_exact_pr_and_bounded_window_validation(self) -> None:
        request = resolve_request(pr_ref="matuteiglesias/office-auto-lab#52")
        self.assertEqual(request.pr_ref, "matuteiglesias/office-auto-lab#52")
        with self.assertRaises(EditorialStagingError):
            resolve_request(pr_ref="office-auto-lab#52")
        with self.assertRaises(EditorialStagingError):
            resolve_request(
                since="2026-09-01T00:00:00Z",
                until="2026-10-01T00:00:00Z",
            )

    def test_lookback_is_resolved_into_an_overlapping_explicit_window(self) -> None:
        now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
        request = resolve_request(lookback_hours=96, now=now)
        self.assertEqual(request.since, "2026-10-02T12:00:00Z")
        self.assertEqual(request.until, "2026-10-06T12:00:00Z")

    def test_projection_only_run_writes_bundle_without_model_provider(self) -> None:
        gateway = InMemorySheetGateway()
        bundle = _bundle()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary, artifact = stage_bundle(
                bundle,
                out_dir=root / "runs",
                summary_out=root / "summary.md",
                apply_sheet=True,
                gateway=gateway,
            )
            self.assertTrue(artifact.is_file())
            self.assertTrue((root / "summary.md").is_file())
            self.assertEqual(summary["projection_status"], "applied")
            self.assertEqual(summary["inventory_status"], "DEGRADED_INVENTORY")

    def test_degraded_inventory_is_completed_editorial_outcome(self) -> None:
        self.assertEqual(inventory_status(_bundle()), "DEGRADED_INVENTORY")


if __name__ == "__main__":
    unittest.main()
