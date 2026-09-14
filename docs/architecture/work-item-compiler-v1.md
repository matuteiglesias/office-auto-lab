# Office v2 typed work-item compiler

**Status:** canonical
**Audience:** maintainers, contributors, operators, and agents
**Owner:** `src/office_runtime/office/work_items.py`
**Verified against:** M3 fixture acceptance and Control Tower v2 operating fields observed 2026-09-14

## Purpose

The work-item compiler turns governed Control Tower state into a small typed vocabulary that downstream Staff and Principal stages can reason about deterministically.

It replaces the historical pattern where routing semantics were inferred from prose such as the `needs` field. Human prose remains valuable context, but changing wording must not silently change machine behavior.

## Work vocabulary

M3 uses five work kinds:

- `DECIDE` — Principal participation or judgment is structurally required;
- `UNBLOCK` — the front cannot yet be made safely executable/preparable from current governed context;
- `VERIFY` — explicit runtime evidence says the front needs a bounded verification/diagnostic pass;
- `EXECUTE` — the front is expressed for human focus and has no repository-identity blocker;
- `MAINTAIN` — the front is explicitly expressed for bounded human maintenance.

These are work facets, not mutually exclusive front lifecycle states. One front may emit more than one work item in a generation. For example, a front can require Principal participation and also have an executable focus path.

`WATCH` and `PARKED` are portfolio states, not work kinds, and do not create active work items.

## Structured routing inputs

The compiler uses structured fields only:

- `carry_state_v2.carry_status`;
- `carry_state_v2.principal_mode`;
- `front_registry_v2.lifecycle_status` and `enabled`;
- `front_registry_v2.human_focus`;
- `front_registry_v2.human_maint`;
- `front_registry_v2.staff_get` as a preparation requirement/fallback signal;
- `Capabilities_v2.cap_repo`;
- governed identity-resolution outcomes;
- explicit unhealthy `runtime_health_v2.health_status` values.

`carry_state_v2.needs` and `note` are copied into `context` for later human/Staff reasoning. They are never searched for words such as “decision”, “health check”, “unlocker”, or “execution” to determine a work kind.

## Current deterministic rules

For ACTIVE or ACTIVE_LIGHT fronts whose registry lifecycle is ACTIVE and which are not explicitly disabled:

- `principal_mode=REQUIRED` emits `DECIDE`;
- a repo-capable front without safely resolved repository/workspace identity emits `UNBLOCK` and suppresses `EXECUTE`;
- an explicit unhealthy runtime status (`FAIL`, `FAILED`, `ERROR`, `WARN`, `WARNING`, `DEGRADED`, `STALE`) emits `VERIFY`;
- `human_focus=TRUE` emits `EXECUTE` when repo identity is not blocked;
- `human_maint=TRUE` emits `MAINTAIN`;
- when no other work type is produced and `staff_get=TRUE`, emit `UNBLOCK` with `STAFF_PREPARATION_REQUIRED` so Staff can turn ambiguity into a later executable/decision packet.

M4 may refine preparation depth, but it must not revert to prose-driven routing.

## Identity boundary

Work items carry identity summaries:

- `repo_ids`;
- `workspace_id` values and resolution status;
- `path_authority=repo_workspaces_v2`.

They deliberately do not embed `local_path`, `front_registry.repo_path`, or `front_registry.workdir`. Concrete local paths are resolved only by an execution/evidence adapter when needed.

This keeps work contracts portable and prevents a cached path from becoming semantic identity.

## Preparation is orthogonal

`staff_get=TRUE` maps to `prep_mode=STAFF_REQUIRED`. It is not itself a semantic work type because the current Control Tower intentionally enables Staff preparation on a broad share of the estate.

M4 consumes typed work items and decides cheap triage versus bounded deep preparation. The work compiler does not perform repository scans, document retrieval, model calls, or Staff synthesis.

## Work-item shape

Each emitted item contains at least:

```text
work_item_id
front_id
title
kind
trigger_codes
carry_status
horizon
priority_mode
principal_mode
principal_required
prep_mode
watch_enabled
post_eligible
identity
context
identity_error
source_snapshot_digest
```

The top-level work-item set also records skipped fronts and generation counts.

## Non-goals

M3 does not:

- mutate Control Tower;
- schedule or execute work;
- estimate duration;
- deep-prepare evidence;
- decide Principal recommendations;
- parse free text into control flow;
- embed machine-local paths in portable work objects.

The legacy Office queue compiler remains available during migration. M3 establishes the native typed contract that M4/M5/M6 will use before scheduled runtime cutover.
