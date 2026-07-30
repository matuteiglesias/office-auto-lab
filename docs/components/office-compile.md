# Office compile owner guide

**Status:** canonical
**Audience:** contributors and agents changing Office compilation
**Owner:** `src/office_runtime/office/`
**Verified against:** `cda8b286cc5db3c840d7f4dad143d62497f18a63`

## Purpose and non-goals

Office compile turns configured front-registry and carry-state sheet views into
validated, routed CSV/Markdown artifacts and a manifest. It owns normalization,
merge/routing rules, rendering, run directories, and latest promotion. It does
not own the input sheets, staff briefs, capture processing, or Repo Health.

## Source paths

| Path | Responsibility |
|---|---|
| `office/config.py` | Environment-backed immutable configuration and artifact roots |
| `office/io.py` | Read-only Sheets client, normalization, file writes, latest promotion |
| `office/validate.py` | Required-input and row validation |
| `office/compile.py` | Merge, scoring, routing, orchestration, manifest |
| `office/render.py` | Human-readable Markdown rendering |
| `cli.py` | `office compile` and `daily` handlers, ledger summary |

## Inputs and outputs

Inputs are the front and carry worksheets identified by `OFFICE_SPREADSHEET_ID`,
`OFFICE_FRONT_GID`, and `OFFICE_CARRY_GID`; authentication comes from the local
service-account path. Outputs begin in `OFFICE_OUT_ROOT/runs/<UTC-run-id>/` and
include routed/diagnostic CSVs, Markdown briefs/queues, and `manifest.json`. A
successful run is copied to `OFFICE_OUT_ROOT/latest/`. Run and daily logs live
under `artifacts/logs/` unless their logging roots are overridden in code.

## Canonical command surface

The primary entry point is `python -m office_runtime.cli office compile`; the
Make alias is `office-compile`. `daily` composes Office compile with staff work.
This guide identifies commands but does not replace the PR-OD4 operational
procedure. See the [command inventory](../documentation_inventory.md#command-surface).

## Invariants

- Sheets access in this component uses the read-only OAuth scope.
- `project_id` is the merge key; blank identifiers are discarded.
- A required-input error writes an error manifest and does not promote `latest`.
- Only a successful completed run is promoted.
- `latest` is a mutable copy, not immutable evidence or an atomic pointer swap.
- Ledger success is written only after the CLI receives an `ok` manifest.

## Dependencies and tests

Runtime dependencies include pandas, NumPy, Google authentication/API clients,
and configured sheet access. The synthetic artifact tree under
`fixtures/artifacts_sample/latest/` documents representative output shapes.
There is currently no focused Office compile test module; `make imports` checks
importability only. This is a known validation gap, so the component is
documented as implemented rather than broadly locally validated.

## Failure modes

Credential/API/network failure occurs before compilation can complete. Missing
required columns or invalid rows appear in validation artifacts; strict mode can
raise their severity. A failed run can leave a run directory without changing
`latest`. Interruption during clear-and-copy promotion can expose a partial
latest tree. Operators should inspect the run manifest and expected artifacts,
not rely only on process output.

## Extension points

Add routing rules in `compile.py`, validation in `validate.py`, and renderers in
`render.py`. New artifacts must be included deliberately in the manifest and
latest semantics, documented in the future artifact reference, and covered by
focused tests. Changes to sheet fields, merge keys, completion behavior, or
promotion must also update [ownership and state](../architecture/ownership-and-state.md).
