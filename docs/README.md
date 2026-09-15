# office-auto-lab documentation

**Status:** canonical documentation router
**Audience:** operators, contributors, maintainers, and agents
**Owner:** office-auto-lab maintainers
**Verified against:** `f7af9bbd40e04ba4b27f4e24ec20bd4121e4548a`

Office Auto Lab is the runtime and preparation layer for the governed Office.
The supported product architecture is Office v2: one validated Control Tower
snapshot flows through typed work, Staff preparation, the Principal brief,
execution planning, reentry, coherent publication, and run-record health.

Historical Office v1, Staff-v1, Repo Health/GCP, and legacy prepared-block
implementations were removed in M9. Git history preserves them; they are not
current product or documentation surfaces.

## Start here

1. Read the repository [README](../README.md) for the product boundary, current
   commands, and capability matrix.
2. Read the [system overview](architecture/system-overview.md) for ownership and
   trust boundaries.
3. Follow a [coherent Office v2 generation](architecture/coherent-generation-v2.md)
   from one snapshot to validated publication.
4. Use [routine local operation](operations/local-routines.md) and the
   [CLI reference](reference/cli.md) before running commands.

## Office v2 architecture

- [Control-state intake](architecture/control-state-v2.md)
- [Front, repository, and workspace identity](architecture/identity-resolution-v2.md)
- [Typed work-item compilation](architecture/work-item-compiler-v1.md)
- [Staff preparation](architecture/staff-preparation-v2.md)
- [Principal compilation](architecture/principal-compiler-v2.md)
- [Execution compilation](architecture/execution-compiler-v2.md)
- [Reviewable reentry](architecture/reentry-v2.md)
- [Coherent generation and publication](architecture/coherent-generation-v2.md)
- [Run records and runtime health](architecture/run-record-health-v2.md)

The broader architecture references remain:

- [Runtime and artifact flow](architecture/runtime-and-artifact-flow.md)
- [Ownership and state](architecture/ownership-and-state.md)
- [Trust boundaries](architecture/trust-boundaries.md)
- [Component lifecycle](architecture/component-lifecycle.md)

## Sidecar components

- [Capture](components/capture.md)
- [Evidence](components/evidence.md)
- [Estate Movement Digest](components/estate-movement.md)
- [Editorial projection](architecture/editorial-projection.md)

Sidecars integrate through explicit interfaces. They do not redefine Office
governance semantics or become a second source of repository-estate authority.

## Operations

- [Local development](getting-started/local-development.md)
- [Routine local operation](operations/local-routines.md)
- [Failure and recovery](operations/failure-recovery.md)
- [Portable systemd automation](operations/systemd-automation.md)

Merging runtime changes does not install or change a user's timers. Scheduler
rendering, installation, cutover, and rollback are explicit operator actions.

## Reference

- [CLI and Make](reference/cli.md)
- [Configuration](reference/configuration.md)
- [Artifacts and manifests](reference/artifacts-and-manifests.md)
- [Schemas and contracts](reference/schemas-and-contracts.md)

Source, schemas, tests, and executed commands outrank prose when they disagree.
Generated artifacts are evidence, not editable authority.

## Documentation maintenance

- [Maintenance policy](documentation-maintenance.md)
- [Coverage and known gaps](documentation_coverage.md)
- [Historical and supporting index](historical/README.md)

Run `make docs-check` for the repository documentation gate. The published
frontend additionally runs its content, production-build, navigation, Mermaid,
deep-link, 404, and browser-runtime checks.
