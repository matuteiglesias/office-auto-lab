"""Normalize *observed* X API v2 payloads, never synthesize missing identity."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .contracts import (
    ActivityEvent, NormalizedPage, ObservedPost, ObserverContractError,
    Reference, numeric_id,
)

KINDS = {"retweeted": "REPOST", "reposted": "REPOST", "quoted": "QUOTE",
         "replied_to": "REPLY", "retweet": "REPOST", "quote": "QUOTE", "reply": "REPLY"}


def _as_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ObserverContractError(f"{label} is not an object")
    return value


def page_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reference_values(post: Mapping[str, Any]) -> tuple[bool, list[Any]]:
    # Both current and legacy names are accepted. Never merge a scalar into an array.
    if "referenced_posts" in post:
        value = post["referenced_posts"]
    elif "referenced_tweets" in post:
        value = post["referenced_tweets"]
    else:
        return False, []
    if not isinstance(value, list):
        raise ObserverContractError("referenced posts must be an array")
    return True, value


def normalize_page(payload: Mapping[str, Any], *, actor_id: str, run_id: str) -> NormalizedPage:
    numeric_id(actor_id, "observed user ID")
    if not run_id.strip():
        raise ObserverContractError("source run ID is required")
    raw = _as_object(payload, "X timeline response")
    data = raw.get("data", [])
    if not isinstance(data, list):
        raise ObserverContractError("X timeline data must be an array")
    errors = raw.get("errors", [])
    if not isinstance(errors, list):
        raise ObserverContractError("X timeline errors must be an array")
    meta = raw.get("meta", {})
    meta = _as_object(meta, "X timeline metadata")
    nxt = meta.get("next_token")
    if nxt is not None and (not isinstance(nxt, str) or not nxt):
        raise ObserverContractError("pagination token is malformed")
    result_count = meta.get("result_count")
    if result_count is not None and (not isinstance(result_count, int) or isinstance(result_count, bool) or result_count < 0):
        raise ObserverContractError("result_count is malformed")
    includes = _as_object(raw.get("includes", {}), "timeline includes")
    expanded = includes.get("posts", includes.get("tweets", []))
    if not isinstance(expanded, list):
        raise ObserverContractError("expanded posts must be an array")
    digest = page_digest(raw)
    partial = bool(errors)
    objects: dict[str, Mapping[str, Any]] = {}
    for obj in expanded:
        rec = _as_object(obj, "expanded post")
        pid = numeric_id(rec.get("id"), "expanded post ID")
        if pid in objects and objects[pid] != rec:
            raise ObserverContractError("conflicting duplicate expanded post")
        objects[pid] = rec

    def refs_for(post: Mapping[str, Any]) -> tuple[Reference, ...]:
        _, items = _reference_values(post)
        refs: list[Reference] = []
        for item in items:
            ref = _as_object(item, "reference")
            rid = numeric_id(ref.get("id"), "referenced post ID")
            kind = ref.get("type")
            if not isinstance(kind, str) or not kind.strip():
                raise ObserverContractError("reference type is missing")
            included = objects.get(rid, {})
            author = ref.get("author_id") or included.get("author_id")
            if author is not None:
                numeric_id(author, "referenced author ID")
            refs.append(Reference(
                type=kind, post_id=rid, author_id=author,
                availability="AVAILABLE" if rid in objects else "UNKNOWN",
            ))
        return tuple(refs)

    def post_for(post: Mapping[str, Any]) -> ObservedPost:
        pid = numeric_id(post.get("id"), "post ID")
        auth = post.get("author_id")
        if auth is not None:
            numeric_id(auth, "post author ID")
        value = post.get("text")
        if value is not None and not isinstance(value, str):
            raise ObserverContractError("post text must be a string or null")
        history = post.get("edit_history_post_ids", post.get("edit_history_tweet_ids", []))
        if not isinstance(history, list):
            raise ObserverContractError("edit history must be an array")
        return ObservedPost(
            post_id=pid, author_id=auth, text=value,
            created_at_utc=post.get("created_at") if isinstance(post.get("created_at"), str) else None,
            references=refs_for(post),
            edit_history=tuple(numeric_id(x, "edit history post ID") for x in history),
            availability="AVAILABLE",
            content_sha256=hashlib.sha256(value.encode("utf-8")).hexdigest() if value is not None else None,
            source_page_sha256=digest,
        )

    events: list[ActivityEvent] = []
    posts: dict[str, ObservedPost] = {}
    seen: set[str] = set()
    for item in data:
        rec = _as_object(item, "activity post")
        pid = numeric_id(rec.get("id"), "activity post ID")
        if pid in seen:
            raise ObserverContractError("duplicate activity ID within a provider page")
        seen.add(pid)
        claimed_author = rec.get("author_id")
        if claimed_author is not None and claimed_author != actor_id:
            raise ObserverContractError("timeline post author differs from verified observed actor")
        refs = refs_for(rec)
        classes = {KINDS.get(ref.type.casefold(), "UNKNOWN") for ref in refs}
        if not classes:
            # An absent reference property is ambiguous when an API response is partial.
            kind = "UNKNOWN" if partial else "ORIGINAL"
        else:
            kind = next(iter(classes)) if len(classes) == 1 else "MIXED"
        events.append(ActivityEvent(
            event_id=f"xevt:{actor_id}:{pid}", observed_user_id=actor_id,
            activity_post_id=pid, event_type=kind,
            created_at_utc=rec.get("created_at") if isinstance(rec.get("created_at"), str) else None,
            references=refs, source_run_id=run_id,
            source_page_sha256=digest, evidence_status="PARTIAL" if partial else "OBSERVED",
        ))
        posts[pid] = post_for(rec)
    for pid, rec in objects.items():
        if pid not in posts:
            posts[pid] = post_for(rec)
    for event in events:
        for ref in event.references:
            if ref.post_id not in posts:
                # Missing expansions remain first-class, not misattributed as actor posts.
                posts[ref.post_id] = ObservedPost(
                    post_id=ref.post_id, author_id=ref.author_id, text=None,
                    created_at_utc=None, references=(), edit_history=(),
                    availability="UNKNOWN", content_sha256=None, source_page_sha256=digest,
                )
    return NormalizedPage(
        observed_user_id=actor_id, events=tuple(events),
        posts=tuple(posts.values()), next_token=nxt, page_sha256=digest,
        partial=partial, errors_count=len(errors), result_count=result_count,
    )
