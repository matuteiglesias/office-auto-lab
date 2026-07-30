# PR-G1 Closure Note

- **Retrofit:** `gcp_project_health`
- **PR:** `PR-G1`
- **Status:** `ACCEPTED`
- **Accepted commit:** `56fed10`
- **Goal:** Correct the characterized local semantic defects and make cloud plugin eligibility explicit without provider code.

## Delivered

- Scheduling now requires a due date and satisfied prerequisites. Missing `next` remains visible as `skip_reason: missing_next` but is not scheduled; an all-disabled policy set also returns cleanly instead of referencing uninitialized conflict state.
- `--no-write` now forces plugin dry-run behavior and suppresses EffectiveRunSet, PluginResults, frontier, runtime-health, and file-log mutations.
- Required Sheets policy reads no longer create missing tabs as a side effect.
- Normalized plugin results retain structured `evidence` and `meta`; the compact frontier schema remains unchanged.
- Every current plugin declares `local_only` or `remote_execute` capability metadata.
- GCP selection is an explicit name allowlist intersected with `remote_read`; unknown capability values fail closed. No current plugin is eligible.
- The accepted product direction records that the running office and cross-project carry state are central, while features may be deliberately pruned rather than preserved for compatibility alone.

## Non-goals preserved

- No GitHub API calls or remote repository adapter.
- No Google Cloud provider dependencies or persistence.
- No infrastructure or container changes.
- No generalized plugin framework rewrite.

## Semantic changes

| Surface | Before | After |
|---|---|---|
| Scheduling | `prereq_ok` | `due AND prereq_ok` for enabled projects |
| Missing `next` | scheduled | unscheduled with `missing_next` reason |
| No-write | results/frontier/log files could mutate | console-only execution planning; plugins forced dry-run; no output mutation |
| Policy reads | missing tabs could be created | missing required tabs fail without mutation |
| Plugin result | evidence/meta dropped | evidence/meta retained on normalized record |
| Cloud selection | no trust metadata | explicit allowlist + `remote_read`, unknown values rejected |

## Risks and follow-up

- Existing scheduled volume will decrease because future and missing dates no longer execute. This is intentional and should be observed in the first local run after acceptance.
- Sheet append stringification of structured evidence is still a local compatibility surface; G3 will define producer-owned serialization rather than expanding it here.
- The two GCP allowlist names are reserved for G2 implementations and select nothing until those implementations exist.
- No-write still performs remote Sheet reads because it is a non-mutation mode, not an offline mode.

## Evidence

- Focused Repo Health suite covers accepted G0 defects, capability selection, missing-tab reads, credential compatibility, and compiler determinism.
- Repository audit covers imports, compilation, plugin inventory, and diff hygiene.
- Full-suite status is recorded in the PR description, including unrelated baseline capture failures.

## Carry-state transition proposal

After human acceptance only:

```yaml
current_phase: phase_2
current_pr: null
last_accepted_pr: PR-G1
accepted_commit: <human-accepted-commit>
next_pr: PR-G2
accepted_artifacts:
  - context/closures/PR-G0.md
  - docs/retrofit/gcp_project_health/03_g0_characterization_v0_1.md
  - context/closures/PR-G1.md
```

Human review accepted G1 and authorized G2 on 2026-07-29.
