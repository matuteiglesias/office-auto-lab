REPOS=(
  "/home/matias/repos/thesis"
  "/home/matias/repos/indice-pobreza-UBA"
  "/home/matias/Documents/link/Pobreza"
  "/home/matias/repos/atlas-site"
)


for repo in "${REPOS[@]}"; do
  if [ ! -d "$repo" ]; then
    echo "[SKIP] not a dir: $repo" >&2
    continue
  fi

  echo "[BOOT] $repo"
  mkdir -p "$repo/notes" "$repo/artifacts" "$repo/scripts"

  # 1) .gitignore
  if [ ! -f "$repo/.gitignore" ]; then
    cat >"$repo/.gitignore" <<'EOF'
artifacts/
.venv/
venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.tox/
dist/
build/
.eggs/
*.egg-info/
.node_modules/
node_modules/
.cache/
.DS_Store
.env
.env.*
EOF
  fi

  # 2) notes/runbook.md (canonical)
  if [ ! -f "$repo/notes/runbook.md" ]; then
    cat >"$repo/notes/runbook.md" <<'EOF'
# Runbook

## Purpose
(TODO)

## Quickstart
(TODO)

## Smoke
Command: `make smoke`

Expected outputs:
- `artifacts/` only

## Troubleshooting
(TODO)
EOF
  fi

  # 3) notes/contracts.md
  if [ ! -f "$repo/notes/contracts.md" ]; then
    cat >"$repo/notes/contracts.md" <<'EOF'
# Contracts

## Repo smoke (root)
Purpose: basic offline validation, bounded runtime, no network.
Command: `make smoke`
Outputs: `artifacts/` only
Checks: (TODO add 1-3 assertions)
EOF
  fi

  # 4) README.md (keep lightweight; do not overwrite existing)
  if [ ! -f "$repo/README.md" ]; then
    cat >"$repo/README.md" <<'EOF'
# Project

See `notes/runbook.md`.
EOF
  fi

  # 5) Makefile with offline smoke
  if [ ! -f "$repo/Makefile" ] && [ ! -f "$repo/makefile" ]; then
    cat >"$repo/Makefile" <<'EOF'
.PHONY: smoke

smoke:
	@mkdir -p artifacts
	@echo "TODO: implement offline smoke" | tee artifacts/smoke.txt
	@test -s artifacts/smoke.txt
EOF
  fi
done

