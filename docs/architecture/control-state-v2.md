# Control Tower v2 intake and snapshot

**Status:** canonical
**Audience:** maintainers, contributors, operators, and agents
**Owner:** `src/office_runtime/office/control_snapshot.py`
**Verified against:** Control Tower metadata observed 2026-09-14 and M1 fixture acceptance

## Purpose

Office v2 consumes the Control Tower as one coherent semantic control plane. It must not independently reread and reinterpret individual tabs at later stages of the same Office generation.

M1 introduces `ops.control-state-snapshot.v2`, an immutable normalized snapshot contract over the current v2 tables. The snapshot is an intake artifact, not a routing result and not a compatibility translation into the old `carry`/`project_id` vocabulary.

## Source tables

The snapshot currently covers:

| Table | Default gid | Primary key | Role |
|---|---:|---|---|
| `front_registry_v2` | `1428476550` | `front_id` | canonical front identity and relatively stable semantics |
| `carry_state_v2` | `27157683` | `front_id` | current governed operating posture |
| `Capabilities_v2` | `1779330064` | `front_id` | evidence-backed capability projection |
| `operator_contract_v2` | `1747453443` | `contract_id` | operator powers, prohibitions, seams, and buses |
| `front_aliases_v2` | `1657847512` | `alias_id` | explicit legacy/alternate identity reconciliation |
| `support_artifacts_v2` | `432491750` | `artifact_id` | governed pointers and support surfaces |
| `REPO MONITOR_v2` | `1165460743` | `binding_id` | front-to-repository/workspace bindings |
| `repo_workspaces_v2` | `915945555` | `workspace_id` | observed concrete repository workspaces |
| `runtime_health_v2` | `1528387812` | `front_id` | derived runtime-health projection |

Each gid can be overridden with the corresponding `OFFICE_V2_*_GID` environment variable, but the table identity and schema contract remain explicit in source.

## Snapshot shape

A snapshot contains:

```text
schema_version
observed_at
source
  kind
  spreadsheet_id
tables
  <table>
    gid
    key
    row_count
    rows[]
validation
  status
  issues[]
snapshot_digest
```

The digest is computed over the canonical snapshot payload before the digest field is added. With the same `observed_at`, source metadata, gids, and table values, the snapshot digest is deterministic.

## Validation boundary

M1 rejects structural ambiguity before downstream compilation:

- a required v2 table is missing;
- a required column is missing;
- a primary key is blank;
- a primary key is duplicated;
- a table referencing `front_id` points to an unknown front;
- `REPO MONITOR_v2.workspace_id` points to an unknown declared workspace.

Declared alias collisions are intentionally different. A row whose `resolution_status` is `COLLISION` is preserved and reported as an observation. Intake must not silently choose one identity merely to make later automation convenient.

M1 validates structure and referential identity. It deliberately does not translate v2 values such as `ACTIVE`, `THIS_WEEK`, or `REQUIRED` into the legacy Office spellings. Typed work semantics belong to the M3 work-item compiler.

## Read and mutation boundary

`read_control_tower_v2` uses the existing read-only Google Sheets client. `compile_control_snapshot` writes only a caller-selected local JSON artifact.

The intake layer does not:

- mutate Control Tower;
- change Carry State;
- select or prioritize work;
- resolve legacy aliases automatically;
- execute a repository or workspace;
- generate Principal decisions.

Those responsibilities belong to later layers.

## Generation rule

Downstream Office v2 components must consume the captured snapshot (or a contract-preserving projection of it), not reread the Sheets independently during the same generation.

This rule is what makes a later coherent run possible: Staff and Principal can reason from exactly the state Office observed rather than from slightly different moments in a mutable workbook.

## Migration posture

The existing legacy Office compiler remains available during M1 and continues to use its legacy inputs. M1 is additive: it establishes the native v2 contract and acceptance tests without pretending that the old routing rules understand v2 semantics.

The migration switches routing only after identity and typed-work contracts are ready. This avoids a temporary adapter layer becoming permanent architecture.
