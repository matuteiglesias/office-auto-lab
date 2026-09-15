from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from office_runtime.office.generation_v2 import GenerationV2Error, compile_generation_from_frames


def frame(columns: list[str], *rows: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns)


def frames() -> dict[str, pd.DataFrame]:
    return {
        "front_registry_v2": frame(
            ["front_id", "slug", "title", "group_key", "lifecycle_status", "enabled", "human_maint", "human_focus", "staff_get", "staff_watch", "staff_post"],
            ["fr_exec", "exec-front", "Execution Front", "ops", "ACTIVE", "TRUE", "FALSE", "TRUE", "TRUE", "TRUE", "TRUE"],
        ),
        "carry_state_v2": frame(
            ["front_id", "carry_status", "horizon", "priority_mode", "needs", "note", "principal_mode"],
            ["fr_exec", "ACTIVE", "THIS_WEEK", "SPRINT", "do bounded implementation", "context", "RECOMMENDED"],
        ),
        "Capabilities_v2": frame(
            ["front_id", "cap_repo"],
            ["fr_exec", "TRUE"],
        ),
        "operator_contract_v2": frame(
            ["contract_id", "front_id", "operator_name", "operator_class", "contract_status", "contract_version", "allowed_powers", "forbidden_powers", "required_seams", "must_consume_shared_modules", "must_not_implement_locally"],
            ["opc_exec", "fr_exec", "primary_operator", "AUTOMATION", "ACTIVE", "v1", "read_state;read_repo;run_checks;write_artifacts", "external_send", "run_record_owner", "fr_0004", "identity_resolution"],
        ),
        "front_aliases_v2": frame(
            ["alias_id", "front_id", "alias_namespace", "alias_value", "resolution_status"],
            ["fa_exec", "fr_exec", "legacy.slug", "exec-front", "RESOLVED"],
        ),
        "support_artifacts_v2": frame(
            ["artifact_id", "front_id", "artifact_role", "artifact_kind", "authority_class", "status", "uri"],
            ["sa_exec", "fr_exec", "EXECUTION_CONTEXT", "URL", "ADVISORY", "ACTIVE", "artifact://exec"],
        ),
        "REPO MONITOR_v2": frame(
            ["binding_id", "front_id", "repo_id", "workspace_id", "binding_role", "is_primary", "binding_status"],
            ["rb_exec", "fr_exec", "repo.exec", "ws_exec", "PRIMARY_IMPLEMENTATION", "TRUE", "ACTIVE"],
        ),
        "repo_workspaces_v2": frame(
            ["workspace_id", "repo_id", "local_path", "checkout_kind", "workspace_status", "is_preferred"],
            ["ws_exec", "repo.exec", "/tmp/not-consumed-by-default", "CHECKOUT", "ACTIVE", "TRUE"],
        ),
        "runtime_health_v2": frame(
            ["front_id", "health_status", "health_bucket", "source_run_id", "generated_at"],
            ["fr_exec", "OK", "LAST_RUN_OK", "run-health", "2026-09-15T00:00:00Z"],
        ),
    }


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class GenerationV2Tests(unittest.TestCase):
    def test_one_generation_is_coherent_and_publishes_only_after_full_compile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = compile_generation_from_frames(
                frames(),
                out_root=root,
                run_id="run-1",
                spreadsheet_id="sheet",
                observed_at="2026-09-15T00:00:00Z",
                prepared_at="2026-09-15T00:01:00Z",
                published_at="2026-09-15T00:02:00Z",
            )
            self.assertTrue(result["published"])
            run = root / "v2" / "runs" / "run-1"
            self.assertTrue((run / "control" / "snapshot.json").is_file())
            self.assertTrue((run / "routing" / "work_items.json").is_file())
            self.assertTrue((run / "staff" / "preparation.json").is_file())
            self.assertTrue((run / "principal" / "brief.json").is_file())
            self.assertTrue((run / "principal" / "brief.md").is_file())
            self.assertTrue((run / "execution" / "plan.json").is_file())
            manifest = read_json(run / "manifest.json")
            snapshot_digest = manifest["lineage"]["snapshot_digest"]
            self.assertEqual(snapshot_digest, manifest["lineage"]["source_work_snapshot_digest"])
            self.assertEqual(snapshot_digest, manifest["lineage"]["source_preparation_snapshot_digest"])
            self.assertEqual(snapshot_digest, manifest["lineage"]["source_principal_snapshot_digest"])
            self.assertEqual(snapshot_digest, manifest["lineage"]["source_execution_snapshot_digest"])
            self.assertEqual(manifest["counts"]["work_items"], 1)
            # Typed work alone is not an action contract. Execution remains
            # empty until Staff supplies a concrete mature action.
            self.assertEqual(manifest["counts"]["execution_packets"], 0)
            current = read_json(root / "v2" / "current.json")
            self.assertEqual(current["run_id"], "run-1")
            self.assertEqual(current["manifest_digest"], manifest["manifest_digest"])

    def test_failed_generation_cannot_replace_known_good_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compile_generation_from_frames(frames(), out_root=root, run_id="run-1")
            before = (root / "v2" / "current.json").read_text(encoding="utf-8")
            with patch("office_runtime.office.generation_v2.compile_principal_brief", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    compile_generation_from_frames(frames(), out_root=root, run_id="run-2")
            self.assertEqual((root / "v2" / "current.json").read_text(encoding="utf-8"), before)
            self.assertFalse((root / "v2" / "runs" / "run-2").exists())
            self.assertFalse((root / "v2" / ".staging" / "run-2").exists())

    def test_new_generation_uses_previous_principal_brief_for_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compile_generation_from_frames(frames(), out_root=root, run_id="run-1")
            changed = frames()
            changed["carry_state_v2"].loc[0, "needs"] = "changed bounded implementation"
            compile_generation_from_frames(changed, out_root=root, run_id="run-2")
            brief = read_json(root / "v2" / "runs" / "run-2" / "principal" / "brief.json")
            self.assertNotEqual(brief["delta"]["baseline"], "none")
            self.assertEqual(brief["delta"]["changed"]["ready_pulls"], [])
            self.assertEqual(read_json(root / "v2" / "current.json")["run_id"], "run-2")

    def test_generation_directories_do_not_retain_stale_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compile_generation_from_frames(frames(), out_root=root, run_id="run-1")
            self.assertTrue(list((root / "v2" / "runs" / "run-1" / "staff" / "packets").glob("*.json")))
            quiet = frames()
            quiet["front_registry_v2"].loc[0, "human_focus"] = "FALSE"
            quiet["front_registry_v2"].loc[0, "staff_get"] = "FALSE"
            compile_generation_from_frames(quiet, out_root=root, run_id="run-2")
            self.assertEqual(list((root / "v2" / "runs" / "run-2" / "staff" / "packets").glob("*.json")), [])
            self.assertEqual(list((root / "v2" / "runs" / "run-2" / "execution" / "packets").glob("*.json")), [])

    def test_shadow_generation_can_complete_without_publishing_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = compile_generation_from_frames(frames(), out_root=root, run_id="shadow-1", publish=False)
            self.assertFalse(result["published"])
            self.assertTrue((root / "v2" / "runs" / "shadow-1" / "manifest.json").is_file())
            self.assertFalse((root / "v2" / "current.json").exists())

    def test_duplicate_or_unsafe_run_id_fails_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compile_generation_from_frames(frames(), out_root=root, run_id="run-1")
            current = (root / "v2" / "current.json").read_text(encoding="utf-8")
            with self.assertRaises(GenerationV2Error):
                compile_generation_from_frames(frames(), out_root=root, run_id="run-1")
            with self.assertRaises(GenerationV2Error):
                compile_generation_from_frames(frames(), out_root=root, run_id="../escape")
            self.assertEqual((root / "v2" / "current.json").read_text(encoding="utf-8"), current)


if __name__ == "__main__":
    unittest.main()
