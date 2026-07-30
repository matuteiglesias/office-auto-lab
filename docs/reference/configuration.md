# Configuration reference

**Status:** canonical
**Audience:** operators and contributors
**Owner:** component owners
**Verified against:** `8b4c9b7`

Do not commit credentials. Defaults below are code defaults, not recommendations.

## Office and staff

| Variable | Default / meaning |
|---|---|
| `OFFICE_ROOT` | `.`; base for other defaults |
| `OFFICE_OUT_ROOT` | `<OFFICE_ROOT>/artifacts` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Code contains a host-specific JSON filename fallback; explicitly set a local path |
| `OFFICE_SPREADSHEET_ID` | Code contains a project-specific id; verify before use |
| `OFFICE_FRONT_GID`, `OFFICE_CARRY_GID`, `OFFICE_RUNTIME_GID`, `OFFICE_SUPPORT_GID` | Code contains sheet-specific defaults |
| `OFFICE_SCRIPTS_DIR` | `<OFFICE_ROOT>/src/office_runtime/scripts` |
| `OFFICE_STRICT` | `false`; only literal case-insensitive `true` enables |

Office/staff authenticate locally and read Sheets with read-only scope. Their key
file must not be confused with the GCP Repo Health assigned-identity profile.

## Capture

| Variable | Default / meaning |
|---|---|
| `OFFICE_CAPTURE_PROCESSING_MODEL` | `gpt-4o-mini` fallback |
| `OFFICE_CAPTURE_TRANSCRIPTION_MODEL` | `gpt-4o-mini-transcribe` fallback |
| `OFFICE_FEEDBACK_AUDIO_ROOT` | Preferred audio root |
| `OFFICE_CAPTURE_AUDIO_ROOT` | Legacy/fallback audio root |
| `OFFICE_CAPTURE_MAX_AUDIO_BYTES` | 25 MiB code default |
| `OPENAI_API_KEY` | Consumed by OpenAI client; no repository default |

Audio root resolution falls back to `inbox/human_feedback_audio`. CLI flags can
override models/root/size for a run.

## Repo Health frozen profiles

| Variable | Requirement |
|---|---|
| `REPO_HEALTH_PROFILE` | `local` default; CLI flag overrides |
| `REPO_HEALTH_POLICY_JSON` | Frozen JSON alternative to `--policy` |
| `REPO_HEALTH_RUN_ID`, `REPO_HEALTH_ATTEMPT` | Optional producer identity/attempt overrides |
| `GITHUB_TOKEN` | Optional remote-read authentication; allowlist still enforced |
| `SOURCE_COMMIT` | Required in GCP; must equal snapshot producer commit |
| `GOOGLE_CLOUD_PROJECT` | GCP project or discoverable through ADC |
| `REPO_HEALTH_GCS_BUCKET` | Required in GCP |
| `REPO_HEALTH_BQ_DATASET` | `repo_health` default |
| `GOOGLE_APPLICATION_CREDENTIALS` | Explicitly rejected in GCP profile |

## Terraform and automation

Terraform variables are `project_id`, `billing_account_id`, `region`,
`name_prefix`, `image`, `source_commit`, `policy_snapshot_json`, `dataset_id`,
`evidence_retention_days`, and `allow_destroy`. `preflight.sh` reads
`GCP_PROJECT_ID`, `GCP_BILLING_ACCOUNT_ID`, and optional `GCP_REGION`.
Provider configuration is PR-OD5 scope and all provider commands remain
unexecuted in PR-OD4.

systemd user services do not inherit an interactive shell/Conda activation.
Configure a reviewed local unit/environment; never embed secrets in committed
units or logs.
