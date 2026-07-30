# office-auto-lab

`office-auto-lab` compiles operational data into reviewable Office artifacts and
provides bounded tools for staff briefs, capture processing, evidence collection,
and repository health. The runtime keeps these surfaces separate: each has its
own commands, artifacts, and mutation boundaries.

## Capabilities and status

Status uses the repository's evidence ladder: **implemented** means code exists;
**locally validated** means relevant local tests or checks pass;
**deployment-ready** means the provider adapter, container, infrastructure, and
runbook exist. It does not mean deployed.

| Capability | What it does | Evidence-backed status |
|---|---|---|
| Office compile | Reads configured spreadsheet views and compiles briefs, queues, summaries, validation, and a manifest under `artifacts/`. | Implemented |
| Staff | Builds project bundles and decision, health-check, unlocker, or execution briefs from compiled Office state. | Implemented |
| Capture | Compiles append-only capture lifecycles and supports reviewable transcription, routing, artifact, and reingest proposals. | Implemented; lifecycle tests pass, while the processing suite has known ontology failures |
| Evidence | Traces Git commits and filesystem changes into caller-selected JSONL evidence. | Implemented |
| Repo Health, local | Evaluates repository policy/plugins and produces versioned run bundles and compiler inputs. | Implemented; core semantics locally tested |
| Repo Health, GCP | Runs a bounded, read-only remote profile and persists immutable evidence to Cloud Storage and idempotent history to BigQuery. | Implemented, locally validated, deployment-ready; **not evidenced as deployed or operated** |
| systemd automation | Defines user timers for Office compilation, staff briefs, and daily evidence. | Implemented templates; host-specific paths require configuration |

## Minimal local quickstart

This verified first contact checks the import and CLI surface without accessing
Google Sheets, calling OpenAI, or writing operational artifacts:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
PYTHONPATH=src python3 -m office_runtime.cli --help
make imports
```

Expected result: CLI help lists `daily`, `office`, `staff`, `ops`, `capture`, and
`evidence`; `make imports` ends with `imports ok` and prints the discovered Repo
Health plugins. The help and import commands were executed on commit
`cda8b286cc5db3c840d7f4dad143d62497f18a63`; environment creation and dependency
installation are setup steps and were not re-executed for the documentation PR.

Office compilation is not an offline quickstart: it reads configured Google
Sheets using read-only Sheets scope and requires valid local credentials. Use
the documentation routes below before running a workflow that touches external
services.

## Choose a route

- **New reader or evaluator:** start with the [documentation map](docs/README.md),
  then review the capability status and current evidence boundaries.
- **Operator:** use the current local environment and systemd pages linked from
  the [operations route](docs/README.md#operators). GCP material remains a
  deployment-ready retrofit record, not evidence of a live service.
- **Contributor:** use the [component and source-truth route](docs/README.md#contributors)
  to find the owning package, schema, tests, and known documentation gaps.
- **Agent:** follow the [agent truth-resolution route](docs/README.md#agents).
  The repository currently has no root `AGENTS.md`; the documentation-program
  [`AGENTS.md`](notes/office-auto-lab-documentation-seed-v0_1/AGENTS.md) applies
  only inside its seed-bundle directory.

For the verified PR-OD0 inventory and known drift, see
[`docs/documentation_inventory.md`](docs/documentation_inventory.md). For the
human-reviewable migration plan, see the
[`documentation canonicality map`](docs/documentation_canonicality_map.md).
