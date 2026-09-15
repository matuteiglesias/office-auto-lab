# Closure and Reentry v2

**Status:** canonical
**Audience:** maintainers, operators, executors, and Control Tower reviewers
**Owner:** `src/office_runtime/office/reentry_v2.py`
**Verified against:** M7 fixture acceptance and Execution Compiler v2 packet contracts

## Purpose

M7 closes the bounded execution loop without giving executors authority over governance state.

The canonical return path is:

```text
execution packet
  ↓
human / agent executor
  ↓
execution receipt
  ↓
receipt validation
  ↓
closure fact
  ↓
reviewable reentry proposal
  ↓
human/governed reconciliation later
```

Execution produces evidence. Reentry interprets that evidence into a review surface. Neither stage silently rewrites Control Tower.

## Receipt identity

`ops.execution-receipt.v2` must prove exactly which bounded packet produced it. It carries:

- `receipt_id`;
- `execution_packet_id`;
- `execution_packet_digest`;
- `work_item_id`;
- `front_id`;
- `source_snapshot_digest`.

All of those identities are checked against the exact execution plan and packet. A free-standing receipt that merely names a front is insufficient.

Only one receipt may close one packet in a closure compilation. Duplicate receipt identities or multiple receipts for the same packet fail closed.

## Receipt status

Supported receipt statuses are:

- `COMPLETED`;
- `PARTIAL`;
- `BLOCKED`;
- `NO_CHANGE`;
- `FAILED`.

A `COMPLETED` receipt must report every packet acceptance condition and pass all of them. It must also contain evidence. It cannot claim completion by exit code or narrative alone.

`BLOCKED` and `FAILED` receipts must name at least one explicit blocker.

Receipts may also contain actions taken, residuals, and an executor-suggested next touch. These remain execution facts/recommendations rather than new governance truth.

## Closure classification

The compiler derives a compact lifecycle classification for review:

- `DONE` — packet completed and no residuals remain;
- `FOLLOW_UP` — packet completed/partially completed but bounded residuals remain;
- `WAITING` — blocked, failed, or no-change outcome requires a future review/condition;
- `REVIEW` — fallback for an unexpected but validated state.

This classification is about the work item/packet, not the whole front. `DONE` therefore never implies that a Control Tower front should automatically be parked or closed.

## Reentry proposal

`ops.reentry-proposal.v2` carries:

```text
proposal_id
front_id
work_item_id
execution_packet_id
receipt_id
classification
what_became_true
what_remains[]
suggested_next_touch
evidence[]
reentry_intent
candidate_control_patch
mutation_performed
source_snapshot_digest
source_receipt_digest
proposal_digest
```

In M7, `candidate_control_patch` is deliberately `null` and `mutation_performed` is always false.

This is conservative by design. Execution evidence is now strongly linked enough to support future reviewed Control Tower patches, but M7 does not invent which carry/horizon/priority field should change from a single completed packet.

## Unclosed packets

Execution-plan packets without receipts remain visible as `OPEN_NO_RECEIPT`. They are not interpreted as failures, completed work, or stale work merely because closure compilation ran.

This makes absent evidence distinguishable from negative evidence.

## Authority boundary

Closure/reentry v2 does not:

- mutate Carry State;
- change horizon or priority;
- create a new work item;
- approve an executor-suggested next touch;
- infer that the whole front is done;
- hide packets for which no receipt exists.

The proposal indicates which reviews are warranted. A later governed reconciliation/cutover milestone may turn accepted proposals into Control Tower mutations.

## Relation to legacy closure reentry

`closure_reentry.py` remains as the compatibility consumer for `artifact:ops.closure@1`. M7 introduces the native v2 packet-linked receipt path alongside it. The legacy path should not constrain v2 identity or lifecycle semantics and can be retired after cutover/consumer census.
