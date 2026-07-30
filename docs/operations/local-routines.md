# Routine local operation

**Status:** canonical
**Audience:** local operators
**Owner:** office-auto-lab maintainers
**Verified against:** `8b4c9b7`

## Scope and preflight

This runbook routes recurring local work; exact flags live in the
[CLI reference](../reference/cli.md). First complete
[local development](../getting-started/local-development.md), confirm the target
artifact root, and review the relevant [trust boundary](../architecture/trust-boundaries.md).

## Non-network observer routines

Capture lifecycle compilation and evidence files were executed in PR-OD4 using
the bounded `/tmp` examples on the local-development page. For a real run, choose
an explicit inbox/root, date range, depth, and output. Verify the JSON summary,
zero/unexpected error count, and every reported output path. Stop on an unexpected
root, warning spike, or output outside the intended location.

## Office and staff routine

These commands are **not executed in PR-OD4** because they require configured
Google Sheets credentials and live sheet identifiers:

```bash
PYTHONPATH=src python3 -m office_runtime.cli office compile
PYTHONPATH=src python3 -m office_runtime.cli staff bundles --scan-mode existing
PYTHONPATH=src python3 -m office_runtime.cli staff briefs
```

Alternatively, `daily --scan-mode existing` composes them. Before execution,
confirm `GOOGLE_APPLICATION_CREDENTIALS`, spreadsheet/gids, and
`OFFICE_OUT_ROOT`. Prefer `existing` or `none` scans until each repository target
is reviewed; `refresh` executes local scripts.

Success reconciliation:

1. require an `ok` Office manifest in a new run directory;
2. confirm that `latest/manifest.json` has the same run id;
3. inspect validation warnings and row counts;
4. confirm `ai_jobs.csv`, `brief_index.csv`, and their referenced files;
5. inspect daily/run/event logs, but do not use logs alone as completion proof.

Stop if the manifest is error/missing, `latest` is partial, sheet identity differs
from expectation, or scan paths target an unreviewed repository.

## Capture model-backed routine

Transcribe/route/artifactize/propose/process commands are **not executed in
PR-OD4** because they may send audio/text to OpenAI and append derived JSONL.
Use `--dry-run` to deny append, not to deny API access. Review event id, audio
root, model, and size limit first. Reconcile the derived event or dry-run JSON;
never treat a reingest proposal as approved/applied.

## Evidence Git routine

`evidence git` was not executed in PR-OD4; the files variant was. Select narrow
roots and date bounds, then verify `repos_found`, commits, errors, and output
JSONL. Zero rows can be correct but is not proof of expected activity.
