# Contracts — Editorial Dev Staging v1

This document defines the semantic contracts the implementation must preserve. JSON Schema/Pydantic implementations may be added under `src/office_runtime/editorial/`, but field meaning belongs here.

## 1. `office_runtime.editorial.activity_evidence.v1`

One observed work/activity fact.

Required fields:

```yaml
schema_version
evidence_id
source_kind
source_ref
observed_at
event_at
status
title
summary
repository_ref
visibility
public_eligibility
artifact_refs
```

### `source_kind`

Initial values:

- `github_pr`
- `github_release`
- `github_commit`
- `github_issue_decision`
- `office_run_evidence`
- `producer_receipt`
- `durable_artifact`
- `historical_dev_work`

### `status`

At minimum:

- `completed`
- `merged`
- `released`
- `in_progress`
- `failed`
- `waiting`
- `dropped`
- `superseded`
- `unknown`

No copy may silently promote one status to another.

## 2. `office_runtime.editorial.story_cluster.v1`

One potential public story supported by one or more evidence items.

Required:

```yaml
schema_version
story_id
evidence_refs[]
cluster_kind
working_summary
freshness_class
repository_refs[]
public_eligibility
```

Optional:

```yaml
related_context_refs[]
measured_results[]
open_questions[]
status_language_constraints[]
```

`story_id` is deterministic from ordered evidence refs plus `cluster_kind`.

## 3. `office_runtime.editorial.angle.v1`

Intermediate editorial angle. It is not post copy.

Required:

```yaml
schema_version
angle_id
story_id
angle_type
claim
tension_or_hook
transferable_lesson
evidence_refs[]
audience[]
career_signals[]
why_interesting
risk_class
```

Allowed `angle_type`:

- `lesson`
- `artifact`
- `question`
- `failure`
- `tradeoff`
- `measurement`
- `field_note`
- `synthesis`

Optional:

```yaml
proof_object_refs[]
required_status_wording[]
counterpoint
expiry_hint
```

An angle with an evidence ref not present in the run evidence graph is invalid.

## 4. `office_runtime.editorial.candidate.v1`

The existing W0 candidate contract remains the public component seam:

Required existing fields:

```yaml
schema_version
candidate_id
profile_id
text
risk_class
evidence_refs[]
work_refs[]
```

For dev staging v1, implementations should additionally emit:

```yaml
story_id
angle_id
candidate_family
semantic_fingerprint
language
topic_tags[]
career_signals[]
proof_object_refs[]
freshness_class
generated_at
expires_at
machine_disposition
quality
```

### `machine_disposition`

- `stage`
- `hold`
- `drop`

This is machine editorial judgment, not human approval.

### `quality`

Five bounded dimensions:

```yaml
evidence
specificity
external_usefulness
novelty
professional_signal
```

Each score uses one documented finite scale. The first implementation may use 0–4 or 1–5, but the scale must be consistent inside a schema version.

Gates recorded separately:

```yaml
disclosure_risk
repetition_risk
status_truth_risk
```

No weighted score may override a failed hard gate.

## 5. `office_runtime.editorial.daily_batch.v1`

Represents the final staged inventory decision for one profile/day.

Required:

```yaml
schema_version
batch_id
profile_id
batch_date
target_count
floor_count
ceiling_count
inventory_status
candidate_ids[]
source_tier_counts
diversity_summary
shortage_reasons[]
```

`inventory_status`:

- `HEALTHY`
- `DEGRADED_INVENTORY`
- `FAILED`

`HEALTHY` requires `floor_count <= len(candidate_ids) <= ceiling_count`.

## 6. `office_runtime.editorial.run_bundle.v1`

Immutable execution/provenance evidence.

Required top-level sections:

```yaml
schema_version
run_id
profile_id
started_at
finished_at
policy:
retrieval:
evidence:
stories:
angles:
candidates:
batch:
provider_runs:
errors:
status:
```

### Policy section

Must pin exact policy identity, such as commit/ref plus content hash. "Latest" is not sufficient evidence.

### Retrieval section

Records:

- intended sources;
- actual sources reached;
- time windows;
- access failures;
- unknown/incomplete scope.

### Provider runs

Records model/provider identity, request stage, timing and usage metadata where available. It must not contain secrets or hidden reasoning.

## 7. Sheet projection contract

### `RUNS`

Key: `run_id`.

Machine-owned. A rerun with the same run ID must reconcile, not duplicate.

Minimum columns:

```text
run_id
profile_id
started_at
finished_at
inventory_status
candidate_count
policy_ref
source_summary
error_summary
run_bundle_ref
```

### `CANDIDATES`

Key: `candidate_id`.

Machine-owned, append-only for semantic content.

Minimum columns:

```text
candidate_id
batch_id
run_id
created_at
source_date
source_tier
repo
work_refs
angle_type
candidate_family
claim
evidence_refs
proof_object_refs
career_signals
risk_class
semantic_fingerprint
draft_original
machine_disposition
quality_summary
expires_at
```

Existing candidate rows must not have `draft_original`, provenance, or scores rewritten by a later generation run.

### `QUEUE`

Key: `candidate_id`.

Human/publisher-owned operational fields:

```text
candidate_id
draft_editable
decision
editor_note
target_surface
publisher_status
scheduled_for
published_ref
updated_at
```

New candidates may initialize:

```text
draft_editable = draft_original
decision = REVIEW
target_surface = X
publisher_status = blank
```

After row creation the staging producer must preserve all human/publisher-owned cells.

## 8. Publisher handoff v1

A future publisher consumes queue state. Minimum handoff:

```yaml
candidate_id
profile_id
account_key
draft_text
decision_or_policy_state
risk_class
evidence_refs[]
semantic_fingerprint
expires_at
scheduled_for
```

The publisher is responsible for:

- account identity proof;
- cadence policy;
- publication eligibility;
- duplicate protection against actual X history;
- external mutation;
- returned post ID/URL;
- writeback of publication result.

The staging producer performs none of these responsibilities.

## Referential invariants

1. Every candidate references exactly one angle.
2. Every angle references exactly one story.
3. Every story references one or more evidence items.
4. Every referenced evidence ID exists in the run bundle.
5. Every staged candidate appears in exactly one daily batch for that batch execution.
6. Queue rows may exist only for known candidate IDs.
7. Publication state cannot change evidence/candidate provenance.
8. Human editing changes `draft_editable`, never `draft_original`.
