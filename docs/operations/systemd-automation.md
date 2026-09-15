# systemd user automation

**Status:** installable migration preparation; production cutover is not
enabled by this repository

**Audience:** operators installing local user timers

**Owner:** `systemd/user/` and the Office Runtime maintainers

**Verified against:** M8 coherent-generation runtime and portable installer
contract

## Safety boundary

Tracked units are machine-neutral. Each service reads the operator-specific
environment file:

```text
~/.config/office-auto-lab/runtime.env
```

The installer writes the absolute checkout and interpreter paths as
`OFFICE_ROOT` and `OFFICE_PYTHON`, along with the configured evidence roots.
Checkout paths, Conda paths, credentials, and usernames must not be committed
in a unit file.

The installer renders and installs units but does not enable a timer unless an
explicit enable flag is supplied. Installing or merging this repository does
not change a user's installed systemd state.

## Scheduler topology

### Legacy scheduled path

These units remain available during migration and are not removed here:

```text
office-compile.timer  -> office-compile.service -> Office compile only
staff-briefs.timer    -> staff-briefs.service   -> Staff briefs only
evidence-daily.timer  -> evidence-daily.service -> evidence producers
```

The legacy Office and Staff timers are compatibility surfaces. In particular,
the five-minute offset between Office compile and Staff briefs is not the v2
architecture. Their retirement belongs to the later M9 compatibility-exit
work after explicit v2 cutover.

### Office v2 scheduled path

The v2 scheduler has one Office clock and one coherent routine:

```text
office-v2-generation.timer
  -> office-v2-generation.service
  -> run_generation_v2.py
  -> snapshot -> work compiler -> Staff -> Principal
  -> execution-plan compilation -> validation/promotion
```

The timer fires at 08:05, 12:05, 16:05, and 20:05. It has
`Persistent=true`. Staff and Principal are internal stages of the M8
generation command; systemd does not schedule them independently and the v2
service has no Staff dependency unit.

`office-v2-shadow.service` is available for an explicit manual shadow run. It
uses the same coherent runtime and lock, passing `--shadow`; it has no timer.
The M8 runtime owns the guarantees that shadow mode does not replace the v2
`current` generation, mutate legacy `latest`, write Control Tower, or
execute ready pulls.

## Concurrency and failure semantics

The v2 entrypoint takes one atomic directory lock at the coherent-generation
boundary under `OFFICE_ROOT/artifacts/locks/office-v2-generation.lock`. A
colliding scheduled or manual run exits with status 75 and leaves a visible
journal message; two coherent generations do not run concurrently.

The service uses `exec` to enter the entrypoint, and the entrypoint returns the
canonical M8 command's exit status. A non-zero generation result therefore
fails the oneshot service. No downstream Staff or Principal service is started
after a failure, because those stages are owned by the single generation
routine. A green systemd service indicates that the routine completed
successfully; it does not replace generation validation or artifact inspection.

## Render and verify without installation

From the checkout that should own local Office automation:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_systemd.py render \
  --repo-root "$(pwd)" \
  --python-bin "$(command -v python3)" \
  --evidence-root "$HOME/repos" \
  --evidence-root "$HOME/Documents" \
  --out /tmp/office-systemd

systemd-analyze verify /tmp/office-systemd/units/*.service \
  /tmp/office-systemd/units/*.timer
```

The render output includes both legacy units and the v2 generation service,
timer, and manual shadow service. It writes a rendered `runtime.env` beside
the units and does not contact or mutate the user systemd manager.

## Installation

Install units and reload the user manager while leaving timers disabled:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_systemd.py install \
  --repo-root "$(pwd)" \
  --python-bin "$(command -v python3)" \
  --evidence-root "$HOME/repos" \
  --evidence-root "$HOME/Documents"
```

The legacy-compatible `--enable` flag enables the existing legacy/evidence
timers only. It deliberately does not enable `office-v2-generation.timer`.
At cutover, use the separate explicit flag only after reviewing the rendered
units and M8 artifacts:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_systemd.py install \
  --repo-root "$(pwd)" \
  --python-bin "$(command -v python3)" \
  --evidence-root "$HOME/repos" \
  --evidence-root "$HOME/Documents" \
  --enable-v2
```

`--enable-v2` starts only `office-v2-generation.timer`; it does not disable
the legacy timers. Cutover must explicitly disable the legacy Office and Staff
timers in the same reviewed maintenance window:

```bash
systemctl --user disable --now office-compile.timer staff-briefs.timer
systemctl --user enable --now office-v2-generation.timer
```

The independent `evidence-daily.timer` may remain enabled.

## Shadow and manual operation

After installation, inspect the rendered/installed units and run a shadow
generation explicitly:

```bash
systemctl --user start office-v2-shadow.service
journalctl --user -u office-v2-shadow.service -n 100 --no-pager
```

The manual service is not enabled by the installer and has no timer. It is a
complete generation in M8 shadow mode, not a Staff-only or Principal-only
workflow.

## Verification and status

```bash
systemctl --user list-timers --all
systemctl --user status office-v2-generation.timer office-v2-generation.service
systemctl --user status office-compile.timer staff-briefs.timer evidence-daily.timer
journalctl --user -u office-v2-generation.service -n 100 --no-pager
cat ~/.config/office-auto-lab/runtime.env
```

Inspect the run-scoped tree and validation/promotion result before treating a
scheduled run as operationally successful.

## Rollback

If v2 generation fails or its artifacts do not validate, stop its timer and
leave the v2 service disabled:

```bash
systemctl --user disable --now office-v2-generation.timer
systemctl --user enable --now office-compile.timer staff-briefs.timer
```

Keep `evidence-daily.timer` unchanged unless its own evidence run is the
problem. Inspect the failed v2 journal and run tree before retrying. Rollback
does not delete v2 evidence or silently promote legacy artifacts.

## Upgrade and uninstall

After moving the checkout, changing the Python environment, or changing
evidence roots, rerun `install` with the new absolute values. The installer
replaces the installed unit copies, updates `runtime.env`, and reloads the
user manager; it does not enable v2 implicitly.

To remove installed units:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/install_systemd.py uninstall
```

This disables tracked timers, removes installed unit files, and reloads the
user manager. `--purge-config` additionally removes the runtime environment
file.
