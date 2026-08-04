# AGENTS.md — Office Auto Lab

## Mission

Maintain the bounded Office automation runtime that compiles operator inputs, executes approved capabilities, emits run evidence, and produces reviewable artifacts.

This repository may contain mutation-capable commands. Safety, explicit authorization, dry-run behavior, idempotency, evidence, and repository boundaries take precedence over convenience.

## Authority boundary

Matías owns:

- which capability may run;
- which repositories, files, accounts, or external systems may be touched;
- approval of mutations and consequential side effects;
- interpretation of priorities, governance state, and generated recommendations;
- promotion of experimental capability into routine operation.

Agents may:

- inspect and improve bounded capability implementations;
- add fixture-driven tests and evidence checks;
- repair a reproduced compiler, plugin, run-bundle, or repository-health defect;
- prepare an execution packet describing proposed side effects.

Agents must not independently:

- dispatch mutation commands;
- write to another repository, account, calendar, inbox, cloud resource, or deployment;
- expand repository roots or scanning scope;
- change governance priorities or project state;
- treat generated recommendations as approved actions;
- bypass policy gates, evidence capture, dry-run mode, or stop conditions;
- move accounting document intake or human review responsibilities into this runtime.

## Capability execution contract

Before any consequential execution, record:

```yaml
capability:
targets:
read_scope:
write_scope:
dry_run_command:
apply_command:
expected_evidence:
rollback_or_recovery:
stop_condition:
human_authorization:
```

No authorization means no apply run.

A command that can mutate must make the mode visible in its name, arguments, output, or all three. Never infer apply permission from a previous task or from the existence of credentials.

## Repository and artifact boundaries

This repository owns capability execution, Office compilation, run records, evidence, and repository-health outputs.

It does not own:

- GitHub estate authority, which belongs in `projects`;
- read-only Office presentation, which belongs in `office-review`;
- accounting document intake, which belongs in `accounting-doc-triage`;
- source repository product semantics.

Generated files under artifacts, logs, compiler outputs, evidence traces, and run bundles are execution evidence. Do not hand-edit them to manufacture success.

Do not commit secrets, tokens, private context, absolute user paths, raw email, sensitive documents, or unnecessarily large scan outputs.

## Plugin and scanner rules

- Plugins must declare inputs, outputs, side effects, failure behavior, and evidence.
- Discovery is not authorization.
- A scanner may observe only its declared roots and must tolerate inaccessible repositories explicitly.
- Read-only plugins must not acquire hidden write behavior.
- Mutation plugins require stronger tests, dry-run evidence, idempotency or duplicate protection, and a recovery path.
- Do not turn repository-health findings into automatic fixes unless the capability contract explicitly authorizes that transition.

## Commands

Safe default checks include:

```bash
make imports
make docs-check
make audit
make smoke
make repo-scans
make compile-blocks
```

Review command definitions before running because some checks create bounded local files under temporary or generated-output paths.

Operational commands include:

```bash
make daily
make office-compile
make staff-bundles
make staff-briefs
make capture-lifecycle
make repo-health-policy
make repo-health-run
make evidence-today
make office
```

Do not run operational commands merely to validate documentation or metadata. Confirm inputs, outputs, roots, credentials, network access, and mutation behavior first.

## Change discipline

- Prefer one capability or one compiler defect per PR.
- Add or update evidence contracts together with behavior.
- Preserve run IDs, provenance, timestamps, and failure records.
- Do not silently skip failed targets and report an overall success.
- Avoid broad platform refactors during a bounded capability repair.
- Never claim a command, repository scan, external integration, or mutation was run unless it actually was.
- When scope or authority is ambiguous, stop with a decision packet.

## Completion report

```text
Changed:
Capability affected:
Targets inspected:
Commands run:
Dry run performed:
Apply run performed:
Mutations:
Evidence paths:
Secrets/private data accessed:
Failures/skips:
Recovery needed:
Blocked authorization:
Next:
```
