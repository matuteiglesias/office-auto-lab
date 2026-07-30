# Codex Prompt — PR-G1: Stabilize Repo Health semantics and declare cloud capabilities

Prerequisite: PR-G0 is accepted.

Execute only PR-G1.

## Goal

Correct characterized semantic defects and make plugin execution capability explicit without adding cloud-provider code.

## Scope

- Fix due/scheduled semantics according to the accepted G0 decision.
- Make no-write genuinely non-mutating.
- Preserve accepted evidence/meta fields through normalization.
- Add explicit plugin capability metadata: `local_only`, `remote_read`, `remote_execute`.
- Create an explicit GCP-profile allowlist that accepts only `remote_read`.
- Preserve current local CLI behavior and fixtures where semantically valid.

## Tests

- Regression for each accepted G0 defect.
- Cloud-profile selection rejects local/execute plugins.
- Unknown capability fails closed.
- Local compiler output remains deterministic.

## Non-goals

- No GitHub API calls.
- No provider persistence.
- No infrastructure.
- No general plugin framework rewrite.

Produce `context/closures/PR-G1.md` and propose `PR-G2`.
