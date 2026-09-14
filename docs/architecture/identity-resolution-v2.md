# Office v2 identity resolution

**Status:** canonical
**Audience:** maintainers, contributors, operators, and agents
**Owner:** `src/office_runtime/office/identity.py`
**Verified against:** M2 fixture acceptance and Control Tower v2 identity tables observed 2026-09-14

## Purpose

Office must distinguish semantic identity from machine-local location. A front is identified by `front_id`, a repository by `repo_id`, and a concrete checkout by `workspace_id`. Filesystem paths are observations attached to workspaces; they are not stable identity and must not become direct execution authority.

The v2 chain is:

```text
front_id
  ↓
REPO MONITOR_v2 binding
  ↓
repo_id
  ↓
workspace_id / repo workspace selection
  ↓
repo_workspaces_v2.local_path
```

## Authority rule

`front_registry_v2.repo_path`, `front_registry_v2.workdir`, and convenience path projections on repo-binding rows are never execution authority in Office v2. They may remain migration evidence, but the resolver deliberately ignores them.

A usable local path must come from an ACTIVE `repo_workspaces_v2` row reached through an ACTIVE front-to-repository binding.

## Resolution rules

For a front:

1. require a known canonical `front_id`;
2. select ACTIVE `REPO MONITOR_v2` bindings;
3. order primary bindings before supporting bindings for presentation only;
4. resolve each binding to its `repo_id`;
5. if the binding names a `workspace_id`, require that exact workspace to exist and belong to the same repo;
6. otherwise consider ACTIVE workspaces for the repo;
7. choose a unique `is_preferred=TRUE` workspace when one exists;
8. if there is no preferred workspace, choose only when exactly one ACTIVE workspace exists;
9. keep multiple non-preferred candidates `AMBIGUOUS` rather than guessing;
10. treat multiple preferred workspaces as a contract error.

A front may legitimately have no repository. Human and governance fronts are not forced into fake repo identity merely because Office can operate on repositories.

## Primary repository rule

A front may have several ACTIVE repository bindings but at most one ACTIVE binding marked `is_primary=TRUE`. Multiple primary bindings are a contract error because a downstream execution packet could otherwise acquire an unstable default target.

Supporting repositories remain available in the execution context and can later be selected explicitly by typed work requirements.

## Resolution states

A workspace resolution can be:

- `RESOLVED` — one governed ACTIVE workspace with a local path is available;
- `UNRESOLVED` — no ACTIVE workspace is observed for the repo;
- `AMBIGUOUS` — more than one plausible ACTIVE workspace exists and no unique preference resolves it;
- `UNAVAILABLE` — a selected/explicit workspace is inactive or has no current local-path observation.

Only `RESOLVED` yields a concrete path suitable for local execution.

## Output context

`IdentityResolver.execution_context(front_id)` returns the front identity, all ACTIVE repository bindings with workspace-resolution results, an optional primary repository, and an explicit `path_authority: repo_workspaces_v2` marker.

The resolver does not inspect the filesystem, pull repositories, validate Git status, or infer repository health. Those are evidence/Staff concerns. Identity resolution only determines which governed object an executor would be talking about.

## Downstream implication

M3 work items refer to `front_id`, `repo_id`, and capability requirements rather than embedding local paths. Staff preparation may request a resolved workspace when an evidence adapter actually needs local execution.

This keeps the control plane portable and prevents Office from turning one laptop's directory layout into estate semantics.
