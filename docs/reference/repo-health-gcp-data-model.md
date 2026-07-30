# Repo Health GCP evidence and data model

**Status:** canonical; modeled, not provider-populated
**Audience:** operators, analysts, integrators, and reviewers
**Owner:** Repo Health run bundle, GCP adapters, and Terraform
**Verified against:** `8fbf76a`

## Canonical object packet

GCS stores exactly these objects per logical run:

```text
gs://<evidence-bucket>/repo-health/runs/<run-id>/run_bundle.json
gs://<evidence-bucket>/repo-health/runs/<run-id>/manifest.json
```

The bundle is canonical JSON validated as `repo_health.run_bundle.v1`. The
manifest is written last and records its SHA-256 and byte count. Both writes use
`if_generation_match=0`; identical existing bytes are replay, different bytes are
an identity conflict. No mutable latest object exists. Bucket lifecycle deletes
objects after `evidence_retention_days` (30 by default).

## BigQuery tables

All physical tables are partitioned by required `run_date` and require partition
filters. Common fields are `row_id`, `run_id`, `run_date`, and `bundle_sha256`.

| Table | Typed fields beyond common | Producer identity |
|---|---|---|
| `runs` | status, attempt, timestamps, producer commit, policy id/hash, raw bundle | run id |
| `run_intents` | project id, plugin, raw JSON | intent id |
| `plugin_results` | project id, plugin, normalized class, bucket, raw JSON | result id |
| `exceptions` | category, raw JSON | exception id |
| `prepared_blocks` | archetype, mode, raw JSON | block id |

Every detail retains raw JSON plus useful typed dimensions. MERGE matches stable
`row_id`; a changed bundle digest triggers an error. Detail tables are written
before `runs`, making the runs row the completion/idempotency marker.

## Views

- `latest_plugin_health`: latest result per project/plugin within 30 days;
- `unresolved_issue_signatures`: 90-day grouped non-ok signatures;
- `prepared_blocks_weekly`: 90-day weekly archetype/mode counts.

## Reconciliation contract

For one run, the logical run id, GCS manifest digest, BigQuery
`runs.bundle_sha256`, source commit, and policy identity must agree. Missing
manifest or runs row means incomplete persistence. Never patch conflicting rows
or objects; preserve evidence and investigate producer identity.
