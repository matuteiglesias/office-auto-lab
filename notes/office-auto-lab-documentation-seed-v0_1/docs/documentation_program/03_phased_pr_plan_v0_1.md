# office-auto-lab documentation production plan v0.1

## Sequence

| PR | Outcome | Reader value | Stop condition |
|---|---|---|---|
| PR-OD0 | Complete documentation and command inventory | establishes truth and canonicality map | inventory reviewed; no broad rewrite |
| PR-OD1 | Root README and docs router | repository becomes understandable from the root | reader routes and status language accepted |
| PR-OD2 | System architecture and ownership | explains how subsystems and artifacts fit together | diagrams reconcile with source/tests |
| PR-OD3 | Component owner guides | contributors and agents can work within boundaries | five owner guides use common contract |
| PR-OD4 | Golden paths, operations, and reference | operators can execute and recover workflows | commands verified; duplication removed by links |
| PR-OD5 | GCP Repo Health canonical docs and case study | cloud work becomes legible and senior-level | status remains honest; evidence links complete |
| PR-OD6 | Migration, validation, and maintenance gate | documentation remains trustworthy | old pages classified; automated checks pass |

## PR-OD0 — inventory and canonicality

Deliver:

- `docs/documentation_inventory.md`;
- command/Make/CLI matrix;
- documentation status map;
- duplicate and stale-content register;
- proposed canonical owner for each reader task;
- exact delta from this embryo plan.

Do not rewrite major existing pages.

## PR-OD1 — front door

Deliver:

- concise `README.md`;
- `docs/README.md`;
- status legend;
- audience/task navigation;
- first local quickstart;
- explicit link to `AGENTS.md`.

The README must say that GCP is deployment-ready, not deployed.

## PR-OD2 — architecture

Deliver:

- system overview;
- runtime/artifact flow;
- ownership/state-writer matrix;
- trust-boundary page;
- initial ADRs for durable decisions that cannot be inferred safely.

Use Mermaid diagrams plus prose. Include local and GCP Repo Health profiles.

## PR-OD3 — component documentation

Create owner guides for:

1. Office compile
2. Staff
3. Capture
4. Evidence
5. Repo Health

Every guide must point to source, tests, commands, inputs, outputs, invariants,
and failure modes. Do not copy full operational procedures from runbooks.

## PR-OD4 — operations and reference

Create or consolidate:

- local environment and validation;
- routine local operation;
- systemd automation;
- Repo Health local runbook;
- failure/recovery;
- CLI reference;
- configuration reference;
- artifact/schema/plugin catalogs.

Commands must be run or labeled unverified. Add expected outputs and stop rules.

## PR-OD5 — GCP documentation and engineering case

Promote the retrofit into canonical pages:

- GCP architecture profile;
- first deployment/manual execution runbook;
- security/IAM and denied-access model;
- BigQuery/GCS data model;
- teardown/cost boundary;
- before/after case study;
- claim/status matrix.

Retain retrofit records as supporting history.

## PR-OD6 — migration and documentation quality gate

- mark historical/superseded documents;
- replace duplicated commands with links;
- add relative-link and required-metadata validation;
- add documentation checks to an appropriate smoke/CI path;
- document update obligations for code, CLI, schema, and infrastructure PRs;
- publish a final documentation coverage and known-gaps report.

## Optional later work

A generated documentation site, screenshots, richer diagrams, or API extraction
may follow only after Markdown canonicality and maintenance checks are stable.
