# Operations — Editorial Dev Staging v1

## Operating principle

The staging producer should run without daily human initiation, but it should not require daily human approval to remain healthy.

Healthy daily operation means:

- evidence was inspected;
- a run bundle exists;
- the queue was updated idempotently;
- inventory is either `HEALTHY` or truthfully `DEGRADED_INVENTORY`;
- no external post was created.

## Scheduler

Initial scheduler: GitHub Actions.

Reasons:

- already declared by the W0 Editorial architecture;
- isolated execution;
- secrets management;
- logs/artifacts;
- manual dispatch;
- no new hosting plane.

The exact cadence is configuration. The semantic producer identity must not depend on cron syntax.

A later scheduler migration must not change candidate/run contracts.

## Daily generation strategy

One primary daily staging run should:

1. load pinned editorial policy;
2. read recent queue/history;
3. retrieve fresh Tier 1 evidence;
4. add Tier 2/3 evidence when useful;
5. generate and judge angles/candidates;
6. compile the daily batch;
7. if inventory is below target, perform bounded fallback retrieval/generation passes;
8. write the immutable run bundle;
9. project machine rows;
10. initialize missing queue rows without overwriting human state.

Optional later event-driven/refill runs may add fresh candidates after important work, but they use the same contracts and dedupe rules.

## Inventory refill

Suggested default fallback order:

```text
fresh completed work
  ↓
fresh broader activity
  ↓
recent 14-day work
  ↓
cross-project synthesis
  ↓
governed historical-dev-work bench
```

Each widening pass is recorded.

A run must have a configured maximum number of widening/model passes.

## Manual operator path

Operators need a precise way to reproduce one source.

Required capabilities:

- exact PR/event staging;
- explicit date/window staging;
- dry-run with local artifacts only;
- optional Sheet projection only when authorized.

Manual runs use the same contracts as scheduled runs.

## Sheet ownership

### Machine may write

`RUNS`:

- machine fields for known `run_id`.

`CANDIDATES`:

- create candidate row once;
- never rewrite immutable provenance/original text.

`QUEUE`:

- create row once with defaults.

### Machine must preserve

After creation:

- `draft_editable`;
- `decision`;
- `editor_note`;
- `target_surface`;
- `publisher_status`;
- `scheduled_for`;
- `published_ref`.

If the adapter cannot distinguish machine and human columns, stop instead of writing.

## Recommended queue data validation

Where convenient, the workbook should expose human-friendly dropdowns:

`decision`:

- `REVIEW`
- `APPROVE`
- `HOLD`
- `REJECT`

`target_surface` initially:

- `X`
- `LONGFORM_SEED`
- `LINKEDIN_SEED`
- `NONE`

Only `X` is an active v1 target; the other values are editorial annotations for later consumers.

## Candidate lifecycle

```text
generated
   ↓
staged in CANDIDATES
   ↓
queue row REVIEW
   ├─► APPROVE
   ├─► HOLD
   └─► REJECT

future publisher:
APPROVE/policy-eligible
   ↓
scheduled
   ↓
published / failed / expired
```

The staging producer owns only the left side through queue initialization.

## Freshness and expiry

Candidates should carry a freshness class:

- `timely`
- `recent`
- `evergreen`

Timely candidates should have an explicit expiry. A future publisher must not publish expired candidates merely because they remain approved.

Evergreen candidates sourced from historical work must make temporal wording truthful.

## Run statuses

Recommended:

- `HEALTHY`
- `DEGRADED_INVENTORY`
- `PARTIAL_SOURCE_FAILURE`
- `FAILED`

A source failure and an inventory shortage are different conditions and should remain distinguishable.

### Opt-in acceptance fallback

For bounded W1 acceptance/debugging only, operators may set
`EDITORIAL_FORCE_ONE_SAFE_CANDIDATE=1`.

When enabled and the independent judge would otherwise stage zero candidates, the
runtime may retain exactly one **soft-rejected** candidate only when:

- the story is public-eligible;
- disclosure, repetition, and status-truth hard gates all pass;
- risk is low or medium;
- status wording remains truthful;
- timely material still has an expiry.

The row remains human `REVIEW`, carries a
`FORCED_PIPELINE_ACCEPTANCE` warning in the Sheet projection, and the batch remains
`DEGRADED_INVENTORY`. This mode never compensates for a hard-gate failure and does
not count as evidence that normal editorial inventory quality is healthy.

The default is disabled.

## Retry and overlap

Scheduled runs deliberately use overlapping retrieval windows.

Correctness comes from stable evidence/candidate IDs and dedupe, not from a fragile last-seen cursor.

Retry requirements:

- rerunning a run after model failure may complete missing sections;
- Sheet retries do not duplicate rows;
- partial Sheet success is recoverable;
- human changes made between retries survive.

## Observability

Minimum operator summary per run:

```text
run_id
profile
policy_ref
retrieval sources attempted/reached
evidence count by source kind
story count
angle count
candidate count before/after gates
daily batch count
inventory status
fallback tiers used
source failures
projection status
```

Do not expose private source bodies in routine logs.

## Kill/hold controls

Although W1 does not publish externally, staging itself needs bounded controls:

- global staging disable;
- profile disable;
- Sheet projection disable while retaining local run bundle;
- historical fallback disable;
- per-repository exclusion;
- sensitive-topic exclusion.

These are operational/policy controls, not model prompts.

## Recovery

### Model/provider outage

Write retrieval evidence and failure state. Do not emit fake candidates.

### GitHub partial access

Record scope failure and continue only if remaining evidence is sufficient and the run does not claim full-estate observation.

### Sheet unavailable

Keep canonical run bundle; mark projection failed. Retry projection later by stable IDs.

### Invalid policy

Fail before generation.

### Human/machine ownership conflict

Stop Sheet mutation and preserve run evidence.

## Publisher promotion

A downstream publisher may be implemented only after staging acceptance.

The publisher must have its own:

- policy gate;
- account identity proof;
- X credentials;
- cadence/scheduling semantics;
- publication duplicate check;
- mutation receipt;
- metrics/readback behavior.

Its existence must not make the staging producer mutation-capable.

## Estate onboarding after proof

After operational acceptance:

- register the producer in `projects` with its scheduler-neutral semantic identity;
- register/propose the Sheet surface with owner, consumer, mutation policy, and freshness;
- add the workbook to the Google Sheets Estate Registry;
- preserve Office as runtime owner and weekly governance as editorial-policy owner.

Registration follows proof; it does not manufacture proof.
