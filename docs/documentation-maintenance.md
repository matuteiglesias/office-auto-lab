# Documentation maintenance policy

**Status:** canonical
**Audience:** contributors, reviewers, maintainers, and agents
**Owner:** office-auto-lab maintainers
**Verified against:** `63e6868`

## Quality gate

Run before commit:

```bash
make docs-check
make audit
```

`docs-check` validates repository-relative Markdown targets and anchors across
the root README and `docs/`. It also requires `Status`, `Audience`, `Owner`, and
`Verified against` metadata on canonical architecture, case-study, component,
getting-started, operations, and reference pages. `audit` includes `docs-check`.

The checker deliberately excludes external URL availability and Markdown under
`notes/`/`context/`; those are historical/supporting inputs. It does not prove
commands, diagrams, provider state, or prose accuracy. Review those against
source/runtime evidence.

## Update obligations

| Change | Canonical documentation obligation |
|---|---|
| CLI command, flag, or Make target | Update `reference/cli.md` and affected runbook/component guide |
| Environment variable/default/secret handling | Update `reference/configuration.md` and trust/security page |
| Artifact path, writer, completion marker, replay | Update artifact reference, ownership/state, and component guide |
| Schema, enum, plugin contract/capability | Update schemas/contracts or plugin reference plus compatibility notes |
| Office/staff/capture/evidence behavior | Update owning component and affected operation/failure page |
| Repo Health policy/compiler/bundle | Update component, schema/plugin reference, and local/GCP runbook as applicable |
| systemd unit/wrapper | Update systemd runbook and configuration/reference |
| GCP resource, IAM, data model, cost, teardown | Update GCP architecture, security/data reference, runbooks, and case-study claim matrix |
| Deployment/maturity claim | Supply evidence and update README/router/case matrix; never promote by prose alone |

Every PR changing these surfaces must name the pages updated or justify “no
documentation impact.” Commands added to a runbook must be executed or labeled
illustrative/unexecuted with expected output and stop conditions.

## Canonicality and migration

One page owns each procedure. Reference pages may list syntax; component pages
may identify commands; both link to the owning runbook. When superseding prose:
verify unique facts, create the replacement, replace duplicated procedures with
links, add a status banner, check inbound links, and preserve evidence. Do not
mass-delete notes, retrofit records, closures, or generated examples.

## Review cadence

Review canonical metadata and links on every documentation PR. Review the
[coverage report](documentation_coverage.md) when command/config/schema/IaC
surfaces change and at least before each documentation-program acceptance. The
verification commit identifies the source snapshot, not an evergreen guarantee.
