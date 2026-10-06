# Architecture — Editorial Dev Staging v1

## Boundary

This capability is implemented inside `office-auto-lab` as the existing Editorial SIDECAR.

It is not a new control plane and not a generic content platform.

```text
weekly-ops-governance
(editorial constitution)
         │
         ▼
projects ───────► office-auto-lab / Editorial dev staging
(advisory            │
estate context)      │
                     ▼
                run bundles
                     │
                     ▼
              Google Sheet queue
                     │
                     ▼
              future publisher
```

`projects` may provide identity/context projections and later register the producer/surface. It must never be imported as an execution engine or used to mutate participating repositories.

## Runtime topology

The first unattended runtime is GitHub Actions, consistent with the existing W0 decision.

```text
scheduled workflow / manual dispatch
                │
                ▼
        Activity Retriever
                │
                ▼
        Evidence Normalizer
                │
                ▼
          Story Grouper
                │
                ▼
      Related Context Provider
                │
                ▼
        ADK Editorial Workflow
       ┌────────┴────────┐
       │ Angle Producer  │
       │ deterministic   │
       │ validation      │
       │ Editor/Judge    │
       └────────┬────────┘
                │
                ▼
        Daily Batch Compiler
                │
       ┌────────┴────────┐
       ▼                 ▼
 editorial.run_bundle   Sheets projection
 immutable evidence      RUNS/CANDIDATES/QUEUE
```

No X credential is required for this staging wave.

## Component responsibilities

### 1. Activity Retriever

Read-only acquisition of candidate activity.

Initial adapters:

- GitHub recent merged PRs;
- GitHub releases;
- recent commits;
- issues/PR decisions when explicitly useful.

Next bounded adapters:

- Office estate-movement evidence;
- governed producer receipts or run summaries;
- durable public/project artifacts with exact refs;
- explicitly configured historical-dev-work bench.

The retriever reports inaccessible/unknown sources. It does not silently narrow account scope and pretend the scan was complete.

### 2. Evidence Normalizer

Converts source-specific observations into `ActivityEvidence.v1`.

Responsibilities:

- exact source identity and timestamps;
- observed status;
- public/private eligibility;
- bounded excerpts;
- relevant artifact/test/result refs;
- no unsupported interpretation.

This is primarily deterministic code.

### 3. Story Grouper

Builds `StoryCluster.v1` objects from one or more evidence items.

It may combine evidence only when the relationship is explicit and inspectable. It does not merge unrelated activity merely to create a more dramatic story.

Examples:

- one PR as one story;
- four related PRs as one provider-reliability story;
- a failed run plus its repair PR as one failure/recovery story.

### 4. Related Context Provider

Interface:

```python
get_related_context(story_cluster) -> list[RelatedContext]
```

v1 may use:

- repository-local README/AGENTS/spec context;
- recent candidate/history rows;
- a small pinned editorial context/constitution;
- bounded estate identity/context from `projects`.

A generic embedding/vector platform is explicitly deferred.

### 5. ADK Editorial Workflow

ADK is an implementation detail behind a local interface.

Conceptual graph:

```text
StoryCluster + context
        ↓
AngleProducer
        ↓
validate_angle_refs()      # ordinary Python
        ↓
Editor/Judge
        ↓
CandidateSet
```

Requirements:

- typed/structured outputs;
- bounded candidate counts;
- reject/abstain is normal success;
- every claim must carry evidence refs;
- framework/session objects do not cross the component boundary;
- provider/model metadata is recorded in run evidence;
- changing ADK/model must not change downstream contract shapes.

No multi-agent manager, open-ended delegation loop, or autonomous tool wandering is required in v1.

### 6. Daily Batch Compiler

The batch compiler is deterministic policy over already-generated candidates.

Responsibilities:

- semantic dedupe;
- recent-history repetition checks;
- risk/freshness checks;
- source concentration limits;
- batch diversity;
- target/floor/ceiling enforcement;
- approved fallback-tier expansion;
- final inventory status.

It may request another bounded generation pass over a different eligible evidence tier when inventory is below target. The maximum pass count is configured and finite.

Possible outcomes:

- `HEALTHY` — floor reached;
- `DEGRADED_INVENTORY` — fewer than floor, with no fabrication;
- `FAILED` — runtime/contract failure.

### 7. Run Bundle Writer

Writes immutable `editorial.run_bundle.v1` evidence.

A run bundle includes:

- run identity/time;
- exact editorial policy identity/hash;
- retrieval scope and failures;
- source evidence refs;
- story clusters;
- generated angles;
- judge/editor results;
- batch compiler decisions;
- final candidate IDs;
- provider/model/timing metadata;
- inventory status.

Generated artifacts are evidence and are never hand-edited.

### 8. Sheets Projection Adapter

Projects selected run/candidate state into a Google Sheet.

It must preserve three ownership classes:

- `RUNS`: machine projection;
- `CANDIDATES`: machine append-only projection;
- `QUEUE`: human/publisher operational state.

The adapter is idempotent on stable IDs.

It must never overwrite an existing human edit, decision, note, publisher state, or published reference.

### 9. Publisher handoff

The future publisher is downstream of the queue.

The v1 staging system defines the handoff contract but performs no external mutation.

## IDs and idempotency

### Evidence

Stable source-derived IDs, for example:

```text
github:matuteiglesias/repo:pr:123:merge:<sha>
github:matuteiglesias/repo:release:<tag>
github:matuteiglesias/repo:commit:<sha>
```

### Story clusters

Content-derived from ordered evidence IDs plus cluster kind.

### Candidates

Each candidate has:

- opaque `candidate_id`;
- deterministic `semantic_fingerprint` based on normalized claim/angle + primary evidence family;
- exact `evidence_refs`.

Reruns may generate new wording but must not append a near-duplicate semantic candidate when the fingerprint/repetition gate identifies the same claim.

## GitHub retrieval policy

Retrieval is allowlisted and bounded.

Default current windows:

- current activity: 72h;
- recent fallback: 14d;
- historical bench: explicit eligible records only.

The implementation must retain enough evidence to distinguish:

- merged/completed;
- open/work in progress;
- failed;
- cancelled;
- superseded;
- unknown.

Repository visibility must not be inferred from absence.

## Privacy and public eligibility

Private repositories may inform candidate generation only when the evidence policy permits it.

A candidate that refers to private evidence must still contain a safe public-facing claim and must not leak:

- credentials;
- private URLs;
- client/private correspondence;
- personal/family/health/legal material;
- confidential employment material;
- sensitive security details;
- local absolute paths;
- private raw data.

Evidence refs in the private run bundle may be richer than the Sheet projection. The Sheet should contain only what is necessary for editorial review.

## Dependency authority

Editorial must use the repository's existing dependency-profile system. Do not create an ad-hoc requirements file.

If ADK is introduced, add it to canonical `requirements/constraints.txt` and to an explicit supported profile. The existing `full == office ∪ sidecars` invariant must either continue to hold or be changed through a deliberate dependency-contract update with tests.

## Credentials

Initial staging credentials:

- estate-scoped **read-only** GitHub access;
- model/provider credentials or workload identity as required;
- Google Sheets write access to the configured staging workbook.

No X write credential belongs in W1 staging.

Secrets never enter:

- committed config;
- run bundles;
- Sheet rows;
- logs;
- candidate text.

## Failure model

Fail closed on:

- missing/unpinned policy;
- malformed model output;
- unsupported evidence refs;
- inability to prove source status needed by a claim;
- privacy classifier/gate failure;
- ambiguous Sheet ownership conflict;
- duplicate/idempotency uncertainty.

Individual source/evidence failures should be isolated where possible and recorded. The run may still finish as `DEGRADED_INVENTORY`.

## Framework portability

The durable architecture is:

```text
Evidence -> Story -> Angle -> Candidate -> Batch -> Queue
```

not:

```text
GitHub -> ADK -> Sheet
```

ADK is replaceable. The semantic contracts and evidence lineage are not.
