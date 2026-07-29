# GCP Project Health Sprint Contract v0.1

**Status:** FROZEN FOR IMPLEMENTATION  
**Sequence:** First cloud sprint  
**Host repository:** `matuteiglesias/office-auto-lab`  
**Workload:** Repo Health Policy Engine + Remote Inspection + Work-Block Compiler  
**Estimated implementation:** 8 deep-focus blocks, approximately 24–30 hours  
**Learning focus:** distinguish product semantics from local-runtime accidents, then assign each cloud component one explicit responsibility.

---

## 1. Claim to be earned

After acceptance, the honest portfolio claim is:

> Designed, deployed, and operated a policy-driven repository-health batch job on GCP using Cloud Run Jobs, workload identity, Cloud Scheduler, BigQuery, Cloud Storage, and Terraform. The job reads a frozen governance snapshot, inspects an allowlist of GitHub repositories without executing their code, normalizes findings through the existing frontier contract, compiles them into bounded human work blocks, persists longitudinal evidence, and survives a controlled failure and retry.

This claim does **not** include remote CI, arbitrary repository execution, production-scale platform ownership, or complete parity with every local plugin.

---

## 2. Architecture decision

### Decision: GitHub API-native inspection for v0.1

Do **not** shallow-clone repositories in the first GCP slice.

The current plugin family contains materially different trust and data requirements:

| Current plugin | Real semantic | GCP v0.1 disposition |
|---|---|---|
| `commit_recent` / Git activity | Inspect repository metadata, commits, branch, and activity | Reimplement over a read-only GitHub repository adapter |
| `runbook` | Discover and score repository documentation | Reimplement over GitHub tree/file reads |
| `smoke` | Execute `make smoke` or `make run_all` inside a repository | `local_execution_only`; excluded |
| `pipeline_output` | Search generated artifacts and modification times on a local filesystem | `runtime_local_only`; excluded |
| `env` | Inspect the Python/container environment and optional local Git facts | Split into a job self-check; not a project-health plugin |

Why this is the mature first boundary:

1. API-native inspection preserves the useful policy → intent → result → frontier → work-block spine.
2. It avoids executing repository-controlled code under a cloud service identity.
3. It avoids pretending that a clean Git checkout contains generated runtime outputs.
4. It makes the cloud claim precise: **remote source-governance inspection**, not remote build execution.
5. A future trusted execution runner can be designed as a separate security boundary rather than smuggled into this sprint.

### Deferred architecture

A future `trusted_repo_execution_runner` may use ephemeral shallow clones for selected repositories and execute bounded smoke targets in a sandbox with no cloud credentials and restricted egress. That is a separate product and threat model.

Do not create that repository during this sprint.

---

## 3. Bounded workload

The accepted workload is exactly one Cloud Run Job execution that:

1. reads four governance tables:
   - project registry;
   - capabilities;
   - plugin policy;
   - plugin prerequisites;
2. validates and freezes them as one immutable input snapshot;
3. computes effective run intents;
4. filters to:
   - at most **3 allowlisted public GitHub repositories**;
   - exactly **2 remote-capable plugins**: activity and runbook;
5. executes only read-only GitHub API calls;
6. normalizes results into the existing frontier row shape;
7. runs the existing deterministic classifier and work-block compiler;
8. writes immutable run evidence to Cloud Storage;
9. appends modeled history to BigQuery;
10. exits with a contractual status.

Initial cadence: manual execution.  
Acceptance cadence: once daily for at least three runs.

### Input identity

Cloud rows must use:

```text
project_id
repository_full_name = owner/repository
enabled
next
priority
capability tags
```

`repo_path`, `workdir`, and arbitrary filesystem paths are invalid for remote plugins.

### Runtime limits

- 1 task;
- 1 vCPU;
- 512 MiB–1 GiB memory;
- 15-minute timeout;
- one platform retry;
- no more than 3 repositories;
- no more than 2 plugins;
- no repository code execution.

---

## 4. Architecture

```text
Cloud Scheduler
      │
      ▼
Cloud Run Job: repo-health-remote
      │
      ├── service identity / ADC
      ├── read governance Sheet
      ├── freeze + hash input snapshot
      ├── compute policy intents
      ├── GitHub read adapter
      ├── remote inspection plugins
      ├── normalize frontier
      ├── classify issues
      └── compile prepared work blocks
             │
             ├── Cloud Storage: immutable evidence packet
             ├── BigQuery: modeled longitudinal history
             └── Cloud Logging: structured operational logs
```

Cloud Run jobs can be scheduled through Cloud Scheduler and should use an assigned service account as their service identity; Application Default Credentials are the runtime mechanism for Google Cloud API calls.

### 4.1 Internal seams

Introduce these concepts inside `office-auto-lab` before cloud code:

```python
class RepoSource(Protocol):
    def get_repository(self, repository_full_name: str) -> RepositoryFacts: ...
    def list_tree(self, repository_full_name: str, ref: str) -> list[TreeEntry]: ...
    def read_text(self, repository_full_name: str, path: str, ref: str) -> str: ...
    def list_commits(self, repository_full_name: str, *, since: datetime) -> list[CommitFacts]: ...

class PluginExecutionClass(Enum):
    REMOTE_INSPECTION = "remote_inspection"
    LOCAL_INSPECTION = "local_inspection"
    LOCAL_EXECUTION = "local_execution"
    RUNNER_SELF_CHECK = "runner_self_check"
```

The cloud runner must load plugins from an explicit registry, not dynamic folder discovery.

Suggested package boundary:

```text
src/office_runtime/ops/repo_health/
  core/
    policy.py
    result_contract.py
    frontier.py
  remote/
    github_source.py
    activity_plugin.py
    runbook_plugin.py
    registry.py
  compiler/
  cloud/
    run_job.py
    evidence.py
    bigquery_writer.py
```

Do not move files merely for aesthetics. Establish imports and tests first; relocate only when the seam is stable.

### 4.2 Control plane versus history

**Google Sheets remains an authoring control plane**, not execution history.

At job start:

1. read the four tabs;
2. validate required columns;
3. canonicalize ordering and values;
4. serialize one snapshot;
5. compute SHA-256;
6. write it under the run evidence prefix;
7. use only that frozen snapshot for the run.

The cloud job performs **no Sheet writeback** in v0.1.

This prevents policy edits during a run from changing its meaning and prevents the mutable authoring surface from becoming the audit log.

### 4.3 Cloud Storage evidence layout

```text
gs://<bucket>/repo-health/
  runs/YYYY/MM/DD/<run_id>/
    input/governance_snapshot.json
    input/governance_snapshot.sha256
    run_manifest.json
    intents.jsonl
    plugin_results.jsonl
    frontier.csv
    prepared_blocks.jsonl
    summary.json
```

Objects under a completed run prefix are immutable by convention and IAM.

### 4.4 BigQuery model

Dataset: `repo_health`

Tables:

- `runs`
  - partition by `run_date`;
  - cluster by `status`;
- `run_intents`
  - partition by `run_date`;
  - cluster by `project_id`, `plugin`;
- `plugin_results`
  - partition by `run_date`;
  - cluster by `project_id`, `plugin`, `normalized_class`;
- `prepared_blocks`
  - partition by `run_date`;
  - cluster by `archetype`, `mode`.

Preserve compact typed columns for common queries and one `raw_json` field for producer-owned details.

Required views:

- latest health result per repository/plugin;
- unresolved issue signatures by severity and age;
- prepared blocks produced per week.

Partition and cluster choices must be justified by actual query predicates, not added as decoration.

### 4.5 Identity and permissions

Use separate identities:

1. **Scheduler invoker**
   - permission only to execute the named Cloud Run Job.
2. **Job runtime service account**
   - read the named governance Sheet;
   - access one GitHub read credential secret if required;
   - create objects only under the repo-health bucket prefix;
   - append only to the named BigQuery dataset/tables;
   - emit logs.
3. **Terraform deployer**
   - provisioning permissions;
   - not used by the runtime.

The GitHub credential, when required, is read-only and restricted to the allowlisted repositories. It is stored in Secret Manager, never in the image or Sheet.

---

## 5. Pre-cloud corrections

These are Gate 0 work, not optional cleanup.

1. **Scheduling semantics**
   - Current policy computes `due` but schedules whenever prerequisites pass.
   - Freeze the intended rule and test it.
   - v0.1 rule: `scheduled = enabled AND due AND prereq_ok`.

2. **Dry-run/no-write semantics**
   - `--no-write` must guarantee no Sheet, frontier, BigQuery, or Cloud Storage mutation.
   - Planning output may be printed or written only to an explicitly supplied temporary directory.

3. **Result preservation**
   - Preserve plugin `evidence` and `meta` in the run artifact.
   - The normalized frontier remains compact, but raw diagnostic evidence must not disappear.

4. **Plugin registry**
   - Replace cloud-time dynamic folder scanning with a declared allowlist.
   - Reject an intent whose plugin is not registered for `REMOTE_INSPECTION`.

5. **Credentials**
   - Remove the required service-account file argument from the cloud entrypoint.
   - Use ADC/service identity.

6. **Writeback**
   - Disable the current project/runtime-health Sheet writeback path.
   - Longitudinal execution truth belongs in BigQuery and immutable evidence packets.

7. **Run contract**
   - One orchestration `run_id`;
   - deterministic intent IDs beneath it;
   - contractual status: `success`, `partial_success`, `error`, or `empty_success`;
   - manifest finalized once.

---

## 6. Gates

### Gate 0 — Local behavior characterization

Pass when:

- current policy cases are pinned by tests;
- due/not-due behavior is explicit;
- `--no-write` has a non-mutation test;
- plugin result evidence survives normalization;
- one local fixture produces deterministic frontier and prepared blocks.

### Gate 1 — Remote boundary freeze

Pass when:

- `repository_full_name` replaces local path semantics for remote plugins;
- execution classes are declared;
- only activity and runbook are remote-capable;
- an arbitrary plugin name is rejected before execution;
- an unallowlisted repository is rejected before API access.

### Gate 2 — GitHub adapter

Pass when:

- adapter tests use deterministic fixtures;
- activity plugin reproduces the intended repository-level facts;
- runbook plugin produces deterministic scoring from a remote tree;
- pagination, missing files, 404, 403, and rate-limit responses are classified;
- no GitHub write method exists in the adapter interface.

### Gate 3 — Evidence and BigQuery

Pass when:

- the immutable evidence packet validates locally;
- checksums and row counts agree;
- BigQuery DDL is versioned;
- repeated insertion of the same run is idempotent;
- three required views return useful results on fixture data.

### Gate 4 — Container and Terraform

Pass when:

- a minimal image contains only the remote repo-health runtime and compiler dependencies;
- it runs as a non-root user;
- Terraform provisions job, identities, bucket, dataset, scheduler, logging/alert resources, and budget;
- a clean plan/apply succeeds;
- teardown is documented.

### Gate 5 — Manual GCP execution

Pass when:

- one real job inspects 1–3 allowlisted repositories;
- the governance snapshot hash is recorded;
- Cloud Logging can locate the complete run by `run_id`;
- GCS and BigQuery evidence agree;
- prepared blocks are produced or an honest `empty_success` is recorded.

### Gate 6 — Failure and recovery

Pass when the controlled failure probe succeeds.

### Gate 7 — Operated evidence

Pass when:

- at least three scheduled executions complete;
- one failure/recovery cycle is present;
- the latest BigQuery view is correct;
- cost and retention checks are recorded;
- the evidence packet is understandable without repository archaeology.

---

## 7. Failure probe

Use two separate probes.

### Domain failure

Add one allowlisted test row pointing to a nonexistent repository.

Expected result:

- plugin returns a normalized, bounded failure/ineligible result;
- the job continues with other repositories;
- status becomes `partial_success`;
- evidence identifies the repository and HTTP class;
- no stack trace is required to understand the issue.

### Platform retry and idempotency

Use a test-only failpoint:

```text
FAILPOINT=after_plugin_results
```

First attempt:

1. freezes governance snapshot;
2. executes plugins;
3. writes staged evidence;
4. exits nonzero before final manifest and BigQuery finalization.

Cloud Run retries once.

Second attempt:

- uses the same logical run identity plus incremented attempt;
- does not duplicate final BigQuery rows;
- finalizes exactly one accepted manifest;
- preserves the failed attempt as operational evidence.

Acceptance requires proving both the failed attempt and the successful recovery.

---

## 8. Evidence

Required sprint evidence:

- architecture decision record;
- current-plugin classification table;
- local characterization test output;
- Terraform plan;
- deployed resource inventory;
- IAM policy summary;
- container image digest and source commit;
- Cloud Run Job execution IDs;
- structured log query by `run_id`;
- governance snapshot and checksum;
- GCS run manifest;
- BigQuery row-count reconciliation;
- SQL for the three required views;
- failure and retry evidence;
- cost estimate and actual billing snapshot;
- teardown command;
- concise case-study README.

A screenshot may supplement evidence but cannot replace machine-readable artifacts.

---

## 9. Cost boundary

Hard limits:

- one GCP project for the sprint;
- one Cloud Run Job;
- one daily schedule after acceptance;
- maximum 3 repositories and 2 plugins;
- 1 vCPU;
- maximum 1 GiB memory;
- 15-minute timeout;
- one retry;
- no VPC connector;
- no persistent VM;
- no GKE;
- no Cloud SQL;
- GCS run evidence lifecycle: 30 days for raw packets, longer only for selected evidence;
- BigQuery partition filters required in documented queries;
- budget alert at **$10/month**.

Pause scheduled execution if the budget forecast exceeds the boundary.

---

## 10. Exclusions

- shallow repository clones;
- `make smoke` or `run_all`;
- arbitrary shell execution;
- generated-output freshness checks;
- private repositories in v0.1;
- repository write operations;
- automatic PRs/issues;
- Sheet execution-history writeback;
- Control Tower integration;
- Pub/Sub;
- GKE;
- multi-region design;
- multi-tenant API;
- remote interactive dashboard;
- extraction into a new repository during the sprint.

---

## 11. Stop condition

Stop and mark the sprint `PARKED` when any of these occurs:

1. the work cannot remain read-only;
2. useful output requires executing repository code;
3. the adapter needs broader GitHub authority than read-only allowlisted access;
4. local policy semantics cannot be pinned by tests;
5. `--no-write` cannot be made trustworthy without redesigning the runner;
6. BigQuery becomes a raw dump without useful queries;
7. the sprint exceeds 30 focused hours without reaching manual remote execution;
8. a second cloud service is proposed only to make the diagram look more complete.

The stop artifact must record the failed gate, evidence, and smallest re-entry condition.

---

## 12. Deep-focus implementation plan

### Block 1 — Characterize the existing control loop

**Goal:** prove what the local system currently means.

Work:

- pin policy and scheduling cases;
- reproduce frontier and prepared-block outputs from fixtures;
- document current side effects;
- add non-mutation tests.

Learning checkpoint:

> Can you state which outputs are product contracts and which are local operator conveniences?

Exit: Gate 0 tests are red for known defects and then green after bounded fixes.

### Block 2 — Classify plugin trust and portability

**Goal:** prevent false cloud parity.

Work:

- introduce execution classes;
- build explicit plugin registry;
- mark existing plugins;
- reject unsupported cloud intents.

Learning checkpoint:

> Does a plugin inspect source, inspect a runtime, or execute untrusted code?

Exit: Gate 1.

### Block 3 — Implement the GitHub source adapter

**Goal:** replace filesystem assumptions with a narrow read interface.

Work:

- repository metadata and commit reads;
- default-branch resolution;
- tree listing;
- bounded text fetch;
- pagination and error classification;
- allowlist enforcement.

Exit: adapter fixture suite passes.

### Block 4 — Port two remote inspection plugins

**Goal:** preserve semantics without preserving implementation accidents.

Work:

- activity plugin;
- runbook plugin;
- parity tests against controlled local fixtures;
- normalized result and raw evidence preservation.

Exit: Gate 2.

### Block 5 — Build the run envelope and evidence packet

**Goal:** make every execution independently auditable.

Work:

- run/attempt identity;
- frozen governance snapshot;
- checksum;
- staged/final manifest;
- idempotent local writer;
- exact acceptance validator.

Exit: complete local evidence packet.

### Block 6 — Model BigQuery and write Terraform

**Goal:** create the smallest useful cloud substrate.

Work:

- DDL and queries;
- GCS bucket and lifecycle;
- Cloud Run Job;
- identities and IAM;
- Secret Manager integration if needed;
- Scheduler disabled by default;
- budget alert.

Exit: Gate 3 and Gate 4.

### Block 7 — Execute remotely and probe failure

**Goal:** prove operation, not deployment.

Work:

- manual job;
- reconcile GCS/BigQuery/logs;
- domain failure;
- failpoint/retry;
- idempotency proof;
- repair only the failed acceptance boundary.

Exit: Gate 5 and Gate 6.

### Block 8 — Operate, externalize, and decide extraction

**Goal:** earn the claim and freeze the next boundary.

Work:

- enable daily schedule;
- collect three runs;
- package evidence;
- write case study;
- decide whether the remote runtime merits a separate deployable package.

Extraction rule:

Create a separate repository only when there is either:

1. a second consumer of the remote repo-health core; or
2. a security/release lifecycle incompatible with `office-auto-lab`.

Until then, keep one repository and a narrow build context.

Exit: Gate 7 and sprint closure.
