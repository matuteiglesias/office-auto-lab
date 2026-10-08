# Argentina Econ — GitHub Actions cloud publisher (proposal)

**Status:** prepared, not promoted
**Audience:** editorial operators and release engineers
**Owner:** office-auto-lab Editorial publisher
**Verified against:** `argentina_econ` profile, PR #71 branch

Cloud GitHub Actions runs independently of
Matías's laptop. This is the **publisher** for `argentina_econ` only, NOT the
Editorial Dev generation workflow, and it does not use Cloud Run.

## Binding and authority

| Item | Value |
| --- | --- |
| Profile | `argentina_econ` |
| Account key | `x_argentina_econ` |
| X identity | `matuteiglesias`, numerical user ID `57242581` |
| Workbook | `1LAVlYY3T7POA3IUydn3zy2MQBrxc-3c1w-iUq7oFtgo` |
| Approved authoring surface | `DRAFTS` → `CANDIDATES` + `QUEUE` |
| App | `argentina-econ-editorial` using OAuth2 |
| Production policy | `max_posts_per_day=1`, minimum 24-hour spacing |
| Normal run mode | one due, approved, low-risk post OR no-op |
| Polling | `7,37 * * * *` UTC; best effort, not an exact-time SLA |
| Stale posts | skip if more than 75 minutes past scheduled time; operator reschedules |
| Dev account | **out of scope**; no changes to ModernAIDev workflow/timers/credentials |

The normal policy is not the high-frequency October 8 pilot. The pilot-mode
flags are **never** passed to the cloud entrypoint. The first verified live
economics post was `https://x.com/matuteiglesias/status/2108270033432457625`.

### Execution packet

```yaml
capability: editorial.argentina_econ.sheet_publisher.v1
targets: [Google Sheet Editorial Economia y Politica, X user 57242581]
read_scope: [DRAFTS, CANDIDATES, QUEUE, X whoami, recent account posts]
write_scope: [economics workbook editorial rows, one approved X post, private OAuth2 token state]
dry_run_command: python src/office_runtime/scripts/run_editorial_argentina_cycle.py --dry-run
apply_command: python src/office_runtime/scripts/run_editorial_argentina_cycle.py --apply
expected_evidence: [published X URL, QUEUE PUBLISHED, DRAFTS PUBLISHED, GH Actions run id]
rollback_or_recovery: [enable kill switch, inspect PUBLISHING, reconcile from X without repost]
stop_condition: [wrong X ID, unknown credential state, stale schedule, duplicate, Sheet outage,
                 unresolved PUBLISHING, 24h cadence, high risk, missing user approval]
human_authorization: [approved Sheet row, explicit account-level cloud promotion]
```

## Repository variables: set before first manually dispatched DRY RUN

Go to **office-auto-lab → Settings → Secrets and variables → Actions → Variables**:

```text
EDITORIAL_ARGENTINA_ECON_SHEET_ID=1LAVlYY3T7POA3IUydn3zy2MQBrxc-3c1w-iUq7oFtgo
EDITORIAL_ECON_AUTH_GCS_BUCKET=<dedicated private bucket>
EDITORIAL_ECON_AUTH_GCS_OBJECT=auth/argentina_econ/xurl-auth.yml
EDITORIAL_ECON_SCHEDULER_ENABLED=false
EDITORIAL_ECON_PUBLISH_ENABLED=false
EDITORIAL_ECON_RUNTIME_PROMOTED=false
EDITORIAL_ARGENTINA_ECON_PUBLISHER_DISABLED=1
```

Existing **Actions secret** `EDITORIAL_GOOGLE_CREDENTIALS_JSON` is reused for
Google Sheets and the private GCS bucket. The backing service-account identity
must be granted the minimum read/write object permissions for this dedicated
bucket, and Sheet Editor on the economics workbook. Do not put OAuth tokens in
repository variables, workflows, logs, or artifacts. Do not modify the existing
ModernAIDev X app credentials.

## Durable OAuth2 storage (one private GCS object; no Cloud Run)

Current `xurl` OAuth2 user tokens can refresh/rotate. A static GitHub secret
containing `~/.xurl/auth.yml` would therefore become stale. For unattended
GitHub runners, use a dedicated private Google Cloud Storage object containing
only the economics X app and economics OAuth2 user.

Prepare the object LOCALLY under operator oversight:
1. Export **only** the `argentina-econ-editorial` app from local `~/.xurl/auth.yml`.
   Preserve its own OAuth2 `matuteiglesias` user token, refresh token,
   client ID and client secret. Use a private temp file with chmod 600.
   **Never upload the complete multi-app auth.yml.**
2. Create a private, uniform-bucket-access GCS bucket with public access
   prevention. Grant the existing Sheets service account object read/write
   only to this bucket; no broad project-level permission.
3. Upload the economics-only auth YAML to
   `gs://<bucket>/auth/argentina_econ/xurl-auth.yml`. Remove temporary
   exported files after verifying upload. Do not paste tokens into Codex chat.
4. `editorial_econ_oauth_store.py restore` fetches this GCS object, validates
   its one-app/one-user identity, writes only to temporary runner HOME, and
   records the GCS generation.
5. After the publishing cycle, `persist` verifies identity again and uploads
   refreshed OAuth2 state with `if_generation_match`. A generation conflict
   blocks; it never overwrites another session's credential state.
6. If the runner crashes **after X refresh but before token persistence**,
   the remote refresh token may become invalid. Fail closed, diagnose, and
   reauthorize locally. Never automatically recreate credentials.

### Critical runtime conditions

- The **GitHub workflow concurrency group** serializes this workflow's own
  executions. Disable ALL local economics publishing timers before activation;
  do not run a second external economics publisher against the same queue.
- **Google Sheets is the durable publication ledger.** The existing publisher
  writes `PUBLISHING` to QUEUE before X mutation. The next execution must
  reconcile that state from X before any new post. Do not rely on ephemeral
  Actions filesystem receipts, uploaded Actions artifacts, or only the target
  candidate's receipt for account-wide limits.
- A publication failure or uncertain X result blocks future publication
  until reconciled. Never automatically retry the post.
- The selector also checks all QUEUE PUBLISHED timestamps and the authenticated
  account's recent X post timestamps before a new post.
- `DRAFTS` already staged or published with past schedule must remain valid,
  while brand-new stale scheduled drafts must be refused. No catch-up bursts.
- Dispatched `dry_run` MUST NOT write to X or Sheets. It may perform read-only
  authenticated account verification.
- One post per run. No deliberate test exceptions in the cloud schedule.
- The profile is permanently bound to the exact account ID, workbook,
  xurl app and OAuth2 type; any mismatch blocks.

## Promotion checklist

**Stage A (safe by default):** merge only after local tests and review. The
schedule is defined, but a false `EDITORIAL_ECON_SCHEDULER_ENABLED` causes
scheduled jobs to skip before allocating a runner. Manual `workflow_dispatch`
with `mode=dry_run` is allowed after provisioning; verify identity and NO
mutations, including when a QUEUE row is `PUBLISHING`.

**Stage B (ready for cloud dry runs):**
- Confirm `src/office_runtime/scripts/run_editorial_argentina_cycle.py` and
  `editorial_econ_oauth_store.py` work with a real economics-only GCS object.
- Install exact runtime dependencies under Actions Python 3.12.
- Run mock tests for X success, Sheet writeback failure, subsequent resume,
  token rotation, wrong identity, repeated runs, stale and overlapping slots.
- Manual `workflow_dispatch` dry run **twice**, in separate Actions jobs.
- Verify token persistence, GCS generation and that no X or Sheet mutations
  occurred.

**Stage C (explicit first cloud post):**
- Operator chooses one fresh, approved, future-scheduled low-risk economics post.
- Local test verifies one-post policy and identity.
- Explicit approval for one GitHub Actions `apply` dispatch.
- Set `EDITORIAL_ECON_RUNTIME_PROMOTED=true`,
  `EDITORIAL_ECON_PUBLISH_ENABLED=true`, and
  `EDITORIAL_ARGENTINA_ECON_PUBLISHER_DISABLED=0` only for the approved
  promotion window. Keep scheduler disabled during this single-shot test.
- Observe X post ID and both Sheet writebacks. If anything is uncertain,
  reenable kill switch immediately and reconcile read-only.

**Stage D (unattended):** After proof, enable
`EDITORIAL_ECON_SCHEDULER_ENABLED=true`. The same policy gates still apply.
Adjust schedules of remaining 2026-10-08 pilot rows so old posts are never
sent as catch-up. The 30-minute poll does NOT guarantee exact publishing time.
Inspect run failures, missed triggers and monthly Actions minutes; later add a
missing-run alert based on workflow-run timestamps.

**Emergency stop:** set
`EDITORIAL_ARGENTINA_ECON_PUBLISHER_DISABLED=1` OR
`EDITORIAL_ECON_PUBLISH_ENABLED=false`. For zero runner cost also set
`EDITORIAL_ECON_SCHEDULER_ENABLED=false`.

## Known follow-up checks for local Codex

1. Run `pytest` for `tests/test_editorial_argentina_cycle.py`, existing
   editorial publisher/manual-intake tests, and dependency/CI checks.
2. Audit `PilotPublisher._receipt_paths`: it filters by **candidate ID**, so
   the in-process legacy 24-hour cadence check is not account-wide. Fix it
   as part of this PR rather than trusting ephemeral receipts.
3. Verify publisher's `PUBLISHING` reconciliation checks authenticated
   account identity before any Sheet mutation, and make `--dry-run` strictly
   read-only. Existing `PilotPublisher.run` may reconcile before its dry-run
   gate; ensure the cloud entrypoint doesn't let this occur.
4. Verify expected public X user ID and exact text on X readback. Verify
   full metadata for older PUBLISHED rows before relying on `updated_at`.
5. Validate this workflow YAML, pinned `xurl` npm version availability,
   PyYAML dependency, GCS service-account permissions, and OAuth2 refresh
   behavior on real GitHub-hosted runners.
6. Add or repair tests for past-due **already staged** DRAFTS and explicit
   schedule/approval propagation. Do not silently assume a change in DRAFTS
   decision updates an already-created QUEUE decision.
7. Propose a follow-up time-monitoring workflow only after reliable runs.

No GitHub cloud jobs have been triggered by this PR. No secrets have been
read or created in GitHub. No additional X post is authorized by this document.
