#!/usr/bin/env bash
# repo_explorer.sh
# Usage:
#   ./repo_explorer.sh /path/to/repo
#   ./repo_explorer.sh /path/to/repo --depth 4 --max-depth-du 2 --largest 40
#
# Prints a lightweight snapshot to stdout (console). No files written.

set -euo pipefail

DIR="${1:-}"
shift || true

if [[ -z "${DIR}" || "${DIR}" == "-h" || "${DIR}" == "--help" ]]; then
  cat <<'USAGE'
repo_explorer.sh
Usage:
  ./repo_explorer.sh /path/to/repo [--depth N] [--max-depth-du N] [--largest N] [--no-ignore]

Options:
  --depth N         Directory walk depth (default 4)
  --max-depth-du N  du depth (default 2)
  --largest N       Show N largest files (default 40)
  --no-ignore       Do not ignore common heavy dirs (artifacts, venv, node_modules, etc)

Notes:
  - Prints to console only
  - Uses tree/rg if installed; falls back when missing
USAGE
  exit 0
fi

DEPTH=4
DU_DEPTH=2
LARGEST=40
NO_IGNORE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --depth) DEPTH="${2:?missing N}"; shift 2 ;;
    --max-depth-du) DU_DEPTH="${2:?missing N}"; shift 2 ;;
    --largest) LARGEST="${2:?missing N}"; shift 2 ;;
    --no-ignore) NO_IGNORE=1; shift 1 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ ! -d "${DIR}" ]]; then
  echo "Not a directory: ${DIR}" >&2
  exit 2
fi

# Resolve to absolute path for clarity
DIR="$(cd "${DIR}" && pwd)"

have() { command -v "$1" >/dev/null 2>&1; }

sep() {
  printf "\n============================================================\n"
  printf "%s\n" "$1"
  printf "============================================================\n"
}

# Ignore patterns to avoid noisy/heavy scans
IGNORE_DIRS_REGEX='(\.git|artifacts|\.venv|venv|node_modules|__pycache__|\.mypy_cache|\.pytest_cache|\.ruff_cache|\.tox|dist|build|\.next|\.cache)'
IGNORE_FIND_PRUNE=(
  -name .git -o -name artifacts -o -name .venv -o -name venv -o -name node_modules -o -name __pycache__ -o
  -name .mypy_cache -o -name .pytest_cache -o -name .ruff_cache -o -name .tox -o -name dist -o -name build -o
  -name .next -o -name .cache
)

if [[ "${NO_IGNORE}" -eq 1 ]]; then
  IGNORE_DIRS_REGEX='(\.git)'
  IGNORE_FIND_PRUNE=(-name .git)
fi

sep "0) CONTEXT"
echo "timestamp: $(date -Iseconds)"
echo "host: $(hostname 2>/dev/null || true)"
echo "cwd: ${DIR}"
echo "shell: ${SHELL:-unknown}"
echo "user: ${USER:-unknown}"

sep "1) GIT STATUS (if available)"
if (cd "${DIR}" && git rev-parse --is-inside-work-tree >/dev/null 2>&1); then
  (cd "${DIR}" && echo "repo_root: $(git rev-parse --show-toplevel)")
  (cd "${DIR}" && git status -sb || true)
  (cd "${DIR}" && git log -1 --oneline --decorate || true)
  (cd "${DIR}" && git branch --show-current 2>/dev/null || true)
else
  echo "not a git repo (or git not available)"
fi

sep "2) TOP LEVEL FILES OF INTEREST"
(
  cd "${DIR}"
  ls -la \
    Makefile makefile pyproject.toml requirements.txt requirements-dev.txt Pipfile poetry.lock \
    package.json pnpm-lock.yaml yarn.lock \
    Dockerfile docker-compose.yml compose.yml \
    .env.example .env.sample .python-version \
    README.md README.txt RUNBOOK.md runbook.md \
    2>/dev/null || true
)

sep "3) DISK USAGE SUMMARY (du)"
if have du; then
  (cd "${DIR}" && du -h --max-depth="${DU_DEPTH}" . 2>/dev/null | sort -h | tail -n 200)
else
  echo "du not found"
fi

sep "4) LARGEST FILES (excluding common heavy dirs if not --no-ignore)"
# Using find -printf for timestamp and size
if have find; then
  (
    cd "${DIR}"
    # Prune heavy dirs (unless --no-ignore)
    find . \( "${IGNORE_FIND_PRUNE[@]}" \) -prune -o \
      -type f -printf '%s\t%TY-%Tm-%Td %TH:%TM\t%p\n' 2>/dev/null \
      | sort -nr | head -n "${LARGEST}"
  )
else
  echo "find not found"
fi

sep "5) CHRONOLOGICAL TREE VIEW (recent layers)"
if have tree; then
  (
    cd "${DIR}"
    tree -a -p -u -g -D -t -L "${DEPTH}" -I "${IGNORE_DIRS_REGEX}" 2>/dev/null || true
  )
else
  echo "tree not found, using find fallback (showing last 200 entries by time)"
  (
    cd "${DIR}"
    find . \( "${IGNORE_FIND_PRUNE[@]}" \) -prune -o \
      -printf '%TY-%Tm-%Td %TH:%TM\t%y\t%p\n' 2>/dev/null \
      | sort | tail -n 200
  )
fi

sep "6) ENTRYPOINT DISCOVERY"
echo "6.1) smoke-ish / run-ish scripts near root"
(
  cd "${DIR}"
  find . -maxdepth 3 \( "${IGNORE_FIND_PRUNE[@]}" \) -prune -o \
    -type f \( -iname "*smoke*" -o -iname "run*.sh" -o -iname "*.mk" -o -iname "Makefile" -o -iname "makefile" \) \
    -print 2>/dev/null | sort | head -n 200
)

echo
echo "6.2) Python CLIs (argparse / typer / click / __main__)"
if have rg; then
  (
    cd "${DIR}"
    rg -n "if __name__ == ['\"]__main__['\"]|argparse\.ArgumentParser|typer\.Typer|click\.(command|group)" . \
      --hidden --glob '!.git/*' --glob '!artifacts/*' 2>/dev/null | head -n 200
  )
else
  echo "rg not found, using grep fallback (less precise)"
  (
    cd "${DIR}"
    grep -RIn --exclude-dir=.git --exclude-dir=artifacts --exclude-dir=node_modules \
      -E "if __name__ == ['\"]__main__['\"]|argparse\.ArgumentParser|typer\.Typer|click\.(command|group)" . \
      2>/dev/null | head -n 200
  )
fi

echo
echo "6.3) Make targets preview (first 120 target lines)"
if have make; then
  (
    cd "${DIR}"
    make -qp 2>/dev/null | awk '/^[A-Za-z0-9][^$#\/\t=]*:/{print}' | head -n 120
  ) || true
else
  echo "make not found"
fi

sep "7) EXTERNAL TOUCHPOINTS (risk scan)"
echo "7.1) Network and credential hotspots"
if have rg; then
  (
    cd "${DIR}"
    rg -n "(requests|httpx|urllib3|boto3|openai|imaplib|smtplib|googleapiclient|oauth|token|API_KEY|SECRET|PASSWORD)" . \
      --hidden --glob '!.git/*' --glob '!artifacts/*' 2>/dev/null | head -n 200
  )
else
  (
    cd "${DIR}"
    grep -RIn --exclude-dir=.git --exclude-dir=artifacts --exclude-dir=node_modules \
      -E "(requests|httpx|urllib3|boto3|openai|imaplib|smtplib|googleapiclient|oauth|token|API_KEY|SECRET|PASSWORD)" . \
      2>/dev/null | head -n 200
  )
fi

echo
echo "7.2) Potential writes and destructive operations"
if have rg; then
  (
    cd "${DIR}"
    rg -n "(open\(.+['\"]w|to_csv\(|to_parquet\(|sqlite3\.connect\(|Path\(.+\)\.write_text|write_bytes|shutil\.rmtree|rm -rf)" . \
      --hidden --glob '!.git/*' --glob '!artifacts/*' 2>/dev/null | head -n 200
  )
else
  (
    cd "${DIR}"
    grep -RIn --exclude-dir=.git --exclude-dir=artifacts --exclude-dir=node_modules \
      -E "(open\(.+['\"]w|to_csv\(|to_parquet\(|sqlite3\.connect\(|Path\(.+\)\.write_text|write_bytes|shutil\.rmtree|rm -rf)" . \
      2>/dev/null | head -n 200
  )
fi

sep "DONE"
echo "Snapshot printed. No files written."

