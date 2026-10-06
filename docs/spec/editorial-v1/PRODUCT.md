# Product specification — Editorial Dev Staging v1

## Product promise

Every day, maintain a sufficiently rich queue of X-ready ideas derived from Matías's real technical activity so publication no longer depends on remembering what happened, rediscovering why it mattered, or writing from a blank page.

The staging system optimizes for **useful inventory**, not posting volume. The downstream publisher decides what actually leaves the private system.

## Primary user

Matías is the editor and policy owner. He needs to be able to:

- see what real work each candidate came from;
- quickly understand the proposed angle;
- edit candidate copy directly;
- approve, hold, reject, or leave it untouched;
- distinguish fresh work from historical/evergreen material;
- trust that a rerun will not destroy edits;
- let a future publisher consume approved/policy-eligible rows without reconstructing provenance.

## Daily staging objective

Default dev-profile inventory policy:

| Parameter | Default |
|---|---:|
| candidate target | 8/day |
| defensible floor | 5/day |
| hard ceiling | 12/day |
| maximum candidates from one source event | 2 |
| maximum near-duplicate candidates per semantic claim | 1 |
| default freshness window for current activity | 72h |
| recent-work fallback horizon | 14d |
| historical bench | governed, provenance-preserving |

These are configuration values, not editorial truth. Changing them does not authorize publication.

### Floor semantics

The floor means: attempt to maintain at least five distinct, defensible staged candidates by widening retrieval through approved fallback tiers.

It does **not** mean:

- invent a lesson from a trivial change;
- restate one insight five ways;
- describe unfinished work as shipped;
- turn private evidence into public copy;
- promote an old claim as current without labeling its time context.

If safe inventory remains below the floor, emit `DEGRADED_INVENTORY` with explicit shortage reasons.

## Evidence source hierarchy

### Tier 1 — fresh completed work

Highest priority.

Examples:

- merged PRs;
- releases;
- completed deployments;
- durable artifacts;
- benchmark/evaluation results;
- explicit issue decisions;
- completed research/data milestones;
- verified incident resolutions.

### Tier 2 — fresh activity with careful status language

Useful when there is a real insight even if the work is not a completed release.

Examples:

- nontrivial commits;
- active PRs with inspectable design decisions;
- failed tests or incidents that produced a general lesson;
- Office/producer run evidence;
- bounded investigations with a real result;
- WAITING/DROP decisions that reveal a useful engineering constraint.

Candidate copy must preserve status. Work in progress must not be described as shipped.

### Tier 3 — recent cross-project synthesis

Several weak events may jointly support one strong claim.

Examples:

- the same reliability pattern appearing in three repositories;
- repeated use of explicit state or evidence boundaries;
- several changes that together form an architecture lesson;
- a recurring tension between deterministic and model-based decisions.

### Tier 4 — governed historical dev bench

Used to refill the inventory when current activity is thin.

Only evidence with stable provenance and safe public status is eligible. The system should prefer material that is still technically useful and has not been recently exhausted on X.

Historical material must not be phrased as if it happened today.

## Candidate families

Every staged candidate must be one of the following:

- **LESSON** — a transferable technical or scientific lesson;
- **ARTIFACT** — an inspectable object/result worth showing;
- **QUESTION** — a genuine unresolved technical question that can support useful conversation;
- **FAILURE** — a failure mode and what it revealed;
- **TRADEOFF** — a deliberate architecture or product choice and why;
- **MEASUREMENT** — a quantitative result with exact evidence;
- **FIELD_NOTE** — concise observation from real execution;
- **SYNTHESIS** — a pattern supported by multiple work events.

The taxonomy may grow only through a contract change.

## Public narrative

The dev profile should make the following capabilities legible through evidence rather than slogans:

- production Python and backend engineering;
- data systems and reproducibility;
- applied AI / LLM / agentic systems;
- evaluation, observability, reliability, and safe failure;
- cloud/deployment/automation;
- quantitative experimentation;
- architecture and engineering judgment;
- end-to-end ownership.

Career relevance may influence **curation priority**, but must never invent work or cause unsupported technology claims.

## Diversity rules

A daily batch should avoid becoming a mono-topic changelog.

The batch compiler should prefer, when evidence permits:

- multiple repositories/projects;
- multiple candidate families;
- more than one professional capability;
- at least one candidate understandable without repository-specific jargon;
- at least one artifact/result/question when such evidence exists.

No quota can override evidence quality.

## From activity to candidate

The editorial process is:

```text
ActivityEvidence[]
    ↓
evidence normalization
    ↓
StoryCluster[]
    ↓
AngleCard[]
    ↓
independent editorial criticism
    ↓
PostCandidate[]
    ↓
daily diversity / dedupe / freshness compiler
    ↓
staging queue
```

The LLM is not asked merely to "tweet this PR." It is asked to identify externally useful claims supported by the evidence.

## Candidate quality bar

A candidate should normally answer:

1. What is the claim or observation?
2. Which exact work evidence supports it?
3. Why could someone outside the repository care?
4. What is the transferable mechanism/lesson?
5. What status words are required to stay truthful?
6. Why is this not redundant with recent staged/published material?

Candidates that only announce implementation details should normally be rejected.

Bad:

> Added retry handling to project X.

Potentially good:

> Retries are not a substitute for failure provenance: an upstream outage and an internal application failure need different recovery semantics.

The second candidate is valid only when the underlying evidence genuinely supports it.

## Google Sheet workflow

The operational workbook is an editable review surface, not source-work authority.

The required logical tabs are:

### `RUNS`

Machine-written run summary/projection.

### `CANDIDATES`

Machine-written append-only candidate projection. Original generated text and provenance are immutable.

### `QUEUE`

Human/publisher operational state keyed by `candidate_id`.

Human-owned fields include at minimum:

- `draft_editable`;
- `decision`;
- `editor_note`;
- `target_surface`;
- `publisher_status`;
- `published_ref`.

The staging producer may create a missing queue row once. It must not overwrite human-owned fields on rerun.

## Queue decisions

Initial human decision vocabulary:

- `REVIEW`
- `APPROVE`
- `HOLD`
- `REJECT`

The staging producer defaults new rows to `REVIEW`.

The future publisher may consume only states explicitly allowed by its own publication policy. The staging producer itself does not interpret `APPROVE` as permission to mutate X.

## Publisher boundary

The staging system produces a stable handoff. A future publisher may use:

- candidate ID;
- editable final text;
- evidence refs;
- risk class;
- expiration/freshness;
- approval/policy state;
- duplicate fingerprint;
- account/profile identity.

The publisher must not need ADK session state, model prompts, hidden reasoning, or direct access to raw GitHub diffs.

## Long-form and LinkedIn

They are future downstream consumers, not v1 responsibilities. The candidate contract may carry optional `recommended_surfaces` and thematic tags so strong accumulated fragments can later be promoted into LinkedIn or long-form workflows without changing the X staging pipeline.
