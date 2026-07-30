# office-auto-lab documentation quality and acceptance v0.1

## Page-level quality bar

A canonical page must:

- identify audience, owner, status, and verification commit;
- state scope and non-goals;
- use current capability names rather than PR labels;
- point to executable source and tests;
- distinguish commands executed from illustrative examples;
- include expected observable results;
- describe failure, recovery, and stop conditions where operational;
- identify security or mutation boundaries;
- link rather than duplicate another page's canonical procedure;
- avoid unsupported claims.

## Seniority signals the documentation should expose

- clear product and component ownership;
- explicit invariants and state writers;
- trade-offs and rejected alternatives;
- idempotency and replay semantics;
- least-authority identity and denied operations;
- failure reconciliation instead of success-by-exit-code;
- cost, retention, rollback, and teardown boundaries;
- versioned contracts and compatibility commitments;
- honest maturity/status language;
- maintenance ownership and freshness checks.

## Evidence ladder

Use exactly these meanings:

| Level | Meaning |
|---|---|
| Designed | decision/contract exists |
| Implemented | code exists on the inspected commit |
| Locally validated | relevant local tests or smoke runs passed |
| Deployment-ready | provider adapter, container, IaC, and runbook exist |
| Deployed | provider resources and one execution are evidenced |
| Operated | repeated execution, failure/recovery, and observability evidence exist |

Never collapse these states.

## PR acceptance checklist

- [ ] Active PR only; no later-phase work.
- [ ] Source commit recorded.
- [ ] All new relative links checked.
- [ ] Commands executed or explicitly marked unverified.
- [ ] No product behavior changed.
- [ ] No duplicated canonical command introduced.
- [ ] Status and deployment claims reviewed.
- [ ] Historical pages preserved or redirected safely.
- [ ] Closure note added.
- [ ] Carry update proposed, not self-accepted.

## Documentation review questions

1. Can a reader find this page from the root?
2. Does the page solve one recognizable reader problem?
3. Could the instructions cause an unsafe mutation?
4. Is there an independent verification surface?
5. Would a source change make this page stale? If so, who must update it?
6. Is a more authoritative page being duplicated?
7. Does the page reveal a durable engineering decision or merely narrate files?
