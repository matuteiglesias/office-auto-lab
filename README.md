# Office Auto Lab

Command-driven Python runtime for the Office operating system.

The runtime compiles operational fronts and Carry State into bounded human/staff work surfaces, handles capture/staff/evidence capabilities, and hosts compatibility repository-health machinery during the repository-governance migration.

## Authority boundary

- Office owns operational front identity, Carry State, selection, preparation, and compile outputs.
- `front_id` is the canonical operational identity; legacy `project_id` remains a compatibility alias.
- GitHub repository identity/readiness belongs to the `projects` control plane.
- Optional repository context may enrich fronts through `context:github-repositories@1`; it is advisory and never automatically changes carry, horizon, priority, or escalation.
- Repo Health remains physically implemented here during compatibility migration, but repository-health semantic authority is being separated toward the GitHub estate control plane.

## Main surfaces

- **Office compile** — normalize Front Registry + Carry State, validate, route attention, and produce principal/support/block artifacts.
- **Staff** — enriched operational bundles and deterministic briefs/indexes.
- **Capture** — append-only processing and review artifacts.
- **Evidence** — bounded filesystem/Git evidence capture.
- **Repo Health (compatibility)** — repository-health execution pending semantic migration to the GitHub estate control plane.
- **Automation** — optional systemd/runtime scheduling.

## Front identity compatibility

Office accepts legacy `project_id`, canonical `front_id`, or both when they agree. See `docs/architecture/front-identity.md`.

Optional front-owned repository associations may be supplied in `repo_ids`. When `OFFICE_REPO_CONTEXT_JSON` points to a valid `context:github-repositories@1` artifact, compile outputs include advisory repository-context diagnostics. See `docs/architecture/repository-context.md`.

## Verification

Use the repository's canonical runtime/parent audit commands documented in `Makefile`, `SYSTEM.yaml`, and the architecture/component guides. Runtime changes should remain bounded, deterministic where practical, and explicit about authority/provenance.
