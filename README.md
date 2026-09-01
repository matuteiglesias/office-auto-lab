# office-auto-lab

> **Documentation frontend:** the review-ready public site package lives in
> [`docs-site/`](docs-site/README.md). Until a separate Vercel project is linked,
> its honest status is **deployment-ready, not publicly deployed**.

`office-auto-lab` compiles operational data into reviewable Office artifacts and
provides bounded tools for staff briefs, capture processing, evidence collection,
and repository health. The runtime keeps these surfaces separate: each has its
own commands, artifacts, and mutation boundaries.

## Authority and identity boundary

Office owns operational front identity, Carry State, selection, preparation, and
compile outputs. `front_id` is the canonical operational identity; legacy
`project_id` remains a compatibility alias during migration.

GitHub repository identity, lifecycle, and readiness belong to the `projects`
control plane. Office may optionally enrich fronts with the repo-keyed
`context:github-repositories@1` artifact through `OFFICE_REPO_CONTEXT_JSON` and an
Office-owned `repo_ids` association. That context is advisory: it does not
automatically change carry, horizon, priority, principal posture, escalation, or
block eligibility. See [`front-identity.md`](docs/architecture/front-identity.md)
and [`repository-context.md`](docs/architecture/repository-context.md).

Repo Health remains physically implemented in this repository during the
compatibility phase; that does not make Office the long-term semantic authority
for repository-estate readiness.

## Capabilities and status

Status uses the repository's evidence ladder: **implemented** means code exists;
**locally validated** means relevant local tests or checks pass;
**deployment-ready** means the provider adapter, container, infrastructure, and
runbook exist. It does not mean deployed.

| Capability | What it does | Evidence-backed status |
|---|---|---|
| Office compile | Reads configured spreadsheet views and compiles briefs, queues, summaries, validation, and a manifest under `artifacts/`. | Implemented |
| Staff | Builds project bundles and decision, health-check, unlocker, or execution briefs from compiled Office state. | Implemented |
| Capture | Compiles append-only capture lifecycles and supports reviewable transcription, routing, artifact, and reingest proposals. | Implemented; lifecycle/transcription are in stable parent-runtime acceptance, while processing ontology issue #21 remains open |
| Evidence | Traces Git commits and filesystem changes into caller-selected JSONL evidence. | Implemented |
| Repo Health, local | Evaluates repository policy/plugins and produces versioned run bundles and compiler inputs. | Implemented; core semantics locally tested |
| Repo Health, GCP | Runs a bounded, read-only remote profile and persists immutable evidence to Cloud Storage and idempotent history to BigQuery. | Implemented, locally validated, deployment-ready; **not evidenced as deployed or operated** |
| systemd automation | Defines user timers for Office compilation, staff briefs, and daily evidence. | Portable install/render contract implemented; installed runtime paths are operator configuration rather than tracked source |

## Dependency profiles

The repository has one declared dependency authority:

```text
requirements/constraints.txt
requirements/profiles/
    office.txt
    capture.txt
    repo-health.txt
    full.txt
    legacy-auto-checker.txt
```

The root `requirements*.txt` files are compatibility shims, not separate version
authorities. `legacy-auto-checker` is compatibility-only and is not included in
the active `full` profile.

Inspect/validate the dependency contract without installing packages:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py --list
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py --check
```

## Minimal local quickstart

```bash
python3 -m venv .venv
. .venv/bin/activate
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py full
PYTHONPATH=src python3 -m office_runtime.cli --help
make runtime-contracts
make imports
```

Expected result: CLI help lists the current top-level runtime surfaces;
`runtime-contracts` validates dependency and scheduler contracts; `make imports`
ends with `imports ok` and prints discovered Repo Health plugins.

Office compilation is not an offline quickstart: it reads configured Google
Sheets using read-only Sheets scope and requires valid local credentials. Use
the documentation routes below before running a workflow that touches external
services.

## Parent-runtime CI

`.github/workflows/runtime-ci.yml` validates the non-Editorial parent runtime in
clean environments. It:

- checks dependency and portable-systemd contracts without network mutation;
- installs every declared capability profile independently;
- verifies the active `full` profile on Python 3.11 and 3.12;
- runs stable Capture and Repo Health offline suites;
- deliberately leaves capture-processing ontology repair to issue #21 rather
  than hiding it behind infrastructure success.

## Portable local automation

Tracked services under `systemd/user/` no longer contain a username or checkout
path. Render a configuration without mutating systemd:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_systemd.py render \
  --repo-root "$(pwd)" \
  --python-bin "$(pwd)/.venv/bin/python" \
  --evidence-root "$HOME/repos" \
  --out /tmp/office-systemd
```

See [`docs/operations/systemd-automation.md`](docs/operations/systemd-automation.md)
for install, enable, verification, upgrade, and uninstall procedures.

## Choose a route

- **New reader or evaluator:** start with the [documentation map](docs/README.md),
  then review capability status and current evidence boundaries.
- **Operator:** use the current local environment and systemd pages linked from
  the [operations route](docs/README.md#operators). GCP material remains a
  deployment-ready retrofit record, not evidence of a live service.
- **Contributor:** use [local development](docs/getting-started/local-development.md)
  and the [component/source-truth route](docs/README.md#contributors).
- **Agent:** start with the root [`AGENTS.md`](AGENTS.md), then follow the
  [agent truth-resolution route](docs/README.md#agents).

For the historical documentation inventory and drift record, see
[`docs/documentation_inventory.md`](docs/documentation_inventory.md). For the
human-reviewable migration plan, see the
[`documentation canonicality map`](docs/documentation_canonicality_map.md).
