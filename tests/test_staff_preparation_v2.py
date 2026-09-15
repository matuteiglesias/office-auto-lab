from __future__ import annotations

import inspect
import unittest

from office_runtime.staff import preparation_v2
from office_runtime.office.action_candidates import ControlPlaneEvidenceProducer, RepositoryEvidenceProducer
from office_runtime.staff.preparation_v2 import StaffPreparationError, prepare_work_items


class CountingAdapter:
    name = "counting"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def collect(self, snapshot: dict, work_item: dict) -> dict:
        self.calls.append(str(work_item["work_item_id"]))
        return {"adapter": self.name, "status": "ok", "fact": work_item["kind"]}


def snapshot() -> dict:
    return {
        "snapshot_digest": "sha256:snapshot",
        "tables": {
            "front_registry_v2": {"rows": [
                {"front_id": "fr_decide", "title": "Decision front", "lifecycle_status": "ACTIVE"},
                {"front_id": "fr_exec", "title": "Execution front", "lifecycle_status": "ACTIVE"},
                {"front_id": "fr_blocked", "title": "Blocked front", "lifecycle_status": "ACTIVE"},
                {"front_id": "fr_maint", "title": "Maintenance front", "lifecycle_status": "ACTIVE"},
            ]},
            "runtime_health_v2": {"rows": [
                {"front_id": "fr_decide", "health_status": "OK", "health_bucket": "TEST"},
                {"front_id": "fr_exec", "health_status": "UNKNOWN", "health_bucket": "TEST"},
            ]},
            "support_artifacts_v2": {"rows": [{
                "artifact_id": "sa_1", "front_id": "fr_decide", "artifact_role": "DECISION_CONTEXT",
                "artifact_kind": "URL", "authority_class": "ADVISORY", "status": "ACTIVE",
                "uri": "artifact://decision-context",
            }]},
            "operator_contract_v2": {"rows": [{
                "contract_id": "opc_1", "front_id": "fr_exec", "operator_name": "primary_operator",
                "operator_class": "AUTOMATION", "contract_status": "ACTIVE", "contract_version": "v1",
                "allowed_powers": "read_state;write_artifacts", "forbidden_powers": "external_send",
            }]},
            "REPO MONITOR_v2": {"rows": []},
            "repo_workspaces_v2": {"rows": []},
        },
    }


def item(front_id: str, kind: str, *, principal_required: bool = False, prep_mode: str = "STAFF_REQUIRED", identity_status: str = "RESOLVED") -> dict:
    return {
        "work_item_id": f"wi:{front_id}:{kind.lower()}",
        "front_id": front_id,
        "title": front_id,
        "kind": kind,
        "carry_status": "ACTIVE",
        "horizon": "THIS_WEEK",
        "priority_mode": "SPRINT",
        "principal_mode": "REQUIRED" if principal_required else "RECOMMENDED",
        "principal_required": principal_required,
        "prep_mode": prep_mode,
        "identity": {"repo_ids": [], "workspace_states": [], "path_authority": "repo_workspaces_v2", "status": identity_status},
        "context": {"needs": "human prose only", "note": "context"},
        "source_snapshot_digest": "sha256:snapshot",
    }


def work_set(*items: dict) -> dict:
    return {"schema_version": "ops.work-item-set.v1", "source_snapshot_digest": "sha256:snapshot", "work_items": list(items)}


def action_contract(*, front_id: str = "fr_exec", surface_type: str = "REPOSITORY") -> dict:
    surface = {"type": surface_type}
    if surface_type == "REPOSITORY":
        surface.update({"repo_id": "repo.exec", "workspace_id": "ws.exec", "revision": "abc123"})
    else:
        surface.update({"table": "front_registry_v2", "front_id": front_id})
    return {
        "objective": "Verify the named governed surface at its recorded revision.",
        "entry_surface": surface,
        "why_now": "The bounded verification is on the current frontier.",
        "scope_boundary": "Inspect only the named surface and do not mutate state.",
        "acceptance_conditions": ["The named surface is checked."],
        "stop_conditions": ["Stop after recording the result."],
        "expected_evidence": ["A bounded verification receipt."],
        "known_uncertainties": [],
        "decision_dependencies": [],
    }


def action_candidate(candidate_id: str = "ac:repo:verify", *, freshness: str = "CURRENT") -> dict:
    candidate = action_contract()
    candidate.update({
        "schema_version": "ops.staff-action-candidate.v1",
        "candidate_id": candidate_id,
        "front_id": "fr_exec",
        "producer": "REPOSITORY_EVIDENCE",
        "generated_at": "2026-09-15T00:00:00Z",
        "source_evidence": [{"repo_id": "repo.exec", "workspace_id": "ws.exec", "revision": "abc123"}],
        "source_freshness": freshness,
    })
    return candidate


class StaffPreparationV2Tests(unittest.TestCase):
    def test_module_has_no_sheet_reader_or_office_config_dependency(self) -> None:
        source = inspect.getsource(preparation_v2)
        self.assertNotIn("read_sheet_values", source)
        self.assertNotIn("OfficeConfig", source)
        self.assertNotIn("googleapiclient", source)

    def test_rejects_cross_generation_work_set(self) -> None:
        bad = work_set(item("fr_exec", "EXECUTE"))
        bad["source_snapshot_digest"] = "sha256:other"
        with self.assertRaises(StaffPreparationError):
            prepare_work_items(snapshot(), bad)

    def test_every_item_is_triaged_but_deep_preparation_is_bounded(self) -> None:
        adapter = CountingAdapter()
        result = prepare_work_items(
            snapshot(),
            work_set(item("fr_exec", "EXECUTE"), item("fr_decide", "DECIDE", principal_required=True)),
            adapters=[adapter],
            max_deep=1,
            prepared_at="2026-09-15T00:00:00Z",
        )
        self.assertEqual(len(result["triage"]), 2)
        self.assertEqual(result["deep_used"], 1)
        self.assertEqual(adapter.calls, ["wi:fr_decide:decide"])
        by_id = {packet["work_item_id"]: packet for packet in result["packets"]}
        self.assertEqual(by_id["wi:fr_decide:decide"]["preparation_status"], "PREPARED_DEEP")
        self.assertEqual(by_id["wi:fr_exec:execute"]["preparation_status"], "DEFERRED_BY_BUDGET")

    def test_lane_budgets_keep_action_work_from_decision_monopoly(self) -> None:
        items = [item(f"fr_decide_{i}", "DECIDE", principal_required=True) for i in range(5)]
        items += [item(f"fr_exec_{i}", "EXECUTE") for i in range(4)]
        result = prepare_work_items(snapshot(), work_set(*items), adapters=[CountingAdapter()], max_deep=6)
        deep = [packet for packet in result["packets"] if packet["preparation_status"] == "PREPARED_DEEP"]
        self.assertEqual(result["deep_by_lane"], {"DECISION": 2, "ACTION": 4, "REPAIR_VERIFY": 0})
        self.assertEqual(len(deep), 6)
        self.assertEqual(result["counts"]["DEFERRED_BY_BUDGET"], 3)

    def test_lane_capacity_spills_over_deterministically(self) -> None:
        items = [item("fr_exec", "EXECUTE"), item("fr_maint", "MAINTAIN")]
        result = prepare_work_items(snapshot(), work_set(*items), adapters=[CountingAdapter()], max_deep=6)
        self.assertEqual(result["deep_by_lane"], {"DECISION": 0, "ACTION": 2, "REPAIR_VERIFY": 0})
        self.assertEqual([p["work_item_id"] for p in result["packets"]], ["wi:fr_exec:execute", "wi:fr_maint:maintain"])

    def test_blocked_identity_does_not_invoke_expensive_adapter(self) -> None:
        adapter = CountingAdapter()
        blocked = item("fr_blocked", "UNBLOCK", identity_status="NOT_READY")
        blocked["identity"]["workspace_states"] = [{"repo_id": "repo.blocked", "workspace_id": None, "status": "AMBIGUOUS"}]
        result = prepare_work_items(snapshot(), work_set(blocked), adapters=[adapter], max_deep=5)
        self.assertEqual(adapter.calls, [])
        packet = result["packets"][0]
        self.assertEqual(packet["preparation_status"], "BLOCKED")
        self.assertTrue(packet["blockers"])
        self.assertEqual(packet["evidence"][0]["adapter"], "control_snapshot")

    def test_explicit_unresolved_decision_dependency_blocks_action(self) -> None:
        action = item("fr_exec", "EXECUTE")
        action["decision_dependency"] = {"decision_id": "dec:fr_exec:launch", "status": "PENDING"}
        result = prepare_work_items(snapshot(), work_set(action), max_deep=1)
        packet = result["packets"][0]
        self.assertEqual(packet["preparation_status"], "BLOCKED")
        self.assertIn("decision dependency dec:fr_exec:launch is unresolved", packet["blockers"])

    def test_principal_posture_does_not_make_action_principal_needed(self) -> None:
        result = prepare_work_items(snapshot(), work_set(item("fr_exec", "EXECUTE", principal_required=True)), max_deep=1)
        packet = result["packets"][0]
        self.assertEqual(packet["principal_posture"], "REQUIRED")
        self.assertFalse(packet["principal_needed"])

    def test_deep_action_without_contract_is_not_ready_for_pull(self) -> None:
        result = prepare_work_items(snapshot(), work_set(item("fr_exec", "EXECUTE")), max_deep=1)
        packet = result["packets"][0]
        self.assertEqual(packet["preparation_status"], "PREPARED_DEEP")
        self.assertEqual(packet["action_maturity"], "NEEDS_MORE_PREP")

    def test_concrete_repo_contract_makes_deep_action_ready(self) -> None:
        action = item("fr_exec", "EXECUTE")
        action["action_contract"] = action_contract()
        result = prepare_work_items(snapshot(), work_set(action), max_deep=1)
        packet = result["packets"][0]
        self.assertEqual(packet["action_maturity"], "READY_FOR_PULL")
        self.assertEqual(packet["action_contract"]["entry_surface"]["type"], "REPOSITORY")

    def test_control_state_contract_can_be_ready_without_repository(self) -> None:
        action = item("fr_exec", "EXECUTE")
        action["action_contract"] = action_contract(surface_type="CONTROL_STATE")
        result = prepare_work_items(snapshot(), work_set(action), max_deep=1)
        self.assertEqual(result["packets"][0]["action_maturity"], "READY_FOR_PULL")

    def test_unresolved_contract_dependency_blocks_readiness(self) -> None:
        action = item("fr_exec", "EXECUTE")
        action["action_contract"] = action_contract()
        action["action_contract"]["decision_dependencies"] = [{"decision_id": "dec:go", "status": "PENDING"}]
        result = prepare_work_items(snapshot(), work_set(action), max_deep=1)
        packet = result["packets"][0]
        self.assertEqual(packet["action_maturity"], "BLOCKED")
        self.assertIn("decision dependency dec:go is unresolved", packet["blockers"])

    def test_candidate_is_observation_until_staff_deep_prepares_and_validates_it(self) -> None:
        action = item("fr_exec", "EXECUTE")
        result = prepare_work_items(
            snapshot(), work_set(action), candidate_producers=[RepositoryEvidenceProducer([action_candidate()])], max_deep=0,
        )
        packet = result["packets"][0]
        self.assertEqual(packet["preparation_status"], "DEFERRED_BY_BUDGET")
        self.assertEqual(packet["action_maturity"], "NEEDS_MORE_PREP")
        self.assertFalse(packet["principal_needed"])

    def test_fresh_candidate_becomes_staff_owned_mature_contract(self) -> None:
        action = item("fr_exec", "EXECUTE")
        result = prepare_work_items(
            snapshot(), work_set(action), candidate_producers=[RepositoryEvidenceProducer([action_candidate()])], max_deep=1,
        )
        packet = result["packets"][0]
        self.assertEqual(packet["action_maturity"], "READY_FOR_PULL")
        self.assertEqual(packet["action_contract"]["objective"], action_candidate()["objective"])
        self.assertEqual(packet["current_state"]["horizon"], "THIS_WEEK")

    def test_stale_or_path_leaking_candidate_is_rejected(self) -> None:
        stale = action_candidate(freshness="STALE")
        leaking = action_candidate("ac:repo:path")
        leaking["entry_surface"]["local_path"] = "/home/matias/repos/secret"
        result = prepare_work_items(
            snapshot(), work_set(item("fr_exec", "EXECUTE")), candidate_producers=[RepositoryEvidenceProducer([stale, leaking])], max_deep=1,
        )
        packet = result["packets"][0]
        self.assertEqual(packet["action_maturity"], "NEEDS_MORE_PREP")
        self.assertIn("stale or unknown", " ".join(packet["uncertainties"]))
        self.assertIn("machine-local path", " ".join(packet["uncertainties"]))

    def test_candidates_are_bounded_and_deterministic(self) -> None:
        candidates = [action_candidate(f"ac:repo:{number}") for number in range(5)]
        result = prepare_work_items(
            snapshot(), work_set(item("fr_exec", "EXECUTE")), candidate_producers=[RepositoryEvidenceProducer(list(reversed(candidates)))], max_deep=1,
        )
        evidence = next(row for row in result["packets"][0]["evidence"] if row["adapter"] == "action_candidates")
        self.assertEqual([row["candidate_id"] for row in evidence["candidates"]], ["ac:repo:0", "ac:repo:1", "ac:repo:2"])

    def test_control_plane_candidate_cannot_change_governed_work_state(self) -> None:
        candidate = action_candidate()
        candidate["producer"] = "CONTROL_PLANE_EVIDENCE"
        result = prepare_work_items(
            snapshot(), work_set(item("fr_exec", "EXECUTE")), candidate_producers=[ControlPlaneEvidenceProducer([candidate])], max_deep=1,
        )
        state = result["packets"][0]["current_state"]
        self.assertEqual((state["carry_status"], state["horizon"], state["priority_mode"]), ("ACTIVE", "THIS_WEEK", "SPRINT"))

    def test_non_execute_facets_do_not_receive_action_contract_missing_uncertainty(self) -> None:
        verify = item("fr_exec", "VERIFY")
        verify["human_focus"] = True  # ACTION budget lane, not an EXECUTE facet.
        decide = item("fr_decide", "DECIDE", principal_required=True)
        result = prepare_work_items(snapshot(), work_set(verify, decide), max_deep=2)
        packets = {packet["kind"]: packet for packet in result["packets"]}
        self.assertEqual(packets["VERIFY"]["action_maturity"], "NOT_AN_ACTION")
        self.assertNotIn("action contract", " ".join(packets["VERIFY"]["uncertainties"]))
        self.assertNotIn("action contract", " ".join(packets["DECIDE"]["uncertainties"]))

    def test_maintenance_without_staff_requirement_stays_light(self) -> None:
        adapter = CountingAdapter()
        result = prepare_work_items(snapshot(), work_set(item("fr_maint", "MAINTAIN", prep_mode="NONE")), adapters=[adapter], max_deep=0)
        packet = result["packets"][0]
        self.assertEqual(packet["preparation_status"], "PREPARED_LIGHT")
        self.assertEqual(packet["triage"]["prep_depth"], "LIGHT")
        self.assertEqual(result["deep_used"], 0)

    def test_snapshot_adapter_preserves_runtime_support_and_operator_evidence(self) -> None:
        result = prepare_work_items(snapshot(), work_set(item("fr_decide", "DECIDE", principal_required=True), item("fr_exec", "EXECUTE")), max_deep=2)
        packets = {packet["front_id"]: packet for packet in result["packets"]}
        decide_evidence = packets["fr_decide"]["evidence"][0]
        exec_evidence = packets["fr_exec"]["evidence"][0]
        self.assertEqual(decide_evidence["runtime"]["health_status"], "OK")
        self.assertEqual(decide_evidence["support_artifacts"][0]["artifact_id"], "sa_1")
        self.assertEqual(exec_evidence["operator_contracts"][0]["contract_id"], "opc_1")
        self.assertIn("runtime health is unknown", packets["fr_exec"]["uncertainties"])

    def test_packet_contains_no_governance_reread_or_local_execution_path(self) -> None:
        result = prepare_work_items(snapshot(), work_set(item("fr_exec", "EXECUTE")), max_deep=1, prepared_at="2026-09-15T00:00:00Z")
        packet = result["packets"][0]
        self.assertEqual(packet["source_snapshot_digest"], "sha256:snapshot")
        self.assertEqual(packet["identity"]["path_authority"], "repo_workspaces_v2")
        self.assertNotIn("local_path", str(packet))

    def test_identical_inputs_produce_identical_preparation(self) -> None:
        first = prepare_work_items(
            snapshot(),
            work_set(item("fr_exec", "EXECUTE"), item("fr_decide", "DECIDE", principal_required=True)),
            max_deep=2,
            prepared_at="2026-09-15T00:00:00Z",
        )
        second = prepare_work_items(
            snapshot(),
            work_set(item("fr_exec", "EXECUTE"), item("fr_decide", "DECIDE", principal_required=True)),
            max_deep=2,
            prepared_at="2026-09-15T00:00:00Z",
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
