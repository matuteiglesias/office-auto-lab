# Repo Health local operation

**Status:** canonical
**Audience:** local Repo Health operators
**Owner:** Repo Health maintainers
**Verified against:** `8b4c9b7`

## Choose the local profile

Two local paths exist:

- sheet-backed `ops repo-health`: reads policy tabs and may write dedicated tabs;
- frozen-snapshot `cloud.run_job --profile local`: reads allowlisted GitHub data
  and persists only local run packets/history.

Do not mix their credentials or mutation expectations.

## Frozen-snapshot preflight and validation

This validation was executed in PR-OD4 and performs no network or writes:

```bash
PYTHONPATH=src python3 -m office_runtime.ops.repo_health.cloud.run_job \
  --profile local --policy fixtures/gcp_policy_snapshot.json --validate-only
```

Expected: `{"profile":"local","projects":1,"status":"valid"}`. Stop on local
path fields, unsupported plugins, unallowlisted identities, or invalid policy.
A real execution (without `--validate-only`) was **not executed** because it reads
GitHub. It writes `<out>/<run-id>/{run_bundle.json,manifest.json}` plus
`history.jsonl`. Verify schema, manifest digest, run status, exceptions, and
idempotent replay.

## Sheet-backed preflight

The following is **not executed in PR-OD4** because it requires live Sheets:

```bash
PYTHONPATH=src python3 -m office_runtime.ops.repo_health.runner \
  --sheet-id "$SHEET_ID" --sa "$SA" --policy-only --no-write
PYTHONPATH=src python3 -m office_runtime.ops.repo_health.runner \
  --sheet-id "$SHEET_ID" --sa "$SA" --no-write
```

Use the direct runner until the primary CLI's remainder forwarding is repaired:
without `--`, wrapper options are rejected, while with `--` the separator is
forwarded and rejected by the runner. The corresponding Make targets omit the
required sheet/credential arguments. Begin with `--policy-only --no-write`;
review scheduled intents, prerequisites, plugin selection, and repositories. A
normal run without `--no-write` can write results/frontier; `--apply` can update
summary fields.

## Reconciliation and recovery

For frozen runs, the manifest is local packet completion and exact replay should
be a no-op; conflicting bytes for one run id must fail. For sheet-backed runs,
reconcile effective run set, plugin results, frontier files, logs, and denied
writes. Stop on unexpected scheduled projects/plugins, mutation without approval,
system errors, invalid bundle links/counters, or identity conflict. Never repair
history by overwriting a conflicting run. GCP operation belongs to PR-OD5.
