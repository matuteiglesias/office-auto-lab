#!/usr/bin/env bash
set -euo pipefail

missing=0
for command_name in terraform gcloud docker git python3; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'MISSING command=%s\n' "$command_name" >&2
    missing=1
  else
    printf 'OK command=%s path=%s\n' "$command_name" "$(command -v "$command_name")"
  fi
done

for variable_name in GCP_PROJECT_ID GCP_BILLING_ACCOUNT_ID GCP_REGION; do
  if [[ -z "${!variable_name:-}" ]]; then
    printf 'MISSING env=%s\n' "$variable_name" >&2
    missing=1
  else
    printf 'OK env=%s\n' "$variable_name"
  fi
done

if (( missing )); then
  printf 'BLOCKED missing local command or required environment input\n' >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

git diff --quiet && git diff --cached --quiet || { echo 'BLOCKED git worktree is not clean' >&2; exit 3; }
terraform -chdir=infra/gcp version
terraform -chdir=infra/gcp init -backend=false -input=false
terraform -chdir=infra/gcp fmt -check -recursive
terraform -chdir=infra/gcp validate
docker info >/dev/null
gcloud auth application-default print-access-token >/dev/null
gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectId)' >/dev/null
gcloud billing accounts describe "$GCP_BILLING_ACCOUNT_ID" --format='value(name)' >/dev/null
python3 -m json.tool fixtures/gcp_policy_snapshot.json >/dev/null

printf 'READY project=%s billing=%s region=%s commit=%s\n' \
  "$GCP_PROJECT_ID" "$GCP_BILLING_ACCOUNT_ID" "$GCP_REGION" "$(git rev-parse HEAD)"
