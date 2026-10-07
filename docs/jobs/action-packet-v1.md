# Job action packet v1

## Purpose

Turn one current ATS row plus bounded external-authority enrichment into a small,
deterministic action packet. The packet exists to remove application friction,
not to create a second applicant-tracking system.

## Authority

- **ATS 2026** owns application/search state.
- **Projects / Job Search Agenda** owns durable orientation and search posture.
- Gmail, Calendar, Google Contacts and CRM/PERSONAS may provide current
  communication, scheduling and relationship evidence.
- Office owns only the deterministic action projection.
- The packet does not send email, submit an application, create calendar events,
  or mutate ATS.

## Input

`ops.job-action-input@1` contains:

- explicit `as_of`;
- Job Search Agenda orientation state and optional source SHA;
- one canonical ATS row;
- optional normalized enrichment:
  - `action_due_on`;
  - `followup_due_on`;
  - `last_external_touch_on`;
  - contact name/route;
  - packet state;
  - reusable material base.

The connector/agent that prepares the input is responsible for checking the
current owning authorities. Office does not query Gmail, ATS or Calendar here.

## Output

`ops.job-action-packet@1` returns:

- action state;
- why the row matters now;
- blocker;
- exact next block from ATS;
- stop condition;
- contact availability;
- application-material state;
- explicit dates.

Current deterministic action states:

- `blocked_orientation`
- `closed`
- `urgent_action`
- `followup_due`
- `prepare_packet`
- `ready_to_apply`
- `waiting`
- `review`

## Intended agent loop

```text
mctx bootstrap job-search --as-of DATE
  -> read relevant ATS row(s)
  -> enrich only when useful from Gmail / Calendar / Contacts / CRM
  -> compile job-action packet
  -> prepare the application/follow-up block
  -> human sends/submits
  -> update ATS canonical state
```

## Non-goals

- no application submission;
- no email sending;
- no Calendar mutation;
- no scraping every possible contact;
- no job ranking model;
- no inferred submission state;
- no second job database;
- no automatic ATS mutation.
