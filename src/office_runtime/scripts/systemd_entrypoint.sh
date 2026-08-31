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
    echo "expected one of: office-compile, staff-briefs, evidence-daily" >&2
    exit 2
    ;;
esac
