# Coherent Office v2 Generation

**Status:** canonical
**Audience:** maintainers, scheduler/runtime engineers, Staff/Principal consumers
**Owner:** `src/office_runtime/office/generation_v2.py`

## Purpose

M8 makes the already-established Office v2 contracts run as one coherent forward generation.

```text
Control Tower v2
  ↓ read once
control snapshot
  ↓
typed work
  ↓
Staff preparation
  ↓
Principal brief
  ↓
execution plan
  ↓
validated run generation
  ↓
last-known-good current pointer
```

The scheduler is only a clock. It must invoke one coherent generation rather than reproduce the internal DAG with independently timed Staff or Principal jobs.

## One worldview per generation

A generation reads the Control Tower once. Every downstream artifact must carry the same source snapshot digest.

The generation fails rather than publishing if the lineage across work, Staff, Principal, or execution diverges.

No downstream stage rereads the Control Tower during the generation.

## Run-scoped tree

A successful generation produces:

```text
artifacts/v2/runs/<run-id>/
  control/
    snapshot.json
  routing/
    work_items.json
  staff/
    preparation.json
    packets/*.json
  principal/
    brief.json
    brief.md
  execution/
    plan.json
    packets/*.json
  manifest.json
```

Staff and execution packet directories belong exclusively to that run. A later generation cannot inherit stale packet files from an older generation.

## Staging and publication

Compilation occurs under:

```text
artifacts/v2/.staging/<run-id>/
```

Only after the complete forward generation succeeds is the staging tree promoted to:

```text
artifacts/v2/runs/<run-id>/
```

For normal publication, `artifacts/v2/current.json` is then replaced with a pointer to the successful run.

If any stage raises before promotion:

- the staging directory is removed;
- no run is published;
- the previous `current.json` remains untouched.

The current pointer is therefore a last-known-good pointer rather than a record of the most recent attempt.

## Shadow mode

`make office-v2-shadow` compiles the same complete forward generation with publication disabled.

A shadow generation:

- reads the live v2 Control Tower using the canonical v2 table contracts;
- produces the complete run-scoped artifact tree;
- does not replace `artifacts/v2/current.json`;
- does not mutate the legacy `artifacts/latest` surface;
- does not execute ready pulls;
- does not mutate Control Tower.

This is the safe path for live comparison before scheduler cutover.

## Normal manual publication

`make office-v2-generate` performs the same coherent compile and, on success, advances the v2 current pointer.

Merging this capability does not enable a timer and does not alter the currently installed systemd state. Scheduler cutover is an explicit migration operation.

## Previous-brief delta

When a published v2 current generation already exists, the new Principal compiler uses that generation's Principal brief as the delta baseline.

A broken current pointer or unsupported current Principal schema fails visibly rather than silently resetting the baseline.

## Local repository evidence

The default generation does not probe local repositories.

Local Git evidence can be enabled explicitly with `--local-repo-evidence` / `OFFICE_V2_LOCAL_REPO_EVIDENCE`. Even then, local paths are resolved only through the governed M2 identity chain and are not exported in portable Staff or Principal artifacts.

## Concurrency

Generation identity is run-id based and duplicate run ids fail closed. Scheduler-level single-instance locking remains an orchestration concern and is intentionally separate from this semantic generation contract.

The systemd migration should ensure that two coherent generation invocations cannot run concurrently against the publication pointer.

## Non-goals

Coherent generation does not:

- execute execution packets;
- infer Principal approval;
- apply reentry proposals;
- write Control Tower state;
- replace the scheduler merely by being merged;
- remove legacy Office compatibility surfaces.

Those boundaries keep M8 publication independent from M9 compatibility exit and later reviewed governance mutation.
