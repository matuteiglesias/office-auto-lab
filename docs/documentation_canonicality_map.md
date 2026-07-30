# Documentation canonicality map

**Status:** historical planning record; superseded by `docs/README.md`
**Audience:** readers choosing a trustworthy page and maintainers planning PR-OD1+
**Owner:** office-auto-lab maintainers
**Verified against:** `cda8b286cc5db3c840d7f4dad143d62497f18a63`

This map proposes one future canonical owner per reader task. It does not make
the target pages exist early, and it does not self-accept the proposal. Until a
replacement is created and verified, source/tests outrank all prose and the
“current best source” column is the safest available route.

> The PR-OD0 proposal below is preserved for migration history. Its target pages
> now exist; use the [documentation router](README.md) for current canonical
> ownership rather than treating future-tense rows as current status.

| Reader task | Proposed canonical owner | Current best source | Migration action / PR |
|---|---|---|---|
| Understand product, maturity, and first local action | `README.md` | source tree, Makefile, fixture | Create front door; PR-OD1. |
| Navigate documentation and status classes | `docs/README.md` | this map and inventory | Create router; PR-OD1. |
| Prepare a local environment | `docs/getting-started/local-development.md` | `docs/environment.md`, requirements files | Verify dependency split and supersede by link; PR-OD1/OD4. |
| Run first Office compile | `docs/getting-started/first-office-compile.md` | CLI parser, `Makefile`, synthetic fixture | Add non-destructive tutorial; PR-OD1. |
| Understand whole-system ownership and flow | `docs/architecture/system-overview.md` | source packages and `.mmd` diagrams | Reconcile diagrams and add prose; PR-OD2. |
| Resolve artifact writers/readers and state | `docs/architecture/ownership-and-state.md` | producer source and schemas | Build writer/reader matrix; PR-OD2. |
| Understand mutation/security boundaries | `docs/architecture/trust-boundaries.md` | capture tests, Repo Health adapters/tests | Document local/cloud boundaries; PR-OD2. |
| Change Office compile | `docs/components/office-compile.md` | `src/office_runtime/office/`, tests/fixture | Create owner guide; PR-OD3. |
| Change staff bundles/briefs | `docs/components/staff.md` | `src/office_runtime/staff/`, fixture | Create owner guide; PR-OD3. |
| Change capture processing | `docs/components/capture.md` | capture source, schemas, tests; supporting design page | Reconcile “proposed” drift, retain design decisions; PR-OD3. |
| Change evidence tracing | `docs/components/evidence.md` | evidence source and Makefile | Create owner guide; PR-OD3. |
| Change Repo Health | `docs/components/repo-health.md` | repo-health source/spec/tests and retrofit | Create owner guide without copying runbooks; PR-OD3. |
| Run routine local operations | `docs/operations/local-routines.md` | Makefile/CLI | Verify commands and outcomes; PR-OD4. |
| Install/operate systemd timers | `docs/operations/systemd-automation.md` | `docs/systemd_timers.md`, unit files | Replace hard-coded setup with parameterized procedure; PR-OD4. |
| Run/recover local Repo Health | `docs/operations/repo-health-local.md` | CLI/runner/tests | Create bounded runbook; PR-OD4. |
| Recover from common failures | `docs/operations/failure-recovery.md` | tests and scattered prose | Consolidate stop/recovery rules; PR-OD4. |
| Look up CLI/Make syntax | `docs/reference/cli.md` | `src/office_runtime/cli.py`, `Makefile` | Generate/verify exact matrix manually; PR-OD4. |
| Look up environment/configuration | `docs/reference/configuration.md` | config/CLI/cloud source, Terraform variables | Separate secrets, defaults, and profiles; PR-OD4. |
| Look up artifacts/manifests | `docs/reference/artifacts-and-manifests.md` | producers, fixture, bundle schema | Catalog shapes and writers; PR-OD4. |
| Look up versioned contracts | `docs/reference/schemas-and-contracts.md` | four schemas and compiler spec JSON | Link authoritative versioned files; PR-OD4. |
| Look up Repo Health plugins | `docs/reference/repo-health-plugins.md` | plugin source/tests | Catalog local/remote capability and mutation; PR-OD4. |
| Deploy or manually run GCP profile | `docs/operations/repo-health-gcp.md` | retrofit G4/G5 pages, IaC, adapters/tests | Promote only verified material; PR-OD5. |
| Evaluate the GCP engineering case | `docs/case-studies/gcp-project-health-retrofit.md` | retrofit records and closures | Evidence-based narrative; PR-OD5. |
| Find old plans and execution evidence | `docs/historical/README.md` | `notes/`, retrofit directory, closures | Add status map; do not delete unique evidence; PR-OD6. |
| Maintain documentation quality | `docs/documentation-maintenance.md` | seed quality/canonicality rules | Add metadata/link/freshness gate; PR-OD6. |

## Duplicate and stale-content register

| Conflict | Authority now | Required resolution |
|---|---|---|
| Installed GCP retrofit vs bundled copy under `notes/office_auto_lab_gcp_codex_retrofit_bundle_v0_1/` | Installed `docs/retrofit/gcp_project_health/` plus current source | Mark bundle historical; never update both. |
| Old checker/compiler commands in `notes/` vs Makefile/current `src` layout | CLI parser, Makefile, source, tests | Preserve unique decisions, replace operational commands with links after reference pages exist. |
| Capture “proposed” plan vs implemented lifecycle/processing | capture source, schemas, tests | Reclassify design record after component/reference pages exist. |
| Systemd page vs unit files | Unit files for exact behavior; future runbook for installation | Parameterize host paths and link rather than copy unit contents. |
| Direct evidence module CLIs vs primary CLI wrappers | `office_runtime.cli` for users | Document direct entry points as internal/advanced, not parallel golden paths. |
| Repo Health direct runner vs primary CLI/cloud job | Profile-specific canonical runbooks | State which entry point owns local sheet execution and cloud execution. |
| Three requirements files | No documented authority | Document audience for each after verifying imports/tests; do not merge in PR-OD0. |
| Mermaid files vs future architecture pages | Future architecture pages | Embed/link only diagrams reconciled to current source; classify remainder historical. |

## Canonicality rules for the next PR

1. PR-OD1 may create only the root front door, documentation router, status
   legend, reader routes, and first local quickstart named in its prompt.
2. Existing pages remain available until replacements exist and inbound links
   are checked.
3. A command has one canonical operational owner; reference pages may list its
   syntax and other pages must link to the procedure.
4. GCP status remains **deployment-ready, not deployed or operated** unless new
   provider-side evidence is supplied and human-reviewed.
5. The broken Make smoke paths are a product/build defect and remain outside the
   documentation PR sequence unless separately authorized.
