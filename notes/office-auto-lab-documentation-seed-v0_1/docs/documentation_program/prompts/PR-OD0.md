# PR-OD0 — inventory and canonicality map

## Goal

Produce a verified inventory of all documentation, operational commands,
configuration, contracts, artifact surfaces, and documentation drift on current
main.

## Required work

- Inspect the complete repository tree.
- Inventory Markdown/text docs outside generated/vendor areas.
- Enumerate CLI commands and Make targets.
- Enumerate environment variables, schemas, artifacts, systemd units, and GCP infrastructure surfaces.
- Classify documents as candidate canonical, supporting, historical, generated, stale, duplicated, or unknown.
- Identify broken, contradictory, and orphaned instructions.
- Propose one canonical owner page per reader task.
- Record exact deviations from the seed plan.

## Deliverables

- `docs/documentation_inventory.md`
- `docs/documentation_canonicality_map.md`
- closure note
- proposed carry update to `PR-OD1`

## Non-goals

- no broad rewriting;
- no moving/deleting old docs;
- no product changes.

## Verification

Include reproducible inventory commands and the inspected commit SHA.
Stop when the inventory is reviewable.
