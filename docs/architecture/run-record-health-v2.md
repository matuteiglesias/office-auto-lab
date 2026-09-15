# Office v2 Run Records, Health, and Freshness

**Status:** canonical
**Audience:** maintainers, runtime engineers, Office Review consumers
**Owner:** Run Record Owner (`fr_0004`)
**Verified against:** M10 run-record, invariant, runtime-health, and Staff-freshness contract tests

## Purpose

M10 makes Office v2 observable as an operating system rather than merely a successful compiler.

The governing flow is:

```text
scheduled/manual generation attempt
  ↓
coherent Office v2 generation
  ↓
canonical run record
  ↓
Run Record Owner
  ↓
runtime-health projection
```

Run evidence answers what actually happened. It never decides what should matter strategically and never mutates Carry, horizon, priority, or Principal policy.

## Canonical run record

Every accepted real generation attempt has an `ops.office-run-record.v1` record under:

```text
artifacts/v2/run_records/<run-id>.json
```

A record includes:

- stable run identity;
- producer front and routine;
- trigger;
- start / finish / duration;
- success or failure;
- publication state;
- snapshot and manifest digests where available;
- stage results;
- generation counts;
- warnings / failures;
- run artifact reference.

The coherent-generation runtime treats run evidence as part of publication semantics.

For a publishable successful run:

```text
complete run tree
  ↓
write successful NOT_PUBLISHED run evidence
  ↓
atomically advance v2 current pointer
  ↓
finalize the same run record as PUBLISHED
```

If publication fails, the attempt is recorded as `FAILED / NOT_PUBLISHED` rather than silently appearing successful.

Shadow runs are recorded as `SUCCEEDED / SHADOW` and never advance the current pointer.

## Stage results and invariants

The generation records the forward stages:

```text
snapshot
work
staff
principal
execution
invariants
manifest
promotion
run_record
publication
```

The cross-layer invariant suite protects seams that local compiler tests cannot see alone. It currently verifies that:

- every forward layer belongs to one snapshot digest;
- work identities are unique;
- Staff packets cover exactly the typed work set;
- Principal sections are disjoint and refer only to prepared work;
- `Needs You` contains prepared principal work;
- ready pulls no longer require Principal judgment;
- execution packets originate only from ready pulls;
- execution targets have resolved workspace identity;
- execution never regains `update_state` or `open_work_items` powers.

These are architecture invariants, not merely UI expectations.

## Runtime health is a projection

`src/office_runtime/scripts/compile_runtime_health_v2.py` compiles canonical run records into an `ops.runtime-health-projection.v2` artifact.

Default output:

```text
artifacts/v2/runtime_health.json
```

The projected row shape is compatible with the semantic `runtime_health_v2` fields:

```text
front_id
health_status
health_bucket
last_observed_at
last_observed_by
short_diag
evidence_ref
source_run_id
generated_at
```

The Run Record Owner is the compiler of this observation surface. Individual producers do not independently write health truth.

Current states include:

```text
OK / LAST_SCHEDULED_RUN_OK
WARN / SCHEDULED_RUN_STALE
FAIL / LAST_RUN_FAILED
UNKNOWN / OBSERVABILITY_GAP
N/A / NO_RUNTIME_EXPECTED
```

Shadow runs are evidence but do not satisfy scheduled-runtime health.

## Health does not imply strategic state

Runtime health answers questions such as:

- did the expected producer run?;
- did the last real run fail?;
- is the last successful run stale?;
- is there an observability gap?;

It does not answer:

- should this front be ACTIVE?;
- should priority increase?;
- should Mati intervene?;
- should a new work item be created?;

Those remain Control Tower / Office compilation decisions.

## Staff packet freshness

Prepared context is not timeless.

`office_runtime.staff.freshness.evaluate_packet_freshness()` evaluates whether a Staff packet can safely be reused without performing any refresh itself.

The explicit states are:

```text
CURRENT
STALE_STATE
STALE_REPOSITORY
UNKNOWN_EVIDENCE
UNKNOWN_FRESHNESS
```

A packet is reusable only when:

- it still belongs to the current Control Tower snapshot; and
- any repository revisions captured as local evidence still match known current revisions.

If current repository evidence is unavailable, Office does not assume freshness.

This keeps preparation reusable when evidence remains valid without allowing cached context to masquerade as current truth.

## Commands

```bash
make office-v2-generate
make office-v2-shadow
make runtime-health-v2
make run-record-contracts
make freshness-contracts
```

## Publication and scheduler boundary

The systemd layer remains a clock and single-instance guard. It invokes one coherent generation command.

Run records describe what that invocation did. Runtime health derives from those records. Neither layer recreates the semantic Office DAG.

## Non-goals

M10 does not:

- automatically execute ready pulls;
- auto-approve Principal decisions;
- apply reentry proposals;
- write Carry state;
- make runtime health authoritative over portfolio semantics;
- delete legacy compatibility surfaces before their consumers migrate.
