# Job Search Action Packet v1

## Status

Read-only Office **SIDECAR** for reducing job-application preparation and follow-up friction.

The packet is not a second ATS. `ATS 2026` remains canonical for application/search state. CRM/PERSONAS and process-backed contact evidence remain authoritative for human relationships. Gmail and Calendar remain live process evidence. This sidecar only composes normalized facts into one bounded next-action packet.

Contract: `artifact:ops.job-action-packet@1`.

## Operator loop

Begin with governed job-search orientation when Context MCP v0.2 is available:

    mctx bootstrap job-search --as-of YYYY-MM-DD
            ↓
    read exact ATS row
            ↓
    gather only relevant Gmail process evidence
            ↓
    resolve contact only when useful
            ↓
    check Calendar for already-scheduled next stage
            ↓
    normalize evidence
            ↓
    compile job action packet
            ↓
    prepare / follow up / wait / close

The packet does **not** submit applications, send mail, mutate ATS, create Calendar events, or create relationship truth.

## Desired operator experience

For any active ATS row, the operator should be able to answer without archaeology:

- What exactly is this opportunity and current process state?
- Is the next move application preparation, submission, follow-up, waiting, or closure?
- Which materials are required and which are missing?
- Is there a verified process contact?
- If there is no contact, is that actually a blocker?
- Is an interview already on the calendar?
- Is a follow-up due now?
- What existing evidence should be reused?
- What is the stop condition for this block?

## Contact states

The packet distinguishes:

- `verified-person` — process-backed person/contact;
- `organization-channel` — safe organization/application channel but no trusted individual;
- `unresolved-recommended` — ATS/process context implies a person would help, but supplied evidence does not verify one;
- `none-needed` — direct application can proceed without inventing networking work.

A matching name in Contacts is not enough. A contact from another employer/process must not be silently reused.

Accepted verification labels are deliberately narrow: `process-email`, `ats-named+gmail`, `crm-verified`, and `organization-channel`.

## Follow-up v1 rules

### Pre-application

`ready_deadline`, `ready_to_apply`, and `ready_not_applied` do not generate recruiter follow-up. They return `blocked-on-application`: finish the packet first.

### Waiting for scheduling

For `availability_submitted_waiting_schedule` / `waiting_schedule`:

- an existing future Calendar event suppresses follow-up and returns `scheduled`;
- without a future event, two business days after the recorded process-state update returns `due`;
- earlier than that returns `waiting`.

This is a conservative first rule, not universal recruiting etiquette.

### Rejection / closure

A rejected row only receives residual follow-up when ATS explicitly asks for it. If a feedback/relationship message has already been sent, the state becomes `waiting-response`. Otherwise closed processes do not create recurring follow-up work.

## Application preparation

The compiler takes explicit `required` and `available` material labels and computes the missing set. It never claims an application is ready because a generic CV happens to exist.

Typical material labels can include role-specific CV, cover letter, financial proposal, desired salary response, work sample / portfolio link, questionnaire answers, and references.

The evidence-gathering agent determines required materials from the actual posting/application surface; the compiler only performs deterministic reconciliation.

## CLI

    PYTHONPATH=src python3 src/office_runtime/scripts/compile_job_action_packet.py \
      --snapshot /path/to/normalized-job.json \
      --as-of 2026-10-07

Optional `--out` writes the same packet to a caller-chosen output path.

## Privacy and authority

Do not commit live job packets containing personal contact details or raw recruitment correspondence. Tests use synthetic/live-shaped fixtures only.

The packet may recommend an action. It cannot mark an application submitted, promote a contact into CRM, send a message, accept/decline an interview, create a Calendar commitment, or change canonical ATS status.

## Initial dogfood cases

v1 is shaped by five real current process patterns:

1. BEON.tech — rejected; feedback request already sent → wait, do not spam.
2. TELUS Digital — availability submitted, no future event → bounded scheduling follow-up can become due.
3. ZS — strong warm contact, but application still not submitted → preparation first; relationship is not a substitute for application completion.
4. UNICEF — deadline application with organization channel only → prepare required documents now; do not invent a warm contact.
5. Fractal River — direct application, no contact evidence → contact is not a blocker; finish salary/cover-letter packet.

## Promotion / next stages

Do not add new follow-up heuristics from imagination.

Dogfood this contract over additional ATS rows. A new rule is justified only after repeated real cases show the same missing decision.

Potential later stages, if evidence supports them: deterministic post-submission follow-up states; interview-preparation packet; application evidence bundle / CV variant selection; Office-owned daily follow-up watch; bounded draft preparation for a verified contact.

None of these changes ATS authority or grants autonomous submission/sending.
