from __future__ import annotations

import unittest

import pandas as pd

from office_runtime.office.control_snapshot import (
    ControlSnapshotError,
    SCHEMA_VERSION,
    TABLE_SPECS,
    build_snapshot,
    validate_tables,
)


def _frame(columns: list[str], *rows: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns)


def valid_frames() -> dict[str, pd.DataFrame]:
    return {
        "front_registry_v2": _frame(
            ["front_id", "slug", "title", "group_key", "lifecycle_status"],
            ["fr_0001", "control-tower", "Control Tower", "ops", "ACTIVE"],
            ["fr_0003", "office-auto-lab", "Office Auto Lab", "ops", "ACTIVE"],
        ),
        "carry_state_v2": _frame(
            ["front_id", "carry_status", "horizon", "priority_mode", "needs", "principal_mode"],
            ["fr_0001", "ACTIVE", "THIS_WEEK", "SPRINT", "finish migration", "REQUIRED"],
            ["fr_0003", "ACTIVE", "THIS_WEEK", "SPRINT", "wire v2", "RECOMMENDED"],
        ),
        "Capabilities_v2": _frame(
            ["front_id", "cap_repo"],
            ["fr_0001", "FALSE"],
            ["fr_0003", "TRUE"],
        ),
        "operator_contract_v2": _frame(
            ["contract_id", "front_id", "operator_name", "operator_class", "contract_status", "contract_version"],
            ["opc_0001", "fr_0001", "primary_operator", "GOVERNANCE", "ACTIVE", "2026-09-v1"],
        ),
        "front_aliases_v2": _frame(
            ["alias_id", "front_id", "alias_namespace", "alias_value", "resolution_status"],
            ["fa2_0001", "fr_0003", "legacy.id", "3", "COLLISION"],
        ),
        "support_artifacts_v2": _frame(
            ["artifact_id", "front_id", "artifact_role", "artifact_kind", "authority_class", "status"],
            ["sa_0001", "fr_0003", "SYSTEM_DECLARATION", "URL", "AUTHORITATIVE", "ACTIVE"],
        ),
        "REPO MONITOR_v2": _frame(
            ["binding_id", "front_id", "repo_id", "workspace_id", "binding_role", "binding_status"],
            ["rb_0001", "fr_0003", "repo.office-auto-lab", "ws_0134", "PRIMARY_IMPLEMENTATION", "ACTIVE"],
        ),
        "repo_workspaces_v2": _frame(
            ["workspace_id", "repo_id", "local_path", "checkout_kind", "workspace_status"],
            ["ws_0134", "repo.office-auto-lab", "/tmp/office-auto-lab", "CHECKOUT", "ACTIVE"],
        ),
        "runtime_health_v2": _frame(
            ["front_id", "health_status", "health_bucket", "source_run_id", "generated_at"],
            ["fr_0003", "OK", "REPO_WORKSPACE_OBSERVED", "bootstrap", "2026-09-14T19:05:00-03:00"],
        ),
    }


class ControlSnapshotV2Tests(unittest.TestCase):
    def test_table_contract_covers_current_v2_control_plane(self) -> None:
        self.assertEqual(
            [spec.name for spec in TABLE_SPECS],
            [
                "front_registry_v2",
                "carry_state_v2",
                "Capabilities_v2",
                "operator_contract_v2",
                "front_aliases_v2",
                "support_artifacts_v2",
                "REPO MONITOR_v2",
                "repo_workspaces_v2",
                "runtime_health_v2",
            ],
        )

    def test_valid_snapshot_preserves_v2_semantics_and_is_deterministic(self) -> None:
        frames = valid_frames()
        a = build_snapshot(frames, observed_at="2026-09-14T22:00:00Z", spreadsheet_id="sheet-1")
        b = build_snapshot(frames, observed_at="2026-09-14T22:00:00Z", spreadsheet_id="sheet-1")

        self.assertEqual(a["schema_version"], SCHEMA_VERSION)
        self.assertEqual(a["snapshot_digest"], b["snapshot_digest"])
        self.assertEqual(a["tables"]["carry_state_v2"]["rows"][0]["carry_status"], "ACTIVE")
        self.assertEqual(a["tables"]["carry_state_v2"]["rows"][0]["horizon"], "THIS_WEEK")
        self.assertEqual(a["tables"]["carry_state_v2"]["rows"][0]["principal_mode"], "REQUIRED")
        observations = [x for x in a["validation"]["issues"] if x["severity"] == "observation"]
        self.assertEqual(observations[0]["code"], "declared_alias_collisions")

    def test_unknown_front_is_a_hard_error(self) -> None:
        frames = valid_frames()
        frames["carry_state_v2"].loc[0, "front_id"] = "fr_missing"

        issues = validate_tables(frames)
        self.assertTrue(any(x["code"] == "unknown_front_id" for x in issues))
        with self.assertRaises(ControlSnapshotError):
            build_snapshot(frames)

    def test_unknown_workspace_is_a_hard_error(self) -> None:
        frames = valid_frames()
        frames["REPO MONITOR_v2"].loc[0, "workspace_id"] = "ws_missing"

        issues = validate_tables(frames)
        self.assertTrue(any(x["code"] == "unknown_workspace_id" for x in issues))
        with self.assertRaises(ControlSnapshotError):
            build_snapshot(frames)

    def test_duplicate_primary_key_is_a_hard_error(self) -> None:
        frames = valid_frames()
        duplicate = frames["front_registry_v2"].iloc[[0]].copy()
        frames["front_registry_v2"] = pd.concat([frames["front_registry_v2"], duplicate], ignore_index=True)

        issues = validate_tables(frames)
        self.assertTrue(any(x["code"] == "duplicate_primary_key" for x in issues))
        with self.assertRaises(ControlSnapshotError):
            build_snapshot(frames)

    def test_missing_required_column_is_a_hard_error(self) -> None:
        frames = valid_frames()
        frames["operator_contract_v2"] = frames["operator_contract_v2"].drop(columns=["operator_class"])

        issues = validate_tables(frames)
        self.assertTrue(any(x["code"] == "missing_column" and x.get("field") == "operator_class" for x in issues))
        with self.assertRaises(ControlSnapshotError):
            build_snapshot(frames)


if __name__ == "__main__":
    unittest.main()
