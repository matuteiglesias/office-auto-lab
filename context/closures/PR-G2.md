# PR-G2 Closure Note

- **Retrofit:** `gcp_project_health`
- **PR:** `PR-G2`
- **Status:** `ACCEPTED`
- **Accepted commit:** `2e472b8`
- **Goal:** Establish a bounded repository-source boundary and the first API-native, read-only project inspections.

## Delivered

- Added a provider-neutral `RepositorySource` protocol for repository identity, head facts, bounded tree reads, bounded text reads, and commit activity.
- Added `LocalRepositorySource` for parity against controlled local Git repositories.
- Added `GitHubRepositorySource`, restricted to allowlisted `owner/repository` identities and HTTP GET operations with timeouts, response bounds, stable error categories, and no clone or write surface.
- Added `InMemoryRepositorySource` for deterministic tests without live network access.
- Added `activity_remote` and `runbook_remote`, the only two `remote_read` plugins selected by the GCP registry.
- Made unsupported local facts explicit as `NA`, including worktree dirtiness, ahead/behind, origin state, and filesystem freshness.
- Excluded private repositories, archived activity, unallowlisted identities, arbitrary deep content enumeration, shell execution, generated artifacts, and Make targets from remote inspection.

## Preserved contracts

- Plugin status/bucket/message/evidence/meta vocabulary.
- Compact normalized frontier and compiler semantics.
- Existing local plugins as compatibility surfaces; remote implementations are separate rather than false parity labels.

## Security and bounds

- Repository identities are validated and checked against an explicit allowlist before any request.
- GitHub calls are GET-only, timed out, and tree/content/commit responses are capped.
- Runbook inspection considers at most five bounded root/docs/notes candidates and reads at most 100 KB per file.
- GitHub 404, permission, rate-limit, generic HTTP, oversized-tree, and unsupported-content outcomes have stable source categories.
- Unit tests use fake sessions and in-memory/local sources; no live GitHub access is required.

## Risks and follow-up

- GitHub pagination beyond the first 100 commits is intentionally absent because activity only needs a bounded threshold signal.
- Local adapter uses fixed Git subprocess commands for parity; it is never eligible for the GCP profile.
- Remote runbook freshness is honestly `NA` because GitHub tree/content facts do not provide filesystem mtime semantics.
- G3 must place raw source/plugin evidence into an atomic producer-owned run bundle before persistence adapters are introduced.

## Evidence

- Deterministic GitHub fake-response tests.
- Allowlist-before-network and failure-category tests.
- Local-versus-in-memory supported-fact plugin parity fixture.
- Registry test proving exactly two cloud-eligible plugins.
- Existing compiler determinism and local semantic regression suite.

## Carry-state transition proposal

After human acceptance only:

```yaml
current_phase: phase_3
current_pr: null
last_accepted_pr: PR-G2
accepted_commit: <human-accepted-commit>
next_pr: PR-G3
accepted_artifacts:
  - context/closures/PR-G0.md
  - docs/retrofit/gcp_project_health/03_g0_characterization_v0_1.md
  - context/closures/PR-G1.md
  - context/closures/PR-G2.md
```

Human review accepted G2 and authorized G3 on 2026-07-29.
