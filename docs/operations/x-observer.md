# X Observer operations

**Status:** Phase A/O1 gated; offline O2–O6 preparation only
**Audience:** Observer operators and future read-only consumers
**Owner:** office-auto-lab X Observer SIDECAR
**Verified against:** `docs/spec/x-observer-v0/PHASE_A_FREEZE.md` and PR #78

The X Observer is a read-only SIDECAR. It is independent from both
`editorial-argentina-econ-publisher.yml` and the ModernAIDev publisher.
It has no X mutation capability.

## Current gate

Phase A/O1 is not promoted. The configured account remains disabled and the
workflow is closed unless `X_OBSERVER_SCHEDULER_ENABLED=true` is explicitly
promoted after the gates below pass. The required credential is a dedicated
read-only `X_OBSERVER_BEARER_TOKEN`; publisher OAuth1 credentials must never be
used as a substitute.

The current local proof is offline only:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_x_observer_phase_a tests.test_x_observer_storage_projection
PYTHONPATH=src python3 -m office_runtime.scripts.run_x_observer --dry-run
```

The live qualification, when separately authorized, is bounded to two pages,
five to ten results per page, and a declared estimated USD ceiling:

```bash
X_OBSERVER_BEARER_TOKEN=... \
PYTHONPATH=src python3 -m office_runtime.scripts.run_x_observer \
  --qualify-live --handle JMilei --max-pages 2 --max-results 5 --max-usd 0.25
```

The token must be supplied in a private operator shell and must not be printed,
committed, placed in a Sheet, or copied from either publishing account.

## Evidence and recovery

`EvidenceStore` is a portable local adapter for the canonical boundary. It
writes immutable page evidence and manifests, and uses a revision-checked
cursor. `commit_page` advances the cursor only after projection succeeds. A
crash after page persistence but before projection or cursor commit is safe to
replay. The local adapter is not a production unattended store; a private
durable object-store adapter and its IAM must be qualified before enabling the
Actions workflow.

The Sheet workbook is a projection only. No live Sheet write is authorized by
Phase A. The future projection must preserve `EVENTS`, `POSTS`, `RUNS`, and
`CURSORS` ownership and must never overwrite human-owned `ACCOUNTS` settings.

## Promotion packet

Before enabling the workflow, record:

- verified numeric identity and public status for each configured account;
- actual endpoint fields, expansions, pagination, partial errors, and rate evidence;
- dedicated read-only credential scope;
- durable evidence backend, prefix, generation/CAS behavior, and rollback;
- estimated X resource cost and Actions minutes;
- explicit account list, schedule, budget, stop conditions, and coverage gaps.

Until that packet exists, leave the scheduler disabled. A consumer such as Milei
Mirror may use `office_runtime.x_observer.consumer.recent_activity` over a
read-only snapshot, but it cannot access credentials, the HTTP client, or
mutate evidence.
