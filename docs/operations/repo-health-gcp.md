# Repo Health GCP first deployment and manual execution

**Status:** canonical procedure; all provider commands unexecuted
**Audience:** authorized GCP deployers
**Owner:** Repo Health GCP maintainers
**Verified against:** `8fbf76a`

## Execution status

No provider command in this runbook was executed in PR-OD5. This environment has
no Terraform, gcloud, Docker/Podman, or bq command and no project, billing account,
operator ADC, or runtime IAM. The only executed GCP-profile check was local
validation:

```bash
SOURCE_COMMIT=fixture PYTHONPATH=src python3 \
  -m office_runtime.ops.repo_health.cloud.run_job \
  --profile gcp --policy fixtures/gcp_policy_snapshot.json --validate-only
```

It returned one project and `status: valid`; it created no client or resource.

## Required authority and preflight

Require Terraform >=1.6, gcloud, Docker/BuildKit, bq, clean accepted commit,
billing-enabled project, billing account budget authority, one supported region,
and deployer permissions for declared APIs/resources/IAM. Use operator ADC; never
a service-account key. Then run the repository preflight (**unexecuted**):

```bash
export GCP_PROJECT_ID="replace-me"
export GCP_BILLING_ACCOUNT_ID="000000-000000-000000"
export GCP_REGION="us-central1"
./infra/gcp/preflight.sh | tee g5-preflight.log
```

Expected: tool/env/ADC/project/billing/Terraform/Docker/policy checks and final
`READY`. Stop on any `MISSING` or `BLOCKED`, dirty worktree, wrong account/project,
or policy/commit mismatch.

## Bootstrap and immutable image

Artifact Registry must precede the first push. The following is **unexecuted**:

```bash
terraform -chdir=infra/gcp init
terraform -chdir=infra/gcp apply \
  -target=google_project_service.required \
  -target=google_artifact_registry_repository.images
COMMIT="$(git rev-parse HEAD)"
IMAGE_BASE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/repo-health/repo-health"
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev"
docker build -f Dockerfile.repo-health -t "${IMAGE_BASE}:${COMMIT}" .
docker push "${IMAGE_BASE}:${COMMIT}"
DIGEST="$(gcloud artifacts docker images describe "${IMAGE_BASE}:${COMMIT}" \
  --format='value(image_summary.digest)')"
```

Preserve image description. Put `${IMAGE_BASE}@${DIGEST}`, accepted commit, and
frozen policy JSON in a private `infra/gcp/terraform.tfvars`; do not commit it.

## Full plan and apply

The following is **unexecuted**:

```bash
terraform -chdir=infra/gcp plan -out=g5.tfplan
terraform -chdir=infra/gcp show -json g5.tfplan > g5.tfplan.json
terraform -chdir=infra/gcp apply g5.tfplan
terraform -chdir=infra/gcp output -json > g5.outputs.json
```

Review exactly one job, service account, bucket, dataset with five tables and
three views, registry, budget, metric/alert, and bounded IAM. Verify Scheduler is
absent, image is digest-pinned in the managed registry, and deletion protection
is enabled. Stop on unexpected resources, roles, region, or destructive action.

## First manual run

The following is **unexecuted**:

```bash
RUN_ID="g5-$(date -u +%Y%m%dT%H%M%SZ)"
gcloud run jobs update repo-health-remote --region "$GCP_REGION" \
  --update-env-vars "REPO_HEALTH_RUN_ID=${RUN_ID},REPO_HEALTH_ATTEMPT=1"
gcloud run jobs execute repo-health-remote --region "$GCP_REGION" --wait
```

Do not retry under a new run id until the first attempt is reconciled. The job
must use its assigned identity, one-to-three allowlisted projects, and only the
two remote-read plugins.

## Reconciliation and denial checks

Use the GCS manifest, partition-filtered BigQuery run query, and Cloud Run logs to
prove run id, digest, source commit, policy identity, status, and execution agree.
Then run the negative probes defined in
[security/IAM](../reference/repo-health-gcp-security.md#required-negative-evidence).
All such commands are **unexecuted** here.

Store preflight, bootstrap, image, plan/apply/outputs, execution, manifest,
BigQuery row, logs, denial responses, budget, and teardown disposition in
`context/evidence/G5/<RUN_ID>/`, plus an acceptance JSON joining their identities.
Missing or mismatched evidence means the deployment remains unaccepted.

## Recovery and next step

On job failure, preserve the same run id and evidence, inspect exceptions/logs,
correct only the narrow cause, increment attempt, and reconcile idempotent sinks.
Never overwrite conflicting history or broaden IAM after a denial. Use
[cost and teardown](repo-health-gcp-cost-and-teardown.md) after evidence export.
