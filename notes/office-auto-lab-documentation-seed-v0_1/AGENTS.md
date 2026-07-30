# Agent operating contract

Before performing documentation work, read:

1. `docs/documentation_program/CODEX_START_HERE.md`
2. `docs/documentation_program/00_documentation_charter_v0_1.md`
3. `docs/documentation_program/01_current_state_inventory_v0_1.md`
4. `docs/documentation_program/carry_state_v0_1.yaml`

Documentation PRs are evidence-constrained work.

- Inspect current source, tests, CLI wiring, schemas, infrastructure, and generated artifact shapes before describing behavior.
- Execute only the PR named by `next_pr`.
- Do not change product semantics inside a documentation PR.
- Do not claim GCP deployment or repeated operation without provider-side evidence.
- Keep `notes/`, retrofit closure records, and evidence packets available as historical/supporting material; they are not automatically canonical documentation.
- Prefer one canonical page for each command or operational path, with other pages linking to it rather than copying it.
- Update the documentation closure note and propose a carry-state change. Human review owns acceptance.
