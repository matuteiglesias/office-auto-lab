# GCP Project Health Retrofit — Starting Context v0.1

## Repository

`matuteiglesias/office-auto-lab`

## Product slice

The retrofit concerns only:

```text
src/office_runtime/ops/repo_health/
```

plus the minimal CLI, tests, configuration, container, and `infra/gcp` surfaces required to operate it.

The broader office/capture/staff runtime is unrelated and must not be migrated.

## Current components to inspect first

- `src/office_runtime/ops/repo_health/policy.py`
- `src/office_runtime/ops/repo_health/sheets.py`
- `src/office_runtime/ops/repo_health/runner.py`
- `src/office_runtime/ops/repo_health/frontier_export.py`
- `src/office_runtime/ops/repo_health/plugin_loader.py`
- `src/office_runtime/ops/repo_health/plugins/base.py`
- `src/office_runtime/ops/repo_health/plugins/git_activity_plugin.py`
- other plugin modules under `plugins/`
- `src/office_runtime/ops/repo_health/compiler/generate.py`
- compiler IR/classification/spec files
- `src/office_runtime/cli.py`
- `Makefile`
- existing fixtures under `fixtures/`

## Existing product semantics to preserve

1. Policy determines eligible intents.
2. Plugins return compact status, message, bucket, evidence, and metadata.
3. Unknown/malformed plugin output becomes a system error.
4. Findings are normalized into a frontier.
5. The compiler deterministically transforms issues into bounded work blocks.
6. Work blocks include timeboxes, expected evidence, and stop rules.
7. Cloud infrastructure does not own project-health meaning.

## Findings to verify in PR-G0

These are hypotheses from prior inspection, not permission to patch them before characterization:

- due-state calculation and scheduled intent may be conflated;
- no-write may not guard every writeback;
- normalized rows may discard useful evidence/meta;
- plugins are discovered dynamically;
- current credentials rely on a service-account file;
- local plugins assume `repo_path` and shell/git availability.

## Initial remote plugin decision

Supported in v0.1:

- commit recency/activity using GitHub metadata;
- repository hygiene/runbook presence through bounded content/path reads.

Unsupported in v0.1:

- dirty worktree;
- local ahead/behind;
- `make smoke`;
- generated artifact inspection;
- arbitrary repository commands;
- private repository discovery outside an allowlist.

## Human gates

The human reviewer must approve:

- G0 characterization conclusions;
- G1 semantic fixes;
- G2 supported remote fact vocabulary;
- G3 run-bundle schema;
- G5 IAM and cost boundary;
- G6 final market claim.

## First one-hour Codex task

Execute `PR-G0` only.

A good G0 is more valuable than a rushed Dockerfile. It leaves the next task with proven facts, focused tests, and a settled cloud capability boundary.
