# PR-G4 Closure Note

- **Retrofit:** `gcp_project_health`
- **PR:** `PR-G4`
- **Status:** `ACCEPTED`
- **Accepted commit:** `ff0dbf6`
- **Goal:** Implement bounded GCP persistence and a cloud-safe container entrypoint while retaining local persistence as the default.

## G3 acceptance audit

G3 was checked against the accepted embryo plan and its closure note. The versioned schema plus semantic validator cover required identities, linkage, failures, counters, status, checksums, replay, and compiler compatibility. No genuine acceptance blocker was found and the contract was not redesigned. G3 is recorded accepted at `acc7e1c`.

## Delivered

- Added immutable Cloud Storage run packets under `repo-health/runs/<run_id>/` using generation-match-zero preconditions.
- Added exact-replay verification and conflicting-object rejection; the job writes no mutable latest object.
- Added modeled BigQuery rows for runs, intents, plugin results, exceptions, and prepared blocks.
- Added typed query columns, partitioning/clustering, and three useful longitudinal views.
- Added atomic per-row BigQuery `MERGE` behavior keyed by producer row IDs and `bundle_sha256`; conflicting identities fail instead of updating history.
- Made the `runs` row the completion/idempotency marker and wrote detail models first.
- Added explicit ADC discovery and assigned-service-identity use. The GCP profile rejects `GOOGLE_APPLICATION_CREDENTIALS` file paths.
- Added one cloud-safe orchestrator that reads a frozen policy snapshot, executes only the two remote-read plugins, compiles the existing frontier, builds the accepted G3 bundle, and sends that same bundle to persistence ports.
- Added cloud-profile validation that rejects local paths, unallowlisted repositories, unsupported plugins, private repositories, and more than three projects.
- Added a non-root, narrow-dependency container and a no-network/no-write `--validate-only` smoke path.
- Added an environment/deployment contract and versioned BigQuery DDL. No infrastructure was provisioned.

## Persistence contract

### Cloud Storage

- Create-only objects: `run_bundle.json`, then `manifest.json` as completion marker.
- `if_generation_match=0` on every upload.
- Exact existing bytes produce `duplicate`; different bytes produce `DuplicateRunError`.
- No `latest` object.

### BigQuery

- Partitioned tables: `runs`, `run_intents`, `plugin_results`, `exceptions`, `prepared_blocks`.
- Producer-owned row IDs and bundle SHA on every row.
- Atomic `MERGE` per bounded row; matched rows with another bundle SHA fail.
- `runs` written last and used for exact replay lookup.
- Views: latest plugin health, unresolved issue signatures, and prepared blocks per week.

## Identity and environment

The entrypoint calls `google.auth.default()` with Cloud Platform scope and passes those credentials to Storage and BigQuery clients. It accepts no service-account key argument and rejects the service-account-file environment path in the GCP profile. G5 must assign the Cloud Run Job runtime service account.

Required GCP execution inputs, which intentionally do not exist in G4:

- `GOOGLE_CLOUD_PROJECT` or ADC project discovery;
- `REPO_HEALTH_GCS_BUCKET`;
- optional `REPO_HEALTH_BQ_DATASET` (default `repo_health`);
- frozen policy snapshot;
- optional public-repository GitHub token.

## Validation evidence

- Fake GCS create-only/exact-replay/conflict tests.
- Fake BigQuery modeled-row/completion-marker/exact-replay/conflict tests.
- Cloud policy path/allowlist/plugin rejection tests.
- In-memory end-to-end orchestration into a valid G3 bundle.
- ADC key-file rejection test.
- BigQuery DDL/model/view inventory test.
- Local entrypoint `--validate-only` execution.
- Focused G0–G4 Repo Health suite and repository import audit.

## Environment limitation

The current execution container has no Docker/Podman binary, so the Dockerfile could not be built here. The entrypoint itself ran locally with the committed fixture, and all imported GCP dependencies were installed and tested through fakes. This is not an account/permission blocker for G4 review; G4 provisions and deploys nothing. Image build/digest and real permissions belong to G5 acceptance.

## Risks and G5 inputs

- A real BigQuery/GCS contract probe requires the GCP project, bucket, dataset, and assigned runtime identity that G5 will provision.
- GCS WORM strength ultimately depends on G5 IAM/retention configuration; the adapter itself is create-only.
- BigQuery writes are intentionally bounded row-by-row to make MERGE idempotency and conflicts explicit rather than optimizing prematurely.
- The local profile still performs GitHub reads for a real run; `--validate-only` is the offline container smoke.

## Carry-state transition proposal

After human acceptance only:

```yaml
current_phase: phase_5
current_pr: null
last_accepted_pr: PR-G4
accepted_commit: <human-accepted-commit>
next_pr: PR-G5
accepted_artifacts:
  - context/closures/PR-G0.md
  - docs/retrofit/gcp_project_health/03_g0_characterization_v0_1.md
  - context/closures/PR-G1.md
  - context/closures/PR-G2.md
  - context/closures/PR-G3.md
  - context/closures/PR-G4.md
```

Human review accepted G4 and authorized G5 on 2026-07-29. The G5 entry audit added an environment-delivered frozen policy snapshot because a Cloud Run Job cannot consume the local host policy path; no G4 persistence or run-bundle contract was redesigned.
