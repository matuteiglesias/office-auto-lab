# Closure → Office reentry

**Status:** canonical
**Audience:** operators, Office maintainers, and agents
**Owner:** office-auto-lab maintainers
**Verified against:** local fixture suite and acceptance projection

## Purpose

This is the small read-only bridge from bounded execution closure back into
Office review:

```text
Ops execution → artifact:ops.closure@1 → Office intake → exact front reconciliation
→ reentry proposal → review surface → next-session restart seed
```

It preserves the division of authority. Ops owns what happened, evidence,
closure, next touch, escalation observations and recommendations. Office owns
front reconciliation, compilation and any later human-approved Carry State
change. This bridge owns neither execution truth nor approval.

## Operator route

Use an explicit JSON or JSONL packet/file directory and a read-only Front
Registry CSV snapshot. Directory inputs are intentionally non-recursive.

```bash
PYTHONPATH=src python3 -m office_runtime.cli office reentry compile \
  --closures /explicit/ops-closures \
  --front-registry artifacts/latest/merged_state.csv \
  --out artifacts/closure-reentry/review
```

Equivalent Make route:

```bash
make office-reentry CLOSURES=/explicit/ops-closures \
  FRONT_REGISTRY=artifacts/latest/merged_state.csv \
  REENTRY_OUT=artifacts/closure-reentry/review
```

JSON is the supported v1 interchange because `ops-wiki` currently documents
the semantic contract but carries no checked-in machine-readable YAML schema or
parser dependency. This does not redefine the upstream contract.

Normal `office compile` may receive an optional `OFFICE_CLOSURE_SOURCE`. When
unset it reports `closure_reentry: unconfigured` and its historical behavior is
unchanged. When set, malformed input fails visibly; valid proposals appear in
the Office Summary's **Recent closures / reentry** section.

## Input and validation

The consumer accepts the documented `artifact:ops.closure@1` semantics:

- non-empty `front_id`;
- `status`: `done`, `partial`, `blocked`, or `no-change`;
- non-empty Ops `evidence`;
- closure text/object;
- concrete `next_touch` for `partial` and `blocked`;
- allowed carry recommendation;
- optional horizon, follow-up spawns, repo evidence and notes;
- escalation preserved exactly as supplied.

`done` may legitimately have `next_touch: null`; Office will not invent work.
Absent optional values are represented as `not supplied`, never as negative
facts. A closure's upstream id is retained when present; otherwise Office uses a
canonical-content SHA-256 identity. Exact replay is idempotent. Different
closures for the same front remain separate.

## Reconciliation and review

Office reconciles only an exact canonical `front_id` match, using the Front
Registry's existing `project_id` compatibility alias. It never fuzzy-matches
names, repos, or closure prose. An unknown front stays in the review output as
`UNRESOLVED_FRONT`; its closure is preserved but no actionable carry/horizon
proposal or restart seed is emitted.

For reconciled `partial` and `blocked` closures the review projection includes a
compact restart seed: previous closure, what became true, Ops evidence, exact
next touch, and clearly labelled carry/horizon/escalation proposals. The seed
is enough to resume a bounded session without reconstructing it, but it is not a
new plan.

## Outputs and safety

The output directory contains:

- `normalized_closures.jsonl` — producer-local normalized records;
- `reentry_proposals.jsonl` — `artifact:ops.office-reentry-proposal@1` review
  projections;
- `reentry_review.md` — human review surface;
- `manifest.json` — source hashes, reconciliation and output hashes;
- `qa.json` — counts and explicit `mutation_performed: false`.

Durable manifests retain safe file references and hashes, never absolute local
input paths. The bridge makes zero Carry, horizon, priority, escalation, or
follow-up mutations. A future automation may consume proposals only through an
existing explicit Office approval/mutation route; none is enabled here.

## Acceptance evidence

The implementation is covered by partial, blocked, done, unknown-front,
duplicate-replay, same-front-distinct-closure, malformed-input and absent-
optional-field fixtures. Local real-front acceptance output is intentionally
ignored under `artifacts/` because it contains private operational evidence.
