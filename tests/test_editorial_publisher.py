from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from office_runtime.editorial.publisher.pilot import (
    EXPECTED_USER_ID,
    EXPECTED_USERNAME,
    PilotPolicy,
    PilotPublisher,
)
from office_runtime.editorial.publisher.config import PublisherConfig
from office_runtime.editorial.publisher.xurl_adapter import XIdentity, XPost
from office_runtime.editorial.staging.sheets import (
    CANDIDATES_HEADERS,
    CANDIDATES_TAB,
    InMemorySheetGateway,
    QUEUE_HEADERS,
    QUEUE_TAB,
)

NOW = datetime(2026, 10, 7, 21, 0, tzinfo=timezone.utc)
P1 = "cand:b9572a5fdc329e88dee0bcaf"


class FakeX:
    def __init__(self, *, identity: XIdentity | None = None, recent: list[XPost] | None = None):
        self.identity = identity or XIdentity(EXPECTED_USERNAME, EXPECTED_USER_ID)
        self.recent = list(recent or [])
        self.created: list[str] = []
        self.reads: list[str] = []

    def whoami(self) -> XIdentity:
        return self.identity

    def recent_posts(self, username: str, max_results: int = 100) -> list[XPost]:
        return list(self.recent)

    def create_post(self, text: str) -> XPost:
        post = XPost(str(100 + len(self.created)), text, username=EXPECTED_USERNAME, created_at=NOW.isoformat(), author_id=EXPECTED_USER_ID)
        self.created.append(text)
        self.recent.insert(0, post)
        return post

    def read_post(self, post_id: str) -> XPost:
        self.reads.append(post_id)
        return next(post for post in self.recent if post.post_id == post_id)


def gateway_for(*, decision: str = "APPROVE", target: str = "X", status: str = "", expires: str = "2026-10-21T20:25:00Z", quality: dict | None = None):
    quality = quality or {"manual_seed": True}
    candidate = [
        P1, "batch", "run", "2026-10-07T20:25:00Z", "2026-10-07", "1", "repo", "[]", "lesson", "LESSON",
        "claim", "[]", "[]", "[]", "low", "fingerprint", "draft", "stage", json.dumps(quality), expires,
        "office_runtime.editorial.sheet.candidates.v1",
    ]
    queue = [P1, "draft", decision, "", target, status, "", "", "", "office_runtime.editorial.sheet.queue.v1"]
    return InMemorySheetGateway({CANDIDATES_TAB: [list(CANDIDATES_HEADERS), candidate], QUEUE_TAB: [list(QUEUE_HEADERS), queue]})


class PublisherTests(unittest.TestCase):
    def test_profiles_are_account_and_transport_isolated(self):
        dev = PublisherConfig.from_profile("dev")
        econ = PublisherConfig.from_profile("argentina_econ")
        self.assertEqual((dev.xurl_app, dev.xurl_auth, dev.expected_user_id), ("modernai-editorial", "oauth1", "1927563136636243968"))
        self.assertEqual((econ.xurl_app, econ.xurl_auth, econ.expected_username, econ.expected_user_id), ("argentina-econ-editorial", "oauth1", "matuteiglesias", "57242581"))
        self.assertNotEqual(dev.sheet_id_env, econ.sheet_id_env)
        self.assertNotEqual(dev.receipt_namespace, econ.receipt_namespace)

    def test_temporary_economics_pilot_is_explicit_and_bounded(self):
        config = PublisherConfig.from_profile("argentina_econ")
        gateway = gateway_for()
        gateway.rows[QUEUE_TAB][1][6] = "2026-10-07T21:00:00Z"
        pilot = PilotPolicy(
            candidate_ids=frozenset({P1}),
            window_start=datetime(2026, 10, 7, 20, 55, tzinfo=timezone.utc),
            window_end=datetime(2026, 10, 7, 21, 5, tzinfo=timezone.utc),
        )
        result = PilotPublisher(gateway, config=config, x=FakeX(identity=XIdentity("matuteiglesias", "57242581")), clock=lambda: datetime(2026, 10, 7, 21, 0, tzinfo=timezone.utc)).run(P1, apply=False, pilot=pilot)
        self.assertEqual((result.state, result.eligible), ("DRY_RUN", True))
        dev_result = PilotPublisher(gateway, x=FakeX(), clock=lambda: NOW).run(P1, apply=False, pilot=pilot)
        self.assertIn("restricted", dev_result.reason)

    def run_publisher(self, gateway, x=None, *, apply=False, allow=True, artifacts=None):
        return PilotPublisher(gateway, x=x or FakeX(), artifacts_dir=artifacts or Path("/tmp/unused-publisher-test"), clock=lambda: NOW).run(P1, apply=apply, allow_manual_seed=allow)

    def test_review_blocked(self):
        result = self.run_publisher(gateway_for(decision="REVIEW"))
        self.assertEqual(result.reason, "queue decision is not APPROVE")

    def test_manual_seed_requires_explicit_flag(self):
        result = self.run_publisher(gateway_for(), allow=False)
        self.assertEqual(result.reason, "manual seed requires --allow-manual-seed")

    def test_approve_manual_seed_dry_run(self):
        result = self.run_publisher(gateway_for())
        self.assertEqual((result.state, result.eligible), ("DRY_RUN", True))

    def test_forced_acceptance_blocked(self):
        result = self.run_publisher(gateway_for(quality={"manual_seed": True, "forced_pipeline_acceptance": True}))
        self.assertIn("forced pipeline", result.reason)

    def test_hold_reject_and_expired_blocked(self):
        self.assertIn("not APPROVE", self.run_publisher(gateway_for(decision="HOLD")).reason)
        self.assertIn("not APPROVE", self.run_publisher(gateway_for(decision="REJECT")).reason)
        self.assertEqual(self.run_publisher(gateway_for(expires="2026-10-07T20:00:00Z")).reason, "candidate is expired")

    def test_wrong_identity_and_duplicate_and_published_blocked(self):
        wrong = FakeX(identity=XIdentity("Other", "1"))
        self.assertIn("identity", self.run_publisher(gateway_for(), x=wrong).reason)
        duplicate = FakeX(recent=[XPost("1", "draft")])
        self.assertIn("exact text", self.run_publisher(gateway_for(), x=duplicate).reason)
        self.assertIn("already published", self.run_publisher(gateway_for(status="PUBLISHED")).reason)

    def test_apply_readback_and_sheet_writeback(self):
        with TemporaryDirectory() as directory:
            gateway = gateway_for()
            x = FakeX()
            result = self.run_publisher(gateway, x=x, apply=True, artifacts=Path(directory))
            self.assertEqual(result.state, "PUBLISHED")
            row = gateway.read_rows(QUEUE_TAB)[1]
            self.assertEqual(row[5], "PUBLISHED")
            self.assertEqual(row[7], "https://x.com/ModernAIDev/status/100")
            self.assertEqual(len(x.created), 1)

    def test_sheet_failure_reconciles_without_repost(self):
        with TemporaryDirectory() as directory:
            gateway = gateway_for()
            x = FakeX()
            gateway.fail_after_writes = 1
            with self.assertRaises(Exception):
                self.run_publisher(gateway, x=x, apply=True, artifacts=Path(directory))
            gateway.fail_after_writes = None
            result = self.run_publisher(gateway, x=x, apply=True, artifacts=Path(directory))
            self.assertEqual(result.reason, "reconciled prior publication")
            self.assertEqual(len(x.created), 1)

    def test_dry_run_does_not_reconcile_publishing_row(self):
        gateway = gateway_for(status="PUBLISHING")
        x = FakeX(recent=[XPost("777", "draft", username=EXPECTED_USERNAME, author_id=EXPECTED_USER_ID)])
        result = self.run_publisher(gateway, x=x, apply=False)
        self.assertEqual(result.state, "BLOCKED")
        self.assertEqual(gateway.read_rows(QUEUE_TAB)[1][5], "PUBLISHING")
        self.assertEqual(gateway.read_rows(QUEUE_TAB)[1][7], "")

    def test_reconciliation_requires_correct_identity(self):
        gateway = gateway_for(status="PUBLISHING")
        x = FakeX(identity=XIdentity("Other", "123"), recent=[XPost("777", "draft")])
        result = self.run_publisher(gateway, x=x, apply=True)
        self.assertEqual(result.reason, "X account identity mismatch")
        self.assertEqual(gateway.read_rows(QUEUE_TAB)[1][5], "PUBLISHING")

    def test_receipt_cadence_is_account_wide_across_candidates(self):
        with TemporaryDirectory() as directory:
            previous = Path(directory) / "other-candidate.json"
            previous.write_text(json.dumps({
                "profile_id": "dev",
                "candidate_id": "cand:some-other-candidate",
                "state": "PUBLISHED",
                "published_at": NOW.isoformat(),
            }), encoding="utf-8")
            result = self.run_publisher(gateway_for(), artifacts=Path(directory))
            self.assertEqual(result.state, "BLOCKED")
            self.assertIn("cadence", result.reason)

    def test_only_explicit_pilot_id_can_be_mutated(self):
        gateway = gateway_for()
        gateway.rows[CANDIDATES_TAB][1][0] = "cand:not-authorized"
        gateway.rows[QUEUE_TAB][1][0] = "cand:not-authorized"
        result = self.run_publisher(gateway, apply=True)
        self.assertIn("missing", result.reason)


if __name__ == "__main__":
    unittest.main()
