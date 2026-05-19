
# Auto Projects Checker runbook (v0)

This repo runs lightweight checks across projects, writes “Frontier” health surfaces, compiles those surfaces into an actionable daily Block Queue, and publishes the queue to Google Sheets.

This runbook is operational. Human responsibility and ontology definitions live in the wiki.

## 0) What is “done” for v0

Release is considered working when these endpoints are true:

- E1 Local compile works (fixture CSV -> prepared_blocks.jsonl).
- E2 Live compile works (out/frontier/latest.csv -> prepared_blocks.jsonl).
- E3 Sheet publish works (prepared_blocks.jsonl -> BlockQueue tab).
- E4 Wiring works (after frontier update, compiler runs and refreshes BlockQueue tab).

## 1) Architecture

Pipeline chain:

1) Runner (project checks)
- Reads project config and plugin policy
- Runs plugins and records CheckResult per project :contentReference[oaicite:0]{index=0}
- Produces frontier CSV(s) and artifacts

2) Frontier export contract (deterministic)
- Writes a canonical file that always exists after successful frontier update:
  - `out/frontier/latest.csv`
- Optionally writes a dated snapshot:
  - `out/frontier/YYYY-MM-DD/frontier.csv`

3) Compiler (blocks)
- Reads a frontier CSV (fixture or latest)
- Produces:
  - `out/compiler/YYYY-MM-DD/prepared_blocks.jsonl`

4) Publisher (sheets)
- Reads prepared_blocks.jsonl
- Writes to Google Sheets tab `BlockQueue` (idempotent, rewrite tab)

## 2) Data contracts

### 2.1 CheckResult (plugin output)

Each plugin returns a structured result with evidence and meta, with safety rules about secrets and NA vs ERROR :contentReference[oaicite:1]{index=1}.

### 2.2 Frontier CSV (compiler input)

Canonical path:
- `out/frontier/latest.csv`

Required columns (v0):
- `bucket, date, duration_ms, executed, normalized_class, plugin, project_id, run_id, short_diag, ts_started`

Rule:
- Compiler ignores unknown columns.

Determinism rules for latest.csv:
- Sort rows by `(normalized_class, plugin, project_id, bucket, run_id)` before writing.
- Write CSV as UTF-8, `index=False`, `lineterminator="\n"`.

### 2.3 Prepared blocks JSONL (publisher input)

Path:
- `out/compiler/YYYY-MM-DD/prepared_blocks.jsonl`

Properties:
- Ordering must be deterministic (stable sort and tie breaks).
- Re-running compile twice with the same frontier must produce identical JSONL bytes.

### 2.4 Outputs and artifacts

Runner output expectations include timestamped artifacts, logs, and reports :contentReference[oaicite:2]{index=2}.
Compiler output is the JSONL above plus optional logs in `out/compiler/YYYY-MM-DD/`.

## 3) Quick start

### 3.1 Prereqs
- Python 3.10+
- A working venv or conda env (recommended name: `new_env`)
- Google service account JSON (kept in `private/`, never committed)

### 3.2 One-time setup
1) Create env and install deps
- Use a single env that owns ALL python deps for this repo.
- Avoid mixing system site packages with env packages.

2) Put service account at:
- `private/service_account_file.json`

3) Share the Google Sheet with the service account email (Editor).

4) Export variables:
- `SHEET_ID="<your sheet id>"`
- `SA="/absolute/path/to/private/service_account_file.json"`

## 4) Operator commands (Makefile interface)

### 4.1 Smoke (offline, fixture driven)
- Purpose: validate compiler can run locally with committed fixture.

```bash
make smoke
```

### 4.2 Live cycle (frontier -> compile -> publish)

* Purpose: run the full chain end-to-end.

Recommended invocation to avoid user-site pollution:

```bash
conda activate new_env
PYTHONNOUSERSITE=1 SHEET_ID="$SHEET_ID" SA="$SA" make live-cycle
conda deactivate
```

### 4.3 Individual steps

```bash
conda activate new_env
PYTHONNOUSERSITE=1 SHEET_ID="$SHEET_ID" SA="$SA" make frontier
PYTHONNOUSERSITE=1 make compile-queue
PYTHONNOUSERSITE=1 SHEET_ID="$SHEET_ID" SA="$SA" make publish-queue
conda deactivate
```

## 5) Automation (systemd user timer)

Goal: run `make live-cycle` hourly without interactive shells.

### 5.1 Gotchas

* systemd does not “know” your conda activation unless you explicitly do it.
* mixing system python and env python can pull incompatible oauthlib or requests-oauthlib paths (symptom: oauthlib import errors).
* fix is: run inside the env and set `PYTHONNOUSERSITE=1`.

### 5.2 Recommended pattern

* Store runtime config in a local env file (not committed):

  * `private/runtime.env`

Example `private/runtime.env`:

```ini
SHEET_ID=...
SA=/home/matias/Documents/auto-projs-checker/private/service_account_file.json
PYTHONNOUSERSITE=1
```

### 5.3 Unit files

Create: `systemd/auto-projs-checker.service`

```ini
[Unit]
Description=Auto Projects Checker hourly run

[Service]
Type=oneshot
WorkingDirectory=%h/Documents/auto-projs-checker
EnvironmentFile=%h/Documents/auto-projs-checker/private/runtime.env
ExecStart=/bin/bash -lc 'source "$HOME/miniconda3/etc/profile.d/conda.sh" && conda activate new_env && make live-cycle'
```

Create: `systemd/auto-projs-checker.timer`

```ini
[Unit]
Description=Run Auto Projects Checker hourly

[Timer]
OnCalendar=hourly
Persistent=true
Unit=auto-projs-checker.service

[Install]
WantedBy=timers.target
```

Enable:

```bash
systemctl --user daemon-reload
systemctl --user enable --now auto-projs-checker.timer
systemctl --user status auto-projs-checker.timer
journalctl --user -u auto-projs-checker.service -n 200 --no-pager
```

If the timer refuses to start because the service is “not loaded”, it means the `.service` file is missing, not discoverable by systemd, or the `Unit=` name does not match. Put both files under `~/.config/systemd/user/` or symlink them there.

## 6) Verifying correctness

### 6.1 Compile determinism

Run twice and compare:

```bash
python3 scripts/compile_blocks.py --frontier out/frontier/latest.csv --date "$(date +%F)"
cp out/compiler/$(date +%F)/prepared_blocks.jsonl /tmp/a.jsonl
python3 scripts/compile_blocks.py --frontier out/frontier/latest.csv --date "$(date +%F)"
diff -u /tmp/a.jsonl out/compiler/$(date +%F)/prepared_blocks.jsonl
```

### 6.2 Sheet idempotency

Run publish twice, confirm row count unchanged and no duplicates (tab is rewritten).

## 7) Troubleshooting

### 7.1 oauthlib / gspread import errors

Symptom:

* `ModuleNotFoundError: No module named 'oauthlib.oauth2.rfc6749.grant_types.base'`

Cause:

* importing a partially installed oauthlib from system/user site instead of your env.

Fix:

* always run with:

  * `PYTHONNOUSERSITE=1`
  * and inside the env (`conda activate new_env`)
* confirm:

  * `which python`
  * `python -c "import gspread; import oauthlib; print(gspread.__version__, oauthlib.__version__)"`

### 7.2 “BlockQueue updated but frontier stale”

Check:

* `ls -l out/frontier/latest.csv`
* confirm timestamps in latest.csv and the compiler date folder align.

### 7.3 systemd timer not running

Check:

* `systemctl --user list-timers | rg auto-projs-checker`
* `systemctl --user cat auto-projs-checker.timer`
* `systemctl --user cat auto-projs-checker.service`
* logs:

  * `journalctl --user -u auto-projs-checker.service -n 200 --no-pager`

## 8) Repo hygiene (minimum)

* Never commit `private/` (service account, runtime.env).
* Keep `fixtures/frontier_sample.csv` committed for smoke.
* Keep a stable Makefile interface; callers should not need to remember python module paths.



If you paste your current `notes/runbook.md` (the one inside the repo) I can do a tight diff and fold in anything specific you already documented there.

