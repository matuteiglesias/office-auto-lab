from __future__ import annotations

import unittest

from office_runtime.staff.freshness import PacketFreshnessError, evaluate_packet_freshness


PACKET = {
    "source_snapshot_digest": "sha256:snap",
    "prepared_at": "2026-09-15T08:06:00Z",
    "evidence": [
        {
            "adapter": "local_repo",
            "status": "ok",
            "repo_id": "repo.example",
            "revision": "abc123",
        }
    ],
}


class StaffPacketFreshnessTests(unittest.TestCase):
    def test_current_packet_is_reusable(self) -> None:
        result = evaluate_packet_freshness(
            PACKET,
            current_snapshot_digest="sha256:snap",
            current_repo_revisions={"repo.example": "abc123"},
        )
        self.assertEqual(result["status"], "CURRENT")
        self.assertTrue(result["reusable"])

    def test_snapshot_change_is_stale(self) -> None:
        result = evaluate_packet_freshness(
            PACKET,
            current_snapshot_digest="sha256:new",
            current_repo_revisions={"repo.example": "abc123"},
        )
        self.assertEqual(result["status"], "STALE_STATE")
        self.assertFalse(result["reusable"])

    def test_repository_revision_change_is_stale(self) -> None:
        result = evaluate_packet_freshness(
            PACKET,
            current_snapshot_digest="sha256:snap",
            current_repo_revisions={"repo.example": "def456"},
        )
        self.assertEqual(result["status"], "STALE_REPOSITORY")
        self.assertFalse(result["reusable"])

    def test_unknown_current_revision_is_not_assumed_fresh(self) -> None:
        result = evaluate_packet_freshness(
            PACKET,
            current_snapshot_digest="sha256:snap",
            current_repo_revisions={},
        )
        self.assertEqual(result["status"], "UNKNOWN_EVIDENCE")
        self.assertFalse(result["reusable"])

    def test_missing_snapshot_identity_is_invalid(self) -> None:
        with self.assertRaises(PacketFreshnessError):
            evaluate_packet_freshness(PACKET, current_snapshot_digest="")


if __name__ == "__main__":
    unittest.main()
