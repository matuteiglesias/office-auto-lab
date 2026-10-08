# Editorial `argentina_econ` manual Sheet publisher

This is a manual-authored, Sheet-only intake for the `argentina_econ` profile.
It does not collect news, run a model, generate copy, or schedule recurring
publication. The operator writes the post and source context in the economics
workbook's `DRAFTS` tab.

## Bindings

```text
profile: argentina_econ
account key: x_argentina_econ
Sheet: 1LAVlYY3T7POA3IUydn3zy2MQBrxc-3c1w-iUq7oFtgo
X handle: @matuteiglesias
X user ID: 57242581
xurl app: argentina-econ-editorial
auth: oauth2
```

The publisher requires `EDITORIAL_ARGENTINA_ECON_SHEET_ID` and the existing
`EDITORIAL_GOOGLE_CREDENTIALS_JSON`/ADC convention. It uses the separate
`argentina-econ-editorial` xurl app and never falls back to the ModernAIDev
app, Sheet, or receipts.

## Operator workflow

1. Add a row to `DRAFTS`. Enter `post_text`, a decision (`DRAFT`, `REVIEW`,
   `APPROVE`, `HOLD`, or `REJECT`), optional UTC `scheduled_for_utc`, topic,
   source URLs, editor note, risk (`low`, `medium`, or `high`), and optional
   future UTC expiry.
2. Run the intake projector. `DRAFT` becomes queue `REVIEW`; other decisions
   are preserved. The projector assigns a stable candidate ID, creates one
   immutable `CANDIDATES` snapshot and one `QUEUE` row, and writes only machine
   columns back to `DRAFTS`.
3. Review/approve and schedule in the resulting `QUEUE` row. `APPROVE`, `X`,
   due schedule, low risk, non-expired state, and a non-empty post are all
   required. High-risk drafts must be held.
4. Run the publisher in dry-run mode first. Add `--apply` only after an
   explicit W3 first-post authorization. This task does not grant that
   authorization.
5. Inspect `QUEUE.publisher_status`, `published_ref`, and the matching
   `DRAFTS.sync_status`/`published_ref`. Publication receipts are under
   `artifacts/editorial/publisher/argentina_econ/`.

Once a draft is staged, changing its text or risk is fail-closed as
`REVISION_REQUIRED`; create a new DRAFTS row for an explicit revision. Existing
queue approvals, schedules, edits, and publication state are never overwritten
by a retry.

## Commands

```bash
export EDITORIAL_ARGENTINA_ECON_SHEET_ID=1LAVlYY3T7POA3IUydn3zy2MQBrxc-3c1w-iUq7oFtgo
export EDITORIAL_GOOGLE_CREDENTIALS_JSON='...loaded locally, never printed...'

PYTHONPATH=src python3 src/office_runtime/scripts/run_editorial_argentina_intake.py --apply

PYTHONPATH=src python3 src/office_runtime/scripts/run_editorial_dev_publisher.py \
  --profile argentina_econ \
  --candidate-id <candidate-id> \
  --allow-manual-seed
```

The last command is dry-run unless `--apply` is explicitly added. Do not add
`--apply` until account and content review are complete. There is no recurring
economics timer.

## Authentication and pause

The operator authenticates the separate xurl app outside the agent session;
never paste secrets into chat. Verify with:

```bash
xurl --app argentina-econ-editorial --auth oauth2 whoami
```

Expected identity is `matuteiglesias`, user ID `57242581`. Set
`EDITORIAL_ARGENTINA_ECON_PUBLISHER_DISABLED=1` to pause apply runs. A dry-run
still reads the Sheet but never mutates X.
