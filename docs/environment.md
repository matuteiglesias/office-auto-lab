# Environment setup for local + systemd runs

This project can run in lean environments, but commands that touch office/staff flows require Python dependencies (for example `numpy`, `pandas`).

## Local venv (recommended)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python3 -m office_runtime.cli --help
make imports
```

## Conda workflow (optional)

```bash
conda activate new_env
pip install -r requirements.txt
PYTHONPATH=src python3 -m office_runtime.cli --help
make imports
```

## Notes for systemd user services

- User-level systemd services do **not** automatically inherit your interactive shell state.
- In particular, Conda activation from your terminal session is not automatically applied to `systemctl --user` services.
- If timers/services fail with missing Python packages, install dependencies into the Python environment used by systemd user services, or add explicit environment configuration in unit files (future hardening work).
- Current unit templates intentionally avoid fragile shell activation snippets.

## Quick verification checklist

```bash
python3 -m compileall src
make imports
PYTHONPATH=src python3 -m office_runtime.cli evidence files --roots . --start 2026-05-19 --end 2026-05-19 --out artifacts/evidence/fs_trace/env_check.jsonl --max-depth 1
```
