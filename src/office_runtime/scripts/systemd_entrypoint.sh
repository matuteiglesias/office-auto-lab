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
case "${routine}" in
  office-v2-generation)
    # M8 owns the canonical coherent-generation command. Keep this adapter
    # fail-closed until the scheduler branch is rebased onto that runtime;
    # never substitute the legacy Office or Staff routines here.
    lock_dir="${OFFICE_V2_LOCK_DIR:-${OFFICE_ROOT}/artifacts/locks/office-v2-generation.lock}"
    mkdir -p "$(dirname "${lock_dir}")"
    if ! mkdir "${lock_dir}" 2>/dev/null; then
      echo "Office v2 generation skipped: another generation is running (lock=${lock_dir})" >&2
      exit 75
    fi
    cleanup_lock() {
      rmdir "${lock_dir}" 2>/dev/null || true
    }
    trap cleanup_lock EXIT
    echo "Office v2 generation adapter is awaiting the canonical M8 runtime command" >&2
    exit 78
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
    exec "${OFFICE_RUN}" evidence files \
      --roots "${roots[@]}" \
      --start "${today}" \
      --end "${today}" \
      --out "${out_root}/fs_trace/${today}_${today}.jsonl" \
      --max-depth "${OFFICE_EVIDENCE_MAX_DEPTH:-8}"
    ;;
  *)
    echo "unsupported scheduled routine: ${routine:-<empty>}" >&2
    echo "expected one of: office-v2-generation, office-compile, staff-briefs, evidence-daily" >&2
    exit 2
    ;;
esac
