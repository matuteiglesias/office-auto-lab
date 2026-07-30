# Codex Prompt — PR-G2: RepositorySource boundary and GitHub API-native plugins

Prerequisite: PR-G1 is accepted.

## Goal

Introduce a bounded repository-source abstraction and implement the first GitHub API-native, read-only inspection plugins.

## Required design

- `LocalRepositorySource` for current supported local facts.
- `GitHubRepositorySource` behind an interface.
- Allowlisted `owner/repo` identities only.
- Fake/test adapter; no live-network dependence in unit tests.
- Remote plugins for:
  - commit activity/recency;
  - basic hygiene and runbook presence.
- Explicit `NA`/ineligible outputs for unsupported local facts.

## Preserve

- Plugin result vocabulary.
- Normalized frontier.
- Compiler semantics.

## Exclude

- clone;
- shell;
- `make smoke`;
- dirty worktree;
- generated artifacts;
- arbitrary path/content enumeration.

Produce parity fixtures, `context/closures/PR-G2.md`, and propose `PR-G3`.
