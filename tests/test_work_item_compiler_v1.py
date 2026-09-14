from __future__ import annotations

import json
import unittest

from office_runtime.office.work_items import compile_work_items


def snapshot(
    *,
    carry_status="ACTIVE",
    principal_mode="RECOMMENDED",
    needs="arbitrary prose",
    human_focus="TRUE",
    human_maint="FALSE",
    staff_get="TRUE",
    cap_repo="FALSE",
    health_status="OK",
    binding=True,
    workspace_status="ACTIVE",
) -> dict:
    bindings = []
    workspaces = []
    if binding:
        bindings = [
            {
                "binding_id": "rb_1",
                "front_id": "fr_1",
                "repo_id": "repo.one",
                "workspace_id": "ws_1",
                "binding_role": "PRIMARY_IMPLEMENTATION",
                "is_primary": "TRUE",
                "binding_status": "ACTIVE",
            }
        ]
        workspaces = [
            {
                "workspace_id": "ws_1",
                "repo_id": "repo.one",
                "local_path": "/real/workspace",
                "checkout_kind": "CHECKOUT",
                "workspace_status": workspace_status,
                "is_preferred": "TRUE",
            }
        ]
    return {
        "snapshot_digest": "sha256:test",
        "tables": {
            "front_registry_v2": {
                "rows": [
                    {
                        "front_id": "fr_1",
                        "title": "Example front",
                        "lifecycle_status": "ACTIVE",
                        "enabled": "TRUE",
                        "human_focus": human_focus,
                        "human_maint": human_maint,
                        "staff_get": staff_get,
                        "staff_watch": "TRUE",
                        "staff_post": "TRUE",
                        "repo_path": "/wrong/direct/path",
                        "workdir": "/wrong/direct/workdir",
                    }
                ]
            },
            "carry_state_v2": {
                "rows": [
                    {
                        "front_id": "fr_1",
                        "carry_status": carry_status,
                        "horizon": "THIS_WEEK",
                        "priority_mode": "SPRINT",
                        "needs": needs,
                        "note": "human context only",
                        "principal_mode": principal_mode,
                    }
                ]
            },
            "Capabilities_v2": {"rows": [{"front_id": "fr_1", "cap_repo": cap_repo}]},
            "runtime_health_v2": {
                "rows": [
                    {
                        "front_id": "fr_1",
                        "health_status": health_status,
                        "health_bucket": "TEST",
                    }
                ]
            },
            "REPO MONITOR_v2": {"rows": bindings},
            "repo_workspaces_v2": {"rows": workspaces},
        },
    }


def kinds(result: dict) -> list[str]:
    return [item["kind"] for item in result["work_items"]]


class WorkItemCompilerV1Tests(unittest.TestCase):
    def test_needs_wording_does_not_route_work(self) -> None:
        a = compile_work_items(snapshot(needs="health check decision unlocker execution"))
        b = compile_work_items(snapshot(needs="completely different prose"))
        self.assertEqual(kinds(a), kinds(b))
        self.assertEqual(kinds(a), ["EXECUTE"])

    def test_principal_and_focus_are_distinct_typed_work(self) -> None:
        result = compile_work_items(snapshot(principal_mode="REQUIRED"))
        self.assertEqual(kinds(result), ["DECIDE", "EXECUTE"])
        decide = result["work_items"][0]
        self.assertTrue(decide["principal_required"])
        self.assertEqual(decide["trigger_codes"], ["PRINCIPAL_REQUIRED"])

    def test_explicit_unhealthy_runtime_emits_verify(self) -> None:
        result = compile_work_items(snapshot(health_status="DEGRADED"))
        self.assertEqual(kinds(result), ["VERIFY", "EXECUTE"])
        self.assertEqual(result["work_items"][0]["trigger_codes"], ["RUNTIME_DEGRADED"])

    def test_maintenance_signal_emits_maintain(self) -> None:
        result = compile_work_items(snapshot(human_focus="FALSE", human_maint="TRUE"))
        self.assertEqual(kinds(result), ["MAINTAIN"])

    def test_repo_capability_without_ready_identity_emits_unblock_and_suppresses_execute(self) -> None:
        result = compile_work_items(snapshot(cap_repo="TRUE", binding=False))
        self.assertEqual(kinds(result), ["UNBLOCK"])
        self.assertEqual(result["work_items"][0]["identity"]["status"], "NOT_READY")

    def test_staff_get_is_preparation_fallback_not_work_kind_parser(self) -> None:
        result = compile_work_items(snapshot(human_focus="FALSE", human_maint="FALSE", staff_get="TRUE"))
        self.assertEqual(kinds(result), ["UNBLOCK"])
        self.assertEqual(result["work_items"][0]["trigger_codes"], ["STAFF_PREPARATION_REQUIRED"])
        self.assertEqual(result["work_items"][0]["prep_mode"], "STAFF_REQUIRED")

    def test_watch_and_parked_carry_do_not_generate_active_work(self) -> None:
        for status in ("WATCH", "PARKED"):
            with self.subTest(status=status):
                result = compile_work_items(snapshot(carry_status=status))
                self.assertEqual(result["work_items"], [])
                self.assertEqual(result["skipped_fronts"][0]["reason"], f"CARRY_{status}")

    def test_work_items_do_not_embed_local_or_legacy_paths(self) -> None:
        result = compile_work_items(snapshot(cap_repo="TRUE"))
        serialized = json.dumps(result)
        self.assertNotIn("/real/workspace", serialized)
        self.assertNotIn("/wrong/direct/path", serialized)
        self.assertNotIn("/wrong/direct/workdir", serialized)
        item = result["work_items"][0]
        self.assertEqual(item["identity"]["repo_ids"], ["repo.one"])
        self.assertEqual(item["identity"]["workspace_states"][0]["workspace_id"], "ws_1")


if __name__ == "__main__":
    unittest.main()
