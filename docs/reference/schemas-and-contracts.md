# Schemas and contracts

**Status:** canonical
**Audience:** integrators and contributors changing machine contracts
**Owner:** component owners
**Verified against:** `8b4c9b7`

## Versioned JSON schemas

| Contract | Path | Required purpose |
|---|---|---|
| Work Block Candidate Stub | `src/office_runtime/capture/schemas/work_block_candidate_stub.schema.json` | Strict reviewable work-block proposal requiring human approval |
| Capture Reingest Candidate | `src/office_runtime/capture/schemas/reingest_candidate.schema.json` | Strict proposed reingest record requiring human approval |
| Repo Health run bundle v1 | `src/office_runtime/ops/repo_health/spec/run_bundle.schema.json` | Producer-owned run/source/policy/results/frontier/block/exception/counter graph |
| PreparedBlock v0 | `src/office_runtime/ops/repo_health/compiler/spec/v0/prepared_block.schema.json` | Deterministic compiler output block |

Compiler v0 also owns `enums.json`, `operator_registry.json`, `archetypes.json`,
and `classify_rules.json`. Loaders in `compiler/spec/load_v0.py` are authoritative
for their filenames.

## Code-defined contracts

The plugin v1 result requires `status` and `message`, with optional bucket,
evidence, and JSON-serializable metadata. Capture raw/processing events, Office
manifest/artifacts, staff bundles/indexes, evidence rows, and run packet manifest
are code-defined rather than independently versioned schemas. Their writers and
validation limitations are cataloged in component guides and
[artifacts](artifacts-and-manifests.md).

## Compatibility rules

- Do not weaken recursive strictness or human-approval constants in capture
  candidates without an explicit reviewed contract change.
- Repo Health bundle identity, links, counters, canonical JSON, and status derivation
  must validate together.
- Additive unversioned artifact fields still require consumer review and fixtures/tests.
- Breaking schema meaning requires a new version and compatibility/migration plan;
  do not silently edit historical packets.
- Infrastructure tables persist producer meaning; table changes cannot redefine a
  run-bundle field.
