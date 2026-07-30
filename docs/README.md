# office-auto-lab documentation

**Status:** documentation router  
**Audience:** evaluators, operators, contributors, maintainers, and agents  
**Owner:** office-auto-lab maintainers  
**Verified against:** `cda8b286cc5db3c840d7f4dad143d62497f18a63`

This page is the documentation front door. Current documentation is incomplete,
so each route distinguishes reader-facing guidance from supporting or historical
records. Source, schemas, tests, infrastructure, and executed commands outrank
prose when they disagree.

## Status legend

### Evidence maturity

| Status | Meaning |
|---|---|
| Designed | A decision or contract exists. |
| Implemented | Code exists on the inspected commit. |
| Locally validated | Relevant local tests or smoke checks passed. |
| Deployment-ready | Provider adapter, container, infrastructure, and runbook exist. |
| Deployed | Provider resources and one execution are evidenced. |
| Operated | Repeated execution, failure/recovery, and observability evidence exist. |

### Document class

| Class | How to use it |
|---|---|
| Candidate canonical | Best current reader page, pending reconciliation or human acceptance. |
| Supporting | Background or evidence; follow its links rather than assuming its commands are canonical. |
| Historical | A past plan or execution record, not current operational guidance. |
| Generated | Derived output; find its producer before treating it as a contract. |

## Evaluators and new readers

1. Read the repository [README](../README.md) for the system boundary, capability
   matrix, honest maturity status, and a non-network first contact.
2. Read the verified [documentation inventory](documentation_inventory.md) for
   the complete current surface and discovered drift.
3. Read the proposed [canonicality map](documentation_canonicality_map.md) to see
   how architecture, component, operations, and reference pages will be added.

The GCP Repo Health profile is implemented, locally validated, and
deployment-ready. The repository contains no provider-side evidence that it is
deployed or operated.

## Architecture

- [System overview](architecture/system-overview.md) — subsystem purposes,
  separation, profiles, and maturity boundary.
- [Runtime and artifact flow](architecture/runtime-and-artifact-flow.md) — data
  flow, publication order, completion markers, and replay behavior.
- [Ownership and state](architecture/ownership-and-state.md) — authoritative
  writers, readers, update modes, and state invariants.
- [Trust boundaries](architecture/trust-boundaries.md) — credentials, external
  authorities, mutation boundaries, denied operations, and stop conditions.

These pages own the system-level architecture. The component guides below own
component-specific implementation boundaries, while operational commands remain
with the operator/reference phase rather than being duplicated here.

## Components

- [Office compile](components/office-compile.md)
- [Staff](components/staff.md)
- [Capture](components/capture.md)
- [Evidence](components/evidence.md)
- [Repo Health](components/repo-health.md)

Each owner guide defines purpose and non-goals, source ownership, inputs and
outputs, command surface, invariants, dependencies and tests, failure modes, and
extension points. They intentionally link to architecture and the command
inventory instead of duplicating operational procedures.

## Operators

| Task | Canonical page | Safety/status note |
|---|---|---|
| Prepare and validate Python locally | [Local development](getting-started/local-development.md) | Setup downloads are labeled; bounded checks are verified. |
| Run routine local workflows | [Routine local operation](operations/local-routines.md) | Network/model commands are explicitly unexecuted. |
| Install/inspect user timers | [systemd automation](operations/systemd-automation.md) | Units contain `/home/matias/...` and must be adapted to the host. |
| Run Repo Health locally | [Repo Health local](operations/repo-health-local.md) | Distinguishes sheet-backed writes from frozen local persistence. |
| Recover a failed workflow | [Failure and recovery](operations/failure-recovery.md) | Preserve evidence and reconcile completion markers. |
| Understand capture processing before running it | [Capture processing layer](capture_processing_layer.md) | Supporting design; some “proposed” labels and artifact names have drifted from source. |
| Understand the GCP profile | [GCP architecture](architecture/repo-health-gcp.md) | Deployment-ready is not deployed. |
| Deploy and execute manually | [GCP deployment/manual run](operations/repo-health-gcp.md) | Provider commands are unexecuted and require authorized context. |
| Control cost or tear down | [GCP cost and teardown](operations/repo-health-gcp-cost-and-teardown.md) | Destruction requires explicit evidence export and approval. |

The GCP runbook is canonical but unexecuted; it does not establish provider
state. Do not use legacy commands under `notes/` as golden paths.

## Reference

- [CLI and Make](reference/cli.md)
- [Configuration](reference/configuration.md)
- [Artifacts and manifests](reference/artifacts-and-manifests.md)
- [Schemas and contracts](reference/schemas-and-contracts.md)
- [Repo Health plugins](reference/repo-health-plugins.md)
- [Repo Health GCP security/IAM](reference/repo-health-gcp-security.md)
- [Repo Health GCP data model](reference/repo-health-gcp-data-model.md)

Reference pages own exact lookup facts; runbooks own safe sequencing, expected
results, denial checks, recovery, and stop rules.

## Case studies

- [Bounded GCP Repo Health retrofit](case-studies/gcp-project-health-retrofit.md)
  — before/after architecture, decisions, rejected alternatives, evidence, and
  the exact designed-through-operated claim boundary.

## Contributors

Use these source-truth routes alongside the component owner guides:

| Component | Owning source | Contracts and executable evidence |
|---|---|---|
| Office compile | [`src/office_runtime/office/`](../src/office_runtime/office/) | Synthetic [artifact fixture](../fixtures/artifacts_sample/latest/README.md); no focused Office test module currently exists. |
| Staff | [`src/office_runtime/staff/`](../src/office_runtime/staff/) | Synthetic bundles and briefs under [`fixtures/artifacts_sample/latest/`](../fixtures/artifacts_sample/latest/). |
| Capture | [`src/office_runtime/capture/`](../src/office_runtime/capture/) | [Capture schemas](../src/office_runtime/capture/schemas/) and the three `test_capture_*` modules under [`tests/`](../tests/). |
| Evidence | [`src/office_runtime/evidence/`](../src/office_runtime/evidence/) | Primary CLI wiring in [`src/office_runtime/cli.py`](../src/office_runtime/cli.py). |
| Repo Health | [`src/office_runtime/ops/repo_health/`](../src/office_runtime/ops/repo_health/) | [Run-bundle schema](../src/office_runtime/ops/repo_health/spec/run_bundle.schema.json), compiler [v0 spec](../src/office_runtime/ops/repo_health/compiler/spec/v0/), and `test_repo_health_*` modules. |
| GCP infrastructure | [`infra/gcp/`](../infra/gcp/) | Terraform, SQL, preflight script, cloud adapter tests, and the [retrofit record](retrofit/gcp_project_health/). |
| User automation | [`systemd/user/`](../systemd/user/) | Six unit files plus the current [timer page](systemd_timers.md). |

Before changing a command, flag, variable, schema, artifact path, plugin,
systemd unit, GCP resource, or maturity claim, consult the
[canonicality map](documentation_canonicality_map.md) and identify the future
canonical page affected.

## Agents

1. Inspect repository-level instructions first. At this commit there is no root
   `AGENTS.md`; do not apply the seed bundle's scoped instructions to unrelated
   product files.
2. Resolve the reader task through this page and the
   [canonicality map](documentation_canonicality_map.md).
3. Verify behavior against the CLI parser, source, schemas, tests, infrastructure,
   or runtime evidence; do not infer truth from directory names or old plans.
4. Treat [`notes/`](../notes/) as working/historical material and
   [`context/closures/`](../context/closures/) as supporting execution evidence.
5. For documentation-program work only, read the scoped
   [seed agent contract](../notes/office-auto-lab-documentation-seed-v0_1/AGENTS.md),
   its [start page](../notes/office-auto-lab-documentation-seed-v0_1/docs/documentation_program/CODEX_START_HERE.md),
   and current carry proposal before executing a PR.

## Current documentation program

- PR-OD0 produced the [inventory](documentation_inventory.md) and
  [canonicality map](documentation_canonicality_map.md).
- PR-OD1 adds only the repository front door, this router, and bounded program
  closure/carry records.
- PR-OD2 adds the four canonical system architecture pages linked above.
- PR-OD3 adds the five canonical component owner guides linked above.
- PR-OD4 consolidates canonical local operations and reference pages.
- PR-OD5 distills canonical GCP architecture, operations, security, data, cost,
  and case-study documentation from the retrofit record.
- Automated documentation checks remain planned for PR-OD6; they
  are not silently supplied by retrofit or note files.

Historical retrofit prompts and closure notes remain available for evidence but
are intentionally absent from primary reader navigation.
