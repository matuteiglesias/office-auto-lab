# Job Application Prep v1

## Purpose

`artifact:ops.job-application-prep@1` turns a job's explicit material requirements plus the human-owned `ATS 2026 / Assets` registry into a deterministic readiness packet.

It exists because Drive search is not an authority for which CV/template is current. The registry records stable asset IDs, track, language and review status; Office only selects among those records.

## Status vocabulary

- `approved_current` — explicitly safe as the current base for that asset family; still tailor when the live posting requires it.
- `candidate_needs_review` — usable base candidate, but requires factual/role review before submission.
- `reference_only` — may guide a new draft; never send unchanged.
- `missing` — recognized durable gap.
- `retired` — never select.

## Selection outcome

For each required material the compiler returns one of:

- `approved` — exact/current registry asset selected;
- `review-required` — best available candidate requires review/tailoring;
- `draft-from-reference` — only a reusable reference exists;
- `missing-known` — the registry explicitly records the missing asset;
- `missing-unregistered` — no registry coverage exists.

`ready_for_submission_materially=true` only when every requirement resolves to `approved`. It does not mean the ATS application has been submitted and does not bypass the human submission gate.

## Current registry seed

The initial dogfood created a native `Assets` table inside the existing `ATS 2026` workbook rather than a second job database.

Current seed intentionally records:

- generic English Data/AI CV as `candidate_needs_review`;
- historical cover-letter template as `reference_only`;
- Data & AI Engineering CV base as `missing`;
- Data Science / Applied ML CV base as `missing`;
- Institutional / consulting CV base as `missing`;
- financial-proposal template as `missing`.

This is a truthful starting state, not a declaration that the application estate is already complete.

## Dogfood implications

### ZS

The current ZS Lead/Senior Analyst applications can use the generic CV only as a review-required base until a Data Science / Applied ML variant is explicitly approved.

### Fractal River

The generic CV is a review-required fallback for the missing Data & AI Engineering base. The existing cover-letter document is only a historical reference, so a new company-specific letter must be drafted.

### UNICEF

The generic CV can seed a reviewed institutional variant, the cover-letter reference can seed a new draft, and the financial-proposal template is a known missing asset. This makes the deadline blocker explicit instead of hiding it behind generic 'prepare application' language.

## Authority boundary

- ATS `Current` remains canonical application/process state.
- ATS `Assets` is human-owned asset identity/readiness state.
- Drive owns the files themselves.
- Office compiles readiness only.

Office does not write or approve CV content, fabricate application materials, or change an asset status to `approved_current` without an explicit human review decision.

## Next promotion

Only after at least one role-family CV has been explicitly reviewed and promoted should we automate role-specific derivation from that approved base. Until then, generation should remain draft/review work, not silent asset promotion.


## CLI

    PYTHONPATH=src python3 src/office_runtime/scripts/compile_job_application_prep.py \
      --snapshot normalized-prep-input.json \
      --as-of 2026-10-07

The snapshot contains `job_ref`, explicit `requirements`, and normalized rows from the human-owned ATS `Assets` table. The command performs no Drive search or writes.
