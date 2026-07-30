from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from office_runtime.ops.repo_health.adapters.gcp import BigQueryHistorySink, GCSRunEvidenceSink, GoogleBigQueryClient
from office_runtime.ops.repo_health.cloud.run_job import build_gcp_dependencies, execute_snapshot, main, validate_cloud_snapshot
from office_runtime.ops.repo_health.remote import CommitFacts, InMemoryRepositorySource, RepositoryFacts, TreeEntry
from office_runtime.ops.repo_health.run_bundle import DuplicateRunError

NOW = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
RUNBOOK = "Prerequisites: Python\nTroubleshooting: logs\nAcceptance: green\nRun: make smoke\n"


def snapshot():
    return {
        "producer_commit": "abc123", "policy_input_id": "policy-1", "repository_allowlist": ["owner/repo"],
        "projects": [{"project_id": "demo", "repository_full_name": "owner/repo", "enabled": True, "next": "2026-07-29"}],
        "capabilities": [{"project_id": "demo", "capability_tag": "remote"}],
        "plugin_policy": [
            {"capability_tag": "remote", "plugin": "activity_remote", "default_mode": "on"},
            {"capability_tag": "remote", "plugin": "runbook_remote", "default_mode": "on"},
        ],
        "plugin_prereqs": [
            {"plugin": "activity_remote", "required_fields": "repository_full_name"},
            {"plugin": "runbook_remote", "required_fields": "repository_full_name"},
        ],
    }


def source():
    return InMemoryRepositorySource(
        RepositoryFacts("owner/repo", "main", "a" * 40),
        [TreeEntry("README.md", "blob"), TreeEntry(".gitignore", "blob"), TreeEntry("docs/runbook.md", "blob")],
        {"README.md": "hi", ".gitignore": "*.pyc", "docs/runbook.md": RUNBOOK},
        [CommitFacts("a" * 40, NOW - timedelta(days=1), "recent")],
    )


class Blob:
    def __init__(self, name, objects): self.name, self.objects = name, objects
    def upload_from_string(self, value, **kwargs):
        if self.name in self.objects: raise RuntimeError("precondition")
        self.objects[self.name] = bytes(value)
    def download_as_bytes(self): return self.objects[self.name]


class Bucket:
    def __init__(self, name): self.name, self.objects = name, {}
    def blob(self, name): return Blob(name, self.objects)


class StorageClient:
    def __init__(self): self.buckets = {}
    def bucket(self, name): return self.buckets.setdefault(name, Bucket(name))


class BigQueryClient:
    def __init__(self): self.identities, self.inserts = {}, []
    def lookup_run_sha(self, table, run_id, run_date): return self.identities.get(run_id)
    def insert_rows(self, table, rows, row_ids):
        self.inserts.append((table, list(rows), list(row_ids)))
        if table.endswith(".runs"):
            self.identities[rows[0]["run_id"]] = rows[0]["bundle_sha256"]


class RepoHealthGCPTests(unittest.TestCase):
    def bundle(self): return execute_snapshot(snapshot(), repository_source=source(), run_id="run-g4", started_at=NOW)

    def test_cloud_snapshot_rejects_paths_unallowlisted_and_unsupported_plugins(self):
        value = snapshot(); value["projects"][0]["repo_path"] = "/tmp/repo"
        with self.assertRaisesRegex(ValueError, "local path"):
            validate_cloud_snapshot(value)
        value = snapshot(); value["repository_allowlist"] = []
        with self.assertRaisesRegex(ValueError, "not in repository_allowlist"):
            validate_cloud_snapshot(value)
        value = snapshot(); value["plugin_policy"].append({"capability_tag": "remote", "plugin": "smoke", "default_mode": "on"})
        with self.assertRaisesRegex(ValueError, "unsupported plugins"):
            validate_cloud_snapshot(value)

    def test_cloud_orchestrator_builds_valid_bundle_with_two_remote_plugins(self):
        bundle = self.bundle()
        self.assertEqual(bundle["run"]["status"], "success")
        self.assertEqual(sorted(row["plugin"] for row in bundle["plugin_results"]), ["activity_remote", "runbook_remote"])
        self.assertEqual(bundle["counters"]["plugin_results"], 2)

    def test_gcs_packet_is_create_only_and_has_no_latest_object(self):
        client = StorageClient(); sink = GCSRunEvidenceSink(client, "evidence")
        value = self.bundle()
        first, second = sink.write(value), sink.write(value)
        self.assertEqual((first["status"], second["status"]), ("created", "duplicate"))
        names = sorted(client.bucket("evidence").objects)
        self.assertEqual(names, ["repo-health/runs/run-g4/manifest.json", "repo-health/runs/run-g4/run_bundle.json"])
        self.assertFalse(any("latest" in name for name in names))

    def test_gcs_conflicting_object_is_rejected(self):
        client = StorageClient(); sink = GCSRunEvidenceSink(client, "evidence")
        sink.write(self.bundle())
        client.bucket("evidence").objects["repo-health/runs/run-g4/run_bundle.json"] = b"different"
        with self.assertRaises(DuplicateRunError): sink.write(self.bundle())

    def test_bigquery_rows_are_idempotent_and_runs_is_completion_marker(self):
        client = BigQueryClient(); sink = BigQueryHistorySink(client, "project")
        value = self.bundle()
        first, second = sink.append(value), sink.append(value)
        self.assertEqual((first["status"], second["status"]), ("appended", "duplicate"))
        self.assertTrue(client.inserts[-1][0].endswith(".runs"))
        self.assertEqual(len([item for item in client.inserts if item[0].endswith(".runs")]), 1)
        plugin_insert = next(item for item in client.inserts if item[0].endswith(".plugin_results"))
        self.assertIn("normalized_class", plugin_insert[1][0])
        self.assertIn("bundle_sha256", plugin_insert[1][0])
        client.identities["run-g4"] = "0" * 64
        with self.assertRaises(DuplicateRunError): sink.append(value)

    def test_bigquery_replay_lookup_satisfies_required_partition_filter(self):
        job = Mock()
        job.result.return_value = []
        client = Mock()
        client.query.return_value = job
        self.assertIsNone(GoogleBigQueryClient(client).lookup_run_sha("project.repo_health.runs", "run-g4", "2026-07-29"))
        query = client.query.call_args.args[0]
        self.assertIn("run_date = @run_date", query)

    def test_gcp_profile_rejects_service_account_file_before_client_creation(self):
        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/secret/key.json"}, clear=False):
            with self.assertRaisesRegex(ValueError, "assigned service identity"):
                build_gcp_dependencies("project", "bucket", "repo_health", ["owner/repo"], None)

    def test_bigquery_ddl_has_all_models(self):
        ddl = Path("infra/gcp/bigquery.sql").read_text()
        for table in ("runs", "run_intents", "plugin_results", "exceptions", "prepared_blocks"):
            self.assertIn(f"repo_health.{table}", ddl)
        for view in ("latest_plugin_health", "unresolved_issue_signatures", "prepared_blocks_weekly"):
            self.assertIn(f"repo_health.{view}", ddl)

    def test_container_is_non_root_and_uses_narrow_requirements(self):
        dockerfile = Path("Dockerfile.repo-health").read_text()
        self.assertIn("USER office", dockerfile)
        self.assertIn("requirements-repo-health.txt", dockerfile)
        self.assertIn("office_runtime.ops.repo_health.cloud.run_job", dockerfile)

    def test_entrypoint_accepts_environment_delivered_frozen_policy(self):
        with patch.dict(os.environ, {"REPO_HEALTH_POLICY_JSON": json.dumps(snapshot()), "SOURCE_COMMIT": "abc123"}, clear=False):
            self.assertEqual(main(["--profile", "gcp", "--validate-only"]), 0)

    def test_gcp_entrypoint_rejects_policy_image_commit_mismatch(self):
        with patch.dict(os.environ, {"REPO_HEALTH_POLICY_JSON": json.dumps(snapshot()), "SOURCE_COMMIT": "different"}, clear=False):
            with self.assertRaisesRegex(ValueError, "image provenance"):
                main(["--profile", "gcp", "--validate-only"])

    def test_g5_terraform_is_bounded_and_has_no_scheduler(self):
        terraform = "\n".join(path.read_text() for path in Path("infra/gcp").glob("*.tf"))
        self.assertIn("google_cloud_run_v2_job", terraform)
        self.assertIn('task_count = 1', terraform)
        self.assertIn('cpu = "1"', terraform)
        self.assertIn('memory = "512Mi"', terraform)
        self.assertRegex(terraform, r'timeout\s*=\s*"900s"')
        self.assertRegex(terraform, r'max_retries\s*=\s*1')
        self.assertIn("google_billing_budget", terraform)
        for view in ("latest_plugin_health", "unresolved_issue_signatures", "prepared_blocks_weekly"):
            self.assertIn(f'google_bigquery_table" "{view}', terraform)
        self.assertNotIn("google_cloud_scheduler", terraform)


if __name__ == "__main__": unittest.main()
