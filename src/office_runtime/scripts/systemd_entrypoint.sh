#!/usr/bin/env bash
set -euo pipefail

: "${OFFICE_ROOT:?OFFICE_ROOT must be configured by the systemd installer}"
: "${OFFICE_PYTHON:?OFFICE_PYTHON must be configured by the systemd installer}"

OFFICE_RUN="${OFFICE_ROOT}/src/office_runtime/scripts/office_run.sh"
if [[ ! -x "${OFFICE_RUN}" ]]; then
  echo "office runtime wrapper is missing or not executable: ${OFFICE_RUN}" >&2
  exit 2
fi

generation_lock_dir=""

run_receipted() {
  local producer_id="$1"
  shift
  local evidence_args=()
  while [[ "$#" -gt 0 && "$1" != "--" ]]; do
    evidence_args+=("$1")
    shift
  done
  if [[ "$#" -eq 0 ]]; then
    echo "receipt command separator is required" >&2
    exit 2
  fi
  shift
  if [[ -n "${OFFICE_PRODUCER_RECEIPT_RUNNER:-}" ]]; then
    exec "${OFFICE_PYTHON}" "${OFFICE_PRODUCER_RECEIPT_RUNNER}" \
      --producer "${producer_id}" \
      --cwd "${OFFICE_ROOT}" \
      "${evidence_args[@]}" \
      -- "$@"
  fi
  exec "$@"
}

routine="${1:-}"

run_v2_generation() {
  local mode="${1:-generation}"
  local generation_script="${OFFICE_ROOT}/src/office_runtime/scripts/run_generation_v2.py"
  local status
  generation_lock_dir="${OFFICE_ROOT}/artifacts/locks/office-v2-generation.lock"

  if [[ ! -f "${generation_script}" ]]; then
    echo "Office v2 generation runtime is missing: ${generation_script}" >&2
    return 78
  fi
  mkdir -p "$(dirname "${generation_lock_dir}")"
  if ! mkdir "${generation_lock_dir}" 2>/dev/null; then
    echo "Office v2 generation skipped: another generation is running (lock=${generation_lock_dir})" >&2
    return 75
  fi
  cleanup_lock() {
    if [[ -n "${generation_lock_dir}" ]] && ! rmdir "${generation_lock_dir}" 2>/dev/null; then
      echo "warning: could not remove Office v2 generation lock: ${generation_lock_dir}" >&2
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

run_evidence_daily() {
  local today="$1"
  local out_root="$2"
  local git_out="${out_root}/git_trace/${today}_${today}.jsonl"
  local files_out="${out_root}/fs_trace/${today}_${today}.jsonl"
  local activity_out="${out_root}/activity_trace/${today}_${today}.jsonl"
  local roots=()

  : "${OFFICE_EVIDENCE_ROOTS:?OFFICE_EVIDENCE_ROOTS must contain colon-separated absolute paths}"
  IFS=':' read -r -a roots <<< "${OFFICE_EVIDENCE_ROOTS}"
  if [[ "${#roots[@]}" -eq 0 ]]; then
    echo "no evidence roots configured" >&2
    return 2
  fi
  for root in "${roots[@]}"; do
    if [[ "${root}" != /* || ! -e "${root}" ]]; then
      echo "invalid configured evidence root: ${root}" >&2
      return 2
    fi
  done

  "${OFFICE_RUN}" evidence git \
    --roots "${roots[@]}" \
    --start "${today}" \
    --end "${today}" \
    --out "${git_out}"
  "${OFFICE_RUN}" evidence files \
    --roots "${roots[@]}" \
    --start "${today}" \
    --end "${today}" \
    --out "${files_out}" \
    --max-depth "${OFFICE_EVIDENCE_MAX_DEPTH:-8}"
  "${OFFICE_RUN}" evidence activity \
    --start "${today}" \
    --end "${today}" \
    --out "${activity_out}"
}

case "${routine}" in
  office-v2-generation)
    run_v2_generation generation
    ;;
  office-v2-shadow)
    run_v2_generation shadow
    ;;
  office-compile)
    run_receipted producer.local.office-compile \
      --evidence-changed "artifacts/v2/current.json" \
      --evidence-json 'artifacts/v2/current.json#/schema_version=ops.office-current-pointer.v2' \
      -- bash "${BASH_SOURCE[0]}" office-compile-inner
    ;;
  office-compile-inner)
    run_v2_generation generation
    ;;
  staff-briefs)
    exec "${OFFICE_RUN}" staff briefs
    ;;
  evidence-daily)
    today="$(date +%F)"
    out_root="${OFFICE_EVIDENCE_OUT_ROOT:-artifacts/evidence}"
    run_receipted producer.local.office-evidence-daily \
      --evidence-changed "${out_root}/git_trace/${today}_${today}.jsonl" \
      --evidence-changed "${out_root}/fs_trace/${today}_${today}.jsonl" \
      --evidence-changed "${out_root}/activity_trace/${today}_${today}.jsonl" \
      -- bash "${BASH_SOURCE[0]}" evidence-daily-inner "${today}" "${out_root}"
    ;;
  evidence-daily-inner)
    run_evidence_daily "$2" "$3"
    ;;
  *)
    echo "unsupported scheduled routine: ${routine:-<empty>}" >&2
    echo "expected one of: office-v2-generation, office-v2-shadow, office-compile, staff-briefs, evidence-daily" >&2
    exit 2
    ;;
esac
