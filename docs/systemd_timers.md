# User-level systemd timer scaffolding

These are **opt-in templates** for background operation. They are not auto-installed or auto-enabled.

## Important default path

The provided units assume this repository path:

- `/home/matias/repos/office-auto-lab`

If your local checkout is elsewhere, edit both `WorkingDirectory=` and `ExecStart=` paths before installing.

## Install user units

```bash
mkdir -p ~/.config/systemd/user
cp systemd/user/*.service systemd/user/*.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now office-compile.timer
systemctl --user enable --now staff-briefs.timer
systemctl --user enable --now evidence-daily.timer
systemctl --user list-timers
```

## Inspect runs

```bash
systemctl --user status office-compile.service
journalctl --user -u office-compile.service -n 100 --no-pager
tail -n 30 artifacts/logs/daily/*.ledger.log
find artifacts/logs/wrapper -type f | tail
```

## Disable timers

```bash
systemctl --user disable --now office-compile.timer
systemctl --user disable --now staff-briefs.timer
systemctl --user disable --now evidence-daily.timer
```

## Service behavior notes

- Units call `src/office_runtime/scripts/office_run.sh` (wrapper), not Python modules directly.
- `office_run.sh` preserves child exit codes, captures stdout/stderr to wrapper logs, and appends compact daily ledger error lines on failures.
- `staff-briefs.service` intentionally runs `daily --scan-mode existing` so bundle + briefs are executed together using existing scans.
- Python dependencies/environment (for example `numpy`, `pandas`) must be available to the user-level systemd service environment.
- If you need a custom Python interpreter or venv, prefer adding an environment file in a future PR rather than embedding fragile activation logic in `ExecStart`.
