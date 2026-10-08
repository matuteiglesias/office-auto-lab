import tempfile
import unittest
from datetime import datetime, timezone

from office_runtime.x_observer.contracts import ActivityEvent, ObservedPost, Reference, ObserverContractError
from office_runtime.x_observer.consumer import recent_activity
from office_runtime.x_observer.persistence import EvidenceStore
from office_runtime.x_observer.projection import MemoryProjection


def event(actor: str, post: str, run: str) -> ActivityEvent:
    return ActivityEvent(f"xevt:{actor}:{post}", actor, post, "REPOST", "2026-10-08T12:00:00Z", (Reference("retweeted", "9", "8", "AVAILABLE"),), run, "a" * 64)


class ObserverStorageTests(unittest.TestCase):
    def test_page_manifest_and_cursor_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EvidenceStore(directory)
            page = store.write_page(run_id="run-1", page_number=1, payload={"data": []})
            store.write_manifest("run-1", {"run_id": "run-1", "pages": [page.path]})
            store.compare_and_set_cursor("101", None, {"highest_committed_since_id": "9"})
            with self.assertRaises(ObserverContractError):
                store.compare_and_set_cursor("101", None, {"highest_committed_since_id": "10"})
            self.assertEqual(store.read_cursor("101")["highest_committed_since_id"], "9")

    def test_projection_failure_does_not_advance_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EvidenceStore(directory)
            with self.assertRaises(RuntimeError):
                store.commit_page(user_id="101", run_id="run-1", page_number=1, payload={"data": []}, expected_revision=None, project=lambda _: (_ for _ in ()).throw(RuntimeError("projection")), cursor={"highest_committed_since_id": "9"})
            self.assertIsNone(store.read_cursor("101"))

    def test_replay_is_idempotent_and_reference_is_shared(self):
        projection = MemoryProjection()
        first = event("1", "2", "r1")
        second = event("3", "4", "r2")
        post = ObservedPost("9", "8", "source", None, (), (), "AVAILABLE", "h", "a" * 64)
        projection.apply([first, second, first], [post, post])
        self.assertEqual(len(projection.events), 2)
        self.assertEqual(len(projection.posts), 1)

    def test_consumer_reports_evidence_without_interpretation(self):
        snapshot = {"events": [event("1", "2", "r1").record()], "coverage": "PARTIAL_WINDOW", "gaps": ["pagination"]}
        result = recent_activity(snapshot, now=datetime(2026, 10, 8, 13, tzinfo=timezone.utc))
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["coverage"], "PARTIAL_WINDOW")
        self.assertEqual(result["gaps"], ["pagination"])


if __name__ == "__main__":
    unittest.main()
