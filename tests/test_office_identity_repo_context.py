import tempfile
import unittest
from pathlib import Path

import pandas as pd

from office_runtime.office.compile import canonicalize_front_identity, _merge
from office_runtime.office.repo_context import enrich_with_repo_context, load_repo_context


class OfficeIdentityRepoContextTests(unittest.TestCase):
    def test_legacy_project_id_becomes_front_id(self):
        df = pd.DataFrame([{"project_id": "front-a", "Title": "A"}])
        out = canonicalize_front_identity(df)
        self.assertEqual(out.loc[0, "front_id"], "front-a")
        self.assertEqual(out.loc[0, "project_id"], "front-a")

    def test_front_id_only_keeps_legacy_alias(self):
        df = pd.DataFrame([{"front_id": "front-a", "Title": "A"}])
        out = canonicalize_front_identity(df)
        self.assertEqual(out.loc[0, "front_id"], "front-a")
        self.assertEqual(out.loc[0, "project_id"], "front-a")

    def test_conflicting_front_and_project_id_fails_closed(self):
        df = pd.DataFrame([{"front_id": "front-a", "project_id": "front-b"}])
        with self.assertRaisesRegex(ValueError, "front_id/project_id conflict"):
            canonicalize_front_identity(df)

    def test_merge_uses_front_identity_and_preserves_legacy_projection(self):
        front = pd.DataFrame([{"front_id": "front-a", "Title": "A"}])
        carry = pd.DataFrame([{"project_id": "front-a", "carry": "Active"}])
        merged, unmatched_front, unmatched_carry = _merge(front, carry)
        self.assertEqual(merged["front_id"].tolist(), ["front-a"])
        self.assertEqual(merged["project_id"].tolist(), ["front-a"])
        self.assertTrue(unmatched_front.empty)
        self.assertTrue(unmatched_carry.empty)

    def test_repo_context_is_advisory_and_allows_front_without_repo(self):
        df = pd.DataFrame(
            [
                {"front_id": "front-a", "repo_ids": "repo.one;repo.unknown", "carry": "Active"},
                {"front_id": "front-b", "repo_ids": "", "carry": "Escalate"},
            ]
        )
        payload = {
            "contract": "context:github-repositories@1",
            "generated_at": "2026-09-01T00:00:00Z",
            "repositories": {"repo.one": {"github": "owner/one", "readiness": "ready"}},
        }
        out, summary = enrich_with_repo_context(df, payload)
        self.assertEqual(out.loc[0, "repo_context_status"], "partial")
        self.assertEqual(out.loc[1, "repo_context_status"], "none")
        self.assertEqual(out["carry"].tolist(), ["Active", "Escalate"])
        self.assertEqual(summary["known_repo_refs"], 1)
        self.assertEqual(summary["unknown_repo_refs"], 1)

    def test_missing_repo_context_is_nonfatal(self):
        df = pd.DataFrame([{"front_id": "front-a", "repo_ids": "repo.one"}])
        out, summary = enrich_with_repo_context(df, None)
        self.assertEqual(out.loc[0, "repo_context_status"], "context-unavailable")
        self.assertEqual(summary["repo_refs"], 1)

    def test_wrong_repo_context_contract_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "repo-context.json"
            path.write_text('{"contract":"wrong","repositories":{}}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected repository context contract"):
                load_repo_context(path)


if __name__ == "__main__":
    unittest.main()
