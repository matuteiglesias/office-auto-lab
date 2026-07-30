# systemd user automation

**Status:** canonical
**Audience:** operators installing local user timers
**Owner:** `systemd/user/` and office-auto-lab maintainers
**Verified against:** `8b4c9b7`

## Safety boundary

The committed units hard-code `/home/matias/repos/office-auto-lab`. Do not install
them unchanged on another host. The commands below are **illustrative / not
executed in PR-OD4** because this environment does not represent the operator's
user systemd session.

## Preflight and installation

1. Review all six files under `systemd/user/`.
2. Replace both `WorkingDirectory` and absolute `ExecStart` paths in a local copy.
3. Ensure the service environment can import dependencies and access only the
   credentials required by its command.
4. Syntax-check local copies where available: `systemd-analyze --user verify ...`.
5. Install, reload, then enable only reviewed timers:

```bash
mkdir -p ~/.config/systemd/user
cp /path/to/reviewed/*.service /path/to/reviewed/*.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now office-compile.timer staff-briefs.timer evidence-daily.timer
```

Expected schedules: Office at 08:05/12:05/16:05/20:05, staff at 08:10/16:10,
and evidence at 23:00, with persistent catch-up.

## Verification

```bash
systemctl --user list-timers --all
systemctl --user status office-compile.timer staff-briefs.timer evidence-daily.timer
journalctl --user -u office-compile.service -n 50 --no-pager
```

Reconcile service exit status with domain artifacts: Office manifest/latest,
staff indexes, or evidence JSONL. The wrapper preserves child exit codes and
writes local logs, but neither proves artifact correctness.

## Recovery and teardown

On failure, stop the affected timer, inspect journal plus runtime logs/artifacts,
correct the local unit/environment, reload, and manually start its service once
before re-enabling the timer. Disable with:

```bash
systemctl --user disable --now office-compile.timer staff-briefs.timer evidence-daily.timer
```

Stop if paths, credentials, Python environment, or artifact ownership are
ambiguous. See [failure recovery](failure-recovery.md).
