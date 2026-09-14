# Component lifecycle and active product boundary

**Status:** canonical
**Audience:** maintainers, contributors, operators, and agents
**Owner:** office-auto-lab maintainers
**Verified against:** `f5f03c2a6d16853b2e8dbb01b0736c8e941122fe` plus M0 migration branch

## Purpose

This page declares which in-tree capabilities belong to the supported Office runtime, which are adjacent sidecars, and which remain only for compatibility during the Office v2 migration.

The classification is operational. It controls active acceptance, dependency profiles, documentation language, and whether new product work may depend on a component.

## Lifecycle classes

### CORE

CORE components define the supported Office control loop. They may participate in the active smoke/acceptance path and may be extended as part of Office v2.

Current CORE:

- `src/office_runtime/office/` — control-state compilation, validation, routing, manifests, closure/reentry proposals;
- `src/office_runtime/staff/` — preparation bundles and deterministic brief rendering;
- `src/office_runtime/ledger.py` and run/logging primitives used by supported runtime flows;
- `src/office_runtime/scripts/office_run.sh` plus portable systemd render/install support;
- repository/surface context adapters consumed by Office as advisory evidence.

### SIDECAR

SIDECAR components are useful adjacent producers or consumers with explicit interfaces to CORE. They are not allowed to redefine Office carry, priority, identity, or completion semantics.

Current SIDECAR:

- `src/office_runtime/capture/` — append-only capture processing and reviewable reentry candidates;
- `src/office_runtime/evidence/` — bounded Git/filesystem evidence production;
- estate-movement/delta producers;
- `src/office_runtime/editorial/` — bounded editorial contracts and experiments.

A SIDECAR may have its own tests and operational command surface. It does not automatically become part of the CORE smoke path.

### COMPAT

COMPAT components are retained because consumers may still exist. They are frozen against new product semantics except for bounded compatibility repairs and migration support.

Current COMPAT:

- `src/office_runtime/ops/repo_health/`;
- `requirements/profiles/repo-health.txt`;
- `requirements/profiles/legacy-auto-checker.txt`;
- `src/office_runtime/scripts/legacy/` and the legacy prepared-block compiler;
- Repo Health GCP/container/IaC surfaces whose semantic authority has moved to `projects`.

New Office functionality must not depend on COMPAT components. Compatibility entry points must be visibly prefixed or documented as compatibility-only.

### HISTORICAL

Historical plans, closures, audits, migration bundles, and superseded design records are retained only when they provide unique evidence. They do not define current runtime behavior.

## Active acceptance rule

`make smoke` is the supported CORE smoke check. It must not invoke COMPAT implementations or legacy compilers.

Compatibility code may retain dedicated tests and CI slices until its consumers are audited and migrated. A compatibility test passing proves that the retained compatibility contract still works; it does not promote the component back into CORE.

## Dependency rule

The `full` dependency profile means the supported local runtime, not every implementation that happens to remain in the repository. It is the union of the active Office and Capture profiles.

Compatibility consumers install their explicit profile (`repo-health` or `legacy-auto-checker`) rather than relying on `full` to bring compatibility dependencies transitively.

## Exit rule

A COMPAT component is removed only after:

1. known callers and readers are inventoried;
2. replacement authority and interface are identified;
3. consumers are migrated or explicitly retired;
4. the component is absent from active acceptance and active dependency profiles;
5. unique evidence is preserved in documentation/history where needed.

Deletion is the last step, not the first.

## Office v2 migration implication

The migration sequence builds the new control-state → identity → work-item → staff-preparation → principal-brief spine only on CORE contracts. SIDECAR producers can attach through explicit evidence/proposal interfaces. COMPAT code must not constrain the new model.
