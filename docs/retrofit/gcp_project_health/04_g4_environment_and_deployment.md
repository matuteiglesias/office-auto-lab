# G4 Environment and Deployment Contract

> **Status: supporting retrofit record.** Canonical current documentation:
> [GCP architecture](../../architecture/repo-health-gcp.md),
> [security/IAM](../../reference/repo-health-gcp-security.md), and
> [deployment/manual runbook](../../operations/repo-health-gcp.md). Preserve this
> page as implementation history; do not maintain a second canonical procedure.

## Profiles

- `local` is the default. It uses the same read-only GitHub source but writes the accepted run bundle through local evidence/history adapters.
- `gcp` uses assigned service identity through Application Default Credentials, immutable Cloud Storage objects, and BigQuery modeled history.
- `--validate-only` performs policy/profile validation without credentials, network calls, or writes and is the local container smoke path.

## Required inputs

| Input | Local | GCP | Meaning |
|---|---:|---:|---|
| `--policy <json>` | yes | optional | Frozen governance snapshot file; mutually exclusive alternative to `REPO_HEALTH_POLICY_JSON` |
| `REPO_HEALTH_POLICY_JSON` | optional | yes | Frozen canonical governance snapshot injected into the bounded G5 job environment |
| `REPO_HEALTH_GCS_BUCKET` | no | yes | Existing evidence bucket provisioned in G5 |
| `GOOGLE_CLOUD_PROJECT` | no | optional | Project override; otherwise ADC project discovery |
| `REPO_HEALTH_BQ_DATASET` | no | optional | Defaults to `repo_health` |
| `GITHUB_TOKEN` | optional | optional | Read token; public allowlisted repositories can operate without it at lower rate limits |
| `REPO_HEALTH_RUN_ID` | optional | optional | Retry-stable logical run identity supplied by orchestration |
| `REPO_HEALTH_ATTEMPT` | optional | optional | Positive attempt, defaults to 1 |

`GOOGLE_APPLICATION_CREDENTIALS` is rejected in the GCP profile. Cloud Run must assign a runtime service account and let `google.auth.default()` obtain service identity. No key file is accepted by the entrypoint.

## Cloud safety checks

Before any repository or GCP API call, the job rejects:

- more than three projects or an empty project set;
- `repo_path`, `workdir`, or `path` values;
- a repository not present in `repository_allowlist`;
- any enabled plugin other than `activity_remote` and `runbook_remote`;
- private repositories at plugin execution;
- service-account JSON paths in the GCP profile.

## Persistence behavior

Cloud Storage writes only:

```text
gs://<bucket>/repo-health/runs/<run_id>/run_bundle.json
gs://<bucket>/repo-health/runs/<run_id>/manifest.json
```

Both objects use `if_generation_match=0`. Exact bytes are an idempotent replay; different bytes under the same key are rejected. There is no mutable `latest` object.

BigQuery writes detail tables first and `runs` last as the completion marker. `runs.bundle_sha256` is the accepted replay identity. Exact replay is a no-op; a conflicting SHA for the same `run_id` is rejected. Insert row IDs use producer-owned intent/result/exception/block identities.

## Local container check

```bash
docker build -f Dockerfile.repo-health -t repo-health:g4 .
docker run --rm \
  -v "$PWD/fixtures/gcp_policy_snapshot.json:/policy.json:ro" \
  repo-health:g4 --profile local --policy /policy.json --validate-only
```

Expected JSON includes `{"profile":"local","projects":1,"status":"valid"}`.

## GCP preparation for G5

G4 intentionally provisions nothing. Before a real `--profile gcp` execution, G5 must provide:

1. a project with BigQuery, Cloud Run, Artifact Registry, and Cloud Storage APIs enabled;
2. tables created from `infra/gcp/bigquery.sql` after replacing `${PROJECT_ID}` and `${REGION}`;
3. an evidence bucket and create/get-only runtime access under `repo-health/runs/`;
4. a runtime service account with dataset insert/query and bounded object permissions;
5. a built image tied to the accepted commit.
