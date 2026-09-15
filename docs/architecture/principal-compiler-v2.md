# Principal Compiler v2

**Status:** canonical
**Audience:** maintainers, operators, agents, and Office Window consumers
**Owner:** `src/office_runtime/office/principal.py`
**Verified against:** M5 fixture acceptance and Staff Preparation v2 packet contract

## Purpose

The Principal Compiler compresses prepared Staff work into the smallest useful human-attention surface. It does not reread Control Tower, resolve identity, compile work, or perform evidence gathering.

The canonical flow is:

```text
control snapshot
  ↓
typed work
  ↓
Staff preparation
  ↓
Principal Compiler
  ↓
needs_you / ready_pulls / exceptions / delta
```

The compiler therefore sees the result of preparation rather than exposing raw estate ambiguity to the principal.

## Sections

### Needs you

Contains only successfully prepared packets whose structured contract still requires principal judgment. A blocked or budget-deferred decision does not become raw principal work; it remains an Office exception until Staff can make it decision-ready.

Each decision entry carries a bounded question, recommended default, why-now context, compressed evidence references, and acceptable response shapes.

### Ready pulls

Contains successfully prepared non-principal work that can move into bounded execution. The section is an attention shortlist, not an exhaustive queue.

### Exceptions

Contains preparation failures, explicit blockers, budget deferrals, or degraded evidence. Exceptions remain visible but do not manufacture principal attention merely because preparation failed.

### Moved without you

Contains prepared non-principal items that advanced through Staff but were not selected into the small ready-pull window.

### Delta

Compares stable entry IDs and digests with the previous Principal brief. It reports additions, clearances, and materially changed entries for `needs_you`, `ready_pulls`, and `exceptions`.

## Attention budgets

`max_needs_you` and `max_ready_pulls` bound the default human surface. Overflow principal decisions are retained explicitly under `deferred_attention`; ready-pull overflow remains visible under `moved_without_you`.

The budgets are presentation/WIP controls. They do not change Control Tower priority or Staff preparation truth.

## Nothing-required semantics

`nothing_required: true` is a successful Office result. It means no prepared item currently requires principal judgment. Ready pulls and exceptions may still exist without creating a principal action request.

This prevents the Office from inventing human work merely to produce a non-empty brief.

## Evidence compression

Principal entries carry compact evidence references rather than full Staff evidence payloads. Repository evidence exposes `repo_id`, `workspace_id`, revision, and dirty state; machine-local paths are never copied into the Principal surface.

The Staff packet remains the inspectable evidence-rich artifact when deeper review is needed.

## Authority boundary

The Principal Compiler does not approve, execute, send, publish, mutate Carry State, or change priority. It produces a decision/readiness surface. Subsequent execution compilation must consume an explicit approved or pulled item rather than inferring approval from the existence of a Principal entry.

## Rendering

`render_principal_markdown()` is a projection over the structured brief. The structured `ops.principal-brief.v2` artifact is canonical; Markdown and Office Window views are renderers.

## Downstream implication

M6 can now compile ready pulls into bounded execution packets while preserving operator contracts and authorization seams. M8 Office Window can later render the same Principal artifact without reconstructing Office semantics in the UI.
