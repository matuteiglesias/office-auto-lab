from __future__ import annotations

import inspect
import unittest

from office_runtime.office import execution
from office_runtime.office.execution import ExecutionCompileError, compile_execution_plan


def snapshot(*, with_contract: bool = True) -> dict:
    contracts = []
    if with_contract:
        contracts = [{
            "contract_id": "opc_1",
            "front_id": "fr_exec",
            "operator_name": "primary_operator",
            "operator_class": "AUTOMATION",
            "contract_status": "ACTIVE",
            "contract_version": "v1",
            "allowed_powers": "read_state;read_repo;run_checks;write_artifacts;update_state;open_work_items",
            "forbidden_powers": "external_send;merge_without_review",
            "required_seams": "human_review;run_record_owner",
            "must_consume_shared_modules": "fr_0004",
            "must_not_implement_locally": "identity_resolution;generic_run_logging",
            "runbook_or_repo_ref": "repo:/must/not/leak",
        }]
    return {
        "snapshot_digest": "sha256:snapshot",
        "tables": {"operator_contract_v2": {"rows": contracts}},
    }


def ready_entry(*, workspace_status: str = "RESOLVED", kind: str = "EXECUTE") -> dict:
    return {
        "entry_id": "wi:fr_exec:execute",
        "work_item_id": "wi:fr_exec:execute",
        "front_id": "fr_exec",
        "title": "Execution front",
        "kind": kind,
        "horizon": "THIS_WEEK",
        "priority_mode": "SPRINT",
        "why_now": "bounded work is ready",
        "recommended_move": "Perform one bounded implementation step and capture evidence.",
        "evidence_refs": [{"kind": "repository", "repo_id": "repo.exec", "workspace_id": "ws_exec", "revision": "abc123", "dirty": False}],
        "staff_packet_id": "sp:wi:fr_exec:execute",
        "staff_packet_digest": "sha256:staff",
        "entry_context": {
            "repo_ids": ["repo.exec"],
            "workspace_states": [{"repo_id": "repo.exec", "workspace_id": "ws_exec", "status": workspace_status}],
        },
        "preparation_status": "PREPARED_DEEP",
        "entry_digest": "sha256:entry",
    }


def principal_brief(*, ready=None, needs_you=None) -> dict:
    return {
        "schema_version": "ops.principal-brief.v2",
        "source_snapshot_digest": "sha256:snapshot",
        "brief_digest": "sha256:brief",
        "ready_pulls": list(ready or []),
        "needs_you": list(needs_you or []),
    }


class ExecutionCompilerV2Tests(unittest.TestCase):
    def test_execution_compiler_does_not_reread_control_plane_or_resolve_paths(self) -> None:
        source = inspect.getsource(execution)
        self.assertNotIn("read_sheet_values", source)
        self.assertNotIn("OfficeConfig", source)
        self.assertNotIn("IdentityResolver", source)
        self.assertNotIn("local_path", source)

    def test_ready_pull_compiles_bounded_packet(self) -> None:
        plan = compile_execution_plan(snapshot(), principal_brief(ready=[ready_entry()]))
        self.assertEqual(plan["counts"]["packets"], 1)
        packet = plan["packets"][0]
        self.assertEqual(packet["authorization"]["mode"], "READY_PULL")
        self.assertFalse(packet["authorization"]["principal_decision_inferred"])
        self.assertEqual(packet["target"]["repo_ids"], ["repo.exec"])
        self.assertEqual(packet["target"]["workspaces"][0]["workspace_id"], "ws_exec")
        self.assertTrue(packet["acceptance_conditions"])
        self.assertTrue(packet["stop_conditions"])

    def test_state_mutating_and_work_expanding_powers_are_withheld_even_if_contract_allows_them(self) -> None:
        plan = compile_execution_plan(snapshot(), principal_brief(ready=[ready_entry()]))
        operator = plan["packets"][0]["operator"]
        self.assertNotIn("update_state", operator["effective_allowed_powers"])
        self.assertNotIn("open_work_items", operator["effective_allowed_powers"])
        self.assertEqual(set(operator["compiler_withheld_powers"]), {"update_state", "open_work_items"})
        self.assertIn("external_send", operator["contract_forbidden_powers"])

    def test_needs_you_is_never_inferred_as_execution_authorization(self) -> None:
        decision = dict(ready_entry())
        decision["kind"] = "DECIDE"
        decision["work_item_id"] = "wi:fr_exec:decide"
        decision["entry_id"] = "wi:fr_exec:decide"
        plan = compile_execution_plan(snapshot(), principal_brief(needs_you=[decision]))
        self.assertEqual(plan["packets"], [])
        self.assertEqual(plan["ignored_principal_entries"][0]["reason"], "PRINCIPAL_DECISION_IS_NOT_EXECUTION_AUTHORIZATION")

    def test_missing_operator_contract_is_explicit_exception(self) -> None:
        plan = compile_execution_plan(snapshot(with_contract=False), principal_brief(ready=[ready_entry()]))
        self.assertEqual(plan["packets"], [])
        self.assertEqual(plan["exceptions"][0]["code"], "NO_ACTIVE_OPERATOR_CONTRACT")

    def test_unresolved_repository_target_is_explicit_exception(self) -> None:
        plan = compile_execution_plan(snapshot(), principal_brief(ready=[ready_entry(workspace_status="AMBIGUOUS")]))
        self.assertEqual(plan["packets"], [])
        self.assertEqual(plan["exceptions"][0]["code"], "TARGET_NOT_READY")

    def test_unsupported_decide_kind_cannot_hide_inside_ready_pulls(self) -> None:
        plan = compile_execution_plan(snapshot(), principal_brief(ready=[ready_entry(kind="DECIDE")]))
        self.assertEqual(plan["packets"], [])
        self.assertEqual(plan["exceptions"][0]["code"], "UNSUPPORTED_EXECUTION_KIND")

    def test_packet_never_exports_runbook_or_machine_path_from_contract(self) -> None:
        plan = compile_execution_plan(snapshot(), principal_brief(ready=[ready_entry()]))
        self.assertNotIn("/must/not/leak", str(plan))
        self.assertNotIn("runbook_or_repo_ref", str(plan))

    def test_snapshot_generation_mismatch_fails_closed(self) -> None:
        brief = principal_brief(ready=[ready_entry()])
        brief["source_snapshot_digest"] = "sha256:other"
        with self.assertRaises(ExecutionCompileError):
            compile_execution_plan(snapshot(), brief)


if __name__ == "__main__":
    unittest.main()
