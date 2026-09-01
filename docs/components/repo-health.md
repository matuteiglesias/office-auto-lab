# Repo Health compatibility implementation guide

**Status:** compatibility
**Audience:** maintainers and agents supporting or migrating legacy Repo Health consumers
**Owner:** office-auto-lab maintainers (implementation only)
**Verified against:** `governance/m7-demote-repo-health-surface`

## Authority status

Repository-health semantics and safe GitHub-estate sensing are no longer owned by Office. The canonical semantic owner is the `projects` GitHub-estate control plane, which defines repository health/readiness and produces the repo-keyed `context:github-repositories@1` projection.

The code under `src/office_runtime/ops/repo_health/` remains in this repository as a **compatibility implementation** because it contains broader historical execution machinery—sheet-backed policy, plugins, local/environment inspection, cloud orchestration, compiler outputs, and persistence adapters—that cannot be safely or honestly moved into the metadata-only estate control plane as one block.

Do not add new repository-health semantic vocabulary here independently. If compatibility code requires a new durable repository-health concept, define/standardize that concept in `projects` first and then adapt this implementation if still needed.

## What remains here

| Path | Compatibility responsibility |
|---|---|
| `policy.py`, `runner.py`, `sheets.py` | Historical sheet-backed planning/execution and optional writes |
| `plugins/`, `plugin_loader.py` | Legacy plugin discovery and execution capabilities |
| `remote/` | Read-only repository-source abstraction used by the compatibility runner |
| `compiler/` | Historical frontier/prepared-block compilation |
| `run_bundle/`, `spec/run_bundle.schema.json` | Versioned legacy run-bundle model and validation |
| `cloud/run_job.py` | Frozen-snapshot compatibility orchestration |
| `adapters/gcp/` | GCS/BigQuery persistence for legacy run bundles |
| `infra/gcp/`, `Dockerfile.repo-health` | Compatibility deployment assets |

These paths are not part of the active Office product surface merely because they remain tracked and tested.

## Active replacement seam

For ordinary Office use, repository context should arrive through:

```text
projects
  authenticated GitHub observations + estate policy
        ↓
context:github-repositories@1
        ↓
Office optional repo-context enrichment
```

Office owns the front-to-repository association (`repo_ids`) and all operational consequences. Repository context remains advisory and cannot directly change Carry State, horizon, priority, Principal posture, escalation, or block eligibility.

## Compatibility commands

The legacy CLI path remains temporarily available:

```text
python -m office_runtime.cli ops repo-health policy ...
python -m office_runtime.cli ops repo-health run ...
```

The Make aliases are intentionally named as compatibility surfaces:

```text
make compat-repo-health-policy
make compat-repo-health-run
```

New Office workflows should not adopt these as their repository-health authority. Prefer the `projects` sensing/projection path.

## Safety boundary

The compatibility implementation is broader than the safe sensing boundary in `projects`. Depending on flags/plugins it may read Sheets, inspect local repository environments, invoke repository-specific machinery, write result summaries, or use GCP persistence. Those behaviors are precisely why the code is not being copied wholesale into `projects`.

`projects` must remain limited to GitHub-remote/committed metadata observations and deterministic projections; it must not import or run these plugins to claim repository health.

## Tests and dependency profile

The `repo-health` dependency profile and dedicated `test_repo_health_*` suites remain to prevent accidental breakage while compatibility consumers exist. Their continued presence is not evidence that Repo Health remains an active Office product.

The active Office import smoke no longer imports or discovers the Repo Health plugin surface. Compatibility tests continue to run separately in CI.

## Removal condition

Physical deletion of this compatibility implementation is a later cleanup step, not part of M7. Before deleting code, profiles, cloud assets, or schemas:

1. audit known CLI/Make/module consumers;
2. confirm no scheduled or external runtime still depends on the legacy runner;
3. preserve any historical run-bundle evidence that still matters;
4. remove compatibility dependencies and CI slices together;
5. verify Office still receives all required repository context through `context:github-repositories@1`.

Until then, keep this implementation stable and clearly subordinate to the `projects` semantic authority.
