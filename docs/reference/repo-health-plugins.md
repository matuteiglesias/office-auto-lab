# Repo Health plugin reference

**Status:** canonical
**Audience:** Repo Health operators and plugin contributors
**Owner:** `src/office_runtime/ops/repo_health/plugins/`
**Verified against:** `8b4c9b7`

Dynamic discovery was executed in PR-OD4 and found seven plugins.

| Name | Class | Capability | Boundary |
|---|---|---|---|
| `activity_remote` | `RemoteActivityPlugin` | `remote_read` | Bounded GitHub commit facts; GCP allowlisted |
| `commit_recent` | `CommitRecentPlugin` | `local_only` | Local Git activity/worktree facts |
| `env` | `EnvPlugin` | `local_only` | Python/packages, selected environment, optional local/network checks |
| `pipeline_output` | `PipelineOutputPlugin` | `local_only` | Local repository artifact/output inspection |
| `runbook` | `RunbookPlugin` | `local_only` | Local runbook discovery/content signals |
| `runbook_remote` | `RemoteRunbookPlugin` | `remote_read` | Bounded GitHub tree/content signals; GCP allowlisted |
| `smoke` | `SmokeRunPlugin` | `remote_execute` | Executes local repository smoke; never GCP-selected |

## Result contract

A plugin returns uppercase status `PASS`, `FAIL`, `WARN`, `NA`, or `ERROR` and a
short message. Bucket, compact evidence pointers, and structured metadata are
optional. Runners normalize unknown/malformed results to `system_error` rather
than trusting arbitrary vocabulary.

## Selection and extension

Local policy selects discovered plugins subject to prerequisites. GCP selection
requires both the explicit name allowlist (`activity_remote`, `runbook_remote`)
and capability `remote_read`; unknown capabilities fail closed. To extend, add a
`*_plugin.py` subclass of `BasePlugin`, unique name/version/capability, bounded
result vocabulary, and discovery/normalization tests. Remote support additionally
requires the repository-source abstraction and explicit cloud allowlist review.

Do not mark filesystem/subprocess behavior `remote_read`, expose credentials in
evidence/meta, or broaden remote access after a rate-limit/tree-size denial.
