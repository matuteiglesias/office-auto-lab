from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from office_runtime.editorial.context import (
    load_repository_context,
    pin_policy_text,
    sha256_text,
)
from office_runtime.editorial.contracts import (
    AngleCard,
    ContractError,
    PolicyIdentity,
    validate_activity_evidence,
    validate_dev_candidate,
)
from office_runtime.editorial.evidence.github import (
    GitHubEvidenceClient,
    GitHubHTTPError,
    dedupe_evidence,
    normalize_commit,
    normalize_issue_decision,
    normalize_pull_request,
    normalize_release,
)
from office_runtime.editorial.run_bundle import (
    atomic_write_run_bundle,
    build_run_bundle,
    canonical_json_bytes,
    stable_run_id,
    validate_run_bundle,
)
from office_runtime.editorial.story import ExplicitStoryRelation, cluster_stories


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "editorial"
OBSERVED = "2026-10-06T18:00:00Z"
SINCE = "2026-10-04T00:00:00Z"
UNTIL = "2026-10-07T00:00:00Z"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class DeniedTransport:
    def get_json(self, path, params=None):
        raise GitHubHTTPError(404, "inaccessible_or_unknown")


class OwnedRepositoriesTransport:
    def get_json(self, path, params=None):
        if path != "user/repos":
            raise AssertionError(path)
        page = int((params or {}).get("page", 1))
        if page == 1:
            return [
                {
                    "full_name": "matuteiglesias/a",
                    "owner": {"login": "matuteiglesias"},
                    "archived": False,
                    "disabled": False,
                },
                {
                    "full_name": "matuteiglesias/archived",
                    "owner": {"login": "matuteiglesias"},
                    "archived": True,
                    "disabled": False,
                },
                {
                    "full_name": "someone-else/shared",
                    "owner": {"login": "someone-else"},
                    "archived": False,
                    "disabled": False,
                },
            ]
        return []


class EditorialEvidenceSpineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.merged = normalize_pull_request(
            "example/project",
            fixture("merged_pr.json"),
            observed_at=OBSERVED,
            visibility="public",
        )
        self.commit = normalize_commit(
            "example/project",
            fixture("commit.json"),
            observed_at=OBSERVED,
            visibility="public",
        )
        self.policy_text = "editorial policy fixture\nstatus: current\n"
        self.policy = PolicyIdentity.from_mapping(
            {
                "authority": "weekly-ops-governance",
                "source_ref": "github:example/policy:editorial.md",
                "source_revision": "0123456789abcdef0123456789abcdef01234567",
                "content_sha256": sha256_text(self.policy_text),
            }
        )
        self.retrieval = {
            "intended_sources": ["github_pr", "github_commit"],
            "actual_sources": ["github_pr", "github_commit"],
            "time_windows": [
                {"scope": "example/project", "since": SINCE, "until": UNTIL}
            ],
            "failures": [],
            "scope_status": "complete",
        }

    def test_merged_pr_fixture_becomes_valid_activity_evidence(self) -> None:
        payload = self.merged.to_dict()
        self.assertEqual(validate_activity_evidence(payload), payload)
        self.assertEqual(self.merged.status, "merged")
        self.assertEqual(self.merged.repository_ref, "example/project")
        self.assertEqual(self.merged.source_metadata["number"], 42)
        self.assertEqual(
            self.merged.source_metadata["merge_sha"],
            "0123456789abcdef0123456789abcdef01234567",
        )
        self.assertEqual(self.merged.event_at, "2026-10-05T13:04:00Z")
        self.assertEqual(
            self.merged.source_ref,
            "https://github.com/example/project/pull/42",
        )

    def test_evidence_ids_are_stable_across_overlapping_observations(self) -> None:
        second = normalize_pull_request(
            "example/project",
            fixture("merged_pr.json"),
            observed_at="2026-10-06T19:00:00Z",
            visibility="public",
        )
        self.assertEqual(self.merged.evidence_id, second.evidence_id)
        deduped = dedupe_evidence([second, self.merged, second])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].observed_at, OBSERVED)

    def test_open_and_draft_states_cannot_be_promoted_to_completed_status(self) -> None:
        open_pr = normalize_pull_request(
            "example/project",
            fixture("open_pr.json"),
            observed_at=OBSERVED,
            visibility="public",
        )
        draft_release = normalize_release(
            "example/project",
            fixture("draft_release.json"),
            observed_at=OBSERVED,
            visibility="public",
        )
        self.assertEqual(open_pr.status, "in_progress")
        self.assertNotEqual(open_pr.status, "merged")
        self.assertEqual(draft_release.status, "in_progress")
        self.assertNotEqual(draft_release.status, "released")

    def test_release_commit_and_explicit_issue_decision_are_supported(self) -> None:
        release = normalize_release(
            "example/project",
            fixture("release.json"),
            observed_at=OBSERVED,
            visibility="public",
        )
        decision = normalize_issue_decision(
            "example/project",
            fixture("issue_waiting.json"),
            observed_at=OBSERVED,
            visibility="public",
        )
        self.assertEqual(release.status, "released")
        self.assertEqual(self.commit.status, "completed")
        self.assertIsNotNone(decision)
        self.assertEqual(decision.status, "waiting")
        self.assertEqual(decision.source_kind, "github_issue_decision")

    def test_owned_repository_discovery_uses_token_visible_owned_non_archived_scope(self) -> None:
        client = GitHubEvidenceClient(OwnedRepositoriesTransport())
        repos = client.list_owned_repositories(owner="matuteiglesias")
        self.assertEqual(repos, ("matuteiglesias/a",))

    def test_inaccessible_repository_remains_unknown(self) -> None:
        result = GitHubEvidenceClient(
            DeniedTransport()
        ).retrieve_repository_activity(
            "private/unknown",
            since=SINCE,
            until=UNTIL,
            observed_at=OBSERVED,
        )
        self.assertEqual(result.scope_status, "unknown")
        self.assertEqual(result.evidence, ())
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.failures[0].status, "unknown")
        self.assertTrue(
            all(item["status"] == "unknown" for item in result.inventory)
        )

    def test_story_ids_are_deterministic_and_unrelated_events_stay_separate(self) -> None:
        singletons = cluster_stories(
            [self.commit, self.merged],
            as_of=OBSERVED,
        )
        self.assertEqual(len(singletons), 2)
        self.assertTrue(
            all(len(story.evidence_refs) == 1 for story in singletons)
        )

        relation_a = ExplicitStoryRelation(
            relation_id="repair-family",
            evidence_refs=(
                self.merged.evidence_id,
                self.commit.evidence_id,
            ),
            relation_kind="same_change_family",
            provenance_ref="github:example/project:issue:99",
        )
        relation_b = ExplicitStoryRelation(
            relation_id="repair-family",
            evidence_refs=(
                self.commit.evidence_id,
                self.merged.evidence_id,
            ),
            relation_kind="same_change_family",
            provenance_ref="github:example/project:issue:99",
        )
        first = cluster_stories(
            [self.merged, self.commit],
            explicit_relations=[relation_a],
            as_of=OBSERVED,
        )
        second = cluster_stories(
            [self.commit, self.merged],
            explicit_relations=[relation_b],
            as_of=OBSERVED,
        )
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].story_id, second[0].story_id)
        self.assertEqual(first[0].evidence_refs, second[0].evidence_refs)

    def test_story_relation_with_unknown_evidence_fails_closed(self) -> None:
        relation = ExplicitStoryRelation(
            relation_id="bad",
            evidence_refs=(
                self.merged.evidence_id,
                "missing:evidence",
            ),
            relation_kind="same_change_family",
            provenance_ref="github:example/project:issue:99",
        )
        with self.assertRaises(ContractError):
            cluster_stories(
                [self.merged],
                explicit_relations=[relation],
                as_of=OBSERVED,
            )

    def test_policy_identity_requires_immutable_revision_and_exact_hash(self) -> None:
        digest = sha256_text(self.policy_text)
        with self.assertRaises(ContractError):
            pin_policy_text(
                self.policy_text,
                authority="weekly-ops-governance",
                source_ref="github:example/policy:editorial.md",
                source_revision="main",
                expected_sha256=digest,
            )
        with self.assertRaises(ContractError):
            pin_policy_text(
                self.policy_text,
                authority="weekly-ops-governance",
                source_ref="github:example/policy:editorial.md",
                source_revision="0123456789abcdef",
                expected_sha256="0" * 64,
            )
        pinned = pin_policy_text(
            self.policy_text,
            authority="weekly-ops-governance",
            source_ref="github:example/policy:editorial.md",
            source_revision="0123456789abcdef",
            expected_sha256=digest,
        )
        self.assertEqual(pinned.identity.content_sha256, digest)

    def test_repository_context_keeps_only_relative_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "context.md").write_text(
                "safe context\n",
                encoding="utf-8",
            )
            docs = load_repository_context(root, ["docs/context.md"])
            self.assertEqual(
                docs[0].repository_path,
                "docs/context.md",
            )
            self.assertNotIn(
                str(root),
                json.dumps(docs[0].provenance()),
            )
            with self.assertRaises(ContractError):
                load_repository_context(
                    root,
                    [root / "docs" / "context.md"],
                )

    def test_retrieval_only_run_bundle_has_stable_id_and_referential_integrity(self) -> None:
        stories = cluster_stories(
            [self.merged, self.commit],
            as_of=OBSERVED,
        )
        bundle = build_run_bundle(
            profile_id="dev",
            started_at="2026-10-06T18:00:00Z",
            finished_at="2026-10-06T18:00:02Z",
            policy=self.policy,
            retrieval=self.retrieval,
            evidence=[self.merged, self.commit],
            stories=stories,
        )
        payload = bundle.to_dict()
        self.assertEqual(validate_run_bundle(payload), payload)
        second_id = stable_run_id(
            profile_id="dev",
            policy=self.policy,
            retrieval=self.retrieval,
        )
        self.assertEqual(bundle.run_id, second_id)
        self.assertEqual(payload["angles"], [])
        self.assertEqual(payload["candidates"], [])
        self.assertIsNone(payload["batch"])

    def test_invalid_angle_evidence_reference_fails_closed(self) -> None:
        story = cluster_stories([self.merged], as_of=OBSERVED)[0]
        angle = AngleCard(
            angle_id="angle:bad",
            story_id=story.story_id,
            angle_type="lesson",
            claim="A grounded claim",
            tension_or_hook="Why retries need provenance",
            transferable_lesson="Failure provenance matters",
            evidence_refs=("missing:evidence",),
            audience=("engineers",),
            career_signals=("reliability",),
            why_interesting="It changes recovery semantics.",
            risk_class="low",
        )
        with self.assertRaises(ContractError):
            build_run_bundle(
                profile_id="dev",
                started_at="2026-10-06T18:00:00Z",
                finished_at="2026-10-06T18:00:02Z",
                policy=self.policy,
                retrieval=self.retrieval,
                evidence=[self.merged],
                stories=[story],
                angles=[angle],
            )

    def test_candidate_must_reference_existing_angle_and_evidence(self) -> None:
        story = cluster_stories([self.merged], as_of=OBSERVED)[0]
        candidate = {
            "schema_version": "office_runtime.editorial.candidate.v1",
            "candidate_id": "candidate:1",
            "profile_id": "dev",
            "text": "Retries need failure provenance.",
            "risk_class": "low",
            "evidence_refs": [self.merged.evidence_id],
            "work_refs": ["example/project#42"],
            "story_id": story.story_id,
            "angle_id": "angle:missing",
            "candidate_family": "LESSON",
            "semantic_fingerprint": "lesson:retries-provenance",
            "language": "en",
            "topic_tags": ["reliability"],
            "career_signals": ["backend"],
            "proof_object_refs": [self.merged.source_ref],
            "freshness_class": "recent",
            "generated_at": OBSERVED,
            "expires_at": None,
            "machine_disposition": "stage",
            "quality": {
                "evidence": 4,
                "specificity": 4,
                "external_usefulness": 4,
                "novelty": 3,
                "professional_signal": 4,
            },
            "disclosure_risk": "pass",
            "repetition_risk": "pass",
            "status_truth_risk": "pass",
        }
        validate_dev_candidate(
            candidate,
            {"profile_id": "dev", "strategy": "dev_projection"},
        )
        with self.assertRaises(ContractError):
            build_run_bundle(
                profile_id="dev",
                started_at="2026-10-06T18:00:00Z",
                finished_at="2026-10-06T18:00:02Z",
                policy=self.policy,
                retrieval=self.retrieval,
                evidence=[self.merged],
                stories=[story],
                candidates=[candidate],
            )

    def test_secret_and_absolute_path_material_cannot_be_serialized(self) -> None:
        bundle = build_run_bundle(
            profile_id="dev",
            started_at="2026-10-06T18:00:00Z",
            finished_at="2026-10-06T18:00:02Z",
            policy=self.policy,
            retrieval=self.retrieval,
            evidence=[self.merged],
            stories=cluster_stories(
                [self.merged],
                as_of=OBSERVED,
            ),
        ).to_dict()
        with_secret = dict(bundle)
        with_secret["provider_runs"] = [{
            "provider": "example",
            "access_token": "ghp_abcdefghijklmnopqrstuvwxyz123456",
        }]
        with self.assertRaises(ContractError):
            canonical_json_bytes(with_secret)

        with_path = dict(bundle)
        with_path["errors"] = [{
            "kind": "debug",
            "detail": "/home/matias/secret/output.json",
        }]
        with self.assertRaises(ContractError):
            canonical_json_bytes(with_path)

    def test_atomic_bundle_write_is_idempotent_but_immutable(self) -> None:
        bundle = build_run_bundle(
            profile_id="dev",
            started_at="2026-10-06T18:00:00Z",
            finished_at="2026-10-06T18:00:02Z",
            policy=self.policy,
            retrieval=self.retrieval,
            evidence=[self.merged],
            stories=cluster_stories(
                [self.merged],
                as_of=OBSERVED,
            ),
        ).to_dict()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "run.json"
            atomic_write_run_bundle(target, bundle)
            first = target.read_bytes()
            atomic_write_run_bundle(target, bundle)
            self.assertEqual(target.read_bytes(), first)
            changed = dict(bundle)
            changed["finished_at"] = "2026-10-06T18:00:03Z"
            with self.assertRaises(ContractError):
                atomic_write_run_bundle(target, changed)


if __name__ == "__main__":
    unittest.main()
