# Codex Prompt — PR-G4: GCP adapters and container job entrypoint

Prerequisite: PR-G3 is accepted.

## Goal

Implement bounded GCP persistence adapters and a cloud-safe container entrypoint while retaining local adapters as the default.

## Scope

- BigQuery DDL/models and idempotent writer.
- Immutable Cloud Storage run packet writer.
- ADC/service-identity credential path.
- Cloud profile rejects local repo paths and unsupported plugins.
- Container build and local execution.
- Tests via fakes/contract fixtures; optional emulator where practical.
- Deployment runbook and environment contract.

## Non-goals

- No Terraform resources yet.
- No Scheduler.
- No Control Tower integration.
- No arbitrary private-repository discovery.

Produce `context/closures/PR-G4.md` and propose `PR-G5`.
