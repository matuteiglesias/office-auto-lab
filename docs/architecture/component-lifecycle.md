# Component lifecycle and active product boundary

**Status:** canonical
**Audience:** maintainers, contributors, operators, and agents
**Owner:** office-auto-lab maintainers
**Verified against:** M9 compatibility-exit branch after M10 hardening

## Purpose

This page declares the supported in-tree Office product boundary after the v2 migration.

The repository now has two runtime lifecycle classes: **CORE** and **SIDECAR**. Superseded Office v1, Staff v1, Repo Health/GCP, and legacy prepared-block implementations were removed in M9 rather than retained as executable compatibility code. Git history is the archive for those implementations.

## CORE

CORE defines the supported Office control loop and participates in active smoke/acceptance.

Current CORE:

- `src/office_runtime/office/` — Control Tower v2 intake, governed identity, typed work, Principal, execution, reentry, coherent generation, invariants, run records and health projection;
- `src/office_runtime/staff/` — bounded Staff v2 preparation and freshness evaluation;
- `src/office_runtime/ledger.py` and `src/office_runtime/run_logging.py` — runtime evidence primitives;
- `src/office_runtime/scripts/run_generation_v2.py` — canonical coherent-generation entrypoint;
- `src/office_runtime/scripts/compile_runtime_health_v2.py` — Run Record Owner projection entrypoint;
- `systemd/user/` and portable render/install support — orchestration boundary.

CORE rules:

1. one Control Tower snapshot per coherent generation;
2. downstream stages consume artifacts from that generation rather than rereading governance state;
3. local paths are resolved observations, not semantic identity;
4. execution cannot silently acquire governance mutation powers;
5. run evidence and last-known-good publication are part of runtime correctness.

## SIDECAR

SIDECAR components are useful adjacent producers or consumers with explicit interfaces to CORE. They cannot redefine Carry, priority, identity, authorization, or completion semantics.

Current SIDECAR:

- `src/office_runtime/capture/` — append-only capture processing and reviewable reentry candidates;
- `src/office_runtime/evidence/` — bounded Git/filesystem evidence production;
- `src/office_runtime/estate_movement.py` — read-only estate delta production;
- `src/office_runtime/editorial/` — bounded editorial contracts and experiments.

A SIDECAR may have its own tests and commands. It does not automatically become part of the Office semantic DAG.

## Historical implementations

The following are no longer repository product surfaces:

- Office v1 spreadsheet compiler and mutable `latest/` queue/brief contract;
- Staff v1 bundles, `ai_jobs.csv`, and per-front Markdown brief generator;
- closure/reentry v1;
- Repo Health policy/plugin/GCP runtime;
- legacy prepared-block compiler;
- legacy compatibility dependency profiles.

They are not renamed or hidden behind compatibility flags. They are absent from the runtime tree. Historical commits remain available in Git when archaeology is required.

## Active acceptance rule

`make smoke` validates the supported CORE plus declared sidecar contract checks. It must fail if a removed compatibility surface becomes an implicit runtime dependency again.

`make parent-audit` is the broader supported-runtime acceptance gate.

## Dependency rule

The dependency profiles are intentionally small:

```text
office
capture
full = office ∪ capture
```

There is no compatibility dependency profile. Adding a new profile requires an active product or sidecar responsibility, not preservation of historical code.

## Removal rule

For future removals, preserve evidence through Git history and durable architecture notes where materially useful. Do not retain executable museum code merely because an old consumer has not yet migrated; downstream projections should migrate to the current artifact contract.

That rule is why Office Review is upgraded after Office rather than forcing Office to continue producing legacy queues and briefs.
