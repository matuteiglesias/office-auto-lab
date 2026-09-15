from __future__ import annotations

import unittest

from office_runtime.office.control_snapshot import build_snapshot
from office_runtime.office.execution import compile_execution_plan
from office_runtime.office.invariants import GenerationInvariantError, validate_forward_generation
from office_runtime.office.principal import compile_principal_brief
from office_runtime.office.work_items import compile_work_items
from office_runtime.staff.preparation_v2 import SnapshotEvidenceAdapter, prepare_work_items
from tests.test_generation_v2 import frames


class GenerationInvariantTests(unittest.TestCase):
    def _compiled(self):
        snapshot = build_snapshot(frames(), observed_at="2026-09-15T00:00:00Z", spreadsheet_id="sheet")
        work_set = compile_work_items(snapshot)
        preparation = prepare_work_items(
            snapshot,
            work_set,
            adapters=[SnapshotEvidenceAdapter()],
            max_deep=6,
            prepared_at="2026-09-15T00:01:00Z",
        )
        principal = compile_principal_brief(preparation)
        execution = compile_execution_plan(snapshot, principal)
        return snapshot, work_set, preparation, principal, execution

    def _compiled_with_ready_action(self):
        snapshot = build_snapshot(frames(), observed_at="2026-09-15T00:00:00Z", spreadsheet_id="sheet")
        work_set = compile_work_items(snapshot)
        action = next(row for row in work_set["work_items"] if row["kind"] == "EXECUTE")
        action["action_contract"] = {
            "objective": "Verify the named execution surface at revision abc123.",
            "entry_surface": {"type": "REPOSITORY", "repo_id": "repo.exec", "workspace_id": "ws_exec", "revision": "abc123"},
            "why_now": "The bounded check is on the active frontier.",
            "scope_boundary": "Inspect only the named surface without mutation.",
            "acceptance_conditions": ["The named surface is checked."],
            "stop_conditions": ["Stop after recording the result."],
            "expected_evidence": ["A bounded verification receipt."],
            "known_uncertainties": [], "decision_dependencies": [],
        }
        preparation = prepare_work_items(snapshot, work_set, adapters=[SnapshotEvidenceAdapter()], max_deep=6, prepared_at="2026-09-15T00:01:00Z")
        principal = compile_principal_brief(preparation)
        execution = compile_execution_plan(snapshot, principal)
        return snapshot, work_set, preparation, principal, execution

    def test_valid_generation_passes_explicit_invariant_suite(self) -> None:
        names = validate_forward_generation(*self._compiled())
        self.assertIn("one_snapshot_lineage", names)
        self.assertIn("execution_withholds_governance_mutation", names)

    def test_digest_drift_fails(self) -> None:
        snapshot, work_set, preparation, principal, execution = self._compiled()
        execution = dict(execution)
        execution["source_snapshot_digest"] = "sha256:not-the-run"
        with self.assertRaises(GenerationInvariantError):
            validate_forward_generation(snapshot, work_set, preparation, principal, execution)

    def test_principal_cannot_reference_unknown_work(self) -> None:
        snapshot, work_set, preparation, principal, execution = self._compiled()
        principal = dict(principal)
        principal["ready_pulls"] = list(principal.get("ready_pulls", [])) + [{"work_item_id": "wi:ghost:execute"}]
        with self.assertRaises(GenerationInvariantError):
            validate_forward_generation(snapshot, work_set, preparation, principal, execution)

    def test_execution_cannot_regain_state_mutation_power(self) -> None:
        snapshot, work_set, preparation, principal, execution = self._compiled_with_ready_action()
        execution = dict(execution)
        packets = [dict(row) for row in execution.get("packets", [])]
        self.assertTrue(packets)
        packets[0] = dict(packets[0])
        packets[0]["operator"] = dict(packets[0].get("operator", {}))
        packets[0]["operator"]["effective_allowed_powers"] = list(packets[0]["operator"].get("effective_allowed_powers", [])) + ["update_state"]
        execution["packets"] = packets
        with self.assertRaises(GenerationInvariantError):
            validate_forward_generation(snapshot, work_set, preparation, principal, execution)


if __name__ == "__main__":
    unittest.main()
