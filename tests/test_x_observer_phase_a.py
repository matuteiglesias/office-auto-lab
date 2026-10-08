"""Offline, no-credential Phase A proofs for provider normalization and budget gates."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from office_runtime.x_observer.client import ReadOnlyXClient, timeline_params
from office_runtime.x_observer.contracts import ObserverContractError
from office_runtime.x_observer.normalize import normalize_page
from office_runtime.x_observer.qualification import qualify

ACTOR = "101"
ORIGINAL_AUTHOR = "202"


def activity(post_id="301", **extra):
    return {"id": post_id, "author_id": ACTOR,
            "text": "public example", "created_at": "2026-10-08T12:00:00Z", **extra}


def page(posts, *, includes=None, errors=None, token=None):
    result = {"data": posts, "meta": {"result_count": len(posts)}}
    if includes is not None:
        result["includes"] = includes
    if errors is not None:
        result["errors"] = errors
    if token:
        result["meta"]["next_token"] = token
    return result


class NormalizationTests(unittest.TestCase):
    def test_original_is_stable_and_repeated_page_has_identical_digest(self):
        raw = page([activity()])
        first = normalize_page(raw, actor_id=ACTOR, run_id="a")
        second = normalize_page(raw, actor_id=ACTOR, run_id="b")
        self.assertEqual(first.events[0].event_id, "xevt:101:301")
        self.assertEqual(first.events[0].event_type, "ORIGINAL")
        self.assertEqual(first.page_sha256, second.page_sha256)
        self.assertNotEqual(first.events[0].source_run_id, second.events[0].source_run_id)

    def test_repost_preserves_original_author(self):
        raw = page([activity(referenced_posts=[{"type": "reposted", "id": "302"}])],
                   includes={"posts": [{"id": "302", "author_id": ORIGINAL_AUTHOR,
                                       "text": "different author's words"}]})
        result = normalize_page(raw, actor_id=ACTOR, run_id="r")
        self.assertEqual(result.events[0].event_type, "REPOST")
        self.assertEqual(result.events[0].observed_user_id, ACTOR)
        self.assertEqual(result.events[0].references[0].author_id, ORIGINAL_AUTHOR)
        self.assertEqual(next(p for p in result.posts if p.post_id == "302").author_id, ORIGINAL_AUTHOR)

    def test_legacy_reference_tweets_normalized_as_quote(self):
        raw = page([activity(referenced_tweets=[{"type": "quoted", "id": "302"}])],
                   includes={"tweets": [{"id": "302", "author_id": ORIGINAL_AUTHOR, "text": "old"}]})
        result = normalize_page(raw, actor_id=ACTOR, run_id="r")
        self.assertEqual(result.events[0].event_type, "QUOTE")

    def test_reply_and_mixed_relations(self):
        raw = page([
            activity("303", referenced_posts=[{"type": "replied_to", "id": "400"}]),
            activity("304", referenced_posts=[
                {"type": "quoted", "id": "401"}, {"type": "replied_to", "id": "402"}]),
        ])
        result = normalize_page(raw, actor_id=ACTOR, run_id="r")
        self.assertEqual([e.event_type for e in result.events], ["REPLY", "MIXED"])
        self.assertEqual(len(result.events[1].references), 2)

    def test_unavailable_expansion_creates_unknown_placeholder(self):
        raw = page([activity(referenced_posts=[{"type": "retweeted", "id": "909"}])])
        result = normalize_page(raw, actor_id=ACTOR, run_id="r")
        target = next(p for p in result.posts if p.post_id == "909")
        self.assertIsNone(target.text)
        self.assertEqual(target.availability, "UNKNOWN")
        self.assertIsNone(target.author_id)
        self.assertEqual(result.events[0].event_type, "REPOST")

    def test_partial_results_do_not_claim_original(self):
        raw = page([activity()], errors=[{"status": 404, "title": "unavailable"}], token="NEXT")
        result = normalize_page(raw, actor_id=ACTOR, run_id="r")
        self.assertTrue(result.partial)
        self.assertEqual(result.events[0].event_type, "UNKNOWN")
        self.assertEqual(result.events[0].evidence_status, "PARTIAL")

    def test_edits_are_retained(self):
        result = normalize_page(
            page([activity(edit_history_post_ids=["300", "301"])]),
            actor_id=ACTOR, run_id="r")
        self.assertEqual(result.posts[0].edit_history, ("300", "301"))

    def test_unknown_reference_type_is_not_invented(self):
        result = normalize_page(
            page([activity(referenced_posts=[{"type": "new_provider_type", "id": "300"}])]),
            actor_id=ACTOR, run_id="r")
        self.assertEqual(result.events[0].event_type, "UNKNOWN")

    def test_differing_claimed_author_fails_closed(self):
        with self.assertRaises(ObserverContractError):
            normalize_page(page([activity(author_id="202")]), actor_id=ACTOR, run_id="r")

    def test_missing_or_nonnumeric_activity_identity_fails(self):
        with self.assertRaises(ObserverContractError):
            normalize_page(page([activity(post_id="not-an-id")]), actor_id=ACTOR, run_id="r")

    def test_duplicate_activity_id_fails(self):
        with self.assertRaises(ObserverContractError):
            normalize_page(page([activity(), activity()]), actor_id=ACTOR, run_id="r")

    def test_partial_and_multiple_references_preserved_in_records(self):
        raw = page([activity(referenced_posts=[
            {"type": "retweeted", "id": "500", "author_id": "555"},
            {"type": "quoted", "id": "501", "author_id": "556"},
        ])], errors=[{"status": 503}])
        value = normalize_page(raw, actor_id=ACTOR, run_id="r")
        record = value.events[0].record()
        self.assertEqual(record["schema_version"], "x.observer.event.v0.1")
        self.assertEqual(len(record["references"]), 2)
        self.assertEqual(record["event_type"], "MIXED")


class ReadOnlyClientTests(unittest.TestCase):
    def test_query_uses_current_fields_without_exclusions(self):
        params = timeline_params(max_results=10, pagination_token="A1")
        self.assertEqual(params["post.fields"], "created_at,conversation_id,lang,edit_history_post_ids")
        self.assertEqual(params["expansions"], "referenced_posts,author_id")
        self.assertNotIn("exclude", params)
        self.assertEqual(params["pagination_token"], "A1")

    def test_max_results_bounds(self):
        for n in (0, 4, 101):
            with self.subTest(n=n), self.assertRaises(ObserverContractError):
                timeline_params(max_results=n)

    def test_client_only_uses_read_identity_and_timeline_gets(self):
        c = ReadOnlyXClient("private-test-value")
        with self.assertRaises(ObserverContractError):
            c._get("/tweets", {})
        with self.assertRaises(ObserverContractError):
            c._get("/users/101/likes", {})

    def test_account_alias_mismatch_is_blocked(self):
        c = ReadOnlyXClient("secret")
        with patch.object(c, "_get", return_value={"data": {"username": "other", "id": ACTOR, "protected": False}}):
            with self.assertRaises(ObserverContractError):
                c.resolve_user("JMilei")

    def test_protected_or_unknown_protected_status_blocked(self):
        c = ReadOnlyXClient("secret")
        for protected in (True, None):
            with self.subTest(protected=protected):
                with patch.object(c, "_get", return_value={"data": {"username": "JMilei", "id": ACTOR, "protected": protected}}):
                    with self.assertRaises(ObserverContractError):
                        c.resolve_user("JMilei")


class FakeX:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def resolve_user(self, handle):
        self.calls.append(("resolve", handle))
        return {"username": handle, "id": ACTOR, "protected": False}

    def user_posts(self, user_id, *, max_results, pagination_token=None):
        self.calls.append(("posts", user_id, max_results, pagination_token))
        return self.pages.pop(0)


class QualificationTests(unittest.TestCase):
    def test_single_page_reports_repost_without_publishing_or_cursor(self):
        raw = page([activity(referenced_posts=[{"type": "retweeted", "id": "300"}])])
        client = FakeX([raw])
        report = qualify(client, handle="JMilei", max_results=5)
        self.assertEqual(report["verified_user_id"], ACTOR)
        self.assertEqual(report["repost_evidence"], "REPOST_OBSERVED")
        self.assertEqual(report["pages_fetched"], 1)
        self.assertEqual(report["cursor_advanced"], False)
        self.assertTrue(report["no_sheet_mutation"])
        self.assertEqual(report["qualification_status"], "BOUNDED_READ_COMPLETE")

    def test_second_page_budget_stops_before_network_request(self):
        client = FakeX([page([activity()], token="TOKEN")])
        report = qualify(client, max_results=10, max_usd=0.25)
        self.assertEqual(report["qualification_status"], "BUDGET_STOP")
        self.assertEqual(len([c for c in client.calls if c[0] == "posts"]), 1)

    def test_partial_provider_page_stops_without_following_token(self):
        client = FakeX([page([activity()], errors=[{"status": 503}], token="NEXT")])
        report = qualify(client, max_results=5)
        self.assertEqual(report["qualification_status"], "PARTIAL_PROVIDER_RESPONSE")
        self.assertEqual(report["partial_pages"], 1)
        self.assertEqual(len(client.calls), 2)

    def test_qualification_never_calls_network_without_explicit_client(self):
        # Tests the pure machinery; live CLI requires env token and --qualify-live.
        from office_runtime.scripts.run_x_observer import main
        with patch("sys.argv", ["run_x_observer", "--dry-run"]), \
             patch("office_runtime.scripts.run_x_observer.ReadOnlyXClient") as constructor:
            self.assertEqual(main(), 0)
            constructor.assert_not_called()

    def test_invalid_budget_prevents_identity_read(self):
        client = FakeX([])
        with self.assertRaises(ObserverContractError):
            qualify(client, max_pages=3)
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
