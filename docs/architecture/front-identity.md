# Operational front identity

## Status

Canonical Office identity contract. Storage migration is intentionally deferred.

## Purpose

Office governs operational fronts, not GitHub repositories. The runtime historically used `project_id` as the join key between Front Registry and Carry State. The canonical semantic name is now `front_id`.

## Contract

- `front_id` is the canonical identity of an operational front.
- `project_id` is a compatibility alias during migration.
- A front may exist without any GitHub repository.
- A front may reference one or many repositories.
- A repository may support zero, one, or many fronts.
- Repository identity never determines front identity.
- Repository lifecycle/readiness never automatically determines carry posture.

## Compatibility behavior

The Office compiler accepts either:

1. legacy sheets containing only `project_id`;
2. migrated sheets containing only `front_id`;
3. transition sheets containing both fields when their non-empty values agree.

When both fields disagree for a row, compilation fails with `front_identity_conflict` rather than silently selecting one value.

Compiled tabular artifacts expose both fields for compatibility. The run manifest exposes:

```json
{
  "identity": {
    "canonical_field": "front_id",
    "legacy_alias": "project_id"
  },
  "selected_front_ids": {}
}
```

`selected_ids` remains temporarily available as a compatibility projection for existing consumers.

## Repository associations

Repository association is optional context. It is not part of the identity key and is intentionally not required by the compiler.

A future optional repository-context interface may attach `repo_id` values and repository-readiness observations to a front. That interface must remain advisory unless an explicit Office rule converts repository context into an operational consequence.

## Migration rule

Do not rename the Google Sheet column as a prerequisite for this contract. Semantic identity changes first. Storage/schema cleanup can happen later after consumers of `project_id` are audited.
