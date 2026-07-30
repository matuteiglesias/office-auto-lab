# office-auto-lab documentation current-state inventory v0.1

## Repository shape inferred from current main

The operational command surface includes Office compilation, staff bundles and
briefs, capture lifecycle, Repo Health, evidence collection, repository scans,
prepared-block compilation, and audit/import checks. The `Makefile` is therefore
a high-value source of operational truth.

Current documentation is valuable but fragmented by implementation episode:

| Existing surface | Current role | Documentation-program treatment |
|---|---|---|
| `docs/environment.md` | lean local environment notes | retain; later supersede with canonical local-development page |
| `docs/systemd_timers.md` | user-level timer operation | retain; verify and promote into operations stack |
| `docs/capture_processing_layer.md` | capture design and migration explanation | verify against current capture pipeline; split concept/reference/runbook if needed |
| `docs/retrofit/gcp_project_health/` | governed retrofit plan, contracts, prompts, runbooks | preserve as implementation record; distill canonical architecture and operations pages |
| `context/closures/PR-G*.md` | retrofit execution evidence | supporting evidence, not reader navigation |
| `fixtures/artifacts_sample/latest/README.md` | fixture-local explanation | keep adjacent to fixture |
| source, schemas, tests, Makefile | executable truth | primary verification sources |

## Main documentation gaps

1. No coherent repository-level product overview and reader routing.
2. No system architecture connecting office compile, staff, capture, evidence,
   Repo Health, artifacts, and automation.
3. No ownership map that says which module writes each canonical artifact.
4. Commands are discoverable from code/Makefile but not organized by reader task.
5. GCP retrofit records are strong but are not integrated into the system story.
6. No reference catalog for CLI, environment variables, schemas, artifacts, and plugins.
7. No explicit status page distinguishing local operation from GCP deployment state.
8. No agent navigation contract before this seed.
9. No documentation freshness or link-validation gate.

## Known high-value truths to preserve

- Office, staff, capture, evidence, and Repo Health are separate product surfaces.
- Repo Health cloud v0.1 is bounded and read-only.
- Cloud infrastructure transports and persists Repo Health meaning; it does not own it.
- GCP mode rejects service-account key files and relies on assigned identity.
- Cloud Storage evidence is immutable and BigQuery history is idempotent.
- Current GCP work is merged and deployment-ready but not provider-operated.

## Inventory work still required in PR-OD0

PR-OD0 must inspect the complete tree and produce a file-level inventory including:

- all Markdown/text documentation outside generated/vendor directories;
- every CLI command and Make target;
- environment/configuration variables;
- JSON schemas and artifact manifests;
- systemd units;
- GCP Terraform resources and operator scripts;
- current tests that can serve as executable documentation;
- duplicated, stale, contradictory, or orphaned instructions.

Do not infer canonicality from directory names alone.
