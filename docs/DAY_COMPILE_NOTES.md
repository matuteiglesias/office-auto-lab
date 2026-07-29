## Full compiled block pack

### 1. 61 - Job Search Management (Coderhub)


**Mode:** execution

**Why included:** active, today, required. 


**Block:** open the row context and force one bounded next action only: apply, reply, update tracker, or diagnose blocker.

**Expected evidence:** sent application, sent reply, updated tracker note, or explicit blocker note.

**Stop rule:** stop after one bounded step; do not widen into general job search. 


**Helper content for human execution**

* Find the exact Coderhub row or note first.
* Translate the row into one verb.
* Execute only that verb.
* Leave a one-line next pointer in the tracker.

### 2. 26.2 - fcen_identity


**Mode:** execution

**Why included:** active, today, required. 

**Block:** open row context and define one bounded repo-level move: inspect one canonical artifact, verify one consolidation issue, or produce one review artifact.

**Expected evidence:** note, diff, updated artifact, or explicit diagnosis.

**Stop rule:** one bounded move only; no redesign. 


**Helper content**

* Do not start with architecture.
* Start with one record family, one linkage issue, or one canonical artifact.
* Aim to leave the identity front more inspectable than before.

### 3. 51 - EPH Survey ML Student Thesis Supervision


**Mode:** decision plus execution

**Decision:** approve the default. The brief already recommends one focused execution block with explicit stop rule and evidence expectation. 

**Block:** enter `/home/matias/repos/Tesis-LCD-EPH` and produce one supervision artifact only: checkpoint note, feedback memo, or narrowed review target. Repo path is explicitly present in the principal brief. 

**Expected evidence:** short supervisory memo.

**Stop rule:** no full re-understanding pass.


**Helper content**

* Ask: what is the next student-facing ask?
* Ask: what exact evidence must the student show next?
* Write only that checkpoint.

### 4. 5 - Email Triage Manager


**Mode:** decision plus health check

**Decision:** approve health check first; postpone redesign. 

**Compiled block:** read the run surface for `/home/matias/Documents/email_manager`, identify canonical entrypoint, and capture whether the front is runnable or not. The principal brief confirms this item is still escalated and required this week. 

**Expected evidence:** health result and next unlock.

**Stop rule:** no redesign or feature planning.


**Helper content**

* Treat this as diagnosis only.
* Output should be “healthy / broken / ambiguous,” plus exact next unlock.

### 5. 2 - Weekly Sweep Ritual: Control Tower + Hedge portfolio


**Mode:** execution

**Why included:** active and required this week. 

**Block:** enter `/home/matias/Documents/control_tower` and inspect the canonical entrypoint or main runnable path.

**Expected evidence:** command output, note, diff, updated artifact, or explicit diagnosis.

**Stop rule:** one bounded sweep-enabling step only. 


**Helper content**

* Good first outcomes are: identify canonical script, confirm stale-check flow, or produce one sweep note.
* Bad outcome is turning this into a full portfolio review session.

### 6. 48.1 - Poverty data pipeline


**Mode:** execution

**Why included:** active, required, and has explicit repo path. 

**Block:** enter `/home/matias/repos/indice-pobreza-UBA` and inspect the canonical entrypoint or main runnable path.

**Expected evidence:** command output, note, diff, updated artifact, or explicit diagnosis.

**Stop rule:** one bounded step only. 


**Helper content**

* The cheapest meaningful step is usually entrypoint confirmation plus one runnable test or one artifact-path clarification.
* Avoid turning this into a publication redesign block.

### 7. 59 - Outreach Scheduler (Rolling contact lists)


**Mode:** execution

**Why included:** active and required this week. 

**Block:** open row context and define one bounded automation move related to recontacting or planned outreach.

**Expected evidence:** note, diff, updated artifact, or explicit diagnosis.

**Stop rule:** no widening into full CRM redesign. 


**Helper content**

* Candidate bounded moves: inspect scheduler entrypoint, define one contact batch, or verify one automation hook.
* Keep it to one list or one scheduling mechanic.

### 8. 60 - Job market focused CRM


**Mode:** execution

**Why included:** active and required this week. 

**Block:** open row context and define one bounded outreach move.

**Expected evidence:** updated note, sent draft, tracker update, or diagnosis.

**Stop rule:** do not merge this with general career strategy. 


**Helper content**

* Good bounded moves: identify one person to contact, one draft to prepare, or one outreach segment to refresh.
* One contact slice is enough.

### 9. 90 - Mind Debrief & Session Summaries


**Mode:** execution

**Why included:** active and required this week. 

**Block:** open row context and define one bounded next action for raw session generation or synthesis.

**Expected evidence:** note, generated raw session, summary stub, or diagnosis.

**Stop rule:** no meta redesign of the reflection system. 


**Helper content**

* Best bounded move is usually either “produce one raw session artifact” or “define one canonical synthesis template.”

### 10. 55 - CRM / Relational Layer


**Mode:** execution

**Why included:** active maintenance front with clear scope. 

**Block:** open row context and choose one bounded move affecting people, rhythms, outreach, or interaction logging.

**Expected evidence:** note, tracker update, message draft, or diagnosis.

**Stop rule:** do not mix CRM architecture with scheduler or job-market CRM in the same block. 


**Helper content**

* This front is broad enough to sprawl.
* So force a noun before starting: one person-set, one rhythm, or one log artifact.

## Staff-preparable diagnostic pack

These are not principal creative blocks. They are clean fractional-developer style backlog pushes because the briefs already define bounded diagnosis.

### 11. 10 - KB Chat Ingest Spine


**Mode:** health check

**Block:** read `/home/matias/Documents/KB/notes/runbook.md`, verify canonical path, compare with the brief’s smoke instruction. The brief itself already shows a tension: it names `make smoke`, but the repo snapshot says there is no Makefile. That contradiction is exactly why this is a good diagnostic block. 

**Expected evidence:** is the runbook stale, or is the brief stale, or is there an alternative entrypoint?

**Stop rule:** resolve entrypoint ambiguity only.

### 12. 14 - Auto Projects checker


**Mode:** health check

**Block:** read runbook, then run `make smoke` from `/home/matias/Documents/auto-projs-checker`, and compare result against `PLUGIN_NOT_FOUND`. This front is especially suitable because the snapshot already shows a stable repo, a Makefile, and explicit smoke target. 

**Expected evidence:** smoke result plus whether the plugin issue is environmental or structural.

**Stop rule:** no fixing beyond first diagnosis.

### 13. 23 - Financial Document Parser


**Mode:** health check

**Block:** read runbook, run `make smoke` from `/home/matias/repos/accounting_doc_triage`, compare result with current error state. 

**Expected evidence:** smoke output and next unlock.

**Stop rule:** do not move into parser redesign.

### 14. 38 - Evaluar app


**Mode:** health check

**Block:** read `/home/matias/repos/evaluar-app/README.md`, verify actual runnable path, and determine whether the “make smoke” instruction is stale, because the snapshot says there is no Makefile. It also flags OAuth/network touchpoints, so this is not a casual run-first block. 

**Expected evidence:** canonical run path and risk note.

**Stop rule:** no auth surgery.

### 15. 15 - Digest Engine


**Mode:** unlocker

**Block:** resolve the repo-path defect first. The brief says the configured path `/home/matias/Documents/kb_digests_v1` is not a directory. So the entire bounded block is “find the real location or confirm the front is miswired.” 

**Expected evidence:** corrected path or confirmed missing repo.

**Stop rule:** path unlock only.

### 16. 32 - AI Paper Chunker


**Mode:** unlocker plus health-style smoke

**Block:** run the bounded smoke path from `/home/matias/Documents/paper-kb` using `make smoke`, because the brief already points there and the repo has an explicit Makefile and smoke target. 

**Expected evidence:** smoke result and next unlock.

**Stop rule:** no rearchitecture.

## What I would not compile yet

I would **not** pretend to compile `93`, `94`, or `97` into real bounded blocks from this packet alone. They appear in the week brief, but there are no attached execution child briefs for them here, so anything more concrete would be guessed rather than compiled. 

## Practical batching

A useful way to exploit this as a fractional-developer backlog pack is to split it into three lanes.


**Lane A, principal execution**

* 61
* 26.2
* 51
* 48.1
* 2


**Lane B, relational / maintenance execution**

* 55
* 59
* 60
* 90


**Lane C, bounded diagnostics**

* 5
* 10
* 14
* 23
* 38
* 15
* 32

That gives you 16 compiled units, but they are not equal. The highest leverage ones for backlog burn without cognitive sprawl are the diagnostic pack, because they are already sharply bounded by the briefs. The most dangerous ones for sprawl are `55`, `59`, `60`, and `90`, because their briefs are valid but abstract and row-context dependent.    
