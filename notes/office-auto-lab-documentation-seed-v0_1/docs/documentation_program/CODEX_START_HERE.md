# Codex start here — office-auto-lab documentation program

## Execution contract

1. Read this file, the charter, current-state inventory, target stack, and carry state.
2. Inspect the current default branch. Existing documentation is evidence, not presumed truth.
3. Execute **only** the PR identified by `next_pr`.
4. Keep the PR documentation-only unless a command cannot be documented because of a confirmed product defect. Record that defect separately; do not repair it opportunistically.
5. Do not mass-move or delete old documents before canonical replacements exist and links have been checked.
6. Every behavioral claim must point to source, schema, test, infrastructure, or runtime evidence.
7. Commands must be executed or explicitly labeled `illustrative / not executed`.
8. Preserve the distinction among `implemented`, `locally validated`, `deployment-ready`, `deployed`, and `operated`.
9. Add a closure note under `docs/documentation_program/context/closures/`.
10. Propose the carry-state update. Do not mark your own PR `ACCEPTED`.
11. Stop when the active PR is coherent, reviewable, and bounded.

## Required PR description

- Reader problem solved
- Why this documentation is canonical
- Exact scope and non-goals
- Source truth inspected
- Pages added, changed, redirected, or marked historical
- Commands and links verified
- Drift discovered
- Risks and remaining ambiguity
- Closure-note path
- Proposed next PR

## Program identity

- Repository: `matuteiglesias/office-auto-lab`
- Program: `office_auto_lab_documentation`
- Initial execution PR: `PR-OD0`

## Hard exclusions

- No feature implementation.
- No GCP deployment.
- No unverified claims of production operation.
- No deletion of retrofit or closure evidence in the inventory phase.
- No documentation generator or site framework before the Markdown information architecture is accepted.
