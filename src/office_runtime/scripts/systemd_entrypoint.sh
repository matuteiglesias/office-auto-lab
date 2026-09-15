#!/usr/bin/env bash
set -euo pipefail

: "${OFFICE_ROOT:?OFFICE_ROOT must be configured by the systemd installer}"
: "${OFFICE_PYTHON:?OFFICE_PYTHON must be configured by the systemd installer}"

OFFICE_RUN="${OFFICE_ROOT}/src/office_runtime/scripts/office_run.sh"
if [[ ! -x "${OFFICE_RUN}" ]]; then
  echo "office runtime wrapper is missing or not executable: ${OFFICE_RUN}" >&2
  exit 2
fi

routine="${1:-}"

run_v2_generation() {
  local mode="${1:-generation}"
  local lock_dir="${OFFICE_ROOT}/artifacts/locks/office-v2-generation.lock"
  local generation_script="${OFFICE_ROOT}/src/office_runtime/scripts/run_generation_v2.py"
  local status

  if [[ ! -f "${generation_script}" ]]; then
    echo "Office v2 generation runtime is missing: ${generation_script}" >&2
    return 78
  fi
  mkdir -p "$(dirname "${lock_dir}")"
  if ! mkdir "${lock_dir}" 2>/dev/null; then
    echo "Office v2 generation skipped: another generation is running (lock=${lock_dir})" >&2
    return 75
  fi
  cleanup_lock() {
    if ! rmdir "${lock_dir}" 2>/dev/null; then
      echo "warning: could not remove Office v2 generation lock: ${lock_dir}" >&2
    fi
    return 0
  }
  trap cleanup_lock EXIT

  export PYTHONPATH="${OFFICE_ROOT}/src:${PYTHONPATH:-}"
  if [[ "${mode}" == "shadow" ]]; then
    if "${OFFICE_PYTHON}" "${generation_script}" --shadow; then
      status=0
    else
      status=$?
    fi
  else
    if "${OFFICE_PYTHON}" "${generation_script}"; then
      status=0
    else
      status=$?
    fi
  fi
  return "${status}"
}

case "${routine}" in
  office-v2-generation)
    run_v2_generation generation
    ;;
  office-v2-shadow)
    run_v2_generation shadow
    ;;
  office-compile)
    exec "${OFFICE_RUN}" office compile
    ;;
  staff-briefs)
    exec "${OFFICE_RUN}" staff briefs
    ;;
  evidence-daily)
    : "${OFFICE_EVIDENCE_ROOTS:?OFFICE_EVIDENCE_ROOTS must contain colon-separated absolute paths}"
    IFS=':' read -r -a roots <<< "${OFFICE_EVIDENCE_ROOTS}"
    if [[ "${#roots[@]}" -eq 0 ]]; then
      echo "no evidence roots configured" >&2
      exit 2
    fi
    for root in "${roots[@]}"; do
      if [[ "${root}" != /* || ! -e "${root}" ]]; then
        echo "invalid configured evidence root: ${root}" >&2
        exit 2
      fi
    done

    today="$(date +%F)"
    out_root="${OFFICE_EVIDENCE_OUT_ROOT:-artifacts/evidence}"
    "${OFFICE_RUN}" evidence git \
      --roots "${roots[@]}" \
      --start "${today}" \
      --end "${today}" \
      --out "${out_root}/git_trace/${today}_${today}.jsonl"
    "${OFFICE_RUN}" evidence files \
      --roots "${roots[@]}" \
      --start "${today}" \
      --end "${today}" \
      --out "${out_root}/fs_trace/${today}_${today}.jsonl" \
      --max-depth "${OFFICE_EVIDENCE_MAX_DEPTH:-8}"
    exec "${OFFICE_RUN}" evidence activity \
      --start "${today}" \
      --end "${today}" \
      --out "${out_root}/activity_trace/${today}_${today}.jsonl"
    ;;
  *)
    echo "unsupported scheduled routine: ${routine:-<empty>}" >&2
    echo "expected one of: office-v2-generation, office-v2-shadow, office-compile, staff-briefs, evidence-daily" >&2
    exit 2
    ;;
esac
