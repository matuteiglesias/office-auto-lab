# <Operational task> runbook

> **Status:** canonical  
> **Audience:** operator  
> **Owner:** <runtime owner>  
> **Last verified against:** `<commit SHA>`  
> **Estimated duration:** <time>  
> **Risk class:** low | medium | high

## Purpose

Define the single operational outcome this runbook produces.

## Preconditions

- Required tools:
- Required credentials:
- Required inputs:
- Expected clean/dirty worktree state:
- Cost or mutation boundary:

## Preflight

```bash
# commands that make no mutations
```

Stop when:

- ...

## Execute

```bash
# bounded execution commands
```

## Verify

List independent evidence surfaces. A successful command exit alone is not enough.

```bash
# reconciliation commands
```

Acceptance requires:

- ...
- ...

## Negative or denied-access checks

Document actions that must fail and the expected denial.

## Failure handling

| Failure point | Preserve | Retry identity | Recovery | Escalation |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

## Rollback / teardown

```bash
...
```

## Evidence packet

```text
...
```

## Last verified execution

- Date:
- Commit:
- Operator:
- Evidence path:
