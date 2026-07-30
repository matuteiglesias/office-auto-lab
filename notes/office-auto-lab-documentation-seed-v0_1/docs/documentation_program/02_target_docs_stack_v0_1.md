# office-auto-lab target documentation stack v0.1

## Target tree

```text
README.md
AGENTS.md
docs/
  README.md
  getting-started/
    local-development.md
    first-office-compile.md
    first-repo-health-run.md
  architecture/
    system-overview.md
    runtime-and-artifact-flow.md
    ownership-and-state.md
    trust-boundaries.md
    decisions/
      ADR-0001-*.md
  components/
    office-compile.md
    staff.md
    capture.md
    evidence.md
    repo-health.md
  operations/
    local-routines.md
    systemd-automation.md
    repo-health-local.md
    repo-health-gcp.md
    failure-recovery.md
  reference/
    cli.md
    configuration.md
    artifacts-and-manifests.md
    schemas-and-contracts.md
    repo-health-plugins.md
  case-studies/
    gcp-project-health-retrofit.md
  historical/
    README.md
  documentation_program/
    ...
```

## Layer contracts

### 1. Root README — product front door

Must answer in under five minutes:

- what the system does;
- its major subsystems;
- current operational status;
- one local quickstart;
- where operators, contributors, agents, and evaluators go next.

It must not become a full runbook.

### 2. `docs/README.md` — documentation router

Routes by audience and task. It owns the canonical documentation map and status
legend. It links to historical material but does not reproduce it.

### 3. Getting started — successful first contact

Tutorial pages are linear and outcome-oriented. They minimize choices and leave
an observable artifact. They are not complete reference pages.

### 4. Architecture — reasoning and boundaries

Architecture pages explain:

- subsystem ownership;
- command → runtime → artifact flows;
- state writers and readers;
- trust boundaries;
- local/GCP profile differences;
- durable decisions and trade-offs.

### 5. Components — owner guides

Each component page uses the same contract:

- purpose and non-goals;
- source paths;
- inputs/outputs;
- canonical commands;
- invariants;
- dependencies;
- tests;
- failure modes;
- extension points.

### 6. Operations — verified procedures

Runbooks own commands for repeated operational tasks. Each includes preflight,
execution, reconciliation, negative checks, recovery, teardown, and evidence.

### 7. Reference — lookup surfaces

Reference pages catalog exact commands, flags, variables, schemas, artifact
locations, plugin capabilities, and status values. They avoid tutorial prose.

### 8. Case study — evidence-based engineering narrative

The GCP case study should show:

- before/after architecture;
- constraints and rejected alternatives;
- implementation surfaces;
- security, idempotency, cost, and provenance decisions;
- validation evidence;
- current deployment status and remaining operations gate.

It must link to source and operational evidence and must not imply deployment.

### 9. Historical material

Retrofit plans, closure notes, and superseded instructions remain accessible
with status banners and links to canonical replacements.
