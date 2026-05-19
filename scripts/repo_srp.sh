#!/usr/bin/env bash
# repo_srp.sh
# Snapshot Reading Protocol (SRP) scanner.
# Purpose: quick, low-noise repo triage: git -> key files -> entrypoints -> minimal risk peek.
# Complementary to repo_explorer.sh (no du/tree/largest here).

set -euo pipefail

usage() {
  cat <<'USAGE'
repo_srp.sh
Usage:
  ./repo_srp.sh /path/to/repo [options]
  ./repo_srp.sh --list /path/to/repos.txt [options]

Options:
  --list FILE           File with repo paths (one per line)
  --maxdepth N          Max depth for entrypoint file search (default 3)
  --full                Do NOT stop early; run deeper risk scan too
  --risk-only           Only run risk scan (credentials/network + writes) and exit
  --outdir DIR          If set, write a per-repo report file into DIR
  --summary-csv FILE    Append one summary CSV line per repo into FILE
  --no-color            Disable ANSI colors
  -h, --help            Show help

Notes:
  - Uses rg if available; falls back to grep/find.
  - Avoids heavy scans by design. Use repo_explorer.sh for deeper archaeology.

USAGE
}

MAXDEPTH=3
FULL=0
RISK_ONLY=0
LIST_FILE=""
OUTDIR=""
SUMMARY_CSV=""
NO_COLOR=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list) LIST_FILE="${2:?missing FILE}"; shift 2 ;;
    --maxdepth) MAXDEPTH="${2:?missing N}"; shift 2 ;;
    --full) FULL=1; shift 1 ;;
    --risk-only) RISK_ONLY=1; shift 1 ;;
    --outdir) OUTDIR="${2:?missing DIR}"; shift 2 ;;
    --summary-csv) SUMMARY_CSV="${2:?missing FILE}"; shift 2 ;;
    --no-color) NO_COLOR=1; shift 1 ;;
    -h|--help) usage; exit 0 ;;
    *) break ;;
  esac
done

have() { command -v "$1" >/dev/null 2>&1; }

if [[ "${NO_COLOR}" -eq 1 ]]; then
  C0=""; C1=""; C2=""; C3=""; C4=""
else
  C0=$'\033[0m'
  C1=$'\033[1;34m'  # blue
  C2=$'\033[1;33m'  # yellow
  C3=$'\033[1;31m'  # red
  C4=$'\033[1;32m'  # green
fi

sep() {
  printf "\n%s== %s ==%s\n" "${C1}" "$1" "${C0}"
}

warn() { printf "%sWARN:%s %s\n" "${C2}" "${C0}" "$*" >&2; }
err() { printf "%sERR:%s %s\n" "${C3}" "${C0}" "$*" >&2; }

# A deliberately small ignore set for SRP (repo_explorer has a bigger one).
IGNORE_DIRS_REGEX='(\.git|\.venv|venv|node_modules|__pycache__|\.mypy_cache|\.pytest_cache|\.ruff_cache|\.tox|dist|build|\.next|\.cache)'
IGNORE_FIND_PRUNE=(
  -name .git -o -name .venv -o -name venv -o -name node_modules -o -name __pycache__ -o
  -name .mypy_cache -o -name .pytest_cache -o -name .ruff_cache -o -name .tox -o -name dist -o -name build -o
  -name .next -o -name .cache
)

abs_path() {
  local p="$1"
  (cd "$p" 2>/dev/null && pwd) || return 1
}

is_git_repo() {
  local dir="$1"
  (cd "$dir" && git rev-parse --is-inside-work-tree >/dev/null 2>&1)
}

git_summary() {
  local dir="$1"
  local branch sha dirty
  branch=""; sha=""; dirty="n/a"
  if is_git_repo "$dir"; then
    branch="$(cd "$dir" && git branch --show-current 2>/dev/null || true)"
    sha="$(cd "$dir" && git rev-parse --short HEAD 2>/dev/null || true)"
    if (cd "$dir" && git diff --quiet && git diff --cached --quiet); then
      dirty="clean"
    else
      dirty="dirty"
    fi
    printf "%s\t%s\t%s\n" "${branch:-?}" "${sha:-?}" "${dirty}"
  else
    printf "not_git\t-\t-\n"
  fi
}

file_flag() {
  local dir="$1"; shift
  local f
  for f in "$@"; do
    if [[ -e "$dir/$f" ]]; then
      printf "%s " "$f"
    fi
  done
}

# Quick target extraction without invoking make -qp (which can be slow/side-effecty).
make_targets_preview() {
  local dir="$1"
  local mf=""
  if [[ -f "$dir/Makefile" ]]; then mf="$dir/Makefile"; fi
  if [[ -f "$dir/makefile" ]]; then mf="$dir/makefile"; fi
  if [[ -z "$mf" ]]; then return 0; fi

  awk '
    BEGIN { FS=":" }
    /^[A-Za-z0-9_.-]+[[:space:]]*:/ {
      t=$1
      gsub(/[[:space:]]+/, "", t)
      if (t !~ /^\./ && t !~ /%/ && t != "PHONY") print t
    }
  ' "$mf" 2>/dev/null | sort -u | head -n 120
}

find_entrypoint_files() {
  local dir="$1"
  # Look for likely entrypoint scripts near root.
  (cd "$dir" && find . -maxdepth "${MAXDEPTH}" \( "${IGNORE_FIND_PRUNE[@]}" \) -prune -o \
    -type f \( \
      -iname "Makefile" -o -iname "makefile" -o \
      -iname "RUNBOOK.md" -o -iname "runbook.md" -o \
      -iname "README.md" -o \
      -iname "*smoke*" -o -iname "run*.sh" -o -iname "*golden*" -o \
      -iname "main.py" -o -iname "__main__.py" -o -iname "cli.py" \
    \) -print 2>/dev/null | sort | head -n 200)
}

python_cli_hits() {
  local dir="$1"
  if have rg; then
    (cd "$dir" && rg -n "if __name__ == ['\"]__main__['\"]|argparse\.ArgumentParser|typer\.Typer|click\.(command|group)" . \
      --hidden --glob '!.git/*' --glob '!.venv/*' --glob '!venv/*' --glob '!node_modules/*' \
      2>/dev/null | cut -d: -f1 | sort -u | head -n 60)
  else
    (cd "$dir" && grep -RIn --exclude-dir=.git --exclude-dir=.venv --exclude-dir=venv --exclude-dir=node_modules \
      -E "if __name__ == ['\"]__main__['\"]|argparse\.ArgumentParser|typer\.Typer|click\.(command|group)" . \
      2>/dev/null | cut -d: -f1 | sort -u | head -n 60)
  fi
}

risk_scan() {
  local dir="$1"

  local net_pat='(requests|httpx|urllib3|boto3|openai|imaplib|smtplib|googleapiclient|oauth|token)'
  local cred_pat='(API_KEY|SECRET|PASSWORD|ACCESS_KEY|PRIVATE_KEY|BEARER|Authorization:)'
  local write_pat='(open\(.+['\''"]w|to_csv\(|to_parquet\(|sqlite3\.connect\(|Path\(.+\)\.write_text|write_bytes|shutil\.rmtree|rm -rf|os\.remove\(|unlink\()'

  sep "EXTERNAL TOUCHPOINTS (risk scan)"
  echo "patterns: network/oauth + credential markers + writes/destructive ops"

  if have rg; then
    echo
    echo "-- network/oauth hits (top 40)"
    (cd "$dir" && rg -n "$net_pat" . --hidden --glob '!.git/*' --glob '!node_modules/*' 2>/dev/null | head -n 40) || true

    echo
    echo "-- credential-marker hits (top 40)"
    (cd "$dir" && rg -n "$cred_pat" . --hidden --glob '!.git/*' --glob '!node_modules/*' 2>/dev/null | head -n 40) || true

    echo
    echo "-- writes/destructive hits (top 60)"
    (cd "$dir" && rg -n "$write_pat" . --hidden --glob '!.git/*' --glob '!node_modules/*' 2>/dev/null | head -n 60) || true
  else
    echo
    echo "-- network/oauth hits (top 40)"
    (cd "$dir" && grep -RIn --exclude-dir=.git --exclude-dir=node_modules -E "$net_pat" . 2>/dev/null | head -n 40) || true

    echo
    echo "-- credential-marker hits (top 40)"
    (cd "$dir" && grep -RIn --exclude-dir=.git --exclude-dir=node_modules -E "$cred_pat" . 2>/dev/null | head -n 40) || true

    echo
    echo "-- writes/destructive hits (top 60)"
    (cd "$dir" && grep -RIn --exclude-dir=.git --exclude-dir=node_modules -E "$write_pat" . 2>/dev/null | head -n 60) || true
  fi
}

minimal_write_peek() {
  local dir="$1"
  local write_pat='(open\(.+['\''"]w|to_csv\(|to_parquet\(|sqlite3\.connect\(|Path\(.+\)\.write_text|write_bytes|shutil\.rmtree|rm -rf|os\.remove\(|unlink\()'
  echo
  echo "${C2}minimal write-risk peek (top 25)${C0}"
  if have rg; then
    (cd "$dir" && rg -n "$write_pat" . --hidden --glob '!.git/*' --glob '!node_modules/*' 2>/dev/null | head -n 25) || true
  else
    (cd "$dir" && grep -RIn --exclude-dir=.git --exclude-dir=node_modules -E "$write_pat" . 2>/dev/null | head -n 25) || true
  fi
}

summarize_to_csv() {
  local dir="$1"
  local name branch sha dirty keyfiles entrypoints risk_hint

  name="$(basename "$dir")"
  read -r branch sha dirty < <(git_summary "$dir" | awk -F'\t' '{print $1, $2, $3}')

  keyfiles="$(file_flag "$dir" RUNBOOK.md runbook.md Makefile makefile pyproject.toml requirements.txt Dockerfile docker-compose.yml README.md)"
  keyfiles="${keyfiles:-none}"

  # Entry points hint: prefer make targets smoke/golden/run/test if present, else scripts.
  entrypoints=""
  if [[ -f "$dir/Makefile" || -f "$dir/makefile" ]]; then
    local mt
    mt="$(make_targets_preview "$dir" | rg -n "smoke|golden|run|test|check|lint|build|deploy" 2>/dev/null | head -n 5 || true)"
    if [[ -n "$mt" ]]; then
      entrypoints="make:{${mt//$'\n'/;}}"
    fi
  fi
  if [[ -z "$entrypoints" ]]; then
    local scripts
    scripts="$(cd "$dir" && find . -maxdepth "${MAXDEPTH}" \( "${IGNORE_FIND_PRUNE[@]}" \) -prune -o \
      -type f \( -iname "*smoke*" -o -iname "run*.sh" -o -iname "*golden*" \) -print 2>/dev/null | head -n 5 | tr '\n' ';')"
    entrypoints="${scripts:-none}"
  fi

  # Very cheap risk hint: presence of .env (not example)
  if [[ -f "$dir/.env" ]]; then risk_hint=".env_present"; else risk_hint="-"; fi

  printf "%s,%s,%s,%s,%q,%q,%s\n" "$name" "$branch" "$sha" "$dirty" "$keyfiles" "$entrypoints" "$risk_hint"
}

scan_one_repo() {
  local dir="$1"
  local abs
  abs="$(abs_path "$dir" 2>/dev/null || true)"
  if [[ -z "$abs" || ! -d "$abs" ]]; then
    err "Not a directory: $dir"
    return 2
  fi

  local report=""
  if [[ -n "$OUTDIR" ]]; then
    mkdir -p "$OUTDIR"
    local safe_name
    safe_name="$(basename "$abs")"
    report="$OUTDIR/${safe_name}.srp.txt"
    : > "$report"
    exec > >(tee -a "$report") 2>&1
  fi

  sep "SRP CONTEXT"
  echo "timestamp: $(date -Iseconds)"
  echo "repo: $abs"

  sep "GIT STATUS"
  if is_git_repo "$abs"; then
    echo "repo_root: $(cd "$abs" && git rev-parse --show-toplevel)"
    echo "branch / sha / dirty:"
    git_summary "$abs" | awk -F'\t' '{printf "  branch=%s  sha=%s  state=%s\n",$1,$2,$3}'
    echo "last commit:"
    (cd "$abs" && git log -1 --oneline --decorate 2>/dev/null || true)
  else
    echo "not a git repo (or git not available)"
  fi

  sep "TOP LEVEL FILES OF INTEREST"
  echo "present:"
  local kf
  kf="$(file_flag "$abs" RUNBOOK.md runbook.md Makefile makefile pyproject.toml requirements.txt requirements-dev.txt poetry.lock \
    Dockerfile docker-compose.yml compose.yml package.json README.md .env.example .env.sample .python-version .env)"
  echo "  ${kf:-none}"

  if [[ "$RISK_ONLY" -eq 1 ]]; then
    risk_scan "$abs"
    return 0
  fi

  sep "ENTRYPOINT DISCOVERY"
  echo "1) likely entrypoint files (maxdepth=${MAXDEPTH})"
  find_entrypoint_files "$abs" | sed 's/^/  /'

  echo
  echo "2) make targets preview (filtered for likely ops)"
  if [[ -f "$abs/Makefile" || -f "$abs/makefile" ]]; then
    make_targets_preview "$abs" | rg -n "smoke|golden|run|test|check|lint|build|deploy|sync|materialize|ingest" 2>/dev/null \
      | head -n 40 | sed 's/^/  /' || true
  else
    echo "  none (no Makefile)"
  fi

  echo
  echo "3) python cli hints (files only, top 60)"
  python_cli_hits "$abs" | sed 's/^/  /' || true

  # Determine if we "found an entrypoint" in a practical sense
  local found=0
  if [[ -f "$abs/Makefile" || -f "$abs/makefile" ]]; then
    if make_targets_preview "$abs" | rg -q "smoke|golden|run|test|check"; then found=1; fi
  fi
  if [[ "$found" -eq 0 ]]; then
    if find_entrypoint_files "$abs" | rg -q "smoke|golden|run|RUNBOOK|runbook"; then found=1; fi
  fi

  if [[ "$found" -eq 1 && "$FULL" -eq 0 ]]; then
    sep "STOP EARLY (entrypoint found)"
    echo "Entry point likely exists. Skipping full risk scan. Use --full or --risk-only if needed."
    minimal_write_peek "$abs"
  else
    risk_scan "$abs"
  fi

  if [[ -n "$SUMMARY_CSV" ]]; then
    mkdir -p "$(dirname "$SUMMARY_CSV")"
    if [[ ! -f "$SUMMARY_CSV" ]]; then
      echo "repo,branch,sha,state,keyfiles,entrypoints,risk_hint" > "$SUMMARY_CSV"
    fi
    summarize_to_csv "$abs" >> "$SUMMARY_CSV"
  fi

  if [[ -n "$OUTDIR" ]]; then
    # Reset stdout redirection for next repo in batch.
    exec >/dev/tty 2>/dev/null || true
    exec 2>/dev/tty 2>/dev/null || true
    echo "wrote: $report"
  fi
}

# Build repo list: either a single positional arg or --list file.
REPOS=()
if [[ -n "$LIST_FILE" ]]; then
  if [[ ! -f "$LIST_FILE" ]]; then err "List file not found: $LIST_FILE"; exit 2; fi
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    REPOS+=("$line")
  done < "$LIST_FILE"
else
  if [[ $# -lt 1 ]]; then usage; exit 2; fi
  REPOS+=("$1")
fi

for r in "${REPOS[@]}"; do
  scan_one_repo "$r"
done

