#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
cd "${REPO_ROOT}"

mkdir -p artifacts/logs/wrapper artifacts/logs/daily

DATE="$(date +%F)"
TS="$(date +%Y%m%dT%H%M%S)"
SAFE_CMD="$(printf '%s_' "$@" | tr -cs 'A-Za-z0-9_.=-' '_' | cut -c1-80)"
LOG_PATH="artifacts/logs/wrapper/${TS}_${SAFE_CMD:-office_run}.log"

export PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}"

{
  echo "ts=${TS}"
  echo "repo=${REPO_ROOT}"
  echo "cmd=python3 -m office_runtime.cli $*"
  echo
} > "${LOG_PATH}"

set +e
python3 -m office_runtime.cli "$@" >> "${LOG_PATH}" 2>&1
CODE=$?
set -e

if [[ "${CODE}" -ne 0 ]]; then
  HHMM="$(date +%H:%M)"
  MODULE="${1:-unknown}"
  SUB="${2:-}"
  if [[ -n "${SUB}" ]]; then
    MODULE="${MODULE}.${SUB}"
  fi

  echo "${HHMM} wrapper.${MODULE} error code=${CODE} log=${LOG_PATH}" >> "artifacts/logs/daily/${DATE}.ledger.log"
fi

exit "${CODE}"
