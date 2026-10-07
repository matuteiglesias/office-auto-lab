# Job Follow-up Watch v1

## Purpose

`artifact:ops.job-followup-watch@1` is the quiet attention layer over already-compiled job action and application-prep packets.

It does not read ATS, Gmail, Calendar, Contacts or CRM directly. Upstream evidence gathering produces normalized packets; this compiler decides whether the resulting state merits a new notification.

## Notify conditions

v1 notifies only when:

- a deterministic process follow-up is due;
- an application action/deadline is immediate or overdue;
- a high/critical-urgency application is blocked by material readiness.

Normal-priority preparation gaps remain visible without creating a daily nag.

## Duplicate suppression

Each job receives a deterministic SHA-256 fingerprint over the material attention state, including ATS due dates and application-prep states.

If the caller supplies the same previous fingerprint, the watch suppresses the repeated notification. A material state change re-arms attention.

## Authority

ATS remains canonical application/process state and owns explicit due dates. ATS `Assets` owns human-reviewed application-asset readiness. Gmail/Calendar are live evidence. CRM/PERSONAS remains relationship authority.

The watch never sends mail, submits an application, mutates ATS, creates Calendar events, or promotes a process contact into CRM.

## CLI

    PYTHONPATH=src python3 src/office_runtime/scripts/compile_job_followup_watch.py \
      --snapshot normalized-watch-input.json \
      --as-of 2026-10-07

The input contains `action_packets`, optional `prep_packets`, and optional `previous_fingerprints`.

## Scheduling

The intended scheduled form is one daily condition watch. During initial dogfood, creation was blocked because the account already had five active ChatGPT tasks. Do not create overlapping reminder machinery; enable one watch only when a task slot is deliberately freed.
