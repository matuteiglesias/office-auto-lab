# X Observer v0.1 — Read-only actor-activity evidence

**Status:** Phase A in development — O0 fixture work; O1 gated live read-only qualification. No cron, X writes, or Sheet projection authorized.

**Provisional owner:** `office-auto-lab` SIDECAR (`SYSTEM.yaml`), designed for future extraction to its own repository. Product consumers are NOT the observer's authority. `media_monitor` can later consume selected public-event evidence without acquiring ownership of X adapters; `weekly-ops-governance` owns editorial policy for satire. This subsystem observes public account actions, without imitating, rating, or publishing content.

**First proving account:** `@JMilei`; resolve the **verified numeric X user ID** using the official API before any collection. Usernames are aliases, never primary keys. Further public accounts are config entries, not code forks.

**Operator workbook:** [X Observer — Milei Mirror (research v0.1)](https://docs.google.com/spreadsheets/d/1L6gMAbfcU3oU8iJKx78M_xfLpRwtoamYP1_Iy4AUhQ4/edit) — ID `1L6gMAbfcU3oU8iJKx78M_xfLpRwtoamYP1_Iy4AUhQ4`. Tabs: `START HERE`, `ACCOUNTS`, `EVENTS`, `POSTS`, `RUNS`, `CURSORS`. Configured JMilei row currently **FALSE / NEEDS_ID_PROOF**; no observations in Sheet.

## 1. Scope

### In v0.1
- Observe **public activity by configured user(s)** using official read-only X access: originals, reposts, quotes, replies, and unknown/mixed events when identification is uncertain.
- Recover referenced content/author from permitted expansions, preserving unavailable references as first-class states.
- Backfill a **bounded user-specified window**, and incrementally poll with overlap, pagination, stable-ID dedupe, cost/freshness/coverage evidence and explicit gaps.
- Materialize a deduplicated public-post index, event log and run/cursor diagnostics to the workbook.
- Provide a portable JSONL contract and local fixture replay for future migration.

### Explicitly excluded
- No posting, reposting, following, liking, replying, quote-posting or engaging from the observer.
- No user home-feed recommendation capture, DMs, likes, protected accounts, following/follower scraping, browser automation, or arbitrary search.
- No automated parody generation or targeting of journalists; those belong to later independent consumers and separate approval gates.
- No assertion of full historical completeness or reconstruction of deleted/protected posts.

## 2. Source contract (verify with live fixture before promotion)

- Resolve `GET /2/users/by/username/{username}` (or equivalent permitted user lookup) -> numeric ID and public/protected status. Bind the numeric ID for the entire run; fail on mismatch.
- Main activity endpoint: `GET /2/users/{id}/tweets` with **no `exclude=retweets` and no `exclude=replies`**. Request documented `post.fields=created_at,conversation_id,lang,edit_history_post_ids` plus `expansions=referenced_posts,author_id` (verify live), maintaining a legacy payload adapter for `tweet.fields` / `referenced_tweets` when available; `expansions=referenced_posts.id,referenced_posts.id.author_id` where supported.
- `max_results=5..100` per API request is the documented bound. Use `pagination_token`, `since_id`, or date boundaries; retain all resulting token and request-window provenance. Never treat one page as all activity.
- Treat provider naming differences (`referenced_posts` vs `referenced_tweets`) as a versioned **adapter** concern. The actual live payload determines parsing and classification; no invented refs/IDs.
- A repost on the timeline is an event performed by the monitored **actor** even if the content author is someone else. Record actor ID, event post ID, reference type, referenced post ID and referenced author independently. If the provider omits a stable action ID, mark `UNRESOLVED_EVENT_ID`; don't fabricate an event ID from wall-clock observation time.
- For quotes/replies, `referenced_posts` may contain more than one relationship. Retain the set of references as structured evidence; a scalar Sheet view may expose the primary relationship only.
- Expanded posts may themselves have revisions, threads, media, or missing content. Do not confuse the short timeline text with the entire referenced object.
- Store response `errors` and `meta` even when `data` exists. 200 with `errors` is partial evidence, not full success.
- Probe current read authorization, actual available timeline span, missing reposts, pagination, expansion coverage and rate/usage response *once* under an explicit small budget. Never infer completeness from docs alone.

Official sources:
- https://docs.x.com/x-api/users/get-posts
- https://docs.x.com/x-api/posts/timelines/introduction
- https://docs.x.com/xdks/python/pagination
- https://developer.x.com/

## 3. Stable contracts (independent of the repository that executes them)

Canonical semantic IDs:
- `observed_user_id`: immutable numeric X account ID (string).
- `activity_post_id`: immutable X event/status ID as returned for the action.
- `event_id = xevt:<observed_user_id>:<activity_post_id>` after provider identity proof. This identifies one observable action for one actor.
- `post_id`: immutable numeric X post ID, including referenced posts.
- `run_id`: unique ingest attempt.
- `event_type`: `ORIGINAL | REPOST | QUOTE | REPLY | MIXED | UNKNOWN` from provider references, never a stylistic inference.
- `reference_type`: `retweeted | quoted | replied_to | other` as returned/normalized.

Canonical producer-local events (JSONL, one per observed action):
```json
{
  "schema_version": "x.observer.event.v0.1",
  "event_id": "xevt:<observed_user_id>:<activity_post_id>",
  "observed_user_id": "<numeric-id>",
  "activity_post_id": "<numeric-id>",
  "event_type": "REPOST",
  "created_at_utc": "<provider timestamp>",
  "references": [{"type": "retweeted", "post_id": "<numeric-id>", "author_id": "<numeric-id or null>"}],
  "source": {"provider": "x_api_v2", "url": "<event url>", "run_id": "<run-id>"},
  "observed_at_utc": "<retrieval timestamp>",
  "evidence_status": "OBSERVED"
}
```
Angle brackets above are **schema illustrations**, not observed data. Source bodies are separate objects keyed by `post_id`. Original user actions and referenced authors must never be conflated. The full reference list and source payload digest must exist in canonical storage even if the Sheet flattens to primary reference columns.

`x.observer.post.v0.1` has `post_id`, `author_id`, `created_at_utc`, `text` (when available/permitted), `referenced_posts[]`, `edit_history`, `source_url`, `availability`, `last_checked_at_utc`, `content_sha256` and source-run provenance. A content hash update must not overwrite the past event ID.

`x.observer.run.v0.1` records run boundaries, requested and observed windows, `max_results`, pages, API reads, source errors, partial-result state, cache use, start/end high watermarks, estimated cost, coverage window, gap flags and persisted manifest URI. Current run status: `COMPLETE | PARTIAL | RATE_LIMITED | BUDGET_STOP | API_BLOCKED | FAILED`.

`x.observer.cursor.v0.1` is per observed numeric user ID and supports `highest_committed_since_id`, `backfill_until_id`, `pagination_token`, overlap, `last_success_at`, `coverage_status`, `gap_detected`, `revision`.

## 4. Persistence and replay

The **Google Sheet is an operational projection**, not the only canonical evidence source:
- `EVENTS` is an event-by-event, deduplicated view; `POSTS` is a content-by-post-id index.
- `ACCOUNTS` is operator configuration. `RUNS` and `CURSORS` show freshness, completeness limits, failures and checkpoints.
- No secret, raw OAuth config or refresh token in Sheets.

Initial fixture/local proof: canonical JSONL+manifest in local test artifacts (not checked in) with deterministic replay to in-memory Sheets. **Unattended** proof should use a durable private object store (e.g. narrowly scoped GCS prefix with manifest and generation preconditions), NOT ephemeral GitHub Actions workspace or artifact retention, to preserve observation evidence across jobs. Sheets projection can be rebuilt from canonical snapshots without requerying X.

For a page: validate provider response -> canonicalize IDs -> write immutable page/manifest -> idempotently project rows -> verify projection -> **advance per-account checkpoint only when the entire page/window is safely represented**. Persist a page digest and completion marker; a crash may replay but must not skip pages. Use optimistic generation/CAS or exclusive writer; do not rely solely on Sheets updates for locking.

An action may disappear because of deletion, de-repost, account protection, withholding, or availability changes. Treat `AVAILABLE | UNAVAILABLE | DELETED | PROTECTED | WITHHELD | UNKNOWN` as separate, revisitable states as permitted. Implement deletion/retention rules and honor platform terms rather than maintaining a permanent unrestricted text archive. No permanent conclusions about content that is no longer retrievable.

## 5. Completeness and budgets

"All" means **all retrievable, observed public actions within a declared window at the qualifying access level**, conditional on API availability. A successful poll does not prove no intermediate action was made and deleted.

- Initial trial: one verified account, e.g. preceding 24–72 hours, `max_pages=2` (up to 200 timeline results) and explicit `max_x_posts_read`/USD ceiling; measure actual API usage before selecting recurring interval.
- No indefinite historical backfill. Extend older windows manually with hard page, result and spend caps. When an endpoint truncates history, report `HISTORICAL_LIMIT`.
- Recurring suggestion **only after qualification**: every 15–30 minutes, with an overlap lookback to protect against delayed schedules. Keep a configurable `max_pages_per_poll` and per-account daily budget, plus global budget. 429 and insufficient credits -> stop and write honest run status, never loop indefinitely.
- X currently advertises pay-per-use (see https://developer.x.com/) and a posted price for read Post resources; costs depend on actual returned objects and billing rules. Track direct read count, expansions, rate and posted charges where available. No unbounded refresh/polling.
- Prevent progress claims when `newest_retrieved_at`, `oldest_retrieved_at`, number of pages and `coverage_status` are unknown. Explicitly report `COMPLETE_WITHIN_WINDOW | PARTIAL_WINDOW | UNKNOWN | HISTORICAL_LIMIT`.

## 6. Package boundaries

Provisional tree:
```text
src/office_runtime/x_observer/
    contracts.py            # pure typed events/posts/runs/cursors
    normalize.py            # provider payload -> canonical records
    client.py               # read-only X API client, no mutation method
    planner.py              # bounded since_id/backfill/page budget
    persistence.py          # immutable JSONL + manifest + CAS
    projection.py           # Sheet view + idempotent upsert
    health.py               # coverage and failure evidence
src/office_runtime/scripts/
    run_x_observer.py        # --dry-run default; --apply-snapshot explicit
config/x_observer/
    accounts.json           # example *disabled*, no API secrets
docs/spec/x-observer-v0/
    README.md
tests/
    test_x_observer_contracts.py
    test_x_observer_normalize.py
    test_x_observer_pagination.py
    test_x_observer_projection.py
    test_x_observer_recovery.py
```
Future extraction carries `x.observer.*.v0.1`, fixture vectors and stable IDs unchanged. Source import paths, GitHub workflow identities and storage adapters are not part of semantic event identity. Avoid importing Media Monitor internals or generic publisher internals.

## 7. Development gates

| Gate | Scope | Evidence required |
| --- | --- | --- |
| O0 | Contracts + realistic deterministic fixtures: ORIGINAL, REPOST, QUOTE, REPLY, mixed, missing reference, edited post | Fixture tests green, stable IDs and actor/content separation |
| O1 | Live read-only identity and API-shape qualification for `JMilei` | Numeric user ID, source endpoint, repost evidence, pagination sample, rate/cost trace; account still disabled for automation |
| O2 | Bounded paginated fetch + backfill and incremental planner | Replay identical page yields zero duplicate events; since_id, page token, partial errors, stop budgets |
| O3 | Canonical durable persistence, crash/restart checkpoint, deletion lifecycle | Page atomicity/restart invariants, generation/lock proof |
| O4 | Workbook projection | Real Sheet writes confined to expected tabs/fields; stable row IDs, no duplicate rows; changes reflect POST availability |
| O5 | GitHub Actions read-only scheduled observer | Explicit promotion, secrets-scoped identity, cost caps, schedule delay detection, positive fresh/partial status evidence |
| O6 | Optional adapter for Milei Mirror consumer | Only stable observer events exposed; consumer cannot mutate observation evidence or publish via observer |

### Acceptance invariants
1. Same event reobserved 10x yields one `EVENTS` identity and a truthful `last_seen_at`.
2. Two actors reposting the same referenced post produce **two distinct events, one referenced post object**.
3. Deleted/unavailable references do not imply that the activity was authored by the monitored actor.
4. A failed page or Sheet projection cannot advance the cursor.
5. Old/late pages cannot erase newer progress; partial runs can't claim complete coverage.
6. API call count, credits, latest successful observation and gaps remain visible.
7. Observer credentials are read-only and isolated from `@matuteiglesias`, `@ModernAIDev`, and any eventual parody account.
8. No new publishing permissions or workflows from O0–O5.

## 8. Immediate next action

Begin **O0+O1 only**. Write fixtures/unit tests; then use one bounded read-only call to prove `JMilei` numeric identity, a live timeline response and at least one repost/referenced-post sample if available. If the retrieved window contains none, report `REPOST_NOT_OBSERVED`, not PASS. Do not enable cron or generate satirical posts.

Required review packet after O1:
```yaml
capability: x_observer.read_public_activity.v0.1
targets: ["@JMilei"]
read_scope: ["public X user identity", "bounded user timeline"]
write_scope: ["operator-authorized local artifacts and workbook only; NO X mutations"]
dry_run_command: "python -m office_runtime.scripts.run_x_observer --dry-run --handle JMilei --max-pages 2"
apply_command: "python -m office_runtime.scripts.run_x_observer --apply-snapshot --handle JMilei --max-pages 2"
expected_evidence: ["verified numeric identity", "per-page digests", "repost classification", "API usage", "run manifest"]
rollback_or_recovery: ["disable observation, restore/rebuild Sheet projection from immutable JSONL"]
stop_condition: ["identity mismatch", "unknown coverage", "api budget cap", "missing durable commit"]
human_authorization: "separate explicit promotion for API reads and Sheet writes"
```

**No publication mode exists in this module.**
