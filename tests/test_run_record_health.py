from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from office_runtime.office.run_records import (
    RunRecordError,
    build_run_record,
    compile_runtime_health,
    load_run_records,
    write_run_record,
)


def record(
    run_id: str,
    *,
    status: str = "SUCCEEDED",
    publication_status: str = "PUBLISHED",
    started_at: str = "2026-09-15T08:05:00Z",
    finished_at: str = "2026-09-15T08:06:00Z",
    failures: list[dict] | None = None,
) -> dict:
    return build_run_record(
        run_id=run_id,
        trigger="scheduled",
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        publication_status=publication_status,
        stage_results={"coherent_generation": {"status": "OK" if status == "SUCCEEDED" else "FAILED"}},
        source_snapshot_digest="sha256:snapshot" if status == "SUCCEEDED" else "",
        manifest_digest="sha256:manifest" if status == "SUCCEEDED" and publication_status == "PUBLISHED" else "",
        counts={"work_items": 3},
        failures=failures or ([{"type": "RuntimeError", "message": "boom"}] if status == "FAILED" else []),
        run_path=f"v2/runs/{run_id}" if status == "SUCCEEDED" else "",
    )


class RunRecordHealthTests(unittest.TestCase):
    def test_record_round_trip_and_success_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_run_record(root, record("run-1"))
            self.assertTrue(path.is_file())
            rows = load_run_records(root)
            self.assertEqual(len(rows), 1)
            projection = compile_runtime_health(rows, generated_at="2026-09-15T09:00:00Z")
            health = projection["rows"][0]
            self.assertEqual(health["health_status"], "OK")
            self.assertEqual(health["health_bucket"], "LAST_SCHEDULED_RUN_OK")
            self.assertEqual(health["source_run_id"], "run-1")
            self.assertEqual(health["last_observed_by"], "fr_0004")

    def test_latest_failure_wins(self) -> None:
        rows = [
            record("run-1"),
            record(
                "run-2",
                status="FAILED",
                publication_status="NOT_PUBLISHED",
                started_at="2026-09-15T12:05:00Z",
                finished_at="2026-09-15T12:05:20Z",
            ),
        ]
        health = compile_runtime_health(rows, generated_at="2026-09-15T12:10:00Z")["rows"][0]
        self.assertEqual(health["health_status"], "FAIL")
        self.assertEqual(health["health_bucket"], "LAST_RUN_FAILED")
        self.assertEqual(health["source_run_id"], "run-2")
        self.assertIn("boom", health["short_diag"])

    def test_shadow_run_does_not_satisfy_runtime_health(self) -> None:
        rows = [record("shadow-1", publication_status="SHADOW")]
        health = compile_runtime_health(rows, generated_at="2026-09-15T09:00:00Z")["rows"][0]
        self.assertEqual(health["health_status"], "UNKNOWN")
        self.assertEqual(health["health_bucket"], "OBSERVABILITY_GAP")

    def test_stale_success_is_warning(self) -> None:
        health = compile_runtime_health(
            [record("run-1")],
            generated_at="2026-09-16T00:30:00Z",
            stale_after_seconds=14 * 60 * 60,
        )["rows"][0]
        self.assertEqual(health["health_status"], "WARN")
        self.assertEqual(health["health_bucket"], "SCHEDULED_RUN_STALE")

    def test_not_expected_is_not_a_failure(self) -> None:
        health = compile_runtime_health(
            [],
            generated_at="2026-09-15T09:00:00Z",
            expected_producers={"fr_0003": False},
        )["rows"][0]
        self.assertEqual(health["health_status"], "N/A")
        self.assertEqual(health["health_bucket"], "NO_RUNTIME_EXPECTED")

    def test_failed_record_requires_failure_evidence(self) -> None:
        with self.assertRaises(RunRecordError):
            build_run_record(
                run_id="run-x",
                trigger="scheduled",
                started_at="2026-09-15T08:05:00Z",
                finished_at="2026-09-15T08:05:01Z",
                status="FAILED",
                publication_status="NOT_PUBLISHED",
                stage_results={"coherent_generation": {"status": "FAILED"}},
            )


if __name__ == "__main__":
    unittest.main()
