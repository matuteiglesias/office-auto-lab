# Codex Prompt — PR-G6: Operate, fail, recover, and package evidence

Prerequisite: PR-G5 is accepted.

## Goal

Demonstrate repeated operation, explicit failure, safe retry, bounded cost, and a market-facing evidence packet.

## Required probes

- non-allowlisted repository;
- GitHub auth/rate-limit failure;
- persistence permission/write failure;
- one plugin failure without loss of run evidence.

## Required outputs

- repeated/manual or scheduled runs;
- retry/idempotency evidence;
- logging/monitoring query or alert;
- cost estimate and teardown;
- final architecture and threat-boundary note;
- machine-readable acceptance record;
- honest maturity label.

Scheduler can be pruned only when the accepted claim is `VALIDATED`, not `OPERATED`.

Produce `context/closures/PR-G6.md`. Set next PR to G7 only when a real Control Tower consumer is approved; otherwise close the retrofit.
