# Repo Health owner guide

**Status:** canonical
**Audience:** contributors and agents changing Repo Health semantics or adapters
**Owner:** `src/office_runtime/ops/repo_health/`
**Verified against:** `cda8b286cc5db3c840d7f4dad143d62497f18a63`

## Purpose and non-goals

Repo Health schedules policy intents, runs capability-declared plugins,
normalizes repository observations, builds frontier issues and prepared blocks,
and publishes a versioned producer-owned run bundle. It owns domain meaning;
local files and GCP infrastructure only transport or persist it. It does not own
Office compile, source-repository mutation in the cloud profile, or automatic
application of prepared blocks.

## Source paths

| Path | Responsibility |
|---|---|
| `policy.py`, `runner.py`, `sheets.py` | Sheet-backed policy planning/execution and optional writes |
| `plugins/`, `plugin_loader.py` | Plugin contract, capabilities, discovery, cloud selection |
| `remote/` | Allowlisted read-only repository-source abstraction/GitHub adapter |
| `compiler/` | Frontier parsing, IR rollup, candidate and prepared-block generation |
| `run_bundle/`, `spec/run_bundle.schema.json` | Versioned bundle model, validation, local sinks |
| `cloud/run_job.py` | Frozen-snapshot validation, profile orchestration and provenance |
| `adapters/gcp/` | Immutable GCS evidence and idempotent BigQuery history |
| `infra/gcp/`, `Dockerfile.repo-health` | Deployment-ready transport/runtime definition |

## Inputs and outputs

The sheet-backed runner reads project, capability, policy, and prerequisite tabs;
it may write an effective run set, append results, export frontier CSV, and apply
summary fields according to flags. The frozen-snapshot runner accepts the same
policy concepts as JSON, a repository allowlist, and producer provenance. Its
canonical output is `repo_health.run_bundle.v1`, containing run/source/policy,
intents, results, frontier, prepared blocks, exceptions, and counters.

Local sinks publish a run-id packet plus JSONL history. GCP sinks publish a
create-only GCS packet and stable-row BigQuery history. Prepared blocks conform
to the compiler v0 schema; they remain proposals rather than Office mutations.

## Canonical command surface

The sheet-backed entry point is
`python -m office_runtime.ops.repo_health.runner`; the primary CLI wrappers and
Make aliases cannot currently deliver their required arguments. Frozen-snapshot
execution uses `python -m office_runtime.ops.repo_health.cloud.run_job --profile
local|gcp`. Use the [local runbook](../operations/repo-health-local.md); GCP
procedures remain PR-OD5 scope.

## Invariants

- Policy scheduling is explicit: disabled, not-due, or prerequisite-failing
  intents do not execute and remain auditable.
- Plugin output normalizes to a bounded classification while retaining evidence
  and metadata in the run bundle.
- A plugin declares `local_only`, `remote_read`, or `remote_execute` capability;
  GCP selection requires both explicit name allowlisting and `remote_read`.
- Cloud policy rejects local paths, unsupported plugins, unallowlisted identity,
  and more than three projects before execution.
- Run bundle links/counters validate and a run id owns one canonical byte payload.
- Exact replay is idempotent; identity/content conflict fails closed.
- Detail history is persisted before its run completion marker.
- GCP uses assigned identity and rejects service-account key-file configuration.

## Dependencies and tests

Local sheet execution depends on Google Sheets access and may depend on Git,
Make, repository files, and project environments according to selected plugins.
Frozen remote execution depends on GitHub reads; GCP persistence depends on ADC,
Storage, and BigQuery. The four `test_repo_health_*` modules cover policy/plugin
semantics, remote boundaries, bundle validation/replay, cloud persistence,
container, and Terraform constraints. At the inspected environment, one GCP
adapter test cannot import `google.cloud.bigquery`; record that limitation rather
than treating the complete suite as passing.

## Failure modes

Missing sheets, credentials, paths, prerequisites, or plugins can make an intent
ineligible or fail execution depending on the boundary. Malformed plugin output
normalizes to system error. Remote rate limits and oversized trees are classified
bounded failures, not permission to broaden reads. Invalid bundle links/counters,
provenance mismatch, missing assigned configuration, immutable-object conflict,
or stable-row digest conflict fail closed. `--no-write` is the mutation denial
for the sheet-backed runner; `--policy-only` plans without executing intents.

## Extension points

Add a plugin by subclassing `BasePlugin`, choosing a capability, returning the
documented result vocabulary, and adding discovery/normalization tests. Remote
support also requires source-abstraction compatibility and explicit cloud
allowlisting. Compiler vocabulary belongs in versioned spec JSON. Bundle field
changes require a schema/version decision and compatibility tests. Storage
adapters implement evidence/history ports and must preserve canonical bytes,
stable identities, ordering, and conflict rejection.
