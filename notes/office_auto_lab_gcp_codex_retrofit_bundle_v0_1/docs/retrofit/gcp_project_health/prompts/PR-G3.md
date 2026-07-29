# Codex Prompt — PR-G3: Freeze run bundle and persistence ports

Prerequisite: PR-G2 is accepted.

## Goal

Make one Repo Health execution an atomic, schema-validated, producer-owned run bundle with provider-neutral persistence interfaces.

## Required outputs

- run-bundle schema and validator;
- atomic local run-directory writer;
- ports for policy source, evidence sink, history sink, and optional latest signal;
- explicit idempotency/duplicate-run rule;
- failed-plugin representation;
- linkage among intents, plugin results, frontier, prepared blocks, exceptions, and source commit;
- checksums where practical.

## Non-goals

- No BigQuery/GCS implementation.
- No Terraform.
- No new dashboard.
- No change to work-block meaning.

Produce `context/closures/PR-G3.md` and propose `PR-G4`.
