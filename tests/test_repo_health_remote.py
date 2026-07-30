from __future__ import annotations

import base64
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from office_runtime.ops.repo_health.plugin_loader import load_plugins_from_folder, select_gcp_plugins
from office_runtime.ops.repo_health.plugins.remote_activity_plugin import RemoteActivityPlugin
from office_runtime.ops.repo_health.plugins.remote_runbook_plugin import RemoteRunbookPlugin
from office_runtime.ops.repo_health.remote import (
    CommitFacts, GitHubRepositorySource, InMemoryRepositorySource, LocalRepositorySource,
    RepositoryFacts, RepositorySourceError, TreeEntry, validate_repository_identity,
)

NOW = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
RUNBOOK = "Prerequisites: Python\nTroubleshooting: inspect logs\nAcceptance: green\nRun: make smoke\n"


class Response:
    def __init__(self, data, status=200, headers=None):
        self.data, self.status_code, self.headers = data, status, headers or {}

    def json(self):
        return self.data


class RepoHealthRemoteTests(unittest.TestCase):
    def fake_source(self) -> InMemoryRepositorySource:
        return InMemoryRepositorySource(
            RepositoryFacts("owner/repo", "main", "a" * 40),
            [TreeEntry("README.md", "blob", 10), TreeEntry(".gitignore", "blob", 4), TreeEntry("docs/runbook.md", "blob", len(RUNBOOK))],
            {"README.md": "hello", ".gitignore": "*.pyc", "docs/runbook.md": RUNBOOK},
            [CommitFacts("a" * 40, NOW - timedelta(days=1), "recent")],
        )

    def test_repository_identity_is_validated_before_network_access(self):
        session = Mock()
        source = GitHubRepositorySource({"owner/repo"}, session=session)
        with self.assertRaisesRegex(RepositorySourceError, "not allowlisted"):
            source.get_repository("other/repo")
        with self.assertRaisesRegex(RepositorySourceError, "owner/repository"):
            source.get_repository("../bad")
        session.get.assert_not_called()

    def test_github_adapter_uses_only_bounded_get_requests(self):
        session = Mock()
        session.get.side_effect = [
            Response({"full_name": "owner/repo", "default_branch": "main", "archived": False, "private": False}),
            Response({"sha": "a" * 40}),
            Response({"tree": [{"path": "docs/runbook.md", "type": "blob", "size": 10}], "truncated": False}),
            Response({"encoding": "base64", "content": base64.b64encode(RUNBOOK.encode()).decode()}),
            Response([{"sha": "a" * 40, "commit": {"author": {"date": "2026-07-28T12:00:00Z"}, "message": "recent\nbody"}}]),
        ]
        source = GitHubRepositorySource({"owner/repo"}, session=session)
        facts = source.get_repository("owner/repo")
        self.assertEqual(facts.head_sha, "a" * 40)
        self.assertEqual(source.list_tree("owner/repo", facts.head_sha)[0].path, "docs/runbook.md")
        self.assertEqual(source.read_text("owner/repo", "docs/runbook.md", facts.head_sha), RUNBOOK)
        self.assertEqual(source.list_commits("owner/repo", since=NOW - timedelta(days=14))[0].subject, "recent")
        self.assertEqual(session.get.call_count, 5)

    def test_github_adapter_classifies_rate_limit_and_large_tree(self):
        limited = Mock()
        limited.get.return_value = Response({}, 403, {"X-RateLimit-Remaining": "0"})
        with self.assertRaisesRegex(RepositorySourceError, "denied") as caught:
            GitHubRepositorySource({"owner/repo"}, session=limited).get_repository("owner/repo")
        self.assertEqual(caught.exception.category, "rate_limited")
        large = Mock()
        large.get.return_value = Response({"tree": [], "truncated": True})
        with self.assertRaises(RepositorySourceError) as caught:
            GitHubRepositorySource({"owner/repo"}, session=large).list_tree("owner/repo", "main")
        self.assertEqual(caught.exception.category, "tree_too_large")

    def test_remote_plugins_preserve_vocabulary_and_report_unsupported_facts(self):
        ctx = {"project": {"repository_full_name": "owner/repo"}, "repository_source": self.fake_source(), "now": NOW}
        activity = RemoteActivityPlugin().run(ctx)
        runbook = RemoteRunbookPlugin().run(ctx)
        self.assertEqual((activity["status"], activity["bucket"]), ("PASS", "RECENT_OK"))
        self.assertEqual(activity["meta"]["unsupported_facts"]["dirty_worktree"], "NA")
        self.assertEqual((runbook["status"], runbook["bucket"]), ("PASS", "RUNBOOK_OK"))
        self.assertEqual(runbook["meta"]["runbook_freshness"], "NA")
        self.assertEqual(runbook["meta"]["hygiene"], {"readme": True, "gitignore": True, "runbook": True})

    def test_remote_plugin_source_failures_are_ineligible_not_exceptions(self):
        source = InMemoryRepositorySource(RepositoryFacts("owner/repo", "main", "a" * 40), [], {}, [])
        result = RemoteActivityPlugin().run({"project": {"repository_full_name": "missing/repo"}, "repository_source": source, "now": NOW})
        self.assertEqual(result["status"], "NA")
        self.assertEqual(result["bucket"], "REPOSITORY_SOURCE:not_found")

    def test_gcp_registry_now_selects_exactly_two_remote_read_plugins(self):
        plugins = load_plugins_from_folder()
        self.assertEqual(sorted(select_gcp_plugins(plugins)), ["activity_remote", "runbook_remote"])

    def test_local_and_fake_sources_have_supported_plugin_parity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
            (root / "docs").mkdir()
            (root / "README.md").write_text("hello")
            (root / ".gitignore").write_text("*.pyc")
            (root / "docs" / "runbook.md").write_text(RUNBOOK)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            env = {"GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.test", "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.test", "GIT_AUTHOR_DATE": "2026-07-28T12:00:00+00:00", "GIT_COMMITTER_DATE": "2026-07-28T12:00:00+00:00"}
            import os
            subprocess.run(["git", "commit", "-q", "-m", "recent"], cwd=root, check=True, env={**os.environ, **env})
            local = LocalRepositorySource({"owner/repo": str(root)})
            facts = local.get_repository("owner/repo")
            fake = InMemoryRepositorySource(facts, local.list_tree("owner/repo", facts.head_sha), {"README.md": "hello", ".gitignore": "*.pyc", "docs/runbook.md": RUNBOOK}, local.list_commits("owner/repo", since=NOW - timedelta(days=14)))
            for plugin in (RemoteActivityPlugin(), RemoteRunbookPlugin()):
                left = plugin.run({"project": {"repository_full_name": "owner/repo"}, "repository_source": local, "now": NOW})
                right = plugin.run({"project": {"repository_full_name": "owner/repo"}, "repository_source": fake, "now": NOW})
                self.assertEqual((left["status"], left["bucket"]), (right["status"], right["bucket"]))


if __name__ == "__main__":
    unittest.main()
