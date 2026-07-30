# CLI and Make reference

**Status:** canonical
**Audience:** operators, contributors, and agents
**Owner:** `src/office_runtime/cli.py` and `Makefile`
**Verified against:** `8b4c9b7`

All help surfaces below were executed in PR-OD4 unless marked pass-through.
Prefix primary commands with `PYTHONPATH=src python3 -m office_runtime.cli`.

## Primary CLI

| Command | Arguments/defaults | Effect boundary |
|---|---|---|
| `daily` | `--scan-mode {none,existing,refresh}`; `existing` | Office then staff bundles/briefs after success |
| `office compile` | none | Network read; local artifact writes |
| `staff bundles` | scan mode; CLI default `refresh` | Network read/local writes; refresh executes scans |
| `staff briefs` | none | Local reads/writes |
| `ops repo-health policy` | intended remainder pass-through | Currently unusable with required runner options; see below |
| `ops repo-health run` | intended remainder pass-through | Currently unusable with required runner options; see below |
| `capture lifecycle` | `--inbox-root`, `--out` | Local observer artifacts |
| `capture transcribe` | required `--event-id`; inbox/model/audio-root/max-bytes/force/dry-run | May call OpenAI; may append event |
| `capture transcribe-pending` | limit 5; inbox/model/force/dry-run | May call OpenAI; may append events |
| `capture route` | required event id; inbox/model/force/dry-run | May call OpenAI; may append event |
| `capture artifactize` | required event id; inbox/model/force/dry-run | May call OpenAI; may append event |
| `capture propose-reingest` | required event id; inbox/model/force/dry-run | May call OpenAI; proposal only |
| `capture process` | required event id; inbox/model/transcription-model/force/dry-run | Runs missing stages in order |
| `evidence git` | required roots/start/end/out; max-depth 4; optional per-repo limit | Reads roots; writes JSONL/logs |
| `evidence files` | required roots/start/end/out; max-depth 8; hidden false; optional limit | Reads roots; writes JSONL/logs |

Repo Health runner arguments are `--sheet-id` and `--sa` (required), `--subset`,
`--rows`, `--plugins`, `--date`, `--apply`, `--no-write`, and `--policy-only`.
Invoke `python -m office_runtime.ops.repo_health.runner` directly. Parser checks
executed in PR-OD4 confirmed that the primary wrapper rejects options without a
separator and incorrectly forwards the separator when one is used.

Frozen-snapshot CLI:

```text
python -m office_runtime.ops.repo_health.cloud.run_job
  [--profile {local,gcp}] [--policy PATH] [--out PATH] [--validate-only]
```

Policy may instead come from `REPO_HEALTH_POLICY_JSON`; local output defaults to
`out/repo-health-runs`.

## Make targets

| Target | Delegates to / note |
|---|---|
| `imports` | Import surface and dynamic plugin discovery |
| `audit` | compileall, imports, `git diff --check` |
| `daily`, `office-compile`, `staff-bundles`, `staff-briefs` | Primary CLI; bundles uses existing scans |
| `capture-lifecycle` | Primary lifecycle command |
| `repo-health-policy`, `repo-health-run` | Broken: omit required runner sheet/credential arguments |
| `evidence-git`, `evidence-files`, `evidence-today` | Uses `ROOTS`, `START`, `END`, `OUT_DIR`, `GIT_OUT`, `FILES_OUT` |
| `logs-tail` | Last 30 lines of daily ledgers |
| `office` | References missing `office.main`; not a canonical operation |
| `smoke`, `repo-scans`, `compile-blocks` | Known broken pre-`src` script paths; do not use until product repair |

For safe sequencing, expected results, and recovery, use
[routine operation](../operations/local-routines.md) and
[Repo Health local](../operations/repo-health-local.md).
