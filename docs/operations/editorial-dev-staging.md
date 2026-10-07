# Editorial Dev Staging v1 — operational implementation

**Status:** implementation candidate
**Audience:** Editorial runtime maintainers and operators
**Owner:** office-auto-lab maintainers
**Verified against:** PR #52 spec head `f7edaeff729fae1fc006772777aa1c92f60298de`

This document describes the W1 staging/runtime implementation owned by this branch. The semantic authority remains `docs/spec/editorial-v1/`.

## Sheet contract and ownership

One configured workbook is used. It must already contain exactly the logical tabs `RUNS`, `CANDIDATES`, and `QUEUE` with the headers exported by `office_runtime.editorial.staging.sheets`.

Each row carries a schema version. The adapter validates all three tab headers, duplicate keys, and existing row schema versions before the first mutation. It does not create, rename, or repair tabs. A malformed workbook fails closed.

Ownership is deliberately asymmetric:

- `RUNS` is machine-owned and keyed by `run_id`. A retry may reconcile mutable summary fields only when the run identity (`run_id`, profile, start time, policy identity, schema version) still matches.
- `CANDIDATES` is machine-owned and append-only by `candidate_id`. An existing candidate row must exactly match the attempted projection; otherwise projection stops with an identity conflict.
- `QUEUE` is initialized once per `candidate_id`. On creation only, `draft_editable = draft_original`, `decision = REVIEW`, and `target_surface = X`. The staging producer never rewrites an existing queue row, including `draft_editable`, `decision`, `editor_note`, `target_surface`, `publisher_status`, `scheduled_for`, or `published_ref`.

Projection validates the whole workbook before writing, then applies `RUNS`, `CANDIDATES`, and `QUEUE` in that order. Stable keys make a retry after partial success duplicate-safe.

The adapter copies compact references and summaries, not raw source bodies. Routine error summaries keep only bounded status/code/stage metadata.

## Manual and backfill CLI

The repository CLI exposes:

```bash
PYTHONPATH=src python -m office_runtime.cli editorial dev stage \
  --pr owner/repo#123 \
  --dry-run

PYTHONPATH=src python -m office_runtime.cli editorial dev stage \
  --since 2026-10-01T00:00:00Z \
  --until 2026-10-03T00:00:00Z \
  --dry-run

PYTHONPATH=src python -m office_runtime.cli editorial dev stage \
  --date 2026-10-06 \
  --dry-run

PYTHONPATH=src python -m office_runtime.cli editorial dev stage \
  --bundle-in artifacts/editorial/input/run.json \
  --apply-sheet
```

The dedicated scheduled/operator entrypoint is:

```bash
PYTHONPATH=src python src/office_runtime/scripts/run_editorial_dev_staging.py \
  --lookback-hours 96 \
  --apply-sheet
```

`--apply-sheet` is the explicit Sheet-mutation switch. Without it, execution is local-artifact-only; `--dry-run` makes that intent explicit and cannot be combined with `--apply-sheet`.

Windows are bounded to 14 days. Exact-PR mode requires `owner/repo#PR`. Projection-only mode accepts an already-generated `editorial.run_bundle.v1` and does not load a model/ADK producer.

## Candidate-production integration seam

This branch does not implement a competing evidence or model generator.

When a run bundle is not supplied, the entrypoint loads a narrow callable configured as:

```text
EDITORIAL_DEV_BUNDLE_PROVIDER=package.module:produce_bundle
```

or by `--provider package.module:produce_bundle`.

The callable receives a plain request mapping and must return a mapping conforming to `editorial.run_bundle.v1`. Framework/session objects do not cross this seam. The evidence-spine and editorial-intelligence branches can therefore integrate by providing one adapter function without changing Sheet or scheduler code.

## GitHub Actions topology

`.github/workflows/editorial-dev-staging.yml` is the first unattended staging topology. It provides:

- daily scheduled invocation plus manual dispatch;
- an overlapping default 96-hour lookback;
- checkout under repository-scoped `GITHUB_TOKEN` only for this repository;
- a separate estate-scoped read-only GitHub token for retrieval;
- model/runtime credential plumbing for the candidate producer;
- Google Sheets credential/access;
- one run-bundle artifact per successful editorial invocation;
- a concise GitHub run summary;
- no X credential and no X mutation path.

`DEGRADED_INVENTORY` exits successfully. `FAILED` inventory is an editorial/runtime failure.

The workflow delegates retrieval/generation/projection to the repository-owned Python entrypoint; YAML does not implement editorial orchestration.

## Expected configuration names

Values are never committed or logged.

- secret `EDITORIAL_ESTATE_GITHUB_TOKEN`: read-only credential whose installation/token scope covers the intended GitHub estate.
- secret `EDITORIAL_MODEL_API_KEY`: opaque model credential made available to the integrated producer adapter. The adapter remains responsible for provider-specific interpretation.
- secret `EDITORIAL_GOOGLE_CREDENTIALS_JSON`: Google service-account JSON with access to the staging workbook. Application Default Credentials are also supported outside Actions.
- variable `EDITORIAL_DEV_SHEET_ID`: workbook ID.
- variable `EDITORIAL_DEV_BUNDLE_PROVIDER`: integrated `module:function` producer adapter; defaults to `office_runtime.editorial.producer:produce_bundle`.
- variable `EDITORIAL_RUNTIME_PROFILE`: dependency profile installed by the scheduled job; defaults to `editorial`.
- variable `EDITORIAL_REPOSITORIES`: repository scope for scheduled/lookback staging. Use `@owned` to discover every non-archived repository owned by `EDITORIAL_GITHUB_OWNER` that the estate token can see, or provide an explicit comma-separated allowlist. The workflow defaults to `@owned`.
- variable `EDITORIAL_GITHUB_OWNER`: expected owner login for `@owned` discovery; defaults to `matuteiglesias`.
- variable `EDITORIAL_MAX_STORIES_PER_RUN`: maximum number of public-eligible story clusters sent through model stages in one run. Default and hard v1 maximum are 12.

There are intentionally no `X_*` secrets in this workflow. `EDITORIAL_MODEL_API_KEY` is deliberately provider-neutral; the producer adapter owns the mapping to provider-specific environment/configuration required by ADK.

Scheduled lookback is deliberately broad in sensing but bounded in expensive judgment. With `EDITORIAL_REPOSITORIES=@owned`, the runtime discovers all non-archived repositories owned by the configured account that the estate-scoped token can see. It then retrieves only the bounded recent evidence windows supported by each GitHub adapter. The model layer receives only public-eligible stories and is capped at 12 per run, so private/internal repository activity can remain visible in governed retrieval evidence without being sent to the external model by default. The complete retrieved evidence/story graph remains in the governed run bundle; the cap and public-eligibility gate affect model processing, not provenance.

## Offline acceptance covered here

`tests/test_editorial_staging.py` proves:

- first projection creates `RUNS`, `CANDIDATES`, and `QUEUE` records;
- retry does not duplicate them;
- queue draft edits and `APPROVE` / `HOLD` / `REJECT` survive;
- publisher state survives;
- a failure after partial projection can retry safely;
- candidate and run identity conflicts fail closed;
- malformed headers/schema versions fail before mutation;
- exact PR and bounded-window operator requests are validated;
- an already-generated bundle can be projected without any model producer;
- `DEGRADED_INVENTORY` remains a completed editorial outcome.

## Live integration deliberately not claimed

This branch does not claim a live Google Sheet smoke test, a live estate retrieval run, or a model/ADK invocation. Those require credentials/environment authorization not present in the cloud editing surface.

Before operational acceptance, run one bounded staging-workbook smoke using a disposable/test candidate and verify a manual queue edit survives a second projection.

## Integration points waiting on parallel branches

The evidence/contracts branch owns the canonical typed contracts, evidence retrieval, policy/context, run-bundle writer, and clustering. The editorial-intelligence branch owns angle generation, judge/editor behavior, and batch compilation.

After those PRs stabilize, wire their repository-owned producer function into `EDITORIAL_DEV_BUNDLE_PROVIDER`. Do not move their semantics into `staging.runtime`; the staging layer should continue to consume the frozen run-bundle seam.
