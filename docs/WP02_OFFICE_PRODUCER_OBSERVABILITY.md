# WP02 — Office Producer Observability

This release connects **existing production timers**, not a new Office
scheduler. Producer IDs are unchanged: `producer.local.office-compile` and
`producer.local.office-evidence-daily`.

- `office-v2-generation.timer` is the actual timer for
  `producer.local.office-compile`. Its entrypoint now invokes the existing
  central `producer_local_receipt.py` wrapper, with an artifact-change and
  schema check. A genuine generation failure emits a **failed** execution
  receipt; the wrapper preserves its exit code.
- `evidence-daily.timer` already had a receipt-capable entrypoint. Enabling
  `OFFICE_PRODUCER_RECEIPT_RUNNER` wires the actual producer.
- `OFFICE_PRODUCER_RECEIPT_OUT` directs immutable receipts outside Git working
  trees, e.g. `%h/.local/state/office-auto-lab/producer-receipts`. No local
  evidence documents, personal paths, or source data are exported.

## Delivery model (host authenticated to GitHub, cloud keyless)

The 15-minute systemd timer `office-producer-receipt-dispatch.timer`
reads the persistent spool. It sends validated, metadata-only receipts through
a **private** `matuteiglesias/projects` repository_dispatch event. It uses
the machine's existing authenticated `gh` CLI; no new GCP key or ADC token.
The receiving GitHub Actions workflow uses tightly scoped OIDC identity and
the central G2 exporter to write the dedicated bucket.

A successful HTTP 204 from GitHub means the event was **submitted**, not that
GCP accepted it. The immutable spool is never deleted. A local dispatch ledger
prevents routine duplicate submissions. Recovery from relay-job failures requires
inspection of the private GitHub workflow and a deliberate safe redrive, not
pretending successful delivery on HTTP 204 alone.

## Installation constraints

1. Use the deployed Office source checkout; do not overwrite unrelated local
   edits. Verify the entrypoint includes the receipt wrapper for both routines.
2. Preserve all existing Office runtime configuration; append these three
   settings (with absolute paths resolved for the account):
   `OFFICE_PRODUCER_RECEIPT_RUNNER`, `OFFICE_PRODUCER_RECEIPT_OUT`, and
   `OFFICE_PRODUCER_DELIVERY_LEDGER`. Restrict file mode to user-only.
3. Update the **existing** `office-v2-generation.service` to execute the
   receipted Office routine. Keep its timer, schedule, and unit name unchanged.
4. Install the two new receipt-dispatch units from `systemd/user/`.
   `systemctl --user daemon-reload`, then enable/start the new dispatch timer
   without restarting any Office producer timers.
5. Read back the installed timer/service configuration. Observe actual
   producer runs and verify both their local receipts and GCP bucket entries.

## Correctness and failure boundaries

- The Office generation process is known to have failed on Oct 24 because
  Control Tower `runtime_health_v2` contains blank primary keys. Receipt
  emission reports this real failure and **does not repair or mask the cause**.
- Daily evidence generation is not changed or triggered for observability.
- Producer receipt generation is local and synchronous with real execution;
  cloud delivery is asynchronous and independently retriable.
- The original `producer-run-receipt@1` contract and privacy guard remain
  authoritative; no new schema or duplicate producer identity is introduced.
- A manual wrapper test may prove mechanism, but only actual scheduled
  executions establish recurring operational acceptance.

## WP02 hardening (2026-10-25)

- Daily evidence may write identical bytes during valid executions. The new
  evidence-written check compares before/after file timestamps and inode; it
  does not require content inequality. Existing content-change checks stay
  strict for other producers, and missing/untouched files still fail.
- The relay workflow now labels its run with the receipt SHA-256, allowing
  the host to verify that a matching GitHub Actions job completed successfully
  before marking the local ledger confirmed. Missing/failed deliveries have
  bounded retries and safe stage-level diagnostics.
- Local HTTP 204 event submission is never mistaken for remote GCP acceptance.
