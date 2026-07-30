# Staff owner guide

**Status:** canonical
**Audience:** contributors and agents changing staff bundles or briefs
**Owner:** `src/office_runtime/staff/`
**Verified against:** `cda8b286cc5db3c840d7f4dad143d62497f18a63`

## Purpose and non-goals

Staff enriches selected Office state into project-scoped JSON bundles and
deterministic Markdown briefs. It may attach existing or refreshed repository
scan evidence. It does not own Office selection/routing rules, run external AI
jobs, or mutate spreadsheets.

## Source paths

| Path | Responsibility |
|---|---|
| `staff/bundles.py` | Sheet enrichment, queue selection, scan modes, bundle and job-index writing |
| `staff/briefs.py` | Bundle/execution rendering and brief-index writing |
| `office/config.py` and `office/io.py` | Shared configuration, read-only sheet reads, file helpers |
| `scripts/repo_contract_scan.sh`, `repo_snapshot_protocol.sh` | Optional local scan producers |
| `cli.py` | `staff bundles`, `staff briefs`, and `daily` composition |

## Inputs and outputs

Bundle input combines front, carry, runtime, and support sheets with
`support_queue.csv` and `principal_brief_today.csv` from the latest Office tree.
Scan mode is `none`, `existing`, or `refresh`; refresh executes local scripts
against the selected repository/workdir. Outputs are `bundles/*.json`, scan
files, and `ai_jobs.csv`. Brief input includes those bundles,
`merged_state.csv`, and preferably `focus_get_queue.csv` (falling back to
`block_candidates.csv`). Outputs are `briefs/*.md` and `brief_index.csv`.

Despite its filename, `ai_jobs.csv` is a deterministic local work index. This
component does not call an AI API.

## Canonical command surface

The primary commands are `staff bundles --scan-mode ...` and `staff briefs`;
Make exposes `staff-bundles` with `existing` scans and `staff-briefs`. `daily`
runs Office, bundles, then briefs only after a successful Office manifest. Full
execution/recovery procedures remain in PR-OD4 scope.

## Invariants

- Sheet access is read-only; staff writes only local artifacts.
- Bundle selection comes from current Office support/principal-today outputs.
- Scan behavior must match the explicit scan mode; `existing` does not execute a
  refresh and `none` attaches no scans.
- Bundle/brief output is keyed by project id and selected brief type.
- Rendering is deterministic from local inputs; no external model result is
  implied by a generated brief.

## Dependencies and tests

Staff depends on pandas, valid Office configuration/sheets, and a coherent latest
Office tree. Refresh mode additionally depends on local Bash scripts and target
repository paths. The synthetic fixture contains representative bundles, briefs,
and indexes. There is no focused staff test module, so import checks and fixtures
do not establish full local validation.

## Failure modes

Missing credentials or sheet access prevents enrichment. Missing or malformed
Office CSVs can fail selection or rendering; briefs require `merged_state.csv`
and one block/focus source. Scan scripts may fail or produce diagnostic output,
and the current scan helper does not make their exit code a component-level
failure. Stale files can remain in `latest/bundles` or `latest/briefs` because
these directories are created and updated, not cleared by the component.

## Extension points

Add bundle selection/type rules in `bundles.py`, scan adapters behind explicit
scan modes, and deterministic renderers/index entries in `briefs.py`. A new
brief type requires a stable filename, bundle shape, fixture, tests, and future
artifact-reference update. Do not embed an external-model call without a new
trust boundary and explicit product authorization.
