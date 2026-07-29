# Codex Prompt — PR-G0: Install retrofit governance and characterize current behavior

Read `CODEX_START_HERE.md`, the embryo plan, starting context, sprint contract, and carry state.

Execute only PR-G0.

## Goal

Install the retrofit control surface in the repository and add characterization tests/notes for the current Repo Health semantics relevant to cloud execution.

## Required work

1. Add the supplied retrofit documents under `docs/retrofit/gcp_project_health/`.
2. Inspect the current policy, runner, Sheets adapter, plugin loader, plugins, frontier exporter, and compiler.
3. Add focused characterization tests or fixtures for:
   - due versus scheduled intent behavior;
   - no-write behavior;
   - current plugin discovery;
   - normalized result evidence/meta retention;
   - local-path assumptions;
   - deterministic compiler output;
   - current credential/config discovery.
4. Produce `context/closures/PR-G0.md`.
5. Propose, but do not mark accepted, the carry-state update to `PR-G1`.

## Non-goals

- No bug fixes.
- No cloud SDK.
- No Docker/Terraform.
- No GitHub API adapter.
- No unrelated office/capture changes.

## Done

The PR makes the current semantics provable and identifies the exact bounded fixes for G1.
