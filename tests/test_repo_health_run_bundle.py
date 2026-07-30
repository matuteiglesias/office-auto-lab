from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from office_runtime.ops.repo_health.compiler.generate import generate_candidate_blocks, parse_frontier_rows, rollup_projects
from office_runtime.ops.repo_health.run_bundle import (
    AtomicLatestSignalSink, DuplicateRunError, JsonlHistorySink, LocalRunEvidenceSink,
    RunBundleValidationError, build_run_bundle, schema_path, validate_run_bundle,
)

SHA = "a" * 64


def bundle(*, failed=False, run_id="run-1"):
    results = [
        {"result_id": "result-1", "intent_id": "intent-1", "project_id": "demo", "plugin": "activity_remote",
         "normalized_class": "system_error" if failed else "warning", "bucket": "EXCEPTION" if failed else "STALE_REPO:older_than_threshold",
         "short_diag": "failed" if failed else "stale", "failed": failed, "evidence": [], "meta": {}},
        {"result_id": "result-2", "intent_id": "intent-2", "project_id": "demo", "plugin": "runbook_remote",
         "normalized_class": "ok", "bucket": "RUNBOOK_OK", "short_diag": "healthy", "failed": False, "evidence": ["docs/runbook.md:abc"], "meta": {}},
    ]
    exceptions = [{"exception_id": "exception-1", "result_id": "result-1", "category": "plugin_failure", "message": "bounded failure"}] if failed else []
    return build_run_bundle(
        run_id=run_id, started_at="2026-07-29T12:00:00+00:00", ended_at="2026-07-29T12:01:00+00:00", attempt=1,
        producer_commit="abc123", policy_input_id="policy-1", policy_sha256=SHA,
        intents=[{"intent_id": "intent-1", "project_id": "demo", "plugin": "activity_remote"}, {"intent_id": "intent-2", "project_id": "demo", "plugin": "runbook_remote"}],
        plugin_results=results,
        frontier=[{"result_id": "result-1", "project_id": "demo", "plugin": "activity_remote", "bucket": results[0]["bucket"], "normalized_class": results[0]["normalized_class"], "short_diag": results[0]["short_diag"]},
                  {"result_id": "result-2", "project_id": "demo", "plugin": "runbook_remote", "bucket": "RUNBOOK_OK", "normalized_class": "ok", "short_diag": "healthy"}],
        prepared_blocks=[{"block_id": "block-1", "source_result_ids": ["result-1"], "title": "Review stale repository"}],
        exceptions=exceptions,
    )


class RepoHealthRunBundleTests(unittest.TestCase):
    def test_schema_is_versioned_and_bundle_validates(self):
        schema = json.loads(schema_path().read_text())
        self.assertEqual(schema["$id"], "office-auto-lab/repo-health/run-bundle/v1")
        validate_run_bundle(bundle())

    def test_failed_plugin_is_linked_and_yields_partial_success(self):
        value = bundle(failed=True)
        self.assertEqual(value["run"]["status"], "partial_success")
        self.assertEqual(value["counters"]["failed_plugins"], 1)
        self.assertEqual(value["exceptions"][0]["result_id"], "result-1")
        validate_run_bundle(value)

    def test_invalid_links_and_counters_fail_closed(self):
        value = bundle()
        value["frontier"][0]["result_id"] = "missing"
        with self.assertRaisesRegex(RunBundleValidationError, "unknown result"):
            validate_run_bundle(value)
        value = bundle()
        value["counters"]["frontier"] = 999
        with self.assertRaisesRegex(RunBundleValidationError, "do not reconcile"):
            validate_run_bundle(value)

    def test_atomic_writer_creates_manifest_and_exact_replay_is_noop(self):
        with tempfile.TemporaryDirectory() as td:
            sink = LocalRunEvidenceSink(td)
            first = sink.write(bundle())
            second = sink.write(bundle())
            self.assertEqual((first["status"], second["status"]), ("created", "duplicate"))
            run_dir = Path(td) / "run-1"
            manifest = json.loads((run_dir / "manifest.json").read_text())
            payload = (run_dir / "run_bundle.json").read_bytes()
            import hashlib
            self.assertEqual(manifest["files"]["run_bundle.json"]["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertFalse(any(path.name.startswith(".run-1") for path in Path(td).iterdir()))

    def test_duplicate_run_id_with_different_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sink = LocalRunEvidenceSink(td)
            sink.write(bundle())
            changed = bundle()
            changed["run"]["ended_at"] = "2026-07-29T12:02:00+00:00"
            with self.assertRaises(DuplicateRunError):
                sink.write(changed)

    def test_history_sink_is_idempotent_and_rejects_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            sink = JsonlHistorySink(Path(td) / "history.jsonl")
            self.assertEqual(sink.append(bundle())["status"], "appended")
            self.assertEqual(sink.append(bundle())["status"], "duplicate")
            with self.assertRaises(DuplicateRunError):
                sink.append(bundle(run_id="run-1") | {"run": {**bundle()["run"], "ended_at": "2026-07-29T12:02:00+00:00"}})

    def test_latest_signal_write_is_atomic(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "latest.json"
            AtomicLatestSignalSink(path).publish({"run_id": "run-1", "status": "success"})
            self.assertEqual(json.loads(path.read_text())["run_id"], "run-1")
            self.assertEqual(list(Path(td).iterdir()), [path])

    def test_existing_compiler_consumes_bundle_frontier_without_drift(self):
        rows = bundle()["frontier"]
        issues = parse_frontier_rows(rows)
        projects = rollup_projects(issues)
        first = generate_candidate_blocks("2026-07-29", projects, issues)
        second = generate_candidate_blocks("2026-07-29", projects, issues)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
