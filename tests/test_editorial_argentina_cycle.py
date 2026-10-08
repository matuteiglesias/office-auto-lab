"""Offline selector regression cases; no network and no X mutation."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from office_runtime.scripts.run_editorial_argentina_cycle import CycleBlocked, select_candidate
from office_runtime.editorial.publisher.pilot import PilotPolicy


class EconomicsActionsSelectorTests(unittest.TestCase):
    now = datetime(2026, 10, 12, 15, 00, tzinfo=timezone.utc)

    @staticmethod
    def candidate(cid="cand:one", **override):
        return {"candidate_id": cid, "machine_disposition": "stage", "risk_class": "low", "expires_at": ""} | override

    def queue(self, cid="cand:one", *, ago_minutes=10, **override):
        scheduled = self.now - timedelta(minutes=ago_minutes)
        return {
            "candidate_id": cid,
            "decision": "APPROVE",
            "target_surface": "X",
            "publisher_status": "",
            "published_ref": "",
            "scheduled_for": scheduled.isoformat().replace("+00:00", "Z"),
            "updated_at": "",
        } | override

    def test_due_low_risk_approved_candidate_selected(self):
        self.assertEqual(
            select_candidate([self.candidate()], [self.queue()], now=self.now),
            ("cand:one", "publish"),
        )

    def test_old_pilot_slots_are_not_caught_up(self):
        self.assertIsNone(
            select_candidate([self.candidate()], [self.queue(ago_minutes=90)], now=self.now)[0]
        )

    def test_future_slot_is_not_selected(self):
        self.assertIsNone(
            select_candidate([self.candidate()], [self.queue(ago_minutes=-10)], now=self.now)[0]
        )

    def test_no_approval_or_wrong_surface_is_skipped(self):
        for overrides in ({"decision": "HOLD"}, {"decision": "REVIEW"}, {"target_surface": "NONE"}):
            with self.subTest(overrides=overrides):
                self.assertIsNone(
                    select_candidate([self.candidate()], [self.queue(**overrides)], now=self.now)[0]
                )

    def test_high_risk_or_unstaged_candidate_is_skipped(self):
        for overrides in ({"risk_class": "high"}, {"machine_disposition": "hold"}):
            with self.subTest(overrides=overrides):
                self.assertIsNone(
                    select_candidate([self.candidate(**overrides)], [self.queue()], now=self.now)[0]
                )

    def test_account_wide_sheet_cadence_blocks_another_candidate(self):
        published = self.queue("cand:previous", publisher_status="PUBLISHED")
        published["updated_at"] = (self.now - timedelta(hours=2)).isoformat()
        queued = self.queue("cand:new")
        self.assertEqual(
            select_candidate(
                [self.candidate("cand:previous"), self.candidate("cand:new")],
                [published, queued], now=self.now,
            ),
            (None, "account cadence gate (Sheet history)"),
        )

    def test_publishing_is_reconciled_before_new_publication(self):
        previous = self.queue("cand:prior", publisher_status="PUBLISHING")
        self.assertEqual(
            select_candidate(
                [self.candidate("cand:prior"), self.candidate("cand:new")],
                [previous, self.queue("cand:new")], now=self.now,
            ),
            ("cand:prior", "reconcile"),
        )

    def test_multiple_unresolved_attempts_fail_closed(self):
        with self.assertRaises(CycleBlocked):
            select_candidate(
                [self.candidate("cand:a"), self.candidate("cand:b")],
                [self.queue("cand:a", publisher_status="PUBLISHING"), self.queue("cand:b", publisher_status="PUBLISHING")],
                now=self.now,
            )

    def test_deterministic_earliest_due_selection(self):
        self.assertEqual(
            select_candidate(
                [self.candidate("cand:later"), self.candidate("cand:earlier")],
                [self.queue("cand:later", ago_minutes=5), self.queue("cand:earlier", ago_minutes=20)],
                now=self.now,
            ),
            ("cand:earlier", "publish"),
        )

    def test_malformed_publication_timestamp_fails_closed(self):
        with self.assertRaises(CycleBlocked):
            select_candidate(
                [self.candidate("cand:old"), self.candidate("cand:new")],
                [self.queue("cand:old", publisher_status="PUBLISHED"), self.queue("cand:new")],
                now=self.now,
            )

    def test_pilot_selects_only_allowlisted_candidate(self):
        pilot = PilotPolicy(
            candidate_ids=frozenset({"cand:one"}),
            window_start=self.now - timedelta(minutes=1),
            window_end=self.now + timedelta(minutes=10),
        )
        self.assertEqual(
            select_candidate(
                [self.candidate("cand:other"), self.candidate("cand:one")],
                [self.queue("cand:other", ago_minutes=2), self.queue("cand:one", ago_minutes=2)],
                now=self.now,
                min_gap=timedelta(minutes=5),
                max_lateness=timedelta(minutes=5),
                pilot=pilot,
            ),
            ("cand:one", "publish"),
        )

    def test_pilot_cap_is_durable_in_queue_history(self):
        pilot = PilotPolicy(
            candidate_ids=frozenset({"cand:previous", "cand:new"}),
            window_start=self.now - timedelta(minutes=10),
            window_end=self.now + timedelta(minutes=10),
            cap=1,
        )
        published = self.queue("cand:previous", publisher_status="PUBLISHED")
        published["updated_at"] = (self.now - timedelta(minutes=1)).isoformat()
        self.assertEqual(
            select_candidate(
                [self.candidate("cand:previous"), self.candidate("cand:new")],
                [published, self.queue("cand:new")],
                now=self.now,
                min_gap=timedelta(minutes=5),
                max_lateness=timedelta(minutes=5),
                pilot=pilot,
            ),
            (None, "temporary pilot cap reached"),
        )


if __name__ == "__main__":
    unittest.main()
