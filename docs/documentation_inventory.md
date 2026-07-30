# Documentation and operational surface inventory

**Status:** historical point-in-time inventory; superseded for navigation
**Audience:** maintainers, contributors, documentation authors, and agents
**Owner:** office-auto-lab maintainers
**Verified against:** `cda8b286cc5db3c840d7f4dad143d62497f18a63`
**Verification date:** 2026-07-30

> Preserve this PR-OD0 baseline as evidence of the starting state. Use the
> current [documentation router](README.md) and
> [coverage report](documentation_coverage.md) for current ownership/status.

## Scope and method

This PR-OD0 inventory records the repository as inspected; it does not promote
existing prose to canonical status or change product behavior. Source, tests,
schemas, infrastructure, and command help take precedence over prose. Generated
and vendor directories are absent from the tracked tree. The two bundles under
`notes/` are retained as working/historical inputs.

The inventory was produced with these commands (all executed from the repository
root):

```bash
git rev-parse HEAD
git ls-files
git ls-files '*.md' '*.txt'
awk -F: '/^[A-Za-z0-9_.-]+:([^=]|$)/ {print $1}' Makefile
PYTHONPATH=src python -m office_runtime.cli --help
rg -n 'add_parser|add_argument' src/office_runtime/cli.py
rg -n 'os\.environ|getenv|_env\(' src infra systemd Makefile
find src -name '*.schema.json' -print
rg -n '^(resource|data|variable|output) ' infra/gcp/*.tf
find systemd -type f -print
```

## Documentation file inventory

Classification here is descriptive and provisional. “Candidate canonical” means
the page contains current useful instructions but still requires reconciliation.

| Path | Classification | Finding / disposition |
|---|---|---|
| `docs/environment.md` | candidate canonical | Concise local setup; candidate source for the later local-development page. |
| `docs/systemd_timers.md` | candidate canonical | Matches the six unit files, but hard-codes one user's path and needs a configurable install procedure. |
| `docs/capture_processing_layer.md` | supporting + stale | Design record contains implemented invariants, but still labels implemented CLI/schema work “proposed” and lists output names that differ from source. |
| `docs/DAY_COMPILE_NOTES.md` | generated/unknown | Undated compiled work product, not system documentation; orphaned from navigation. |
| `docs/{Cell anatomy,Current health response map,Health response triage,Runtime circulation,The 4-hour operating cycle,Weekly metabolism,flow}.mmd` | supporting/unknown | Mermaid sources with no index, ownership metadata, or surrounding explanation. |
| `docs/retrofit/gcp_project_health/00_embryo_plan_v0_1.md` | historical | Initial GCP retrofit plan. Preserve as implementation history. |
| `docs/retrofit/gcp_project_health/01_starting_context_v0_1.md` | historical | Retrofit baseline and claim boundaries. |
| `docs/retrofit/gcp_project_health/02_sprint_contract_v0_1.md` | historical | Retrofit execution contract. |
| `docs/retrofit/gcp_project_health/03_g0_characterization_v0_1.md` | supporting | Characterization evidence; not a reader runbook. |
| `docs/retrofit/gcp_project_health/04_g4_environment_and_deployment.md` | supporting/candidate canonical | Strong deployment input, to be distilled in PR-OD5; does not evidence deployment. |
| `docs/retrofit/gcp_project_health/05_g5_manual_execution_runbook.md` | supporting/candidate canonical | Strong first-run procedure, to be reconciled and promoted in PR-OD5. |
| `docs/retrofit/gcp_project_health/CODEX_START_HERE.md` | historical | Agent entry point for the completed retrofit sequence, not current repository navigation. |
| `docs/retrofit/gcp_project_health/carry_state_v0_1.yaml` | historical | Retrofit state record. |
| `docs/retrofit/gcp_project_health/prompts/PR-G0.md` … `PR-G7_OPTIONAL.md` | historical (8 files) | Execution prompts; preserve, do not expose as operational guidance. |
| `docs/retrofit/gcp_project_health/templates/pr_closure_note.md` | supporting | Retrofit-specific authoring template. |
| `context/closures/PR-G0.md` … `PR-G5.md` | supporting evidence (6 files) | Execution evidence, not reader navigation or canonical commands. |
| `audits/sheet_doctor_2026-05-02_0226.md` | historical evidence | Point-in-time audit output. |
| `fixtures/artifacts_sample/latest/README.md` | supporting | Canonical only within the synthetic fixture. |
| `fixtures/artifacts_sample/latest/{office_summary,today_compile}.md` | generated fixture (2 files) | Expected-output examples, not instructions. |
| `fixtures/artifacts_sample/latest/briefs/{decision__FAKE-ALPHA,execution__FAKE-CHARLIE,healthcheck__FAKE-BRAVO}.md` | generated fixture (3 files) | Synthetic staff output examples. |
| `src/office_runtime/ops/repo_health/compiler/spec/v0/README.md` | stale/unknown | Empty tracked file beside authoritative versioned JSON contracts. |
| `notes/auto_checker_README.md` | historical/stale | Old checker quickstart; referenced top-level scripts are no longer present. |
| `notes/compiler_v0_spec.md` | historical/supporting | ADR-lite for the legacy compiler; JSON spec and tests outrank it. |
| `notes/contracts.md` | stale/unknown | Empty tracked file. |
| `notes/runbook.md` | historical/stale | Contains malformed citation residue and commands/paths from the pre-`src` layout. |
| `notes/office_auto_lab_gcp_codex_retrofit_bundle_v0_1/INSTALL.md` | historical | Imported retrofit bundle installer. |
| `notes/office_auto_lab_gcp_codex_retrofit_bundle_v0_1/docs/retrofit/gcp_project_health/{00_embryo_plan_v0_1,01_starting_context_v0_1,02_sprint_contract_v0_1,CODEX_START_HERE}.md` | historical duplicate (4 files) | Seed copies superseded by the installed `docs/retrofit/` records. |
| `notes/office_auto_lab_gcp_codex_retrofit_bundle_v0_1/docs/retrofit/gcp_project_health/carry_state_v0_1.yaml` | historical duplicate | Bundled state copy. |
| `notes/office_auto_lab_gcp_codex_retrofit_bundle_v0_1/docs/retrofit/gcp_project_health/prompts/PR-G0.md` … `PR-G7_OPTIONAL.md` | historical duplicate (8 files) | Bundled prompt copies. |
| `notes/office_auto_lab_gcp_codex_retrofit_bundle_v0_1/docs/retrofit/gcp_project_health/templates/pr_closure_note.md` | historical duplicate | Bundled template copy. |
| `notes/office-auto-lab-documentation-seed-v0_1/AGENTS.md` | supporting program contract | Applies within the seed bundle and supplied PR-OD0 rules. |
| `notes/office-auto-lab-documentation-seed-v0_1/BUNDLE_MANIFEST.md` | supporting | Documentation-program bundle manifest. |
| `notes/office-auto-lab-documentation-seed-v0_1/docs/documentation_program/{CODEX_START_HERE,00_documentation_charter_v0_1,01_current_state_inventory_v0_1,02_target_docs_stack_v0_1,03_phased_pr_plan_v0_1,04_quality_and_acceptance_v0_1,05_canonicality_and_migration_rules_v0_1}.md` | supporting seed (7 files) | Program governance inputs; notably not installed at the path stated in the user request. |
| `notes/office-auto-lab-documentation-seed-v0_1/docs/documentation_program/carry_state_v0_1.yaml` | supporting seed | Names PR-OD0 as `next_pr`. |
| `notes/office-auto-lab-documentation-seed-v0_1/docs/documentation_program/prompts/PR-OD0.md` … `PR-OD6.md` | supporting seed (7 files) | Bounded documentation PR contracts. |
| `notes/office-auto-lab-documentation-seed-v0_1/docs/documentation_program/templates/{adr_template,closure_note,page_contract,runbook_template}.md` | supporting seed (4 files) | Future authoring templates. |
| `notes/office-auto-lab-documentation-seed-v0_1/docs/documentation_program/context/closures/README.md` | supporting seed | Closure directory instructions. |
| `requirements.txt`, `requirements-auto-checker.txt`, `requirements-repo-health.txt` | configuration, not prose docs | Three dependency lists overlap and have no documented ownership/selection rule. |

No root `README.md`, root `AGENTS.md`, or `docs/README.md` exists. Consequently,
all current reader-facing pages are orphaned from a repository front door.

## Command surface

### Primary CLI

The authoritative parser is `src/office_runtime/cli.py`.

| Command | Options / behavior visible in parser | Make alias |
|---|---|---|
| `daily` | `--scan-mode {none,existing,refresh}` (default `existing`) | `daily` |
| `office compile` | no command-specific flags | `office-compile` |
| `staff bundles` | `--scan-mode {none,existing,refresh}` (CLI default `refresh`; Make uses `existing`) | `staff-bundles` |
| `staff briefs` | no command-specific flags | `staff-briefs` |
| `ops repo-health policy` | `--scan-mode`, default `existing` | `repo-health-policy` |
| `ops repo-health run` | `--scan-mode`, default `existing` | `repo-health-run` |
| `capture lifecycle` | `--inbox-root`, `--out` | `capture-lifecycle` |
| `capture transcribe` | `--event-id` required; `--inbox-root`, `--model`, `--audio-root`, `--max-bytes`, `--force`, `--dry-run` | none |
| `capture transcribe-pending` | `--limit` (default 5), `--inbox-root`, `--model`, `--force`, `--dry-run` | none |
| `capture route` | `--event-id` required; `--inbox-root`, `--model`, `--force`, `--dry-run` | none |
| `capture artifactize` | `--event-id` required; `--inbox-root`, `--model`, `--force`, `--dry-run` | none |
| `capture propose-reingest` | `--event-id` required; `--inbox-root`, `--model`, `--force`, `--dry-run` | none |
| `capture process` | `--event-id` required; `--inbox-root`, `--model`, `--transcription-model`, `--force`, `--dry-run` | none |
| `evidence git` | required `--roots`, `--start`, `--end`, `--out`; optional `--max-depth`, `--limit-per-repo` | `evidence-git` |
| `evidence files` | required `--roots`, `--start`, `--end`, `--out`; optional `--max-depth`, `--include-hidden`, `--limit` | `evidence-files` |

### Other executable entry points

| Entry point | Surface | Status |
|---|---|---|
| `python -m office_runtime.ops.repo_health.cloud.run_job` | `--profile {local,gcp}`, `--policy`, `--out`, `--validate-only` | Current GCP/local adapter entry point; documented only in retrofit material. |
| `src/office_runtime/ops/repo_health/runner.py` | sheet id, service-account path, subset/rows/plugins/date and mutation-policy flags | Legacy/direct entry point; the primary CLI wraps it. |
| `src/office_runtime/evidence/{git_trace,fs_trace}.py` | Standalone forms of evidence commands | Duplicates the primary CLI surface. |
| `src/office_runtime/scripts/legacy/{compile_blocks,publish_block_queue,run_live_cycle,sheet_doctor}.py` | Legacy spreadsheet/compiler utilities | Explicitly legacy; some old prose still treats these as current. |
| `src/office_runtime/scripts/{office_run,repo_contract_bootstrap,repo_contract_scan,repo_deep_explorer,repo_snapshot_protocol}.sh` | Wrapper and repository inspection scripts | Current source-adjacent scripts; no consolidated reference. |

### Make targets

`smoke`, `imports`, `audit`, `daily`, `office-compile`, `staff-bundles`,
`staff-briefs`, `capture-lifecycle`, `repo-health-policy`, `repo-health-run`,
`evidence-git`, `evidence-files`, `evidence-today`, `logs-tail`, `repo-scans`,
`compile-blocks`, and `office` are declared. Variables are `ROOTS`, `START`,
`END`, `OUT_DIR`, `GIT_OUT`, and `FILES_OUT`.

The `repo-scans` and `compile-blocks` recipes incorrectly call `scripts/...`;
the tracked implementations live under `src/office_runtime/scripts/` (and
`legacy/` for `compile_blocks.py`). Therefore `make smoke` is broken before it
can serve as a documentation acceptance check.

## Configuration inventory

| Area | Variables / inputs | Source-truth note |
|---|---|---|
| Office | `OFFICE_ROOT`, `OFFICE_OUT_ROOT`, `OFFICE_SPREADSHEET_ID`, `OFFICE_FRONT_GID`, `OFFICE_CARRY_GID`, `OFFICE_RUNTIME_GID`, `OFFICE_SUPPORT_GID`, `OFFICE_SCRIPTS_DIR`, `OFFICE_STRICT`, `GOOGLE_APPLICATION_CREDENTIALS` | `office/config.py`; currently includes machine/project-specific defaults. |
| Capture | `OFFICE_CAPTURE_PROCESSING_MODEL`, `OFFICE_CAPTURE_TRANSCRIPTION_MODEL`, `OFFICE_FEEDBACK_AUDIO_ROOT`, fallback `OFFICE_CAPTURE_AUDIO_ROOT`, `OFFICE_CAPTURE_MAX_AUDIO_BYTES`, plus `OPENAI_API_KEY` consumed by the OpenAI client | CLI, processing, and transcription modules. |
| Repo Health cloud | `REPO_HEALTH_PROFILE`, `REPO_HEALTH_POLICY_JSON`, `REPO_HEALTH_RUN_ID`, `REPO_HEALTH_ATTEMPT`, `SOURCE_COMMIT`, `GOOGLE_CLOUD_PROJECT`, `REPO_HEALTH_GCS_BUCKET`, `REPO_HEALTH_BQ_DATASET`, `GITHUB_TOKEN`; GCP rejects `GOOGLE_APPLICATION_CREDENTIALS` | `cloud/run_job.py`. |
| Terraform/preflight | `project_id`, `billing_account_id`, `region`, `name_prefix`, `image`, `source_commit`, `policy_snapshot_json`, `dataset_id`, `evidence_retention_days`, `allow_destroy`; shell inputs `GCP_PROJECT_ID`, `GCP_BILLING_ACCOUNT_ID`, `GCP_REGION` | `infra/gcp/variables.tf`, example tfvars, and `preflight.sh`. |
| Repo Health observations | `VIRTUAL_ENV` and a fixed set of ecosystem variables | `repo_env_plugin.py`; these are observed rather than application configuration. |

## Contracts, artifacts, automation, and infrastructure

### Versioned schemas and spec data

- Capture: `reingest_candidate.schema.json` and
  `work_block_candidate_stub.schema.json`.
- Repo Health: `spec/run_bundle.schema.json` and compiler
  `spec/v0/prepared_block.schema.json`.
- Compiler lookup contracts: `archetypes.json`, `classify_rules.json`,
  `enums.json`, and `operator_registry.json`.

### Artifact families

| Producer | Principal surfaces |
|---|---|
| Office compile | Configured `artifacts/runs/<run-id>/` and `artifacts/latest/`: manifest, principal briefs, support/validation/today/clock/office Markdown, queues and merged-state tables, event logs. The fixture documents representative shapes. |
| Staff | `artifacts/latest/bundles/<type>__<project>.json`, `briefs/<type>__<project>.md`, and brief/job indexes. |
| Capture | lifecycle JSON/Markdown, candidate JSON/Markdown, block-candidate CSV/Markdown under the configured latest directory; append-only input/derived JSONL under `inbox/`. |
| Evidence | Caller-selected git/files JSONL, with Make defaults below `artifacts/evidence/`. |
| Repo Health local | `out/repo-health-runs/<run-id>/{run_bundle.json,manifest.json}` and local `history.jsonl`; frontier/compiler outputs include `out/frontier/latest.csv` and dated `prepared_blocks.jsonl`. |
| Repo Health GCP | Immutable GCS run packet and manifest; BigQuery `runs`, `details`, `latest_plugin_health`, `unresolved_issue_signatures`, and `prepared_blocks_weekly`. |

### Automation and GCP resources

Three user services and three timers exist: office compile (08:05, 12:05,
16:05, 20:05), staff daily/briefs (08:10, 16:10), and evidence daily (23:00).
All use `Persistent=true`; service paths are hard-coded to
`/home/matias/repos/office-auto-lab`.

Terraform declares project API enablement, a billing budget, Artifact Registry,
a runtime service account, an evidence bucket with retention/lifecycle and IAM,
a BigQuery dataset plus five tables/view, dataset/project IAM, a log metric and
alert policy, image-pull IAM, and a Cloud Run v2 job. These surfaces are
**implemented, locally validated, and deployment-ready; no provider-side evidence
in this repository establishes deployed or operated status**.

## Executable evidence

| Tests | Behavior evidenced |
|---|---|
| `test_capture_lifecycle.py` | lifecycle merge, warnings, stable artifacts, non-mutation |
| `test_capture_processing.py` | routing/artifact/reingest stages, schemas, idempotence/dry-run behavior |
| `test_capture_transcription.py` | audio selection, limits, transcription event handling |
| `test_repo_health_semantics.py` | policy, plugins, runner and compiler semantics |
| `test_repo_health_run_bundle.py` | bundle validation and immutable local packet writes |
| `test_repo_health_remote.py` | remote source boundaries and plugins |
| `test_repo_health_gcp.py` | cloud adapters, identity rejection, deterministic/idempotent persistence |

## Drift and unresolved facts

1. The requested `docs/documentation_program/CODEX_START_HERE.md` does not exist;
   PR-OD0 was selected from the intact seed under `notes/`. This is the only
   structural deviation from the seed assumed by this PR.
2. `make smoke` refers to three absent top-level `scripts/` paths. This is a
   confirmed product/build defect, recorded but not repaired in this
   documentation-only PR.
3. Capture design prose says multiple implemented surfaces are merely proposed
   and names `capture_candidates.csv`, while current lifecycle code writes
   `capture_candidates.json` plus Markdown.
4. Systemd guidance and units are internally aligned but non-portable because
   they embed one user's home path.
5. Old checker/compiler notes reference a pre-`src` script layout, a live-cycle
   Make interface that no longer exists, and service-account-key workflows that
   must not be confused with GCP Repo Health's assigned-identity boundary.
6. The empty contracts README and malformed citation token in
   `notes/runbook.md` are stale content.
7. No single page owns CLI, configuration, artifacts, schema, plugin, or status
   reference, and no automated relative-link/freshness check exists.

## Exact delta from the seed inventory

- The documentation seed itself remains under `notes/`, rather than installed
  under `docs/documentation_program/`.
- Capture now includes transcription and structured processing commands beyond
  the lifecycle compiler described by the seed inventory.
- Current Make smoke wiring is demonstrably broken by the source-layout move.
- The inventory found seven unindexed Mermaid sources, empty contract/spec
  README files, three overlapping requirements files, and hard-coded systemd
  paths that the embryo inventory did not enumerate.
- No later-phase front door, architecture, component guide, runbook
  consolidation, or validation framework was added in PR-OD0.
