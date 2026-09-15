# Staff Preparation v2

**Status:** canonical
**Audience:** maintainers, operators, agents, and downstream Principal consumers
**Owner:** `src/office_runtime/staff/preparation_v2.py`
**Verified against:** M4 fixture acceptance and Office v2 snapshot/work-item contracts

## Purpose

Staff v2 converts typed Office work into evidence-backed preparation without becoming a second control plane.

The canonical flow is:

```text
Control Tower v2
  ↓ once
control snapshot
  ↓
typed work items
  ↓
cheap Staff triage
  ↓
bounded deep preparation
  ↓
structured Staff packets
```

Staff v2 never rereads Control Tower Sheets. The supplied snapshot is the run's worldview. If the work-item set was compiled from a different snapshot digest, preparation fails rather than mixing generations.

## Boundary from legacy Staff

Legacy `staff/bundles.py` and `staff/briefs.py` remain available during migration, but they are not the v2 preparation contract. The legacy path rereads Sheets, reconstructs `project_id` state, parses `needs`, consumes direct repo/workdir paths, and writes mutable `latest/` bundles and briefs.

Staff v2 deliberately does none of those things. It consumes:

- `artifact:ops.control-state-snapshot@2`;
- `artifact:ops.work-item-set@1` compiled from the same snapshot;
- explicit evidence adapters.

This separation lets the old scheduled runtime remain intact until the later cutover milestone.

## Two-stage preparation

Every work item receives cheap deterministic triage. Triage can classify an item as:

- `READY_FOR_PREP` — deep preparation is warranted;
- `NO_DEEP_PREP_REQUIRED` / `READY_LIGHT` — only light preparation is warranted;
- `BLOCKED` — a prerequisite is explicit enough that expensive/local adapters must not run.

Deep preparation is bounded by `max_deep` and allocated deterministically across `DECISION`, `ACTION`, and `REPAIR_VERIFY` lanes before unused capacity spills over. Items beyond the budget remain visible as `DEFERRED_BY_BUDGET`; they are not silently dropped or escalated as Principal exceptions.

The budget is a WIP bound, not a strategic priority system. Control Tower still owns governed state and priority semantics.

## Evidence adapters

Evidence adapters enrich a typed work item without changing its type, carry, horizon, or principal requirement.

The built-in adapters are:

### Control snapshot adapter

Reads only the already-captured snapshot and exposes current runtime observations, support artifacts, and active operator contracts relevant to the front.

### Local repository adapter

Resolves a workspace through the governed v2 identity resolver and may inspect the selected local Git checkout. A concrete local path is used only inside the adapter. Portable evidence returns `repo_id`, `workspace_id`, revision, branch, and dirty state; it does not export the path.

Additional adapters can later cover documents, recent activity, relationship context, opportunity context, calendars, or public web evidence. They must remain evidence providers rather than hidden routing engines.

For ACTION work, an adapter may additionally provide a Staff-owned action contract. It must specify a concrete objective, typed portable entry surface, why-now, scope boundary, acceptance and stop conditions, expected evidence, uncertainties, and any explicit decision dependencies. Staff does not infer this contract from front prose. Without one, a deeply prepared action is `NEEDS_MORE_PREP`, not a ready pull.

## Observational action candidates

`ops.staff-action-candidate.v1` is the generic seam between domain evidence and
Staff action maturity. A candidate is advisory observation, never Control Tower
state, Principal approval, or execution authorization. It includes its front,
producer, generation time, evidence references/freshness, a proposed bounded
objective and portable entry surface, conditions/evidence, uncertainties, and
explicit decision dependencies.

Repository, control-plane, and connected-context producers may emit candidates
from already-materialized governed artifacts. Staff considers at most three per
front in stable candidate-id order, validates freshness and portability, then
selects a valid candidate into its own mature Action contract. A missing,
stale, vague, or path-leaking candidate remains evidence only.

`support_artifacts_v2` should eventually register stable producer pointers with
the generic role `ACTION_CANDIDATE_SOURCE`; dynamic candidate contents belong
in the referenced generated artifact, not in the Sheet. No such registration
is assumed or written by this component.

An ACTION budget lane is not itself an Action-contract requirement. In this
iteration only the `EXECUTE` facet receives Action maturity; `DECIDE`, `VERIFY`,
`UNBLOCK`, and `MAINTAIN` retain their typed evidence/blocker semantics unless
an explicit future contract extends them.

## Staff packet contract

A packet carries:

```text
staff_packet_id
work_item_id
front_id
kind
preparation_status
triage
question
current_state
identity
evidence[]
uncertainties[]
blockers[]
recommended_move
principal_needed
principal_question
prepared_at
source_snapshot_digest
packet_digest
```

ACTION packets additionally carry `action_maturity` and, only when evidence supports it, `action_contract`. Valid ready maturity is `READY_FOR_PULL`; other states include `NEEDS_MORE_PREP`, `WAITING_FOR_EVIDENCE`, and `BLOCKED`.

`needs` and `note` remain available inside `current_state` as human context. They do not select adapters or work kinds.

The recommended move is advisory. Staff does not authorize execution, rewrite Carry State, or manufacture principal approval.

## Failure and budget semantics

- Snapshot/work-set digest mismatch is a hard error.
- Invalid work-item identity is a hard preparation error.
- A blocked identity produces a coherent blocked packet but does not run expensive/local adapters.
- Budget exhaustion produces `DEFERRED_BUDGET`, not false completion.
- Unknown runtime health becomes an uncertainty, not an invented failure.
- A human/governance front may be valid without any repository adapter being applicable.

## Downstream contract

M5 Principal Compiler consumes these packets, not raw Sheets and not legacy per-front Markdown briefs.

Principal compilation therefore sees the result of Staff preparation: what is ready, what is blocked, what evidence exists, and what remains uncertain. This is what allows the final Principal surface to be materially smaller than the estate.

## Migration rule

Until the v2 cutover, legacy Staff commands may continue to serve the scheduled production path. New Office v2 semantics must be added to `preparation_v2.py` and its structured packet contract, not back-ported into `needs` parsing or legacy bundle types.
