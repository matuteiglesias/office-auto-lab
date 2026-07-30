# Evidence owner guide

**Status:** canonical
**Audience:** contributors and agents changing evidence collection
**Owner:** `src/office_runtime/evidence/`
**Verified against:** `cda8b286cc5db3c840d7f4dad143d62497f18a63`

## Purpose and non-goals

Evidence produces bounded JSONL observations of Git commits or filesystem
modifications over caller-selected roots and time ranges. It owns discovery,
date normalization, row construction, limits, and emission. It does not decide
what the observations mean for Office, staff, or Repo Health and does not ingest
them automatically into another subsystem.

## Source paths

| Path | Responsibility |
|---|---|
| `evidence/git_trace.py` | Repository discovery, commit traversal, Git/error rows, JSONL writer |
| `evidence/fs_trace.py` | Date bounds, bounded filesystem traversal, file/error rows, JSONL writer |
| `cli.py` | Primary commands, summaries, run logs, ledger entries |
| `run_logging.py`, `ledger.py` | Shared execution/event and daily log formats |
| `systemd/user/evidence-daily.*` | Optional daily scheduling templates |

## Inputs and outputs

Both tracers require one or more roots, a start, an inclusive end, and an output
path. Git accepts discovery depth and a per-repository commit limit. Files accepts
traversal depth, hidden-file inclusion, and a row limit. Each writes JSONL to the
exact caller path, prints a JSON summary through the primary CLI, and adds local
run/event and daily ledger logs.

## Canonical command surface

Primary commands are `evidence git` and `evidence files`; Make provides
`evidence-git`, `evidence-files`, and the composed `evidence-today`. Direct module
CLIs exist but are secondary implementation surfaces. Operational examples and
recovery belong to PR-OD4 rather than this owner guide.

## Invariants

- Roots and traversal limits are caller-controlled and explicit.
- A date-only end value is inclusive; filesystem code converts it to an exclusive
  upper bound internally.
- Traversal emits structured error rows where supported instead of silently
  treating every inaccessible target as absent.
- Output location is never inferred as Office or Repo Health state.
- Logs summarize collection but the JSONL output is the collected evidence.

## Dependencies and tests

Git tracing depends on the `git` executable and readable repositories. File
tracing depends on host filesystem metadata and permissions. CLI execution also
uses shared local logging. No focused evidence test module exists; current
confidence is implementation and exercised CLI/import behavior, not a complete
locally validated contract.

## Failure modes

Invalid dates fail argument processing inside the tracer. Missing or unreadable
roots, non-repositories, Git command errors, permission errors, and files that
change during traversal can create error rows or reduce results. Broad roots and
high depth can be expensive; limits are safety controls, not completeness
guarantees. A successful exit with zero rows is not proof that expected activity
exists—inspect the summary, error count, roots, dates, and output.

## Extension points

New evidence kinds should define a stable row vocabulary, deterministic bounds,
explicit error rows, a caller-selected destination, tests, and CLI/ledger
summary fields. Do not make a tracer mutate scanned roots or silently feed a
domain component; that would change this component's observation-only boundary.
