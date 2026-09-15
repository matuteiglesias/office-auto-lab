from __future__ import annotations

import inspect
import unittest

from office_runtime.office import reentry_v2
from office_runtime.office.reentry_v2 import ReentryCompileError, compile_reentry_v2


ACCEPTANCE = [
    "one bounded objective is completed or stopped at a named blocker",
    "expected evidence or artifact is produced",
    "residual work is recorded rather than silently expanded",
]


def snapshot() -> dict:
    return {"snapshot_digest": "sha256:snapshot"}


def packet(*, packet_id: str = "xp:wi:fr_1:execute", work_item_id: str = "wi:fr_1:execute") -> dict:
    return {
        "schema_version": "ops.execution-packet.v2",
        "execution_packet_id": packet_id,
        "work_item_id": work_item_id,
        "front_id": "fr_1",
        "kind": "EXECUTE",
        "objective": "Do one bounded move.",
        "acceptance_conditions": list(ACCEPTANCE),
        "source_snapshot_digest": "sha256:snapshot",
        "packet_digest": f"sha256:{packet_id}",
        "target": {"front_id": "fr_1", "repo_ids": ["repo.one"], "workspaces": [{"repo_id": "repo.one", "workspace_id": "ws_1", "status": "RESOLVED"}]},
    }


def plan(*packets: dict) -> dict:
    return {
        "schema_version": "ops.execution-plan.v2",
        "source_snapshot_digest": "sha256:snapshot",
        "plan_digest": "sha256:plan",
        "packets": list(packets),
    }


def receipt(
    p: dict,
    *,
    receipt_id: str = "rcpt_1",
    status: str = "COMPLETED",
    residuals=None,
    blockers=None,
    evidence=None,
    acceptance_results=None,
) -> dict:
    if acceptance_results is None:
        acceptance_results = [{"condition": condition, "passed": True, "note": "observed"} for condition in p["acceptance_conditions"]]
    return {
        "schema_version": "ops.execution-receipt.v2",
        "receipt_id": receipt_id,
        "execution_packet_id": p["execution_packet_id"],
        "execution_packet_digest": p["packet_digest"],
        "work_item_id": p["work_item_id"],
        "front_id": p["front_id"],
        "status": status,
        "started_at": "2026-09-15T00:00:00Z",
        "finished_at": "2026-09-15T00:10:00Z",
        "actions_taken": ["bounded step"],
        "evidence": [{"kind": "artifact", "ref": "artifact:test"}] if evidence is None else evidence,
        "acceptance_results": acceptance_results,
        "residuals": [] if residuals is None else residuals,
        "blockers": [] if blockers is None else blockers,
        "suggested_next_touch": "",
        "source_snapshot_digest": "sha256:snapshot",
    }


class ReentryV2Tests(unittest.TestCase):
    def test_reentry_compiler_has_no_control_plane_writer(self) -> None:
        source = inspect.getsource(reentry_v2)
        self.assertNotIn("update_state", source)
        self.assertNotIn("write_sheet", source)
        self.assertNotIn("googleapiclient", source)

    def test_completed_receipt_with_all_acceptance_passed_becomes_done_proposal(self) -> None:
        p = packet()
        result = compile_reentry_v2(snapshot(), plan(p), [receipt(p)])
        self.assertEqual(result["counts"]["done"], 1)
        proposal = result["proposals"][0]
        self.assertEqual(proposal["classification"], "DONE")
        self.assertFalse(proposal["mutation_performed"])
        self.assertIsNone(proposal["candidate_control_patch"])
        self.assertEqual(proposal["source_receipt_digest"], result["receipts"][0]["receipt_digest"])

    def test_completed_receipt_with_residuals_becomes_follow_up(self) -> None:
        p = packet()
        result = compile_reentry_v2(snapshot(), plan(p), [receipt(p, residuals=["write docs"])])
        self.assertEqual(result["proposals"][0]["classification"], "FOLLOW_UP")
        self.assertEqual(result["proposals"][0]["what_remains"], ["write docs"])

    def test_blocked_receipt_requires_blocker_and_becomes_waiting(self) -> None:
        p = packet()
        blocked_results = [{"condition": p["acceptance_conditions"][0], "passed": False, "note": "blocked"}]
        with self.assertRaises(ReentryCompileError):
            compile_reentry_v2(snapshot(), plan(p), [receipt(p, status="BLOCKED", blockers=[], acceptance_results=blocked_results)])
        result = compile_reentry_v2(snapshot(), plan(p), [receipt(p, status="BLOCKED", blockers=["missing credential"], acceptance_results=blocked_results)])
        self.assertEqual(result["proposals"][0]["classification"], "WAITING")
        self.assertIn("missing credential", result["proposals"][0]["what_remains"])

    def test_completed_receipt_must_pass_every_packet_acceptance_condition(self) -> None:
        p = packet()
        incomplete = [{"condition": p["acceptance_conditions"][0], "passed": True, "note": "only one"}]
        with self.assertRaises(ReentryCompileError):
            compile_reentry_v2(snapshot(), plan(p), [receipt(p, acceptance_results=incomplete)])

    def test_completed_receipt_requires_evidence(self) -> None:
        p = packet()
        with self.assertRaises(ReentryCompileError):
            compile_reentry_v2(snapshot(), plan(p), [receipt(p, evidence=[])])

    def test_receipt_cannot_claim_unknown_packet_or_wrong_digest(self) -> None:
        p = packet()
        unknown = receipt(p)
        unknown["execution_packet_id"] = "xp:unknown"
        with self.assertRaises(ReentryCompileError):
            compile_reentry_v2(snapshot(), plan(p), [unknown])
        wrong = receipt(p)
        wrong["execution_packet_digest"] = "sha256:wrong"
        with self.assertRaises(ReentryCompileError):
            compile_reentry_v2(snapshot(), plan(p), [wrong])

    def test_only_one_receipt_per_packet_is_accepted(self) -> None:
        p = packet()
        with self.assertRaises(ReentryCompileError):
            compile_reentry_v2(snapshot(), plan(p), [receipt(p, receipt_id="a"), receipt(p, receipt_id="b")])

    def test_packets_without_receipts_stay_explicitly_open(self) -> None:
        p1 = packet()
        p2 = packet(packet_id="xp:wi:fr_1:maintain", work_item_id="wi:fr_1:maintain")
        result = compile_reentry_v2(snapshot(), plan(p1, p2), [receipt(p1)])
        self.assertEqual(len(result["unclosed_packets"]), 1)
        self.assertEqual(result["unclosed_packets"][0]["execution_packet_id"], p2["execution_packet_id"])
        self.assertEqual(result["unclosed_packets"][0]["status"], "OPEN_NO_RECEIPT")

    def test_reentry_never_creates_follow_up_work_or_carry_patch_automatically(self) -> None:
        p = packet()
        r = receipt(p, status="PARTIAL", residuals=["remaining step"])
        r["suggested_next_touch"] = "Try the remaining step after review."
        result = compile_reentry_v2(snapshot(), plan(p), [r])
        proposal = result["proposals"][0]
        self.assertIsNone(proposal["candidate_control_patch"])
        self.assertTrue(proposal["reentry_intent"]["review_follow_up"])
        self.assertEqual(proposal["suggested_next_touch"], "Try the remaining step after review.")
        self.assertFalse(result["mutation_performed"])

    def test_snapshot_mismatch_fails_closed(self) -> None:
        p = packet()
        bad_plan = plan(p)
        bad_plan["source_snapshot_digest"] = "sha256:other"
        with self.assertRaises(ReentryCompileError):
            compile_reentry_v2(snapshot(), bad_plan, [receipt(p)])


if __name__ == "__main__":
    unittest.main()
