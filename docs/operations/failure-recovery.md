# Failure and recovery

**Status:** canonical
**Audience:** local operators and maintainers
**Owner:** office-auto-lab maintainers
**Verified against:** `8b4c9b7`

## Universal response

1. Stop automation or repeated retries.
2. Preserve the run directory, manifest/bundle, logs, command, environment names
   (not secret values), and exact error.
3. Identify the authoritative completion marker in
   [ownership and state](../architecture/ownership-and-state.md).
4. Correct the narrow cause and run once manually.
5. Reconcile expected and denied effects before restoring automation.

## Failure matrix

| Symptom | Likely boundary | Recovery | Stop condition |
|---|---|---|---|
| Import error | Python environment/dependency set | Activate intended environment; install its one requirements file; rerun `make imports` | Conflicting dependency ownership or secret request |
| `make smoke` missing `scripts/...` | Known Make/source-layout defect | Use `make audit` for import/static checks; track product fix separately | Do not create ad-hoc symlinks in a docs task |
| Office credential/API error | Local Sheets credential/network | Confirm path, file permissions, spreadsheet/gids; retry once | Unknown sheet identity or broader OAuth requested |
| Office error manifest | Input validation | Inspect issues and source sheet; preserve failed run | Do not promote/copy failed output manually |
| Partial `artifacts/latest` | Interrupted clear/copy promotion | Preserve run, rerun a valid compile, reconcile run id/files | No complete successful run exists |
| Missing/stale staff output | Latest inputs, selection, scan result | Inspect queues, `ai_jobs.csv`, indexes and referenced paths | Scan targets unreviewed or script error unexplained |
| Capture audio denial | Path/type/size guard | Correct configured root/path or supported file; do not bypass guard | Path escapes root or payload exceeds limit |
| Capture model/schema failure | External API/strict output | Preserve failure event; retry only after cause/model reviewed | Repeated invalid output or unclear external data scope |
| Evidence zero/error rows | Roots, dates, permissions, Git | Narrow and verify inputs; inspect structured errors | Broadening roots would exceed intended authority |
| Repo Health ineligible/system error | Policy, prerequisite, plugin, remote source | Inspect intent/result/evidence; correct policy or dependency | Unexpected plugin/capability or unallowlisted repo |
| Duplicate run conflict | Producer identity violation | Preserve both digests/context and investigate producer | Never overwrite immutable/local/GCP history |
| systemd failure | Host-specific path/environment | Disable timer; repair local copy; manual service run | Service still uses unreviewed paths/credentials |

## Known test limitations

The full suite was not rerun in PR-OD4 because PR-OD3 already recorded four
capture ontology failures and a missing BigQuery client import in this environment.
Office, staff, and evidence have no focused test modules. Do not convert a passing
import/audit check into a behavioral claim.
