# Acceptance — Editorial Dev Staging v1

Acceptance is evidence-driven. Passing unit tests without a real activity-to-queue proof is insufficient.

## A. Boundary and authority

### A1 — existing owner

Implementation lives in `office-auto-lab` Editorial SIDECAR.

**Pass:** no new generic editorial repository or runtime authority is introduced.

### A2 — superseded system remains superseded

**Pass:** no runtime dependency on `editorial-core`.

### A3 — no publication

**Pass:** W1 staging contains no executable X mutation path and requires no X write credential.

### A4 — upstream truth preserved

**Pass:** repository/project scientific/product status is copied/referenced, not silently reinterpreted.

## B. Evidence acquisition

### B1 — merged PR

Given a known merged PR, the system emits a schema-valid evidence item with exact repository, PR, merge SHA, merge time, and status.

### B2 — broader activity

At least three source kinds beyond merged PRs are supported before final v1 acceptance, including at least one non-GitHub-PR activity source.

Examples: release, commit/result, issue decision, Office evidence, producer receipt, durable artifact.

### B3 — bounded access failure

An inaccessible source produces explicit unknown/degraded evidence. It does not cause the system to claim the estate was fully observed.

### B4 — status truth

An open/in-progress artifact cannot produce copy that says it shipped/merged/released unless another evidence item proves that status.

## C. Editorial generation

### C1 — intermediate angles

A real evidence cluster produces structured `AngleCard` objects before post copy is generated.

### C2 — abstention

A dependency bump or other deliberately boring fixture may yield zero stageable candidates.

### C3 — nontriviality

At least one fixture proves the system can turn implementation evidence into a transferable external lesson rather than a changelog sentence.

### C4 — provenance

Every final claim carries inspectable evidence refs that survive into the run bundle and candidate projection.

### C5 — privacy

A sensitive/security/private fixture is held or dropped and does not leak restricted content into the Sheet projection.

## D. Daily inventory compiler

### D1 — target behavior

Default configuration is:

```text
target = 8
floor = 5
ceiling = 12
```

### D2 — fallback behavior

A thin-current-activity fixture causes the compiler to widen through configured evidence tiers rather than duplicate wording from one event.

### D3 — no fabrication

When fewer than five defensible candidates exist after eligible fallbacks, the batch is `DEGRADED_INVENTORY` with shortage reasons.

### D4 — source concentration

No one source event contributes more than the configured per-event maximum to the final batch.

### D5 — semantic dedupe

Near-identical claims generated from the same evidence family do not enter the final batch twice.

### D6 — diversity

When the evidence pool supports it, batch metadata demonstrates more than one repository/project or candidate family. Diversity is never manufactured by weakening evidence gates.

## E. Idempotency and human state

### E1 — rerun

Processing the same source window twice does not duplicate evidence, candidates with the same semantic identity, or queue rows.

### E2 — preserve edits

Given a queue row whose `draft_editable`, `decision`, or `editor_note` was changed by a human, a subsequent staging run preserves those exact values.

### E3 — immutable original

`draft_original` and candidate provenance are not rewritten after initial projection.

### E4 — publication state isolation

The staging producer does not alter `publisher_status`, `scheduled_for`, or `published_ref` after queue-row initialization.

## F. ADK/framework boundary

### F1 — typed seam

ADK/model output is validated into local contract objects before downstream use.

### F2 — replaceability

Tests for batch compilation and Sheet projection operate on contract fixtures without importing ADK.

### F3 — deterministic gates

Risk, evidence-ref validation, dedupe, floor/ceiling, and human-field preservation are ordinary deterministic code, not model self-policing.

## G. Run evidence

### G1 — bundle

Every completed run writes one schema-valid `editorial.run_bundle.v1`.

### G2 — failures visible

Retrieval/model/projection failures are present in the run bundle even when the overall run can finish degraded.

### G3 — policy pin

The run records an exact editorial policy identity/hash.

### G4 — no secrets

Fixtures/tests demonstrate that credentials, raw secret-bearing responses, and local absolute paths are excluded from run bundles and Sheet rows.

## H. Sheet surface

### H1 — workbook shape

A test/staging workbook contains `RUNS`, `CANDIDATES`, and `QUEUE` with the declared ownership split.

### H2 — append/project

A real processing run results in reviewable candidate rows and corresponding queue rows.

### H3 — human use

A human can edit a candidate, set a decision, and see that state survive the next run.

## I. Scheduled staging

### I1 — unattended run

The supported scheduler executes staging without a human initiating it.

### I2 — manual/backfill path

A bounded manual command can process one exact PR/evidence event or one explicit date window for debugging/backfill.

### I3 — duplicate-safe schedule

A repeated scheduler invocation over an overlapping lookback window produces no duplicate queue inventory.

## J. End-to-end acceptance

Before declaring v1 staging operational, capture evidence for at least three scheduled daily batches.

Across that proof window:

- every scheduled run has a run bundle;
- each day reaches the configured floor **or** has a truthful `DEGRADED_INVENTORY` reason;
- at least 15 distinct staged candidates exist across the three days unless explicit evidence shortage explains otherwise;
- one day proves broader-than-merged-PR sourcing;
- one candidate has been manually edited and survives regeneration;
- no X mutation occurs.

Only after these pass should the producer/surface be proposed for estate registration and any downstream publisher implementation begin.
