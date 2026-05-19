#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./repo_prereqs_scan.sh /abs/path/repoA /abs/path/repoB ...
#
# Output:
#   TSV header + one row per repo: repo_path, workdir, runbook_path, output_paths, smoke_cmd, notes

echo -e "repo_path\tworkdir\trunbook_path\toutput_paths\tsmoke_cmd\tnotes"

pick_runbook() {
  local root="$1"
  # Prefer canonical
  if [ -f "$root/notes/runbook.md" ]; then
    echo "$root/notes/runbook.md"
    return 0
  fi
  # Else: best effort discovery
  local found=""
  found="$(find "$root" -maxdepth 4 -type f \( -iname 'runbook.md' -o -iname 'RUNBOOK.md' -o -iname 'README.md' -o -iname 'README.txt' \) \
    -not -path '*/.git/*' -not -path '*/artifacts/*' -not -path '*/node_modules/*' 2>/dev/null | head -n 1 || true)"
  if [ -n "$found" ]; then
    echo "$found"
    return 0
  fi
  echo ""  # none
}

for p in "$@"; do
  if [ ! -d "$p" ]; then
    echo -e "\t\t\t\t\tSKIP:not_a_dir:$p" >&2
    continue
  fi

  root="$(cd "$p" && pwd)"

  # Prefer git toplevel if available
  if (cd "$root" && git rev-parse --is-inside-work-tree >/dev/null 2>&1); then
    repo_root="$(cd "$root" && git rev-parse --show-toplevel)"
  else
    repo_root="$root"
  fi

  workdir="$repo_root"

  runbook="$(pick_runbook "$workdir")"
  notes=""
  if [ -z "$runbook" ]; then
    runbook="$workdir/notes/runbook.md"
    notes="MISSING_RUNBOOK:create_canonical"
  elif [ "$runbook" != "$workdir/notes/runbook.md" ]; then
    notes="RUNBOOK_NONCANON:$runbook"
  fi

  output_paths="$workdir/artifacts"
  smoke_cmd="make smoke"

  echo -e "${repo_root}\t${workdir}\t${runbook}\t${output_paths}\t${smoke_cmd}\t${notes}"
done

