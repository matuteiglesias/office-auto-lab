# Editorial Dev Staging v1

**Status:** implementation specification  
**Scope:** `dev` editorial profile only  
**Owner:** `office-auto-lab` Editorial SIDECAR  
**Publication authority:** explicitly out of scope for this bundle  
**Upstream policy authority:** `weekly-ops-governance`  
**Estate identity/governance authority:** `projects`

## Mission

Continuously turn Matías's real software, data, research-engineering, and operational activity into a healthy inventory of evidence-backed X post candidates.

The system is a **staging producer**, not a posting bot. It should leave a useful, editable queue every day so a separate publication policy and publisher can select, schedule, and publish according to explicit rules.

The desired loop is:

```text
real activity
   ↓
inspectable evidence
   ↓
story / angle discovery
   ↓
candidate drafting + criticism
   ↓
daily inventory compiler
   ↓
human-editable queue
   ↓
later publication policy + publisher
```

## Product outcome

On each scheduled day the dev profile should normally stage:

- **target:** 8 distinct candidates;
- **floor:** 5 defensible candidates;
- **ceiling:** 12 candidates.

The floor is an inventory objective, not permission to fabricate. Fresh work is preferred. When fresh work is insufficient, the system may use governed recent/historical work, cross-project patterns, durable artifacts, or unresolved technical questions with exact provenance. If the evidence bench cannot support five defensible candidates, the run succeeds as `DEGRADED_INVENTORY` and records why.

A candidate is not approval. A staged candidate may still be edited, held, rejected, expire, or never be published.

## Authority order

1. Direct instructions from Matías.
2. Current `weekly-ops-governance` editorial constitution/policy.
3. Repository-local source truth and exact work evidence.
4. `projects` estate identity/context projections.
5. Office Editorial contracts and run evidence.
6. Generated candidate copy.

Generated prose never outranks the source evidence from which it was derived.

## Estate compatibility

This bundle extends the W0 Editorial sidecar already established in `office-auto-lab`.

It must not:

- revive the superseded `editorial-core` repository;
- create a second GitHub-estate authority beside `projects`;
- turn `projects` into a runtime dependency or executor;
- redefine repository-local product/scientific semantics;
- let ADK types become cross-component contracts;
- let a Google Sheet become a second authority for source work;
- write to X;
- silently rewrite human editorial decisions.

## Core distinction

The implementation must preserve the following stages as different semantic objects:

```text
observed work
  != evidence packet
  != story cluster
  != angle
  != staged candidate
  != human/policy approval
  != published post
```

This distinction is a hard invariant.

## Document map

- [PRODUCT.md](PRODUCT.md) — behavior, daily inventory, source hierarchy, user workflow.
- [ARCHITECTURE.md](ARCHITECTURE.md) — runtime components, ADK seam, Sheets projection, failure model.
- [CONTRACTS.md](CONTRACTS.md) — durable intermediate and handoff objects.
- [ACCEPTANCE.md](ACCEPTANCE.md) — testable definition of done.
- [DEVELOPMENT_DAG.md](DEVELOPMENT_DAG.md) — implementation nodes and dependencies.
- [OPERATIONS.md](OPERATIONS.md) — scheduled/manual operation, queue ownership, recovery.

The existing [Editorial projection subsystem](../../architecture/editorial-projection.md) remains authoritative for the shared W0 authority split and future live-publication promotion gates. This bundle is the canonical implementation specification for **dev-profile daily candidate staging**.

## Initial non-goals

- no X mutation;
- no LinkedIn publication;
- no generic multi-channel CMS;
- no new standalone repository;
- no Pub/Sub, Firestore, Supabase, or vector database;
- no autonomous rewrite of editorial policy;
- no generic estate-wide semantic search platform;
- no requirement that every PR generate a post;
- no requirement that every staged candidate eventually publish.

## Success

The v1 staging capability is successful when the system can run unattended, discover evidence across recent activity, produce a diverse daily candidate inventory with exact provenance, project it into a human-editable queue without overwriting human state, and leave a stable publisher handoff that a future publisher can consume without knowing anything about ADK or the internal generation pipeline.
