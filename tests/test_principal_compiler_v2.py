from __future__ import annotations

import inspect
import unittest

from office_runtime.office import principal
from office_runtime.office.principal import PrincipalCompileError, compile_principal_brief, render_principal_markdown


def packet(front_id: str, kind: str, *, principal_needed: bool = False, status: str = "PREPARED_DEEP", blockers: list[str] | None = None, needs: str = "current bounded need", packet_digest: str | None = None) -> dict:
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
            "carry_status": "ACTIVE", "horizon": "THIS_WEEK", "priority_mode": "SPRINT",
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
        brief = compile_principal_brief(preparation(packet("fr_verify", "VERIFY", status="DEFERRED_BUDGET")))
        self.assertEqual(brief["needs_you"], [])
        self.assertEqual(brief["ready_pulls"], [])
        self.assertEqual(brief["exceptions"][0]["exception_code"], "STAFF_PREP_BUDGET")
        self.assertTrue(brief["nothing_required"])

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
