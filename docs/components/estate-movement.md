# Estate Movement Digest

**Status:** canonical producer guide
**Audience:** operators, maintainers, and agents
**Owner:** `src/office_runtime/estate_movement.py`
**Producer:** `ops.estate-movement@1`
**Verified against:** `tests/test_estate_movement.py`

## Purpose

Produce a small, local, read-only movement digest for a caller-selected estate
scope. It answers what changed since the prior digest through stable evidence
IDs; it does not re-summarize the estate or change any repository's lifecycle,
authority, readiness, or priority.

Inputs are bounded local Git commits, safe materialization file metadata,
run-event receipts, and optional `projects` authority-file metadata. No source
contents, credentials, remote APIs, fetches, pulls, or repository commands are
executed.

## Command

```bash
make estate-movement \
  ROOTS="/path/to/repos /path/to/work" \
  START=2026-09-12 \
  END=2026-09-13 \
  DIGEST_ID=2026-09-13-evening \
  CONTROL_PLANE=/path/to/projects
```

To make a true delta, add the exact prior manifest:

```bash
PREVIOUS_MANIFEST=artifacts/estate-movement/2026-09-12-evening/manifest.json
```

Outputs are local ignored artifacts:

```text
artifacts/estate-movement/<digest-id>/
  <digest-id>.md
  evidence.jsonl
  manifest.json
```

## Sections and semantics

`NEW`, `CLOSED`, `BECAME TRUE`, `FAILED`, `AUTHORITY CHANGED`, `RECOVERY
IMPROVED`, `STILL BLOCKED`, `COMPOUNDING CROSSOVERS`, and `NEXT PULL` are
evidence labels. A commit subject, artifact timestamp, or receipt can appear in
more than one label when it supports multiple observations. `NEXT PULL` is a
small evidence-backed review queue, never an automatic action queue.

The first digest is a baseline. Later digests compare current stable evidence
IDs against `previous_manifest`; evidence already present there is omitted from
the narrative delta but retained in the new manifest's accounting.

## Safety

- Roots, dates, depth, output, and optional control plane are explicit.
- Git inspection uses only local `log` and `show` metadata.
- Materialization inspection is restricted to named derived-output directories
  and safe file extensions; source bodies are never copied.
- Run receipts retain only timestamp, module, run ID, status, and event label.
- Generated output is ignored because it may describe private local work.
