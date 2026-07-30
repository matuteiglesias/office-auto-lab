# PR-G5 Closure Note

- **Retrofit:** `gcp_project_health`
- **PR:** `PR-G5`
- **Status:** `BLOCKED_EXTERNAL`
- **Implementation review:** `ACCEPTED` — bounded Terraform, IAM, provenance, safety, tests, and operator packet satisfy the code-review portion of the embryo plan.
- **Execution acceptance:** `NOT ACCEPTED` — no real plan/apply, image, job execution, reconciliation, denial probe, billing evidence, or teardown exists.
- **Goal:** Provision the minimal GCP substrate and complete the first manual Cloud Run Job execution.

## Delivered and reviewable

- Minimal Terraform for required APIs, one Artifact Registry repository, one runtime service account, one evidence bucket, one BigQuery dataset/five tables, one Cloud Run v2 Job, bounded IAM, logging metric/alert, and USD 10 monthly budget.
- Digest-only image validation and explicit source commit input.
- One task, 1 vCPU, 512 MiB, 15-minute timeout, and one retry.
- Frozen policy snapshot injection for at most three allowlisted public repositories and exactly two remote-read plugins.
- Evidence protection by default and an explicit teardown switch.
- Bootstrap, clean plan/apply, image digest, manual execution, reconciliation, denied-access, and teardown commands.
- No Scheduler and no G6 failure/operation work.
- Partition-filter-safe replay lookup and Terraform-managed longitudinal BigQuery views.
- One fail-closed, non-mutating `infra/gcp/preflight.sh` and one consolidated operator packet/runbook with an exact evidence inventory.

## External blocker

This environment exposes none of the prerequisites required to honestly complete G5:

- no `gcloud` executable;
- no Docker/Podman executable;
- no `GOOGLE_CLOUD_PROJECT`/ADC project;
- no billing account ID;
- no deployer permission grant;
- no Artifact Registry image digest;
- no provisioned bucket, dataset, or Cloud Run Job.

Reproducible evidence:

```text
command -v gcloud     # empty
command -v docker     # empty
GOOGLE_CLOUD_PROJECT / CLOUDSDK_CORE_PROJECT / GOOGLE_APPLICATION_CREDENTIALS  # all absent
terraform validate  # success using a temporary Terraform 1.9.8 binary
terraform plan      # fails: could not find default credentials
```

Therefore no plan/apply, remote execution ID, GCS object, BigQuery row, IAM denial probe, billing snapshot, or teardown result is claimed.

## Smallest re-entry condition

Provide:

1. `project_id` with billing enabled;
2. `billing_account_id` and budget-creation permission;
3. deployment region;
4. operator ADC with the provisioning roles enumerated in the G5 runbook;
5. gcloud and a container build engine (Terraform >=1.6 can be restored from the validated lock file).

Then follow `docs/retrofit/gcp_project_health/05_g5_manual_execution_runbook.md` from registry bootstrap. Do not change product semantics or begin G6 while completing the external probes.

## Carry-state proposal

Keep `current_phase: phase_5`, `current_pr: PR-G5`, and `next_pr: PR-G5` while blocked. Do not mark G5 accepted and do not propose G6 until the manual run, reconciliation, denied-access probe, and teardown evidence all exist.
