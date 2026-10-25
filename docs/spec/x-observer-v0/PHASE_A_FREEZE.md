# X Observer Phase A — frozen qualification plan (2026-10-08)

## Authority and boundaries
- Owner: `office-auto-lab` SIDECAR, **read-only**; issue #72, original specification PR #73.
- First research subject: public X handle `JMilei`. Resolve numeric user ID from X API, refuse protected or mismatched identity.
- Does NOT use publishing apps, the `EDITORIAL_ECON_XURL_OAUTH1_YAML` secret, or Google Sheets publisher permissions.
- No cron, X write API methods, publication, Sheet writes, or durable cursor advancement in Phase A.
- Existing economics publisher remains authoritative and untouched. X transport is not shared yet.

## Source-shape investigation
On 2026-10-08 the [Get Users Posts](https://docs.x.com/x-api/users/get-posts) endpoint documents
`GET /2/users/{id}/tweets` with `max_results` range 5..100, a `post.fields` parameter,
`expansions=referenced_posts,author_id`, `pagination_token` and `meta.next_token`.
Older fixtures/docs may expose `tweet.fields`, `referenced_tweets` and `includes.tweets`.
**Only the real bounded O1 response can establish which actual fields/relationships are returned.**
Do not supply `exclude=retweets` or `exclude=replies`; do not infer that missing
references prove an original when the page has partial errors.

Current public pricing reference: https://docs.x.com/x-api/getting-started/pricing
and developer portal (2026-10-08): $0.005/post resource, $0.010/user read;
charge models/credits may change. Count returned unique post IDs including expansions
conservatively and stop before the next request when the estimated cap may be exceeded.

## O0 gates: offline implementation
- Typed identity, reference, event and post structures with versioned dictionaries.
- Stable `xevt:<actor_numeric_id>:<activity_numeric_id>` identity independent of run time.
- Separate observed actor from the **original author's** identity.
- ORIGINAL / REPOST / QUOTE / REPLY / MIXED / UNKNOWN; multi-reference retention;
  legacy/current provider aliases; partial success, unknown author, missing references;
  edited/unavailable references, source-page digest.
- Deterministic test fixtures, no credentials/network; no fake complete coverage.

## O1 gates: live read-only qualification
1. Require `X_OBSERVER_BEARER_TOKEN` in a private shell, dedicated read-only X app if available.
   **Never reuse the economics/ModernAIDev OAuth1 publishing secrets** or put a bearer token in GitHub.
2. Explicit CLI `--qualify-live` flag; default CLI has no network access.
3. Resolve `GET /2/users/by/username/JMilei`; assert handle, numeric ID, public state.
4. Probe up to 2 timeline pages; initial default `max_results=10`, max 20 posts before
   counting expanded referenced objects, and `--max-usd=0.25` (conservative upper bound).
   Do not fetch the next page if there is insufficient remaining ceiling.
5. Prove response shape, actual references and pagination metadata; classify `REPOST_NOT_OBSERVED`
   if there is no verified repost; don't infer repost support from documentation.
6. Emit **non-content**, secret-free JSON summary: verified ID, query shape, pages,
   partial errors, counts, response digests, estimated cost ceiling, pagination and
   repost evidence state; do not persist raw content to a public artifact.
7. Stop on 401/403/429, identity mismatch, protected account, malformed records, partial
   errors or budget uncertainty. Never silently retry an API read or publish.
8. No write to ACCOUNTS until separately qualified/promoted; original workbook disabled.

### Acceptance
O0: unit tests pass offline on 3.11/3.12, no changes to publisher behavior.
O1: genuine X API identity+page evidence and actual schema sample (or a truthful
external blocker with reproduction command). **A fixture result is not O1 proof.**

## Next phases (not authorized by Phase A alone)
O2 bounded backfill and incremental overlap; O3 private source-page manifests and CAS
cursor; O4 idempotent Sheets projection; O5 separately permissioned read-only Actions
schedule; O6 consumer adapter for Milei Mirror. No automatic satire or publication.

## Runbook
```bash
PYTHONPATH=src python3 -m unittest tests.test_x_observer_phase_a
PYTHONPATH=src python3 -m office_runtime.scripts.run_x_observer --dry-run
# If an approved, separate read-only bearer token exists in your private local shell:
PYTHONPATH=src python3 -m office_runtime.scripts.run_x_observer \
    --qualify-live --handle JMilei --max-pages 2 --max-results 10 --max-usd 0.25
```
