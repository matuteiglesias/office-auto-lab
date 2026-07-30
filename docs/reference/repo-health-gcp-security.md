# Repo Health GCP security and IAM

**Status:** canonical; configuration verified, provider state unverified
**Audience:** deployers, security reviewers, and maintainers
**Owner:** `infra/gcp/` and Repo Health GCP adapters
**Verified against:** `8fbf76a`

## Identities

Provisioning uses human/operator ADC with authority to create the declared
resources. Runtime uses the Terraform-created service account assigned directly
to the Cloud Run Job. A service-account key file is not an acceptable substitute;
the entrypoint rejects `GOOGLE_APPLICATION_CREDENTIALS` before client creation.

## Runtime grants

| Scope | Role | Reason |
|---|---|---|
| Evidence bucket | `roles/storage.objectCreator` | Create immutable run objects |
| Evidence bucket | `roles/storage.objectViewer` | Verify exact replay bytes |
| Repo Health dataset | `roles/bigquery.dataEditor` | MERGE producer-owned history rows |
| Project | `roles/bigquery.jobUser` | Execute parameterized queries/MERGE |
| Project | `roles/logging.logWriter` | Emit job logs |
| Managed registry | `roles/artifactregistry.reader` | Pull pinned image |

The bucket enforces uniform access and public-access prevention. No source
repository write role, Secret Manager role, scheduler role, broad Storage admin,
or project editor role is declared.

## Application denials

Before provider/repository calls, policy rejects local paths, non-allowlisted
repository identities, unsupported plugins, and more than three projects. Only
`activity_remote` and `runbook_remote`, both `remote_read`, are selected. The
GitHub adapter performs bounded GET requests. Prepared blocks remain proposals.

## Required negative evidence

After a first run, impersonate the runtime identity and prove unrelated-bucket
listing and unrelated-project BigQuery listing are denied. Record command, exit
code, and response. A denial probe is successful only when access fails for the
intended authorization reason; do not broaden IAM to make the command exit zero.

Also verify absence of Cloud Scheduler and source-write paths. Provider denial
commands are [unexecuted here](../operations/repo-health-gcp.md#execution-status).

## Secrets and provenance

The optional GitHub token is runtime input and must not enter policy, evidence,
metadata, logs, Terraform state, or committed files. The frozen policy is limited
to 30 KB. Image reference must end in a lowercase 64-hex SHA-256 digest, and its
accepted source commit must match both Terraform `source_commit` and policy
`producer_commit` at runtime.
