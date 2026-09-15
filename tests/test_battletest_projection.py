from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from office_runtime.office.battletest_projection import (
    BattleTestProjectionError,
    render_battletest_projection,
    validate_projection_bundle,
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def generation(root: Path, run_id: str) -> Path:
    run = root / run_id
    snapshot = f"sha256:snapshot-{run_id}"
    preparation = f"sha256:preparation-{run_id}"
    principal = f"sha256:principal-{run_id}"
    execution = f"sha256:execution-{run_id}"
    write_json(run / "manifest.json", {
        "run_id": run_id,
        "status": "ok",
        "counts": {"work_items": 2},
        "lineage": {"snapshot_digest": snapshot, "preparation_digest": preparation, "principal_brief_digest": principal, "execution_plan_digest": execution},
    })
    write_json(run / "control" / "snapshot.json", {"snapshot_digest": snapshot})
    write_json(run / "staff" / "preparation.json", {"source_snapshot_digest": snapshot, "preparation_digest": preparation, "counts": {"PREPARED_DEEP": 1, "DEFERRED_BY_BUDGET": 1}, "deep_by_lane": {"ACTION": 1}})
    write_json(run / "principal" / "brief.json", {"source_snapshot_digest": snapshot, "source_preparation_digest": preparation, "brief_digest": principal, "needs_you": [], "ready_pulls": [], "exceptions": [], "staff_follow_up": [], "counts": {"exceptions": 0}})
    write_json(run / "execution" / "plan.json", {"source_snapshot_digest": snapshot, "source_principal_brief_digest": principal, "plan_digest": execution, "packets": [], "exceptions": []})
    return run


class BattleTestProjectionTests(unittest.TestCase):
    def test_projection_binds_every_artifact_to_one_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = generation(root / "runs", "v7")
            result = render_battletest_projection(run, root / "review", generated_at="2026-09-15T04:00:00Z")
            self.assertEqual(result["projection_lineage"]["source_generation_run_id"], "v7")
            self.assertEqual(validate_projection_bundle(root / "review")["status"], "ok")

    def test_stale_artifact_cannot_pass_as_new_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = generation(root / "runs", "v7")
            review = root / "review"
            render_battletest_projection(run, review, generated_at="2026-09-15T04:00:00Z")
            path = review / "2026-09-15-prep" / "principal.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["projection_lineage"]["source_generation_run_id"] = "v3"
            write_json(path, value)
            with self.assertRaises(BattleTestProjectionError):
                validate_projection_bundle(review)

    def test_regeneration_repoints_review_surface_coherently(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            review = root / "review"
            render_battletest_projection(generation(root / "runs", "v3"), review, generated_at="2026-09-15T04:00:00Z")
            render_battletest_projection(generation(root / "runs", "v7"), review, generated_at="2026-09-15T05:00:00Z")
            current = json.loads((review / "projection_current.json").read_text(encoding="utf-8"))
            principal = json.loads((review / "2026-09-15-prep" / "principal.json").read_text(encoding="utf-8"))
            self.assertEqual(current["projection_lineage"]["source_generation_run_id"], "v7")
            self.assertEqual(principal["projection_lineage"], current["projection_lineage"])
            self.assertEqual(validate_projection_bundle(review)["source_generation_run_id"], "v7")

    def test_generation_stage_lineage_must_already_be_coherent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = generation(root / "runs", "v7")
            write_json(run / "principal" / "brief.json", {"source_snapshot_digest": "sha256:wrong", "source_preparation_digest": "sha256:preparation-v7", "brief_digest": "sha256:principal-v7"})
            with self.assertRaises(BattleTestProjectionError):
                render_battletest_projection(run, root / "review", generated_at="2026-09-15T04:00:00Z")


if __name__ == "__main__":
    unittest.main()
