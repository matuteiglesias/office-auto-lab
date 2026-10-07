# Job Follow-up Watch v1

## Purpose

`artifact:ops.job-followup-watch@1` is the quiet attention layer over already-compiled per-job action/preparation packets.

It does not re-read Gmail, ATS, Calendar or Contacts. The evidence-gathering agent/runtime does that upstream, then this compiler decides whether the resulting state merits a notification.

## Notify conditions

v1 notifies only when:

- a deterministic process follow-up is due;
- an application deadline is immediate/overdue;
- a high/critical-urgency application is blocked by materials that are not approved-ready.

Normal-priority preparation gaps do not nag. For example, a ZS CV improvement remains visible in the action/prep packet but does not generate a daily alert merely because the approved role-family CV is still missing.

## Duplicate suppression

Each job's attention state receives a deterministic SHA-256 fingerprint over process/action/follow-up/deadline/material state.

If the caller supplies the same fingerprint as the previous notified state, the watch suppresses the repeat. A meaningful state change produces a different fingerprint and may notify again.

Persistence of the previous fingerprint is caller/automation state. Office does not mutate ATS or create a hidden notification database.

## Current dogfood result

On 2026-10-07 the expected live attention set is:

- `JOB-210` TELUS Digital — scheduling follow-up due; verified process contacts exist and no future Calendar event was found.
- `JOB-213` UNICEF — deadline 2026-10-08 plus unresolved application-material blockers.

BEON is already waiting for a response to the sent feedback request. ZS remains normal-priority application preparation and should not nag.

## Contact-resolution rule

The action packet also carries a deterministic `resolution_plan`:

- verified process person → use them; do not keep searching;
- verified organization channel → use it; do not manufacture networking;
- unresolved but contact-recommended → Gmail exact process first, then CRM/PERSONAS exact identity, then Contacts with organization evidence, then official company source; stop rather than inventing a warm path;
- none-needed → do not waste time finding a contact.

CRM promotion remains a separate human decision. Current recruiter process contacts need not become canonical relationships merely because they are useful for one application.

## CLI

    PYTHONPATH=src python3 src/office_runtime/scripts/compile_job_followup_watch.py \
      --snapshot normalized-watch-input.json \
      --as-of 2026-10-07

Input JSON contains `action_packets`, optional `prep_packets`, and optional `previous_fingerprints`.

## Scheduling

The intended scheduled condition-watch behavior is:

1. read active/recently changed ATS rows;
2. gather only relevant recent process Gmail and Calendar evidence;
3. compile action packets and material readiness;
4. notify only when the follow-up watch says attention is new and actionable;
5. never send mail, submit an application, mutate ATS, or create Calendar events.

A ChatGPT scheduled watch was attempted during initial dogfood but could not be created because the account already had the maximum five active tasks. This is an external scheduling-capacity blocker, not a product-contract blocker.

Once a task slot is available, schedule one daily condition watch (morning is sufficient) using this contract. Do not create multiple overlapping job-reminder tasks.
