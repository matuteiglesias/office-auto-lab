# Local development and validation

**Status:** canonical
**Audience:** local contributors and operators
**Owner:** office-auto-lab maintainers
**Verified against:** `8b4c9b7`

## Scope

Use this page to prepare Python and run non-network validation. It does not
configure Google Sheets, OpenAI, or GCP credentials.

## Setup

The following setup is **illustrative / not re-executed in PR-OD4** because it
creates an environment and may download packages:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

`requirements.txt` is the broad runtime set. `requirements-repo-health.txt` is
the narrow container/cloud set. `requirements-auto-checker.txt` belongs to the
legacy checker workflow; do not install all three indiscriminately.

## Verified preflight

Executed on 2026-07-30:

```bash
PYTHONPATH=src python3 -m office_runtime.cli --help
make imports
make audit
```

Expected: the CLI lists six top-level surfaces, imports prints the seven plugin
names and `imports ok`, and audit completes compile/import/diff checks.

## Optional bounded checks

These commands were executed with output under `/tmp`:

```bash
PYTHONPATH=src python3 -m office_runtime.cli capture lifecycle \
  --inbox-root inbox --out /tmp/office-od4-capture
PYTHONPATH=src python3 -m office_runtime.cli evidence files \
  --roots docs --start 2026-07-30 --end 2026-07-30 \
  --out /tmp/office-od4-evidence/files.jsonl --max-depth 1
PYTHONPATH=src python3 -m office_runtime.ops.repo_health.cloud.run_job \
  --profile local --policy fixtures/gcp_policy_snapshot.json --validate-only
```

Observed: six captures and seven capture artifact files; 13 evidence rows with
zero errors; and `{"profile":"local","projects":1,"status":"valid"}`.
Counts are date/repository dependent; validate status, errors, and output paths.

## Stop rules

Stop before networked commands if credentials or target identifiers are unclear.
Do not use `make smoke`: its tracked recipes still reference missing top-level
`scripts/` paths. Do not interpret imports as behavioral validation. See
[failure recovery](../operations/failure-recovery.md) for known failures.
