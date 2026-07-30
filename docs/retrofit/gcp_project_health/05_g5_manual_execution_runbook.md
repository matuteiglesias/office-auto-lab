# G5 Terraform and First Manual Execution Runbook

> **Status: supporting retrofit record; superseded as a procedure.** Use the
> canonical [deployment/manual runbook](../../operations/repo-health-gcp.md) and
> [cost/teardown runbook](../../operations/repo-health-gcp-cost-and-teardown.md).
> This page records the retrofit execution contract and does not evidence a run.

## Current state

The Terraform and execution protocol are complete. A temporary Terraform 1.9.8 binary completed `init` and `validate`, but planning reproducibly stops because ADC is absent. This workspace also has no `gcloud`, Docker/Podman, GCP project, billing account, or runtime IAM. G5 is therefore `BLOCKED_EXTERNAL`: code review can proceed, but plan/apply/image publication/manual execution evidence cannot be fabricated here.

## Required external inputs

| Input | Required authority/evidence |
|---|---|
| `project_id` | GCP project with billing enabled |
| `billing_account_id` | `billing.budgets.create` authority for the mandatory USD 10 budget |
| `region` | One region supporting Artifact Registry and Cloud Run Jobs |
| deployer identity | Service Usage, Artifact Registry, IAM, Storage, BigQuery, Cloud Run, Logging/Monitoring, and Budget provisioning permissions |
| accepted commit | G4 commit used as the immutable image source label |
| local tools | Terraform >=1.6, gcloud, and Docker/BuildKit or equivalent |

No service-account key file is an acceptable substitute. Use operator ADC for provisioning and an assigned runtime service account for the job.

## Preflight (no mutations)

```bash
export GCP_PROJECT_ID="replace-me"
export GCP_BILLING_ACCOUNT_ID="000000-000000-000000"
export GCP_REGION="us-central1"
./infra/gcp/preflight.sh | tee g5-preflight.log
```

The script fails closed on a missing tool/input, dirty worktree, invalid Terraform, unavailable Docker daemon, absent operator ADC, inaccessible project, inaccessible billing account, or invalid policy fixture. Preserve `g5-preflight.log`.

## Bootstrap registry and image

Artifact Registry must exist before the first image can be pushed, while the digest-pinned image must exist before Cloud Run Job creation. Use a bounded bootstrap target, then return to a normal full plan/apply:

```bash
cd infra/gcp
terraform init
terraform validate
terraform apply -target=google_project_service.required -target=google_artifact_registry_repository.images

COMMIT="$(git rev-parse HEAD)"
REGION="us-central1"
PROJECT_ID="replace-me"
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/repo-health/repo-health"
gcloud auth configure-docker "${REGION}-docker.pkg.dev"
docker build -f ../../Dockerfile.repo-health -t "${IMAGE_BASE}:${COMMIT}" ../..
docker push "${IMAGE_BASE}:${COMMIT}"
DIGEST="$(gcloud artifacts docker images describe "${IMAGE_BASE}:${COMMIT}" --format='value(image_summary.digest)')"
```

Set `image = "${IMAGE_BASE}@${DIGEST}"`, `source_commit = "${COMMIT}"`, and the canonical frozen policy JSON in a private `terraform.tfvars`. The image variable rejects tags and requires a SHA-256 digest.

## Clean full plan/apply

```bash
terraform plan -out=g5.tfplan
terraform show -json g5.tfplan > g5.tfplan.json
terraform apply g5.tfplan
terraform output
```

Review the plan for exactly one job, one runtime service account, one evidence bucket, one dataset with five tables, one registry, bounded IAM, one log metric/alert, and the USD 10 budget. Scheduler must be absent.

## Manual execution

Use a retry-stable logical run ID:

```bash
RUN_ID="g5-$(date -u +%Y%m%dT%H%M%SZ)"
gcloud run jobs update repo-health-remote --region "$REGION" \
  --update-env-vars "REPO_HEALTH_RUN_ID=${RUN_ID},REPO_HEALTH_ATTEMPT=1"
gcloud run jobs execute repo-health-remote --region "$REGION" --wait
```

## Reconciliation

```bash
gcloud storage cat "gs://${PROJECT_ID}-repo-health-evidence/repo-health/runs/${RUN_ID}/manifest.json"
bq query --use_legacy_sql=false --parameter="run_id::${RUN_ID}" \
  --parameter="run_date:DATE:$(date -u +%F)" \
  'SELECT run_id, status, bundle_sha256, producer_commit FROM `'"${PROJECT_ID}"'.repo_health.runs` WHERE run_date=@run_date AND run_id=@run_id'
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="repo-health-remote" AND textPayload:"'"${RUN_ID}"'"' \
  --project "$PROJECT_ID" --limit 100 --format json
```

The GCS manifest SHA, BigQuery `bundle_sha256`, source commit, and logical run ID must agree.

## Denied-access probes

From runtime identity impersonation, prove access is denied outside intended resources:

```bash
RUNTIME_SA="$(terraform output -raw runtime_service_account)"
gcloud storage ls "gs://an-unrelated-bucket" --impersonate-service-account "$RUNTIME_SA"  # must fail
bq ls --project_id="an-unrelated-project" --impersonate_service_account="$RUNTIME_SA"  # must fail
```

Record command, exit code, and denial response. Do not broaden IAM to make a probe pass.

## Expected evidence packet

Store all evidence under `context/evidence/G5/<RUN_ID>/`:

```text
preflight.log
terraform-bootstrap.txt
image-describe.json
terraform-plan.json
terraform-apply.txt
terraform-outputs.json
cloud-run-execution.json
gcs-manifest.json
bigquery-run.json
cloud-logs.json
denied-storage.txt
denied-bigquery.txt
billing-budget.json
teardown.txt
acceptance.json
```

`acceptance.json` must record `run_id`, accepted commit, image digest, GCS URI/SHA, BigQuery SHA/status, Cloud Run execution ID, denial-probe exit codes, and teardown disposition. Missing evidence keeps G5 blocked.

## Rollback and teardown

Evidence resources are protected by default. After exporting accepted evidence:

```bash
terraform apply -var='allow_destroy=true'
terraform destroy -var='allow_destroy=true'
```

Confirm the Cloud Run Job is gone and no schedule exists. API disablement is intentionally not performed by destroy.
