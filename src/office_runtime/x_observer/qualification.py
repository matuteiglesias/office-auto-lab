"""Bounded, report-only Phase A qualification; no Sheet writes or cursors."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .client import ReadOnlyXClient
from .contracts import ObserverContractError
from .normalize import normalize_page

POST_READ_USD = 0.005
USER_READ_USD = 0.010


def qualify(
    client: ReadOnlyXClient,
    *,
    handle: str = "JMilei",
    max_pages: int = 2,
    max_results: int = 5,
    max_usd: float = 0.25,
) -> dict[str, Any]:
    if not 1 <= max_pages <= 2:
        raise ObserverContractError("Phase A cannot request more than 2 pages")
    if not 5 <= max_results <= 10:
        raise ObserverContractError("Phase A only permits 5..10 results/page")
    if not 0.05 <= max_usd <= 0.50:
        raise ObserverContractError("Phase A max_usd must be $0.05..$0.50")

    # Bound requests BEFORE a read. This is an estimated resource allowance,
    # NOT an invoice/guarantee; provider may bill expansions in unexpected ways.
    user = client.resolve_user(handle)
    actor_id = str(user["id"])
    estimated = USER_READ_USD
    # Allow three references per timeline item for conservative prospective budget.
    reserve_per_page = max_results * 4 * POST_READ_USD
    result: dict[str, Any] = {
        "schema_version": "x.observer.qualification.v0.1",
        "subject_handle": str(user["username"]),
        "verified_user_id": actor_id,
        "public_identity_proven": True,
        "read_only": True,
        "pages_fetched": 0,
        "events_observed": 0,
        "reposts_observed": 0,
        "referenced_objects_missing": 0,
        "partial_pages": 0,
        "page_digests": [],
        "page_shapes": [],
        "rate_headers_per_page": [],
        "next_page_available": None,
        "repost_evidence": "REPOST_NOT_OBSERVED",
        "estimated_resource_usd": 0.0,
        "cost_is_estimate_not_actual_invoice": True,
        "max_requested_usd": max_usd,
        "coverage": "UNKNOWN",
        "cursor_advanced": False,
        "no_sheet_mutation": True,
        "qualification_status": "UNQUALIFIED",
    }
    token: str | None = None
    read_ids: set[str] = set()
    returned_users: set[str] = {actor_id}
    for page_number in range(max_pages):
        if estimated + reserve_per_page > max_usd + 1e-8:
            result["qualification_status"] = "BUDGET_STOP"
            break
        raw = client.user_posts(actor_id, max_results=max_results, pagination_token=token)
        page = normalize_page(raw, actor_id=actor_id, run_id="phase-a-qualification")
        includes = raw.get("includes", {})
        if not isinstance(includes, Mapping):
            raise ObserverContractError("X includes object malformed")
        raw_users = includes.get("users", [])
        if not isinstance(raw_users, list):
            raise ObserverContractError("X includes.users malformed")
        ids = {post.post_id for post in page.posts}
        new_post_ids = ids - read_ids
        read_ids.update(ids)
        new_user_ids = set()
        for item in raw_users:
            if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
                raise ObserverContractError("X included user malformed")
            new_user_ids.add(item["id"])
        estimated += len(new_post_ids) * POST_READ_USD
        estimated += len(new_user_ids - returned_users) * USER_READ_USD
        returned_users.update(new_user_ids)
        result["pages_fetched"] += 1
        result["events_observed"] += len(page.events)
        result["reposts_observed"] += sum(event.event_type == "REPOST" for event in page.events)
        result["referenced_objects_missing"] += sum(
            post.availability != "AVAILABLE" for post in page.posts
        )
        result["partial_pages"] += int(page.partial)
        result["page_digests"].append(page.page_sha256)
        result["page_shapes"].append({
            "has_referenced_posts": any("referenced_posts" in x for x in raw.get("data", []) if isinstance(x, Mapping)),
            "has_referenced_tweets": any("referenced_tweets" in x for x in raw.get("data", []) if isinstance(x, Mapping)),
            "includes_posts": "posts" in includes,
            "includes_tweets": "tweets" in includes,
            "next_page_available": bool(page.next_token),
            "result_count_reported": page.result_count,
        })
        result["next_page_available"] = bool(page.next_token)
        result["rate_headers_per_page"].append(dict(getattr(client, "last_rate_headers", {})))
        if estimated > max_usd + 1e-8:
            result["qualification_status"] = "BUDGET_EXCEEDED_STOP"
            break
        if page.partial:
            result["qualification_status"] = "PARTIAL_PROVIDER_RESPONSE"
            break
        if not page.next_token:
            result["qualification_status"] = "BOUNDED_READ_COMPLETE"
            break
        if page.next_token == token:
            raise ObserverContractError("provider repeated same pagination token")
        token = page.next_token
    if result["qualification_status"] == "UNQUALIFIED":
        result["qualification_status"] = "MAX_PAGES_STOP"
    if result["reposts_observed"]:
        result["repost_evidence"] = "REPOST_OBSERVED"
    result["estimated_resource_usd"] = round(estimated, 4)
    result["coverage"] = "PARTIAL_OR_UNVERIFIED_WINDOW"
    return result
