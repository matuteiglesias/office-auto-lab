# Documentation coverage and known gaps

**Status:** canonical program report; PR-OD6 candidate pending human acceptance
**Audience:** maintainers, reviewers, evaluators, and agents
**Owner:** office-auto-lab maintainers
**Verified against:** `63e6868`

## Coverage

| Reader need / surface | Canonical owner | Coverage |
|---|---|---|
| Repository orientation and reader routing | Root README; `docs/README.md` | Covered |
| Architecture, flow, ownership, trust | Four system pages plus GCP profile | Covered |
| Office, staff, capture, evidence, Repo Health ownership | Five component guides | Covered |
| Local setup, routines, automation, recovery | Getting-started and four local runbooks | Covered; network commands labeled unexecuted |
| CLI, configuration, artifacts, schemas, plugins | Five general reference pages | Covered |
| GCP deployment, IAM, data, cost/teardown | GCP runbooks and references | Deployment-ready procedure; provider execution unverified |
| Engineering narrative and claim status | GCP case study | Covered without deployment overclaim |
| Historical/supporting navigation | `historical/README.md` and status banners | Covered at collection level |
| Link/metadata validation | `make docs-check`, included in `make audit` | Automated locally |
| Maintenance obligations | `documentation-maintenance.md` | Covered |

## Known product and validation gaps

1. `make smoke`, repository scans, and legacy compiler targets reference missing
   pre-`src` paths; the `office` target references a missing module.
2. Primary CLI Repo Health wrappers cannot pass required runner options, and
   their Make targets omit required sheet/credential inputs.
3. Office, staff, and evidence lack focused behavioral test modules.
4. Capture processing has known realistic-ontology target-surface failures.
5. One GCP adapter test requires an unavailable BigQuery package in the inspected
   environment; the full suite is not currently green here.
6. Office latest promotion clears/copies non-atomically; staff subdirectories can
   retain stale outputs; staff scan exit codes are not component failures.
7. Several Office, staff, evidence, logging, and event shapes are code-defined
   rather than independently versioned schemas.
8. systemd units embed one host path and require local adaptation.

## Evidence and operational gaps

- Office/staff live commands, model-backed capture, GitHub-backed full Repo
  Health, and user-systemd installation were not executed in the documentation
  program environment.
- No provider-side GCP plan/apply, image, resource, execution, GCS, BigQuery,
  logs, denial, billing, recovery, or teardown evidence exists.
- GCP status is therefore deployment-ready, not deployed or operated.
- External URL availability and Mermaid rendering are not automated.

## Program completion gate

PR-OD6 is ready for human review when `make docs-check`, `make audit`, and the
documented bounded commands pass; canonical links/metadata are complete; old
procedures route to replacements; unique evidence is preserved; and the final
carry state does not self-accept. Product/provider gaps above remain explicit
follow-up work rather than blockers to documentation-program completion.
