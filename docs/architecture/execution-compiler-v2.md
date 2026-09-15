# Execution Compiler v2

**Status:** canonical
**Audience:** maintainers, operators, agents, and closure/reentry consumers
**Owner:** `src/office_runtime/office/execution.py`
**Verified against:** M6 fixture acceptance, Principal Compiler v2, and Control Tower operator contracts

## Purpose

The Execution Compiler turns Principal `ready_pulls` into bounded machine-readable execution envelopes. It does not execute them.

A ready pull is a presentation object, not execution authorization. It must already contain a validated Staff action contract; Execution validates and wraps that contract but never invents an objective, entry surface, acceptance condition, or stop condition.

The canonical seam is:

```text
Principal ready pull
  +
frozen Control Tower snapshot
  ↓
Execution Compiler
  ↓
execution packet
  ↓
human / agent / scheduled executor
```

This is the first v2 stage that describes what an executor may do. It therefore fails closed when identity or operator authority is insufficient.

## Authorization rule

Only `ready_pulls` are compilation candidates.

`needs_you` is a decision surface, not authorization. The existence of a Principal decision entry is never interpreted as approval and is reported under `ignored_principal_entries` with reason `PRINCIPAL_DECISION_IS_NOT_EXECUTION_AUTHORIZATION`.

A decision that changes what should happen must first cross a governed decision/reentry boundary and later surface as executable work. This prevents the execution layer from guessing what the principal meant.

## Operator contract

Each executable front must have one unambiguous ACTIVE operator contract. The compiler prefers a unique `primary_operator`; ambiguous active contracts fail closed.

The execution packet projects only portable contract semantics:

- contract identity/version;
- effective allowed powers;
- forbidden powers;
- required seams;
- shared modules that must be consumed;
- capabilities that must not be reimplemented locally.

Machine-local runbook/repo paths are not exported.

## Withheld powers

Even when the current operator contract lists them as allowed, v2 execution packets withhold:

- `update_state`;
- `open_work_items`.

Execution is evidence-producing work, not authority to rewrite governance or manufacture follow-up work. Those outcomes belong to M7 closure/reentry.

The contract remains an upper bound. The packet objective and stop conditions further constrain what an executor should actually do.

## Target identity

Repository targets are expressed only as `repo_id`, `workspace_id`, and resolution state already established upstream. No local filesystem path is embedded in the portable packet.

A repository-backed ready pull with a non-`RESOLVED` workspace becomes a `TARGET_NOT_READY` execution-plan exception rather than falling back to a legacy path.

Human/process fronts may legitimately have no repository target.

## Packet contract

`ops.execution-packet.v2` contains:

```text
execution_packet_id
work_item_id
front_id
kind
objective
why_now
target
operator
evidence_inputs[]
acceptance_conditions[]
stop_conditions[]
authorization
source_snapshot_digest
packet_digest
```

Supported execution kinds are `UNBLOCK`, `VERIFY`, `EXECUTE`, and `MAINTAIN`. `DECIDE` is deliberately excluded.

## Acceptance and stop semantics

Acceptance and stop conditions are supplied by the mature Staff action contract for the named bounded unit. Generic conditions such as “complete one bounded objective” are rejected: they cannot establish that Staff actually prepared a meaningful pull. Execution still withholds forbidden powers and fails closed for unresolved target identity. `VERIFY` failure remains evidence, never automatic repair authorization.

## Plan exceptions

The plan keeps non-executable candidates explicit instead of silently dropping them. Current exception codes include:

- `NO_ACTIVE_OPERATOR_CONTRACT`;
- `TARGET_NOT_READY`;
- `UNSUPPORTED_EXECUTION_KIND`.

## Non-goals

M6 does not:

- run shell commands or mutate repositories;
- resolve local paths;
- send/publish externally;
- infer principal approval;
- mutate Control Tower;
- create follow-up work;
- decide whether an execution receipt is complete.

Those responsibilities remain with the actual executor and the M7 closure/reentry layer.
