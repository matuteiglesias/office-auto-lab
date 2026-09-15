# office-auto-lab

`office-auto-lab` is the runtime and preparation layer for Matías's governed Office.
It consumes the Control Tower semantic control plane, compiles bounded work,
prepares evidence, protects Principal attention, publishes coherent generations,
and records what actually ran.

Repository-estate identity/health semantics remain owned by the `projects` control
plane; Office consumes governed repository/workspace bindings without becoming a
second source of repository truth.

## The Office loop

```text
Control Tower v2
  ↓ one validated snapshot
front / repo / workspace identity
  ↓
typed work
  ↓
Staff preparation
  ↓
Principal brief
  ↓
bounded execution packets
  ↓
execution receipts / closure
  ↓
reviewable reentry proposals
```

A scheduled or manual generation runs the forward half as one coherent unit:

```text
snapshot → work → Staff → Principal → execution plan → validate → publish
```

Downstream stages never reread Control Tower. Every artifact in a generation is
bound to the same snapshot digest.

## Product surfaces

| Surface | Responsibility |
|---|---|
| Control-state intake | Read and validate the nine governed Control Tower v2 tables into one immutable snapshot. |
| Identity resolution | Resolve `front_id → repo_id → workspace_id`; concrete local paths are observations, not semantic identity. |
| Work compiler | Emit `DECIDE`, `UNBLOCK`, `VERIFY`, `EXECUTE`, and `MAINTAIN` from structured state. Free-text `needs` is context, never routing syntax. |
| Staff | Triage every typed item cheaply, deep-prepare only a bounded pull window, and produce structured evidence-backed packets. |
| Principal | Compress prepared work into `Needs You`, ready pulls, exceptions, delegated movement, and delta. No-principal-action-required is a valid success state. |
| Execution compiler | Turn ready pulls into bounded packets constrained by operator contracts. Principal decisions are never inferred as authorization. |
| Reentry v2 | Validate packet-bound receipts and produce non-mutating `DONE` / `FOLLOW_UP` / `WAITING` review proposals. |
| Coherent generation | Publish run-scoped Office generations and advance the v2 current pointer only after the entire generation validates. |
| Run Record Owner | Record every real generation attempt and derive runtime health from evidence rather than producer-specific self-reporting. |
| Capture | SIDECAR append-only capture/transcription/routing/artifact/reingest proposal workflow. |
| Evidence / estate movement | SIDECAR read-only producers for Git/filesystem traces and bounded estate deltas. |
| Editorial | SIDECAR projection capability with its own explicit contract. |

Historical Repo Health/GCP, Office v1 compilation, Staff-v1 bundles/briefs, direct
path authority, and the legacy prepared-block compiler are not product surfaces.
They were removed in M9; Git history is the archive.

## Coherent generations

Manual published generation:

```bash
make office-v2-generate
```

Safe shadow generation:

```bash
make office-v2-shadow
```

Artifacts are generation-scoped:

```text
artifacts/v2/runs/<run-id>/
  control/snapshot.json
  routing/work_items.json
  staff/preparation.json
  staff/packets/
  principal/brief.json
  principal/brief.md
  execution/plan.json
  execution/packets/
  manifest.json
```

`artifacts/v2/current.json` points only to the last fully successful published
generation. A failed run cannot replace it.

Every attempt also leaves:

```text
artifacts/v2/run_records/<run-id>.json
```

Shadow runs are explicitly recorded as shadow evidence and do not satisfy
scheduled-runtime health.

## Runtime health

Run Record Owner compiles health from canonical run records:

```bash
make runtime-health-v2
```

The local projection is written to:

```text
artifacts/v2/runtime_health.json
```

Health is observational (`OK`, stale, failed, observability gap, no runtime
expected). It does not change Carry, horizon, priority, or Principal posture.

## Staff freshness

Prepared context is reusable only while its evidence remains valid. Staff packet
freshness distinguishes current state from changed Control Tower state, changed
repository revisions, and missing current evidence. Unknown evidence is never
silently treated as fresh.

## Dependency profiles

There is one dependency authority:

```text
requirements/constraints.txt
requirements/profiles/
  office.txt
  capture.txt
  full.txt       # exact union of supported Office + Capture runtime
requirements/test.txt
```

Validate without installing:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py --list
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py --check
```

## Local quickstart

```bash
python3 -m venv .venv
. .venv/bin/activate
PYTHONPATH=src python3 src/office_runtime/scripts/install_profile.py full
make runtime-contracts
make imports
make smoke
```

A live Office generation additionally requires read-only Google Sheets credentials
for the configured Control Tower workbook.

## Sidecar CLI

`office_runtime.cli` intentionally does **not** contain another Office compiler.
It exposes sidecar workflows only:

```bash
PYTHONPATH=src python3 -m office_runtime.cli capture --help
PYTHONPATH=src python3 -m office_runtime.cli evidence --help
PYTHONPATH=src python3 -m office_runtime.cli estate --help
```

The canonical Office runtime entrypoint is
`src/office_runtime/scripts/run_generation_v2.py`.

## Automation

Systemd is an orchestration boundary, not a second implementation of the Office
DAG. The target topology is one coherent v2 generation timer; Staff and Principal
are internal stages, never independent wall-clock jobs.

Scheduler installation/cutover is explicit and reversible. Merging runtime code
must not silently enable or change a user's installed timers. See
[`docs/operations/systemd-automation.md`](docs/operations/systemd-automation.md).

## Governance boundaries

- Control Tower owns governed semantic state.
- `projects` owns repository-estate identity/health semantics.
- Office compiles work and preparation from those authorities.
- execution packets withhold governance mutation powers such as `update_state`
  and `open_work_items`.
- execution produces evidence; reentry proposes change.
- reviewed governance, not an executor, changes Carry/priority semantics.
- Office UI consumers are projections. They must migrate to Office v2 artifacts
  rather than constrain the runtime to historical formats.

## Engineering acceptance

```bash
make parent-audit
make smoke
```

The active acceptance surface covers Control Tower intake, identity, work,
Staff, Principal, execution, reentry, coherent generation, run records,
cross-layer invariants, freshness, dependency authority, and scheduler contracts.

For architecture details start with:

- [`docs/architecture/control-state-v2.md`](docs/architecture/control-state-v2.md)
- [`docs/architecture/identity-resolution-v2.md`](docs/architecture/identity-resolution-v2.md)
- [`docs/architecture/work-item-compiler-v1.md`](docs/architecture/work-item-compiler-v1.md)
- [`docs/architecture/staff-preparation-v2.md`](docs/architecture/staff-preparation-v2.md)
- [`docs/architecture/principal-compiler-v2.md`](docs/architecture/principal-compiler-v2.md)
- [`docs/architecture/execution-compiler-v2.md`](docs/architecture/execution-compiler-v2.md)
- [`docs/architecture/reentry-v2.md`](docs/architecture/reentry-v2.md)
- [`docs/architecture/coherent-generation-v2.md`](docs/architecture/coherent-generation-v2.md)
- [`docs/architecture/run-record-health-v2.md`](docs/architecture/run-record-health-v2.md)
