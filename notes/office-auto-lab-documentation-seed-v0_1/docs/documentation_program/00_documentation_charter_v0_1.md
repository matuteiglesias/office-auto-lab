# office-auto-lab documentation charter v0.1

## Mission

Create documentation that lets a new human or agent answer, without repository
archaeology:

1. What is this system and what problems does it solve?
2. Which subsystem owns each behavior and artifact?
3. What is the smallest safe command for a common task?
4. Which invariants and trust boundaries must not be broken?
5. How is success independently verified?
6. What is implemented, deployed, blocked, historical, or merely planned?
7. Where should a contributor make a change, and how should it be tested?

The documentation should demonstrate engineering maturity through precision,
ownership, failure handling, evidence, and explicit trade-offs—not through
marketing adjectives.

## Readers

| Reader | First need | Documentation route |
|---|---|---|
| Evaluator / hiring manager | Understand the engineering case quickly | root README → architecture → case studies |
| New contributor | Find ownership and safe development path | root README → docs index → component guide |
| Operator | Execute and recover a known workflow | operations index → canonical runbook |
| Agent | Resolve source truth and bounded task | AGENTS → docs index → reference/source pointers |
| Maintainer | Detect drift and update the right page | canonicality map → maintenance policy |

## Documentation principles

1. **One front door, multiple routes.**
2. **Capability-oriented names beat PR-era names.**
3. **Source and runtime evidence outrank prose.**
4. **One canonical owner per command, contract, and operational path.**
5. **Runbooks include preflight, verification, denial checks, recovery, and teardown.**
6. **Architecture documents expose ownership, data flow, trust boundaries, and state transitions.**
7. **Historical records remain available but visibly noncanonical.**
8. **Diagrams use Mermaid plus a textual explanation so humans and agents can both parse them.**
9. **Documentation status is explicit:** canonical, supporting, historical, generated.
10. **Claims use an evidence ladder:** designed → implemented → locally validated → deployment-ready → deployed → operated.

## Definition of done for the program

The program is complete when:

- a reader can orient from the repository root;
- every major subsystem has an owner guide;
- common commands have one verified canonical home;
- local and GCP Repo Health paths have separate, honest operational status;
- artifacts, contracts, configuration, and failure modes are findable;
- old retrofit and component notes are classified and linked;
- link and metadata checks run in CI or the repository smoke target;
- an evidence-based GCP case study can be read without overstating deployment.
