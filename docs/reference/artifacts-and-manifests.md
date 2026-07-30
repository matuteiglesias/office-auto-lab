# Artifacts and manifests

**Status:** canonical
**Audience:** operators, integrators, contributors, and agents
**Owner:** artifact-producing components
**Verified against:** `8b4c9b7`

## Catalog

| Family | Location / principal files | Writer | Completion and mutability |
|---|---|---|---|
| Office run | `artifacts/runs/<run-id>/`: manifest, routed CSVs, briefs/queues/validation Markdown | Office compile | `manifest.json`; run-specific directory |
| Office latest | `artifacts/latest/` copy of successful run | Office promotion | Mutable clear-and-copy snapshot |
| Staff | latest `bundles/*.json`, `scans/*`, `ai_jobs.csv`, `briefs/*.md`, `brief_index.csv` | Staff | Index + referenced files; subdirs can retain stale files |
| Capture lifecycle | selected out: lifecycle JSON/CSV/MD, candidates JSON/MD, block stubs CSV/MD | Capture lifecycle | Successful JSON summary plus all reported files; recompiled snapshot |
| Capture events | dated inbox raw/processing JSONL and audio | External raw producer; capture derived writers | Append-only event streams; no global manifest |
| Evidence | caller-selected Git/files JSONL | Evidence tracers | CLI summary and output; caller-owned path |
| Logs | `artifacts/logs/{runs,events,daily}` | shared logger/ledger | Append-only observational logs, not domain completion |
| Frontier/compiler | `out/frontier/latest.csv`, dated CSV, dated `prepared_blocks.jsonl` | Repo Health/export/compiler | Rewritten latest/deterministic dated output |
| Local run packet | `<out>/<run-id>/{run_bundle.json,manifest.json}` plus `history.jsonl` | Repo Health local sinks | Manifest; atomic publish; idempotent exact replay |
| GCS run packet | `repo-health/runs/<run-id>/{run_bundle.json,manifest.json}` | GCS sink | Manifest written last; create-only |
| BigQuery history | runs, run_intents, plugin_results, exceptions, prepared_blocks; derived views | BigQuery sink/Terraform | Details then `runs` completion row; stable-row MERGE |

## Office manifest

A fatal input error manifest contains run id, `status: error`, and issues. A
successful manifest adds timestamps, configured ids, row counts, warnings, and
artifact context before latest promotion. It is not versioned by JSON Schema.
Use the synthetic fixture only as representative, non-production data.

## Repo Health manifest

The packet manifest has schema `repo_health.run_manifest.v1`, run id, and SHA-256
plus byte count for canonical `run_bundle.json`. It is the completion marker, not
a replacement for run-bundle schema validation. One run id may not name different
bytes.

## Consumer rules

Prefer run-specific evidence over `latest`; validate references before consuming
an index; treat logs as diagnostics; never infer approval from a capture
candidate; reject bundle/manifest hash mismatch or run-id conflict. Field-level
versioned contracts are linked from [schemas and contracts](schemas-and-contracts.md).
