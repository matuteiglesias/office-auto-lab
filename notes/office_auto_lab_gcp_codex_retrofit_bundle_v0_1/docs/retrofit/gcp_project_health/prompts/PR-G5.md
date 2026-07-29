# Codex Prompt — PR-G5: Minimal Terraform and first Cloud Run Job execution

Prerequisite: PR-G4 is accepted and required GCP account/project inputs are available.

## Goal

Provision the minimum GCP infrastructure and execute one manually triggered Cloud Run Job.

## Resources

- Artifact Registry;
- runtime service account;
- Cloud Run Job;
- BigQuery dataset/tables;
- Cloud Storage evidence location;
- narrowly scoped IAM;
- logging.

## Acceptance

- clean Terraform plan/apply;
- image digest tied to commit;
- one allowlisted repository inspected;
- GCS and BigQuery reconcile by run ID;
- denied access outside intended resources;
- teardown documented.

Cloud Scheduler is optional and normally deferred to G6.

Produce `context/closures/PR-G5.md` and propose `PR-G6`.
