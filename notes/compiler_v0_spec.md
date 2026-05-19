# Compiler v0 spec (ADR lite)

Status: Accepted
Date: 2026-01-04

Purpose
Freeze the minimum contracts for the block compiler so implementation can proceed without schema thrash.

Non goals (v0)
- No Google Sheet wiring
- No timers or cron wiring
- No AI hydration
- No scoring tuning beyond a simple default
- No automatic project metadata discovery beyond existing frontier inputs

Core loop reminder
Frontier rows -> IssueIR -> ProjectIR rollups -> CandidateBlocks (archetype templates) -> PreparedBlock JSONL

## 1) Enums

### ModeId
- PIPELINE
- TOOLSMITH
- SERVICE
- CONTRACT
- GOVERNANCE
- CONTACT
- MAINT

Notes
- MAINT is a block mode for batching hygiene, not a craft. It is allowed for queue generation.

### Severity
- system_error
- actionable_failure
- ineligible
- warning
- ok

### PluginId
- smoke
- commit_recent
- runbook
- endpoint

### IssueType
These are compiler level issue categories derived from frontier rows.

Substrate and wiring
- repo_not_git
- repo_path_missing
- makefile_missing
- plugin_not_loaded

Execution failures
- cmd_nonzero

Warnings and hygiene
- runbook_missing
- worktree_dirty
- staleness_old_commit

Other
- unknown

### ArchetypeId
Archetypes are templates that compile frontier into runnable blocks.

- substrate_bootstrap_sweep
- plugin_boundary_fix
- smoke_failure_triage
- shared_root_cause_elimination
- runbook_sweep
- hygiene_cleanup
- season_decisions

### OperatorId
Operator ids are stable. v0 registry is names only. Definitions live elsewhere.

- LockInSession
- ADRLite
- DefineCapabilitiesAndTests
- RepoInitUpgrade
- PrereqsBootstrap
- RunSmoke
- FailureClassify
- DebugPacketCreate
- MinimalReproExtraction
- ResolveDebugPacket
- RegressionGuardrailAdd
- RunbookHumanDraft
- RunbookMachineSpec
- EvidenceManifestWrite
- WorktreeClean
- AssessSeasonForProject
- CadenceSetOrArchive

## 2) Minimal OperatorRegistry subset (v0)
We only need legality by mode and default timebox for compilation. Steps are not required in v0.

OperatorRegistry entry fields
- op_id: OperatorId
- legal_modes: list[ModeId]
- default_timebox_min: int
- evidence_pattern: string (short name)
- acceptance_checks: list[string] (names only, no commands yet)

Registry v0 (names plus legality)
- LockInSession: legal_modes [GOVERNANCE, CONTACT], timebox 10
- ADRLite: legal_modes [GOVERNANCE, CONTRACT, TOOLSMITH], timebox 15
- DefineCapabilitiesAndTests: legal_modes [TOOLSMITH, GOVERNANCE], timebox 30
- RepoInitUpgrade: legal_modes [TOOLSMITH], timebox 20
- PrereqsBootstrap: legal_modes [TOOLSMITH], timebox 25
- RunSmoke: legal_modes [PIPELINE, TOOLSMITH], timebox 15
- FailureClassify: legal_modes [PIPELINE, CONTRACT], timebox 20
- DebugPacketCreate: legal_modes [CONTRACT, SERVICE, PIPELINE], timebox 15
- MinimalReproExtraction: legal_modes [CONTRACT], timebox 25
- ResolveDebugPacket: legal_modes [CONTRACT, SERVICE], timebox 45
- RegressionGuardrailAdd: legal_modes [CONTRACT, TOOLSMITH], timebox 25
- RunbookHumanDraft: legal_modes [GOVERNANCE, CONTACT], timebox 15
- RunbookMachineSpec: legal_modes [TOOLSMITH, GOVERNANCE], timebox 20
- EvidenceManifestWrite: legal_modes [PIPELINE, TOOLSMITH], timebox 15
- WorktreeClean: legal_modes [MAINT, TOOLSMITH], timebox 20
- AssessSeasonForProject: legal_modes [GOVERNANCE], timebox 30
- CadenceSetOrArchive: legal_modes [GOVERNANCE], timebox 20

## 3) IR contracts

### FrontierRow (input)
This is the input record shape. Exact field names match what the checker emits.

Required
- bucket: string
- date: string (YYYY-MM-DD)
- normalized_class: Severity as string
- plugin: PluginId as string
- project_id: string
- short_diag: string
- ts_started: int (unix seconds)

Optional
- run_id: string
- executed: bool
- duration_ms: int

### IssueIR
Derived from a single frontier row.

Required
- project_id: string
- plugin: PluginId
- severity: Severity
- issue_type: IssueType
- signature: string
- pointers: object
  - log_path: string|null
  - repo_path: string|null
  - runbook_path: string|null

Rules
- signature is a stable grouping key for batching. v0 signature is:
  - plugin + "|" + issue_type + "|" + normalized bucket prefix
- pointers may be null. do not invent paths.

### ProjectIR
Rollup per project.

Required
- project_id: string
- issues: list[IssueIR]
- blockers: list[IssueType]
- eligibility: object
  - can_run_smoke: bool
  - can_flip_endpoint: bool
- counters: object
  - system_error: int
  - actionable_failure: int
  - ineligible: int
  - warning: int

Rules
- blockers are issue types in {repo_not_git, repo_path_missing, makefile_missing, plugin_not_loaded}
- can_run_smoke is false if any blocker exists except repo_not_git, because smoke may not require git
  - v0: repo_not_git does not block smoke
- can_flip_endpoint is false if can_run_smoke is false

## 4) PreparedBlock contract (output)

Output format
- JSONL file. Each line is one PreparedBlock JSON object.

PreparedBlock fields

Required
- block_id: string (stable, unique, recommended format: YYYYMMDD + "_" + archetype + "_" + 3 digit seq)
- date: string (YYYY-MM-DD)
- duration_min: int (default 90 for focus archetypes, 30 for hygiene)
- mode: ModeId
- archetype: ArchetypeId
- title: string
- triggers: list[object]
  - project_id: string
  - plugin: PluginId
  - severity: Severity
  - issue_type: IssueType
  - signature: string
- targets: list[object]
  - project_id: string
  - issue_signatures: list[string]
- operator_plan: list[object]
  - op_id: OperatorId
  - timebox_min: int
  - stop_rule: string
  - expected_evidence: list[string]
- expected_frontier_deltas: list[object]
  - project_id: string
  - from_issue_type: IssueType
  - to_state: string (one of: removed, downgraded, reclassified)
- stop_rules: list[string]
- acceptance: list[string]

Optional
- score: object
  - total: float
  - components: object
- notes: string
- hydration: object
  - brief: string
  - commands: list[string]

Invariants
- mode must be legal for all operators in operator_plan
- operator_plan must have at least 2 operators for focus blocks
- acceptance must include at least one evidence check statement (human readable is ok in v0)
- PreparedBlock must not claim frontier changes that are impossible under its archetype
  - example: runbook_sweep cannot claim cmd_nonzero becomes pass

## 5) Archetype templates (as data)

Each archetype is a data record with:
- archetype: ArchetypeId
- mode: ModeId
- duration_min: int
- selection_rule: string
- max_projects: int
- operator_plan_template: list[OperatorId] with default timeboxes
- expected_delta_rules: list[string]
- feasibility_rule: string

Archetype definitions v0

1) substrate_bootstrap_sweep
- mode: TOOLSMITH
- duration: 90
- selection_rule: pick up to 4 projects with blockers in {repo_path_missing, makefile_missing, repo_not_git}
- operator_plan_template:
  - RepoInitUpgrade (20)
  - PrereqsBootstrap (25)
  - RunSmoke (15) only if makefile_missing no longer present
  - LockInSession (10)
- feasibility_rule: always feasible if repo_path is known in pointers, otherwise downgrade to GOVERNANCE note
- expected_delta_rules:
  - repo_path_missing should become downgraded or reclassified
  - makefile_missing should become removed
  - repo_not_git should become removed or explicitly excluded by governance

2) plugin_boundary_fix
- mode: CONTRACT
- duration: 90
- selection_rule: one signature group of plugin_not_loaded, highest severity first
- operator_plan_template:
  - MinimalReproExtraction (25)
  - DebugPacketCreate (15)
  - ResolveDebugPacket (45)
  - RegressionGuardrailAdd (25) if time remains
- feasibility_rule: requires pointers.log_path or a repro command in short_diag, otherwise convert to DebugPacketCreate only
- expected_delta_rules:
  - plugin_not_loaded should become removed or reclassified to unknown with a packet

3) smoke_failure_triage
- mode: PIPELINE
- duration: 90
- selection_rule: up to 8 projects with cmd_nonzero where ProjectIR.eligibility.can_run_smoke is true
- operator_plan_template:
  - RunSmoke (15) per repo until time budget consumed
  - FailureClassify (20) once, produces triage table artifact
  - DebugPacketCreate (15) for 1 to 3 real_logic_bug items
  - LockInSession (10)
- feasibility_rule: only include eligible projects
- expected_delta_rules:
  - cmd_nonzero should become reclassified (triaged) even if not removed

4) shared_root_cause_elimination
- mode: CONTRACT
- duration: 90
- selection_rule: only generated if >= 3 IssueIR share same signature class from triage output
- operator_plan_template:
  - MinimalReproExtraction (25)
  - ResolveDebugPacket (45)
  - RegressionGuardrailAdd (25)
  - RunSmoke (15) verify on 2 repos
- feasibility_rule: requires triage table exists, otherwise do not generate
- expected_delta_rules:
  - multiple cmd_nonzero should downgrade or be removed

5) runbook_sweep
- mode: GOVERNANCE
- duration: 90
- selection_rule: up to 10 projects with runbook_missing warnings
- operator_plan_template:
  - RunbookHumanDraft (15) repeated
  - RunbookMachineSpec (20) repeated for top 3
  - LockInSession (10)
- feasibility_rule: always feasible
- expected_delta_rules:
  - runbook_missing should be removed or downgraded

6) hygiene_cleanup
- mode: MAINT
- duration: 30
- selection_rule: projects with worktree_dirty warnings
- operator_plan_template:
  - WorktreeClean (20)
  - RunSmoke (15) optional sanity if time remains
- feasibility_rule: always feasible
- expected_delta_rules:
  - worktree_dirty removed

7) season_decisions
- mode: GOVERNANCE
- duration: 90
- selection_rule: projects with staleness_old_commit warnings
- operator_plan_template:
  - AssessSeasonForProject (30) repeated for up to 3 projects
  - CadenceSetOrArchive (20)
  - ADRLite (15) if a policy change is made
  - LockInSession (10)
- feasibility_rule: always feasible
- expected_delta_rules:
  - staleness_old_commit removed by policy change, not by fake commits

## 6) File layout and CLI

Repo location
- project: Auto Projects checker (compiler lives here for v0)

Paths
- src/compiler/
  - __init__.py
  - enums.py
  - ir_types.py
  - classify.py
  - archetypes.py
  - compile_blocks.py
- fixtures/
  - frontier_fixture.csv (or .tsv)
- out/
  - compiler/
    - blocks.YYYYMMDD.jsonl
    - rollups.YYYYMMDD.json
    - issues.YYYYMMDD.jsonl

CLI
- python -m compiler.compile_blocks --in fixtures/frontier_fixture.csv --out out/compiler --date 2026-01-04

Acceptance checks for v0 implementation work (not this spec)
- produces JSONL with at least 3 PreparedBlock lines on the provided fixture
- every PreparedBlock validates against schema
- blocks do not include ineligible projects for smoke_failure_triage

## 7) Next pointer
Implement IR + classify mapping to meet this schema, then run on fixture and inspect the queue.
