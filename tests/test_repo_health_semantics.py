from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from office_runtime.ops.repo_health import runner
from office_runtime.ops.repo_health.compiler.generate import (
    candidate_to_prepared_block,
    generate_candidate_blocks,
    parse_frontier_rows,
    rollup_projects,
)
from office_runtime.ops.repo_health.frontier_export import REQUIRED_COLS_V0, export_frontier_latest
from office_runtime.ops.repo_health.plugin_loader import load_plugins_from_folder, select_gcp_plugins
from office_runtime.ops.repo_health.policy import RunIntent, compute_effective_runset
from office_runtime.ops.repo_health.plugins.base import BasePlugin, PluginCapability
from office_runtime.ops.repo_health.sheets import SCOPES, auth_gspread, read_tab_records


class RepoHealthSemanticsTests(unittest.TestCase):
    """Protect accepted local semantics and the cloud capability boundary."""

    @staticmethod
    def _policy_intent(next_date: str | None) -> RunIntent:
        projects = [{"project_id": "demo", "enabled": True, "next": next_date, "repo_path": "/tmp/demo"}]
        capabilities = [{"project_id": "demo", "capability_tag": "source"}]
        plugin_policy = [{"capability_tag": "source", "plugin": "commit_recent", "default_mode": "on"}]
        plugin_prereqs = [{"plugin": "commit_recent", "required_fields": "repo_path"}]
        intents = compute_effective_runset(
            projects,
            capabilities,
            plugin_policy,
            plugin_prereqs,
            "2026-07-29",
            return_debug=False,
        )
        return intents[0]

    def test_not_due_intent_is_not_scheduled(self) -> None:
        intent = self._policy_intent("2026-07-30")
        self.assertFalse(intent.due)
        self.assertTrue(intent.prereq_ok)
        self.assertFalse(intent.scheduled)

    def test_due_intent_is_scheduled_when_prerequisites_pass(self) -> None:
        intent = self._policy_intent("2026-07-29")
        self.assertTrue(intent.due)
        self.assertTrue(intent.scheduled)

    def test_due_intent_with_missing_prerequisite_is_not_scheduled(self) -> None:
        intents = compute_effective_runset(
            [{"project_id": "demo", "enabled": True, "next": "2026-07-28"}],
            [{"project_id": "demo", "capability_tag": "source"}],
            [{"capability_tag": "source", "plugin": "commit_recent", "default_mode": "on"}],
            [{"plugin": "commit_recent", "required_fields": "repo_path"}],
            "2026-07-29",
            return_debug=False,
        )
        self.assertTrue(intents[0].due)
        self.assertFalse(intents[0].prereq_ok)
        self.assertFalse(intents[0].scheduled)

    def test_disabled_project_produces_no_intent(self) -> None:
        intents = compute_effective_runset(
            [{"project_id": "demo", "enabled": False, "next": "2026-07-28", "repo_path": "/tmp/demo"}],
            [{"project_id": "demo", "capability_tag": "source"}],
            [{"capability_tag": "source", "plugin": "commit_recent", "default_mode": "on"}],
            [{"plugin": "commit_recent", "required_fields": "repo_path"}],
            "2026-07-29",
            return_debug=False,
        )
        self.assertEqual(intents, [])

    def test_missing_next_date_is_not_scheduled_and_is_auditable(self) -> None:
        intent = self._policy_intent(None)
        self.assertFalse(intent.due)
        self.assertFalse(intent.scheduled)
        self.assertEqual(intent.skip_reason, "missing_next")

    def test_no_write_suppresses_sheet_and_frontier_mutations(self) -> None:
        intent = RunIntent(
            run_id="intent-1",
            run_date="2026-07-29",
            project_id="demo",
            plugin="fixture",
            implied_by_tags=["source"],
            priority="Sprint",
            due=True,
            prereq_ok=True,
            ineligible_bucket="",
            skip_reason="",
            scheduled=True,
            make_target="",
        )
        plugin = Mock()
        plugin.run.return_value = {
            "status": "PASS",
            "bucket": "DETAIL_BUCKET",
            "message": "healthy",
            "evidence": ["commit:abc"],
            "meta": {"branch": "main"},
        }
        sheet = Mock()
        with (
            patch.object(runner, "parse_args", return_value=SimpleNamespace(
                date="2026-07-29", apply=True, no_write=True, policy_only=False,
                sa="fixture.json", sheet_id="sheet", rows=None, subset=None, plugins=None,
            )),
            patch.object(runner, "setup_logging"),
            patch.object(runner, "auth_gspread") as auth,
            patch.object(runner, "read_tab_records", side_effect=[
                [{"project_id": "demo"}], [], [], [],
            ]),
            patch.object(runner, "compute_effective_runset", return_value=([intent], {})),
            patch.object(runner, "load_plugins_from_folder", return_value={"fixture": plugin}),
            patch.object(runner, "write_tab_overwrite") as overwrite,
            patch.object(runner, "append_rows") as append,
            patch.object(runner, "export_frontier_latest") as export,
            patch.object(runner, "ensure_header_has_columns") as ensure_header,
        ):
            auth.return_value.open_by_key.return_value = sheet
            export.return_value = {"rows": 1}
            runner.main([])

        overwrite.assert_not_called()
        ensure_header.assert_not_called()
        append.assert_not_called()
        export.assert_not_called()
        self.assertTrue(plugin.run.call_args.args[0]["dry_run"])

    def test_runner_normalization_preserves_plugin_evidence_and_meta(self) -> None:
        intent = RunIntent(
            run_id="intent-1", run_date="2026-07-29", project_id="demo", plugin="fixture",
            implied_by_tags=[], priority="", due=True, prereq_ok=True,
            ineligible_bucket="", skip_reason="", scheduled=True, make_target="",
        )
        plugin = Mock()
        plugin.run.return_value = {
            "status": "FAIL", "bucket": "DETAIL_BUCKET", "message": "broken",
            "evidence": ["log:123"], "meta": {"exit_code": 2},
        }
        row = runner.execute_intent(intent, {"repo_path": "/tmp/demo"}, {"fixture": plugin}, dry_run=True)
        self.assertEqual(row["normalized_class"], "actionable_failure")
        self.assertEqual(row["bucket"], "DETAIL_BUCKET")
        self.assertEqual(row["evidence"], ["log:123"])
        self.assertEqual(row["meta"], {"exit_code": 2})

    def test_frontier_schema_intentionally_omits_evidence_and_meta(self) -> None:
        row = {
            "run_id": "r1", "date": "2026-07-29", "project_id": "demo", "plugin": "fixture",
            "executed": True, "normalized_class": "warning", "bucket": "WARN",
            "short_diag": "check", "ts_started": 1, "duration_ms": 2,
            "evidence": ["log:123"], "meta": {"detail": True},
        }
        with tempfile.TemporaryDirectory() as td:
            result = export_frontier_latest([row], run_date="2026-07-29", out_root=td)
            with Path(result["latest_csv"]).open(encoding="utf-8", newline="") as f:
                exported = next(csv.DictReader(f))
        self.assertEqual(list(exported), REQUIRED_COLS_V0)
        self.assertNotIn("evidence", exported)
        self.assertNotIn("meta", exported)

    def test_current_plugin_discovery_inventory_is_dynamic_and_complete(self) -> None:
        plugins = load_plugins_from_folder("src/office_runtime/ops/repo_health/plugins")
        self.assertEqual(
            sorted(plugins),
            ["activity_remote", "commit_recent", "env", "pipeline_output", "runbook", "runbook_remote", "smoke"],
        )

    def test_local_git_plugin_requires_a_repository_path(self) -> None:
        plugin = load_plugins_from_folder()["commit_recent"]
        result = plugin.run({"project": {}, "timeouts": {"shell": 1}})
        self.assertEqual(result["normalized_class"], "ineligible")
        self.assertEqual(result["bucket"], "MISSING_METADATA:repo_path")

    def test_existing_plugins_declare_only_local_or_execute_capabilities(self) -> None:
        plugins = load_plugins_from_folder()
        self.assertEqual(plugins["smoke"].capability, PluginCapability.REMOTE_EXECUTE)
        for name in {"commit_recent", "env", "pipeline_output", "runbook"}:
            self.assertEqual(plugins[name].capability, PluginCapability.LOCAL_ONLY)
        self.assertEqual(sorted(select_gcp_plugins(plugins)), ["activity_remote", "runbook_remote"])

    def test_gcp_selection_requires_both_allowlist_and_remote_read_capability(self) -> None:
        class RemoteFixture(BasePlugin):
            name = "activity_remote"
            capability = PluginCapability.REMOTE_READ

        class LocalFixture(BasePlugin):
            name = "runbook_remote"
            capability = PluginCapability.LOCAL_ONLY

        plugins = {
            "activity_remote": RemoteFixture(),
            "runbook_remote": LocalFixture(),
            "unapproved_remote": RemoteFixture(),
        }
        plugins["unapproved_remote"].name = "unapproved_remote"
        self.assertEqual(list(select_gcp_plugins(plugins)), ["activity_remote"])

    def test_gcp_selection_rejects_unknown_capability(self) -> None:
        plugin = BasePlugin()
        plugin.capability = "networkish"
        with self.assertRaisesRegex(ValueError, "unknown capability"):
            select_gcp_plugins({"bad": plugin})

    def test_policy_reads_do_not_create_missing_worksheets(self) -> None:
        sheet = Mock()
        sheet.worksheet.side_effect = RuntimeError("missing")
        with self.assertRaisesRegex(RuntimeError, "missing"):
            read_tab_records(sheet, "Capabilities")
        self.assertFalse(sheet.add_worksheet.called)

    def test_no_write_logging_does_not_create_a_log_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            log_dir = Path(td) / "logs"
            logger = runner.setup_logging("r1", str(log_dir), write_file=False)
            self.assertFalse(log_dir.exists())
            self.assertEqual(len(logger.handlers), 1)

    def test_compiler_output_is_deterministic_for_fixed_frontier_fixture(self) -> None:
        fixture = Path("fixtures/frontier_sample_v2.csv")
        with fixture.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))

        def compile_once() -> str:
            issues = parse_frontier_rows(rows)
            projects = rollup_projects(issues)
            candidates = generate_candidate_blocks("2026-07-29", projects, issues)
            prepared = [candidate_to_prepared_block("2026-07-29", item) for item in candidates]
            return json.dumps(prepared, sort_keys=True, separators=(",", ":"))

        self.assertEqual(compile_once(), compile_once())

    def test_cli_requires_service_account_file_and_auth_uses_it(self) -> None:
        with self.assertRaises(SystemExit):
            runner.parse_args(["--sheet-id", "sheet"])
        with patch("office_runtime.ops.repo_health.sheets.Credentials.from_service_account_file") as load_creds, patch(
            "office_runtime.ops.repo_health.sheets.gspread.authorize"
        ):
            auth_gspread("service-account.json")
        load_creds.assert_called_once_with("service-account.json", scopes=SCOPES)


if __name__ == "__main__":
    unittest.main()
