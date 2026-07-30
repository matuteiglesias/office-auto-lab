# GCP Project Health Retrofit — Embryo Plan v0.1

## North

Turn the current Repo Health subsystem into a bounded, read-only internal developer-platform workload on GCP without changing the meaning of project policy, normalized findings, or prepared human work blocks.

The cloud retrofit must make a new claim honest:

> `office-auto-lab` can inspect an allowlisted set of GitHub repositories from a keyless Cloud Run Job, persist longitudinal health evidence in BigQuery and immutable run packets in Cloud Storage, and compile findings into explainable work blocks with tested failure and retry behavior.

## Architectural decision already frozen

**The first cloud adapter is GitHub API-native. It is not a shallow-clone executor.**

Reason:

- `commit_recent` and runbook-presence facts can be represented through bounded repository metadata/content reads.
- `make_smoke` executes repository-controlled code and materially enlarges the trust boundary.
- `pipeline_output` depends on artifacts produced on a specific local machine.
- `env` diagnoses the runner environment more than the remote repository.

The v0.1 cloud workload therefore supports only explicitly remote-capable, read-only plugin semantics.

## Product ownership

| Concern | Owner |
|---|---|
| Project/capability policy | Repo Health domain in `office-auto-lab` |
| Intent computation | Repo Health policy layer |
| Plugin result vocabulary | Repo Health plugin contract |
| Finding normalization/frontier | Repo Health runner/export layer |
| Human work-block semantics | Repo Health compiler |
| Remote repository reads | GitHub repository-source adapter |
| Cloud execution | `infra/gcp` deployment adapter |
| Longitudinal history | BigQuery adapter |
| Immutable evidence packets | Cloud Storage adapter |
| Latest human-facing state | A governed consumer/compactor, not arbitrary plugin writes |

## Phase map

```text
Phase 0 — Characterize and install retrofit governance
      ↓
Phase 1 — Stabilize local semantics and cloud capability metadata
      ↓
Phase 2 — Introduce repository-source boundary and remote plugins
      ↓
Phase 3 — Freeze run bundle and persistence contracts
      ↓
Phase 4 — Add GCP adapters and container entrypoint
      ↓
Phase 5 — Provision and execute on GCP
      ↓
Phase 6 — Failure, repeated operation, evidence, closure
```

## Critical chain and pruning

| PR | Purpose | Dependency | Classification | Can be pruned? |
|---|---|---|---|---|
| `PR-G0` | Install embryo plan; characterize current behavior and defects | none | Fundamental | No |
| `PR-G1` | Repair policy/no-write/result semantics; declare plugin capabilities | G0 accepted | Critical | No |
| `PR-G2` | RepositorySource boundary + GitHub API-native plugins + parity fixtures | G1 accepted | Critical | No |
| `PR-G3` | Provider-neutral run bundle, immutable evidence, and persistence ports | G2 accepted | Critical | No |
| `PR-G4` | BigQuery/GCS adapters, ADC, container job entrypoint | G3 accepted | Critical | No |
| `PR-G5` | Terraform: Artifact Registry, Cloud Run Job, IAM, optional manual execution | G4 accepted | Critical for cloud claim | No |
| `PR-G6` | Scheduler, failure probes, repeated runs, cost/security/evidence pack | G5 accepted | Critical for `OPERATED` claim | Scheduler may be pruned if the accepted claim stops at `VALIDATED`; failure probe may not |
| `PR-G7` | Control Tower signal and extraction decision | G6 accepted | Optional integration | Yes |

## Phase 0 — Characterize before changing behavior

### PR-G0 — Retrofit control surface and characterization

**Goal**

Add this embryo plan, starting context, prompts, carry state, and characterization tests that pin the current semantics relevant to cloud work.

**Must characterize**

- effective policy and due/scheduled behavior;
- `--no-write` behavior;
- plugin discovery and current plugin inventory;
- normalized result fields retained or discarded;
- local-path assumptions;
- compiler determinism for a fixed frontier fixture;
- current credential discovery behavior.

**No behavior fixes in this PR.**

**Acceptance**

- focused characterization tests pass;
- each suspected defect is either reproduced or explicitly disproved;
- current plugin cloud capability table exists;
- closure note names the exact changes assigned to G1.

## Phase 1 — Stabilize the local product boundary

### PR-G1 — Correctness and capability metadata

**Goal**

Repair only the semantics that would otherwise be amplified in cloud execution.

**Expected scope**

- make due/scheduled semantics intentional and tested;
- ensure no-write mode performs no external writeback;
- preserve sufficient evidence/meta in normalized results;
- replace unrestricted dynamic cloud plugin discovery with explicit capability metadata:
  - `local_only`;
  - `remote_read`;
  - `remote_execute` (unsupported in v0.1);
- retain local behavior for existing commands.

**Acceptance**

- regression tests cover fixes;
- local fixture output changes are explained;
- only `remote_read` plugins are eligible for GCP profile;
- no provider SDK is introduced.

## Phase 2 — Remote repository inspection

### PR-G2 — RepositorySource and GitHub API adapter

**Goal**

Separate repository facts from local filesystem execution.

**Core design**

```text
policy project identity
        ↓
RepositorySource
  ├── LocalRepositorySource
  └── GitHubRepositorySource
        ↓
remote-capable plugins
        ↓
existing normalized frontier
```

**Initial supported facts**

- default branch and current commit identity;
- last commit timestamp/subject;
- recent commit count;
- repository visibility/archival state;
- README presence;
- `.gitignore` presence;
- runbook presence through bounded path/content enumeration.

**Non-goals**

- worktree dirtiness;
- local ahead/behind state;
- executing Make targets;
- searching generated runtime artifacts;
- arbitrary content crawling.

**Acceptance**

- local and GitHub adapters produce semantically equivalent results for supported fixture repositories;
- unsupported facts return explicit `NA`/ineligible classifications rather than fabricated parity;
- API calls are bounded and testable through fakes;
- allowlist and safe repository identity validation exist.

## Phase 3 — Execution and evidence contract

### PR-G3 — Run bundle and persistence ports

**Goal**

Make one repo-health execution a stable producer-owned artifact before adding GCP adapters.

**Run bundle minimum**

- run identity and source commit;
- policy/input identity;
- effective intents;
- plugin results;
- normalized frontier;
- prepared blocks;
- exception inventory;
- counters;
- start/end/status;
- checksums or hashes where practical.

**Ports**

- `PolicySource`;
- `RunEvidenceSink`;
- `HistorySink`;
- optional `LatestSignalSink`.

**Local adapters remain the default.**

**Acceptance**

- atomic local run directory;
- replay/duplicate run behavior is defined;
- output schemas are validated;
- one failed plugin is represented without corrupting the run;
- existing compiler consumes the new frontier without semantic drift.

## Phase 4 — GCP adapters

### PR-G4 — BigQuery, Cloud Storage, ADC, job entrypoint

**Goal**

Implement provider adapters without provisioning production infrastructure.

**BigQuery tables**

- `runs`;
- `run_intents`;
- `plugin_results`;
- `exceptions`;
- optional `prepared_blocks`.

**Cloud Storage**

- immutable run packet under a run-derived key;
- checksum and manifest;
- no mutable latest object written by the job.

**Identity**

- Application Default Credentials;
- no service-account JSON path in the cloud entrypoint.

**Acceptance**

- adapters test against fakes/emulators or contract fixtures;
- BigQuery row identities and idempotency behavior are explicit;
- a container can execute locally with a local profile;
- cloud profile refuses local filesystem repository paths.

## Phase 5 — Minimal infrastructure

### PR-G5 — Terraform and first remote execution

**Goal**

Provision the smallest infrastructure set needed for one manually executed Cloud Run Job.

**Resources**

- Artifact Registry repository;
- runtime service account;
- Cloud Run Job;
- BigQuery dataset/tables;
- Cloud Storage evidence bucket/prefix;
- narrowly scoped IAM;
- logging configuration.

**Initially prunable**

Cloud Scheduler may wait until G6. Manual job execution is sufficient for G5.

**Acceptance**

- Terraform plan/apply from clean state;
- image digest tied to source commit;
- one allowlisted public repository inspected;
- BigQuery and GCS evidence reconcile to the same run ID;
- denied-access probe outside allowed resources.

## Phase 6 — Operate and close

### PR-G6 — Schedule, failure, recovery, cost, evidence

**Goal**

Move from one execution to an operated bounded workload.

**Failure probes**

- invalid/non-allowlisted repository;
- GitHub rate-limit or authentication error;
- BigQuery permission or row-write failure;
- one plugin failure with remaining run evidence intact.

**Acceptance**

- at least two scheduled or repeated executions;
- retry/idempotency behavior demonstrated;
- failed run visible in BigQuery/logs/evidence;
- cost estimate and teardown documented;
- market-facing evidence packet produced;
- honest maturity state assigned: `VALIDATED` or `OPERATED`.

## Optional Phase 7 — Consumer and extraction decision

### PR-G7 — Control Tower signal

Only activate when a real consumer contract is ready.

Possible output:

- latest accepted project-health signal;
- unresolved exception summary;
- pointer to immutable run evidence.

Do not create a general event bus merely to connect the systems.

## Retirement and extraction policy

### Keep in this repository initially

- policy, runner, plugin contracts, compiler;
- repository-source abstraction;
- GCP adapters under `src/.../adapters/gcp` or equivalent;
- Terraform under `infra/gcp`;
- retrofit evidence and runbooks.

### Local compatibility surfaces

- local repo-path plugins;
- systemd/local execution;
- Google Sheet policy adapter.

They remain supported but are not part of the GCP claim.

### Candidates for later retirement

- service-account file requirement in the cloud profile;
- unbounded dynamic plugin discovery in the cloud profile;
- Google Sheet result writeback as execution history.

### Extraction gate

Create a separate repository/package only when:

1. a second system consumes the repository-source or run-bundle package;
2. it needs an independent security/release lifecycle;
3. dependency pressure materially harms `office-auto-lab`.

Do not extract for aesthetic cleanliness alone.

## Stop conditions

The retrofit stops when:

- G6 is accepted and the evidence claim is honest; or
- a blocker is reproducible and the retrofit is parked with exact re-entry; or
- G3 proves the domain cannot be made remote-read-only without changing its meaning.

The retrofit must not expand into arbitrary repository code execution, a generalized internal developer platform, or a portfolio-wide dashboard.
