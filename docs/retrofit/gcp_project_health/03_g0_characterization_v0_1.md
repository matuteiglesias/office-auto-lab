# PR-G0 Repo Health Characterization v0.1

**Status:** Accepted 2026-07-29
**Characterized against:** current repository behavior before any G1 semantic corrections

## Product-contract boundary

The current product spine is policy rows → effective intents → plugin results → normalized frontier → prepared work blocks. PR-G0 does not change that spine. It records which behavior is domain meaning and which behavior is an accident of the local runner so that PR-G1 can make only the accepted corrections.

## Characterization results

| Surface | Current behavior proven in G0 | G1 decision/proposed correction |
|---|---|---|
| Due and scheduled intent | A project with valid prerequisites is scheduled even when `next` is in the future or absent. `due` is calculated but does not gate `scheduled`. | Apply the frozen sprint rule: `scheduled = enabled AND due AND prereq_ok`; define missing `next` as not due and auditable. |
| `--no-write` | It suppresses the EffectiveRunSet overwrite and runtime-health header update, but execution still appends PluginResults and exports `out/frontier/latest.csv` plus a dated CSV. | Gate every Sheet and filesystem mutation behind the no-write contract. Keep planning/execution results in memory unless an explicit temporary output is supplied. |
| Plugin discovery | The loader scans every `*_plugin` module in the local plugins folder and registers every `BasePlugin` subclass. Current inventory is `commit_recent`, `env`, `pipeline_output`, `runbook`, and `smoke`. | Add explicit execution capability metadata and a fail-closed GCP allowlist; preserve local discovery compatibility. |
| Result normalization | Plugins can return `evidence` and `meta`, but `execute_intent` drops both. The compact frontier schema also intentionally excludes both fields. | Preserve raw evidence/meta in producer-owned results while retaining the compact frontier contract. |
| Compiler | A fixed frontier fixture produces byte-equivalent canonical prepared-block JSON across repeated in-process compilations. | Preserve this deterministic behavior. |
| Credentials | The CLI requires `--sa`; Sheets authentication calls `Credentials.from_service_account_file`. | Preserve local file authentication for compatibility; cloud entrypoints later use ADC. |

## Current plugin portability and trust table

These labels describe existing behavior only. Formal capability metadata belongs to PR-G1.

| Plugin | Current inputs/operations | Local assumption | Proposed G1 capability | GCP v0.1 eligibility |
|---|---|---|---|---|
| `commit_recent` | `repo_path`/`workdir`; invokes local `git`; reads worktree and hygiene state | Filesystem, Git executable, checkout | `local_only` for the existing implementation | No; G2 supplies a remote-read activity implementation |
| `runbook` | Walks local repository paths and reads candidate documentation | Filesystem checkout and bounded local traversal | `local_only` for the existing implementation | No; G2 supplies a remote-read runbook implementation |
| `smoke` | Runs a Make target in the repository | Filesystem, Make, and repository-controlled execution | `remote_execute` | Rejected |
| `pipeline_output` | Searches generated artifacts and modification times | Machine-local generated files | `local_only` | Rejected |
| `env` | Inspects the runner environment and optional local Git facts | Local Python/runtime and possibly checkout | `local_only` | Rejected as project health; later runner self-check only |

No current plugin is honestly `remote_read`. PR-G1 should therefore make the GCP-profile selection empty and fail closed until G2 adds the two API-native implementations.

## Product direction accepted after G0

The center is a running office that can inspect projects and own carry state across projects. Compatibility is not an end in itself: later PRs may explicitly prune a feature when keeping it would weaken that center. Pruning must remain deliberate, recorded in carry state, and bounded to the active PR rather than happening as incidental cleanup.

## Exact bounded work proposed for PR-G1

1. Make scheduling depend on enabled, due, and satisfied prerequisites; explicitly cover future, today/past, missing, disabled, and missing-prerequisite cases.
2. Make `--no-write` suppress EffectiveRunSet, PluginResults, frontier files, and runtime-health writeback. Decide separately whether log creation is allowed operational output or must use an explicit destination.
3. Retain `evidence` and `meta` on normalized result records without expanding the compact frontier schema.
4. Declare `local_only`, `remote_read`, and `remote_execute` capability values, reject unknown values, and select only explicitly allowlisted `remote_read` plugins for the GCP profile.
5. Preserve the five-plugin local inventory and deterministic compiler output.
6. Preserve service-account-file authentication only for the existing local CLI; do not introduce provider dependencies in G1.

## Disproved or refined hypotheses

- **Refined:** no-write does guard two write paths, but it does not guard PluginResults append or frontier file export; it is therefore not a non-mutation mode.
- **Confirmed:** useful plugin evidence/meta is lost at runner normalization before frontier export.
- **Confirmed:** all existing project inspection plugins rely on local runtime or local repository state; none can be relabeled as cloud-safe without changing implementation.
