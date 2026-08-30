# Repo Health plugin reference

**Status:** canonical
**Audience:** Repo Health operators and plugin contributors
**Owner:** `src/office_runtime/ops/repo_health/plugins/`
**Verified:** 2026-08-30 against the capability-descriptor contract

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
class implied by the plugin capability, failure behavior, and where evidence is
reported.

Discovery validates this descriptor before registering the plugin. Incomplete
metadata therefore fails closed rather than silently becoming executable. The
contract is intentionally local to Repo Health: it does not create a universal
workflow, tool, or orchestration schema, and plugins only override the common
contracts when their real boundary differs.

## Result contract

A plugin returns uppercase status `PASS`, `FAIL`, `WARN`, `NA`, or `ERROR` and a
short message. Bucket, compact evidence pointers, and structured metadata are
optional. Runners normalize unknown/malformed results to `system_error` rather
than trusting arbitrary vocabulary.

## Selection and extension

Local policy selects discovered plugins subject to prerequisites. GCP selection
requires both the explicit name allowlist (`activity_remote`, `runbook_remote`)
and capability `remote_read`; unknown capabilities fail closed. To extend, add a
`*_plugin.py` subclass of `BasePlugin`, unique name/version/capability, a complete
capability descriptor, bounded result vocabulary, and discovery/normalization
tests. Remote support additionally requires the repository-source abstraction
and explicit cloud allowlist review.

Do not mark filesystem/subprocess behavior `remote_read`, expose credentials in
evidence/meta, or broaden remote access after a rate-limit/tree-size denial.
