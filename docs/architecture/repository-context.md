# Optional repository context in Office

**Status:** canonical
**Audience:** operators, contributors, maintainers, and agents
**Owner:** office-auto-lab maintainers
**Verified against:** `7bdb02b1eff0c3a3aadaea74a88253a347c1afe7`

## Purpose

Office may enrich an operational front with repository-estate context supplied by `projects` without transferring front or carry authority to the GitHub estate.

## Input contract

- Artifact: `context:github-repositories@1`
- Producer: `projects`
- Consumer: Office
- Key: stable estate `repo_id`
- Configuration: optional `OFFICE_REPO_CONTEXT_JSON` path

The producer artifact contains repository context only. It must not contain `front_id`, carry posture, horizon, priority, or execution state.

## Front association

The Office Front Registry may optionally contain a `repo_ids` field. It is consumer-owned metadata describing which stable repository identities support the front.

Examples:

```text
front_id        repo_ids
fcv-research    repo.fcv-empirical-data;repo.fcv-experiment-harness
comp-negotiation
```

A front with no repository association is fully valid.

## Compile behavior

When repository context is available, Office adds advisory diagnostics:

- `repo_context_status`
- `repo_context_known_ids`
- `repo_context_unknown_ids`

The run manifest includes a compact repository-context summary.

Repository context does **not** affect scoring, carry, horizon, principal requirement, escalation, or block eligibility. Missing context is not a compile error. A configured artifact with the wrong contract or malformed structure fails explicitly to avoid ambiguous provenance.

## Authority invariant

Office owns the front-to-repository association and all operational consequences. `projects` owns the semantics and observations attached to each `repo_id`.

## Rollout

No repository-context file is configured by default. Existing Office deployments therefore retain their prior behavior until an operator intentionally supplies `OFFICE_REPO_CONTEXT_JSON`.
