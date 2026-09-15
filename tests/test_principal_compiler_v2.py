from __future__ import annotations

import inspect
import unittest

from office_runtime.office import principal
from office_runtime.office.principal import PrincipalCompileError, compile_principal_brief, render_principal_markdown


def packet(front_id: str, kind: str, *, principal_needed: bool = False, status: str = "PREPARED_DEEP", blockers: list[str] | None = None, needs: str = "current bounded need", packet_digest: str | None = None, decision_maturity: str | None = None, action_maturity: str | None = None, horizon: str = "THIS_WEEK") -> dict:
    is_decision = kind == "DECIDE"
    is_action = kind in {"UNBLOCK", "VERIFY", "EXECUTE", "MAINTAIN"}
    contract = {
        "objective": f"Verify the named surface for {front_id}.",
        "entry_surface": {"type": "REPOSITORY", "repo_id": f"repo.{front_id}", "workspace_id": f"ws.{front_id}", "revision": "abc123"},
        "why_now": "The bounded action is on the active frontier.",
        "scope_boundary": "Inspect only the named surface without mutation.",
        "acceptance_conditions": ["The named surface is checked."],
        "stop_conditions": ["Stop after recording the result."],
        "expected_evidence": ["A bounded verification receipt."],
        "known_uncertainties": [], "decision_dependencies": [],
    } if is_action else {}
    return {
        "schema_version": "ops.staff-packet.v2",
        "staff_packet_id": f"sp:wi:{front_id}:{kind.lower()}",
        "work_item_id": f"wi:{front_id}:{kind.lower()}",
        "front_id": front_id,
        "title": f"Title {front_id}",
        "kind": kind,
        "preparation_status": status,
        "question": f"Question for {front_id}?",
        "current_state": {
            "carry_status": "ACTIVE", "horizon": horizon, "priority_mode": "SPRINT",
            "principal_mode": "REQUIRED" if principal_needed else "RECOMMENDED", "needs": needs,
            "note": "context note", "runtime": {"health_status": "OK", "health_bucket": "TEST"},
        },
        "identity": {
            "repo_ids": [f"repo.{front_id}"],
            "workspace_states": [{"repo_id": f"repo.{front_id}", "workspace_id": f"ws.{front_id}", "status": "RESOLVED"}],
            "path_authority": "repo_workspaces_v2", "status": "RESOLVED",
        },
        "evidence": [{
            "adapter": "local_repo", "status": "ok", "repo_id": f"repo.{front_id}",
            "workspace_id": f"ws.{front_id}", "revision": "abc123", "dirty": False,
            "local_path": "/must/not/leak",
        }],
        "uncertainties": [],
        "blockers": blockers or [],
        "recommended_move": f"Do bounded move for {front_id}.",
        "principal_needed": principal_needed,
        "principal_question": f"Choose bounded move for {front_id}." if principal_needed else "",
        "prepared_at": "2026-09-15T00:00:00Z",
        "source_snapshot_digest": "sha256:snapshot",
        "packet_digest": packet_digest or f"sha256:{front_id}:{kind}",
        "decision_maturity": decision_maturity or ("READY_FOR_PRINCIPAL" if is_decision else "NOT_A_DECISION"),
        "decision": ({
            "question": f"What should happen for {front_id}?",
            "recommendation": "Approve the bounded default.",
            "options": ["approve_default", "defer"],
            "why_now": "The active weekly frontier has a concrete next move.",
            "consequence": "The selected bounded move becomes the next governed state.",
            "default_if_deferred": "Leave the current state unchanged and review next cycle.",
            "post_decision_move": "Staff can prepare the approved next step.",
        } if is_decision else {}),
        "action_maturity": action_maturity or ("READY_FOR_PULL" if is_action and status == "PREPARED_DEEP" and not blockers else "NEEDS_MORE_PREP" if is_action else "NOT_AN_ACTION"),
        "action_contract": contract,
    }


def preparation(*packets: dict) -> dict:
    return {"schema_version": "ops.staff-preparation-set.v2", "source_snapshot_digest": "sha256:snapshot", "preparation_digest": "sha256:prep", "packets": list(packets)}


class PrincipalCompilerV2Tests(unittest.TestCase):
    def test_principal_compiler_does_not_reread_or_recompile_governance(self) -> None:
        source = inspect.getsource(principal)
        self.assertNotIn("read_sheet_values", source)
        self.assertNotIn("OfficeConfig", source)
        self.assertNotIn("IdentityResolver", source)
        self.assertNotIn("compile_work_items", source)

    def test_no_principal_action_is_success_even_with_ready_pull(self) -> None:
        brief = compile_principal_brief(preparation(packet("fr_exec", "EXECUTE")))
        self.assertTrue(brief["nothing_required"])
        self.assertFalse(brief["principal_action_required"])
        self.assertEqual(brief["needs_you"], [])
        self.assertEqual(len(brief["ready_pulls"]), 1)
        self.assertIn("No principal action required", render_principal_markdown(brief))

    def test_principal_item_reaches_needs_you_only_after_successful_preparation(self) -> None:
        ready = compile_principal_brief(preparation(packet("fr_decide", "DECIDE", principal_needed=True)))
        self.assertEqual(len(ready["needs_you"]), 1)
        self.assertFalse(ready["nothing_required"])
        blocked = compile_principal_brief(preparation(packet("fr_decide", "DECIDE", principal_needed=True, status="BLOCKED", blockers=["missing evidence"])))
        self.assertEqual(blocked["needs_you"], [])
        self.assertEqual(blocked["exceptions"][0]["exception_code"], "BLOCKED")
        self.assertTrue(blocked["nothing_required"])
        self.assertFalse(blocked["exceptions"][0]["principal_attention_required"])

    def test_attention_budget_is_bounded_and_overflow_is_explicit(self) -> None:
        prep = preparation(*[packet(f"fr_{i}", "DECIDE", principal_needed=True) for i in range(5)])
        brief = compile_principal_brief(prep, max_needs_you=2)
        self.assertEqual(len(brief["needs_you"]), 2)
        self.assertEqual(len(brief["deferred_attention"]), 3)
        self.assertTrue(brief["principal_action_required"])

    def test_ready_pull_budget_moves_extra_prepared_items_out_of_attention(self) -> None:
        prep = preparation(*[packet(f"fr_{i}", "EXECUTE") for i in range(4)])
        brief = compile_principal_brief(prep, max_ready_pulls=2)
        self.assertEqual(len(brief["ready_pulls"]), 2)
        self.assertEqual(len(brief["moved_without_you"]), 2)
        self.assertTrue(brief["nothing_required"])

    def test_exception_does_not_become_raw_principal_work(self) -> None:
        brief = compile_principal_brief(preparation(packet("fr_verify", "VERIFY", status="DEFERRED_BY_BUDGET")))
        self.assertEqual(brief["needs_you"], [])
        self.assertEqual(brief["ready_pulls"], [])
        self.assertEqual(brief["exceptions"], [])
        self.assertEqual(brief["preparation_frontier"]["deferred_by_budget"], 1)
        self.assertTrue(brief["nothing_required"])

    def test_required_immature_decision_stays_with_staff(self) -> None:
        brief = compile_principal_brief(preparation(packet("fr_decide", "DECIDE", principal_needed=True, decision_maturity="NEEDS_MORE_PREP")))
        self.assertEqual(brief["needs_you"], [])
        self.assertEqual(brief["staff_follow_up"][0]["reason"], "DECISION_NOT_READY")
        self.assertEqual(brief["exceptions"], [])

    def test_mature_relevant_decision_reaches_needs_you(self) -> None:
        brief = compile_principal_brief(preparation(packet("fr_decide", "DECIDE", principal_needed=True)))
        self.assertEqual(len(brief["needs_you"]), 1)
        self.assertEqual(brief["needs_you"][0]["decision_maturity"], "READY_FOR_PRINCIPAL")

    def test_required_but_later_decision_is_not_immediate_attention(self) -> None:
        brief = compile_principal_brief(preparation(packet("fr_decide", "DECIDE", principal_needed=True, horizon="LATER")))
        self.assertEqual(brief["needs_you"], [])
        self.assertEqual(brief["staff_follow_up"][0]["reason"], "DECISION_NOT_READY")

    def test_principal_posture_alone_does_not_veto_ready_pull(self) -> None:
        action = packet("fr_exec", "EXECUTE", principal_needed=False)
        action["current_state"]["principal_mode"] = "REQUIRED"
        brief = compile_principal_brief(preparation(action))
        self.assertEqual([row["work_item_id"] for row in brief["ready_pulls"]], ["wi:fr_exec:execute"])

    def test_deep_action_without_maturity_is_not_a_ready_pull(self) -> None:
        brief = compile_principal_brief(preparation(packet("fr_exec", "EXECUTE", action_maturity="NEEDS_MORE_PREP")))
        self.assertEqual(brief["ready_pulls"], [])

    def test_repeated_blockers_are_compacted_by_front(self) -> None:
        brief = compile_principal_brief(preparation(
            packet("fr_blocked", "VERIFY", status="BLOCKED", blockers=["identity is not ready"]),
            packet("fr_blocked", "UNBLOCK", status="BLOCKED", blockers=["identity is not ready"]),
        ))
        self.assertEqual(len(brief["exceptions"]), 1)
        self.assertEqual(brief["exceptions"][0]["kinds"], ["UNBLOCK", "VERIFY"])
        self.assertEqual(brief["exceptions"][0]["blockers_by_work_item"]["wi:fr_blocked:verify"], ["identity is not ready"])

    def test_compacted_exception_preserves_action_uncertainty_attribution(self) -> None:
        verify = packet("fr_shared", "VERIFY", status="BLOCKED", blockers=["identity is not ready"])
        execute = packet("fr_shared", "EXECUTE", status="BLOCKED", blockers=["identity is not ready"])
        execute["uncertainties"] = ["action contract: action contract is missing"]
        exception = compile_principal_brief(preparation(verify, execute))["exceptions"][0]
        self.assertEqual(exception["uncertainties_by_work_item"]["wi:fr_shared:verify"], [])
        self.assertIn("action contract: action contract is missing", exception["all_uncertainties"])

    def test_action_maturity_does_not_mature_an_unrelated_decision(self) -> None:
        decision = packet("fr_shared", "DECIDE", principal_needed=True, decision_maturity="NEEDS_MORE_PREP")
        action = packet("fr_shared", "EXECUTE")
        brief = compile_principal_brief(preparation(decision, action))
        self.assertEqual(brief["needs_you"], [])
        self.assertEqual(len(brief["ready_pulls"]), 1)
        self.assertEqual(brief["staff_follow_up"][0]["work_item_id"], "wi:fr_shared:decide")

    def test_needs_wording_does_not_change_lane_or_attention(self) -> None:
        first = packet("fr_exec", "EXECUTE", needs="DECIDE urgently")
        second = packet("fr_exec", "EXECUTE", needs="ordinary maintenance")
        first_ids = [row["entry_id"] for row in compile_principal_brief(preparation(first))["ready_pulls"]]
        second_ids = [row["entry_id"] for row in compile_principal_brief(preparation(second))["ready_pulls"]]
        self.assertEqual(first_ids, second_ids)

    def test_principal_surface_compresses_evidence_and_never_exports_local_path(self) -> None:
        brief = compile_principal_brief(preparation(packet("fr_exec", "EXECUTE")))
        self.assertNotIn("/must/not/leak", str(brief))
        ref = brief["ready_pulls"][0]["evidence_refs"][0]
        self.assertEqual(ref["repo_id"], "repo.fr_exec")
        self.assertEqual(ref["workspace_id"], "ws.fr_exec")
        self.assertEqual(ref["revision"], "abc123")

    def test_delta_reports_added_cleared_and_changed_entries(self) -> None:
        previous = compile_principal_brief(preparation(
            packet("fr_a", "DECIDE", principal_needed=True, packet_digest="sha256:old-a"),
            packet("fr_b", "EXECUTE", packet_digest="sha256:old-b"),
        ))
        current = compile_principal_brief(preparation(
            packet("fr_a", "DECIDE", principal_needed=True, needs="changed need", packet_digest="sha256:new-a"),
            packet("fr_c", "EXECUTE", packet_digest="sha256:new-c"),
        ), previous_brief=previous)
        self.assertIn("wi:fr_a:decide", current["delta"]["changed"]["needs_you"])
        self.assertIn("wi:fr_b:execute", current["delta"]["cleared"]["ready_pulls"])
        self.assertIn("wi:fr_c:execute", current["delta"]["added"]["ready_pulls"])

    def test_rejects_wrong_staff_schema(self) -> None:
        with self.assertRaises(PrincipalCompileError):
            compile_principal_brief({"schema_version": "legacy", "source_snapshot_digest": "sha256:x", "packets": []})


if __name__ == "__main__":
    unittest.main()
