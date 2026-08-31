# Repo Health plugin reference

**Status:** canonical
**Audience:** Repo Health operators and plugin contributors
**Owner:** `src/office_runtime/ops/repo_health/plugins/`
**Verified against:** 2026-08-30 capability-descriptor contract

Dynamic discovery exposes seven plugins.

| Name | Class | Capability | Boundary |
|---|---|---|---|
| `activity_remote` | `RemoteActivityPlugin` | `remote_read` | Bounded GitHub commit facts; GCP allowlisted |
| `commit_recent` | `CommitRecentPlugin` | `local_only` | Local Git activity/worktree facts |
| `env` | `EnvPlugin` | `local_only` | Python/packages, selected environment, optional local/network checks |
| `pipeline_output` | `PipelineOutputPlugin` | `local_only` | Local repository artifact/output inspection |
| `runbook` | `RunbookPlugin` | `local_only` | Local runbook discovery/content signals |
| `runbook_remote` | `RemoteRunbookPlugin` | `remote_read` | Bounded GitHub tree/content signals; GCP allowlisted |
| `smoke` | `SmokeRunPlugin` | `remote_execute` | Executes local repository smoke; never GCP-selected |

## Capability descriptor

Every discovered plugin exposes a compact repo-local execution descriptor through
`BasePlugin.capability_descriptor()`. The descriptor identifies the capability
(`repo_health.<name>@<version>`), input and output contracts, the side-effect
boundary, failure behavior, and evidence fields.

The descriptor is deliberately **not** a universal workflow/plugin schema. It
makes Repo Health discovery and execution boundaries inspectable without making
this repository a generic agent framework.

Discovery validates the descriptor before the plugin becomes executable. A
missing or malformed descriptor fails discovery rather than silently widening a
plugin's capability surface.

## Capability classes

- `local_only`: local repository observation/execution only; no remote mutation
  authority.
- `remote_read`: bounded remote read-only access; no remote mutation authority.
- `remote_execute`: bounded execution permitted only where the owning runner's
  explicit policy and dry-run/apply controls authorize it.

The capability class is not itself authorization. The runner policy, target
allowlist, dry-run mode, prerequisites, and stop conditions remain authoritative.

## GCP profile boundary

The GCP remote profile allowlists only `activity_remote` and `runbook_remote`.
Local executable plugins such as `smoke` are never selected by the cloud adapter.
The cloud runtime validates the frozen policy snapshot, repository allowlist,
plugin set, and image/source identity before execution.

## Evidence

Each plugin result must normalize into Repo Health's result contract and retain
structured evidence/meta fields. Malformed results are system errors. Run-level
identity, policy hash, results, exceptions, and prepared blocks are then bound by
`repo_health.run_bundle.v1`; plugin descriptors do not replace that evidence
contract.
