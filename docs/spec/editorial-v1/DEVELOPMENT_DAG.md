# Development DAG — Editorial Dev Staging v1

The DAG is ordered to prove the editorial product before adding broad infrastructure. A downstream node may start only when its input contracts are stable enough for that node.

## Graph

```text
D0 spec/authority freeze
 ├─► D1 contracts
 │    ├─► D2 GitHub evidence
 │    ├─► D3 policy/context loader
 │    └─► D4 run-bundle skeleton
 │
 D2 + D3
 └─► D5 story clustering
      └─► D6 ADK angle producer
           └─► D7 editor/judge
                └─► D8 daily batch compiler
                     ├─► D9 Sheets projection
                     ├─► D10 manual/backfill CLI
                     └─► D11 fixture/eval corpus
                          │
 D4 + D8 + D9 + D10 + D11
 └──────────────────────► D12 scheduled staging
                              │
 D12 ─► D13 broader activity adapters
                              │
 D12 + D13 ─► D14 operational acceptance
                              │
 D14 ─► D15 estate registration + publisher handoff
```

## D0 — Spec and authority freeze

**Goal:** adopt this bundle as the implementation contract.

Required:

- preserve W0 authority split;
- no new repo;
- no X mutation;
- identify current editorial policy source;
- record historical launch-week policy as non-current where applicable.

**Acceptance:** documentation review only.

## D1 — Typed contracts

Implement local Pydantic/dataclass/schema equivalents for:

- `ActivityEvidence.v1`;
- `StoryCluster.v1`;
- `AngleCard.v1`;
- dev candidate extensions;
- `DailyBatch.v1`;
- `editorial.run_bundle.v1`.

Extend contract tests without weakening the existing `office_runtime.editorial.candidate.v1` seam.

**Stop:** do not add model calls before evidence and IDs can be validated without a model.

## D2 — GitHub evidence adapter

Implement bounded read-only retrieval.

First supported event:

- merged PR.

Then add:

- release;
- recent commit/result;
- explicit issue/PR decision.

Use exact IDs and overlapping lookback windows with dedupe.

**Acceptance:** one known real PR becomes a deterministic evidence packet.

## D3 — Policy and context loader

Read:

- pinned dev editorial policy/constitution;
- repository-local context;
- recent staged/published history needed for repetition control;
- optional bounded `projects` context projection.

No broad RAG.

**Acceptance:** context pack carries exact provenance and can be fixture-tested offline.

## D4 — Run-bundle skeleton

Create run identity, atomic writer, canonical serialization and sections for:

- policy;
- retrieval;
- evidence;
- provider calls;
- failures;
- final batch.

Initially empty editorial sections are valid.

**Acceptance:** a retrieval-only run leaves valid immutable evidence.

## D5 — Story clustering

Implement deterministic/simple clustering before model generation.

Capabilities:

- one event → one story;
- explicitly related event family → one story;
- stable story ID;
- no unrelated aggregation.

Initial heuristics may be conservative.

## D6 — ADK angle producer

Add ADK through a narrow local adapter.

Input:

- one `StoryCluster`;
- bounded context.

Output:

- zero to N typed `AngleCard` objects.

The prompt should deliberately inspect known lenses: lesson, artifact, question, failure, tradeoff, measurement, field note, synthesis.

**Acceptance:** typed output, bounded count, valid evidence refs, abstention supported.

## D7 — Independent editor/judge

A second model stage receives source evidence plus angle cards.

Responsibilities:

- reject unsupported claims;
- reject platitudes/changelog copy;
- score useful dimensions;
- generate concise X drafts for survivors;
- label risk and required status wording.

Deterministic validation follows the model.

**Acceptance:** boring and sensitive fixtures are rejected/held; strong fixture survives.

## D8 — Daily batch compiler

Implement deterministic inventory logic.

Default configuration:

```text
target 8
floor 5
ceiling 12
max 2 candidates/source event
```

Responsibilities:

- semantic fingerprinting/dedupe;
- repetition against recent queue/history;
- diversity;
- expiry/freshness;
- bounded fallback passes through eligible source tiers;
- `HEALTHY | DEGRADED_INVENTORY | FAILED`.

This node owns volume; the LLM does not.

## D9 — Google Sheets projection

Create adapter for configured workbook.

Tabs:

- `RUNS`;
- `CANDIDATES`;
- `QUEUE`.

Requirements:

- append/upsert by stable key;
- preserve human-owned queue fields;
- do not copy unnecessary private evidence;
- tolerate retry after partial projection.

Add fixture/fake Sheets tests before live workbook proof.

## D10 — Manual/backfill CLI

Provide bounded operator surfaces, conceptually:

```text
editorial dev stage --pr owner/repo#123
editorial dev stage --since <timestamp>
editorial dev stage --date <date>
```

Exact CLI naming may follow repository conventions.

Must support dry-run/local artifact output without Sheet mutation.

## D11 — Fixture/eval corpus

Minimum cases:

1. strong merged PR with transferable lesson;
2. trivial/dependency PR → abstain;
3. sensitive/security work → hold/drop;
4. cross-PR story;
5. thin-current-day requiring fallback;
6. in-progress work requiring cautious status wording;
7. manual Sheet edit preservation.

Evaluate properties, not exact prose.

Use ADK evaluation support where it reduces custom harness work, but keep contract-level fixtures framework-neutral.

## D12 — Scheduled staging

Add unattended GitHub Actions workflow.

Requirements:

- read-only estate GitHub credential;
- model credential/runtime;
- Sheets credential;
- explicit configured lookback;
- one run bundle per invocation;
- artifact retention sufficient for debugging;
- no X secret.

Manual dispatch remains available.

## D13 — Broader activity adapters

Only after scheduled PR-based staging works, add bounded sources needed to make daily inventory robust:

Priority order:

1. GitHub releases and explicit issue decisions;
2. Office estate-movement/run evidence;
3. governed producer receipts;
4. durable project/research artifacts;
5. explicit historical-dev-work bench.

Every adapter must emit `ActivityEvidence.v1`; downstream code must not know its source-specific representation.

## D14 — Operational acceptance

Run against real activity until the end-to-end acceptance in `ACCEPTANCE.md` is demonstrated.

Do not weaken candidate floor failures by manufacturing copy.

Repair the first failing seam only; avoid widening the system during acceptance.

## D15 — Estate registration and publisher handoff

After the staging producer is real:

1. propose producer entry in `projects`;
2. propose/promote the Editorial Dev Queue surface only after it has a real consumer;
3. register the workbook in the Sheets estate with lineage/ownership;
4. freeze `publisher handoff v1`;
5. begin publisher implementation as a separate bounded wave.

The staging producer remains unaware of X mutation internals.

## Work-pruning rules

Do not pull these into v1 unless a failing acceptance gate proves they are needed:

- Cloud Run;
- Pub/Sub;
- Firestore/Supabase;
- vector DB;
- generic multi-channel CMS;
- autonomous cross-repo tool wandering;
- adaptive content bandits;
- X metrics;
- LinkedIn publisher;
- long-form publisher;
- automatic estate semantic changes.

The current bottleneck is candidate quality + reliable daily inventory, not infrastructure scale.
