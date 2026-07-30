# PR-G3 Closure Note

- **Retrofit:** `gcp_project_health`
- **PR:** `PR-G3`
- **Status:** `ACCEPTED`
- **Accepted commit:** `acc7e1c`
- **Goal:** Freeze one Repo Health execution as an atomic, schema-validated, producer-owned artifact before adding cloud adapters.

## Big-plan checkpoint

| Phase | Outcome |
|---|---|
| G0 — characterize | Accepted; local behavior and cloud accidents made explicit |
| G1 — stabilize | Accepted; scheduling, no-write, evidence retention, and capability boundary corrected |
| G2 — remote inspection | Accepted; allowlisted repository-source boundary and two remote-read plugins delivered |
| G3 — execution contract | Ready for review; atomic run bundle and persistence ports delivered here |
| G4–G6 | Not started; provider adapters, infrastructure, and operated evidence remain |

The critical path remains intact. No dashboard, event bus, remote execution runner, or compatibility-only feature was added.

## Delivered

- Added the versioned `repo_health.run_bundle.v1` JSON schema and a fail-closed semantic validator.
- Added canonical JSON and SHA-256 rules so evidence has stable bytes and a verifiable manifest.
- Linked intents → plugin results → frontier → prepared blocks/exceptions through unique IDs under one run and producer commit.
- Defined contractual run statuses: `success`, `partial_success`, `error`, and `empty_success`, derived from results and exceptions rather than caller preference.
- Represented plugin failure with `failed: true`, `system_error`, evidence/meta, and a linked exception without losing successful results.
- Added atomic local run-directory creation. Exact replay is a no-op; a conflicting payload under the same `run_id` fails.
- Added provider-neutral `PolicySource`, `RunEvidenceSink`, `HistorySink`, and optional `LatestSignalSink` protocols.
- Added local file-policy, immutable-by-contract run evidence, idempotent JSONL history, and atomic latest-signal adapters.

## Artifact layout

```text
<evidence-root>/<run_id>/
  run_bundle.json
  manifest.json
```

`manifest.json` records the canonical bundle byte length and SHA-256. The directory becomes visible only after both files are complete.

## Duplicate-run rule

1. A new `run_id` is written into a sibling temporary directory and atomically renamed.
2. Replaying byte-identical canonical bundle content returns `duplicate` without a write.
3. Reusing the `run_id` with different content raises `DuplicateRunError`.
4. Local history follows the same exact-replay/conflict rule.
5. Provider adapters in G4 must preserve this rule.

## Validation boundaries

- Required top-level surfaces and schema version.
- Safe run ID, ordered timestamps, positive attempt, producer commit, policy identity/hash, and derived status.
- Unique intent/result/block/exception IDs.
- Complete result-to-intent, frontier-to-result, block-to-results, and exception-to-result linkage.
- Explicit failed-plugin representation.
- Reconciled counters for every collection and failed plugin.

## Risks and follow-up

- Local JSONL history is a compatibility adapter, not the cloud history system; G4 must implement BigQuery idempotency with the same producer identities.
- The optional latest-signal adapter is present but not part of the cloud job claim; G4 must not write a mutable GCS latest object.
- Filesystem permissions do not provide WORM storage. Immutability is enforced by writer collision rules locally; G4 owns GCS IAM/retention behavior.
- G4 must wire real orchestration into this bundle rather than inventing a second evidence shape.

## Evidence

- Schema and semantic validation tests.
- Atomic creation, manifest checksum, exact replay, and conflicting replay tests.
- Failed-plugin/partial-success linkage test.
- Idempotent local history and atomic signal tests.
- Existing compiler consumes the bundle frontier without semantic drift.

## Carry-state transition proposal

After human acceptance only:

```yaml
current_phase: phase_4
current_pr: null
last_accepted_pr: PR-G3
accepted_commit: <human-accepted-commit>
next_pr: PR-G4
accepted_artifacts:
  - context/closures/PR-G0.md
  - docs/retrofit/gcp_project_health/03_g0_characterization_v0_1.md
  - context/closures/PR-G1.md
  - context/closures/PR-G2.md
  - context/closures/PR-G3.md
```

Human review accepted G3 and authorized G4 on 2026-07-29. The acceptance audit found no genuine blocker requiring a run-bundle redesign.
