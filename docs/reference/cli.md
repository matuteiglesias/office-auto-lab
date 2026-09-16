# CLI and Make reference

**Status:** canonical
**Audience:** operators, contributors, and agents
**Owner:** `src/office_runtime/cli.py`, `src/office_runtime/scripts/`, and `Makefile`
**Verified against:** `f7af9bbd40e04ba4b27f4e24ec20bd4121e4548a`

The canonical Office v2 entrypoint is
`src/office_runtime/scripts/run_generation_v2.py`. The Python CLI exposes
sidecars only; it does not contain a second Office compiler.

## Office v2 commands

| Make target | Effect boundary |
|---|---|
| `office-v2-shadow` | Read the configured Control Tower and compile a complete run without advancing the current pointer. |
| `office-v2-generate` | Compile, validate, publish a complete run, and advance the current pointer only after success. |
| `runtime-health-v2` | Derive the local runtime-health projection from canonical run records. |

Shadow and published generations do not execute ready pulls or mutate Control
Tower. Review the [coherent generation](../architecture/coherent-generation-v2.md)
and [reentry](../architecture/reentry-v2.md) contracts before operation.

## Sidecar CLI

Prefix these commands with:

```bash
PYTHONPATH=src python3 -m office_runtime.cli
```

| Command family | Subcommands | Effect boundary |
|---|---|---|
| `capture` | `lifecycle`, `transcribe`, `transcribe-pending`, `route`, `artifactize`, `propose-reingest`, `process` | Local capture lifecycle and proposal artifacts; model-backed commands may call OpenAI and append events. |
| `evidence` | `git`, `files` | Read explicitly supplied roots and write local evidence artifacts. |
| `estate` | `movement` | Produce a bounded, read-only Estate Movement Digest from caller-selected roots. |

Use each subcommand's `--help` for its current arguments. Model-backed or
mutation-capable capture paths require explicit inputs, credentials, mode, and
authorization; discovery is not authorization.

## Acceptance and contract targets

| Target | Scope |
|---|---|
| `parent-audit` | Parent documentation, dependency/scheduler contracts, and the complete Office v2 contract surface. |
| `smoke` | Imports, Office v2 contracts, editorial contracts, runtime contracts, and bounded repository scans. |
| `runtime-contracts` | Dependency authority and systemd rendering/install contracts. |
| `docs-check` | Repository documentation metadata and link checks. |
| `imports` | Supported import surface. |

Focused targets are available for control state, identity, work, Staff,
Principal, execution, reentry, generation, run records, freshness, editorial,
dependencies, and systemd. The `Makefile` is the exact target authority.

## Local evidence targets

| Target | Inputs |
|---|---|
| `capture-lifecycle` | Capture inbox and output configuration. |
| `evidence-git` | `ROOTS`, `START`, `END`, and output configuration. |
| `evidence-files` | `ROOTS`, `START`, `END`, and output configuration. |
| `evidence-today` | Runs both bounded evidence producers. |
| `estate-movement` | Caller-selected roots, date window, digest ID, and optional prior manifest/control plane. |
| `logs-tail` | Reads the latest local ledger lines. |

For sequencing, expected results, failure handling, and recovery, use
[routine local operation](../operations/local-routines.md),
[failure and recovery](../operations/failure-recovery.md), and
[systemd automation](../operations/systemd-automation.md).
