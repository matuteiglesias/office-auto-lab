# Frontier view v1

**Status:** first governed slice  
**Audience:** maintainers, Office/runtime engineers, Frontier renderer consumers  
**Owner:** `src/office_runtime/office/frontier_view.py`  
**Verified against:** live Control Tower `relationship_agenda_v1` contract observed 2026-09-22 and `tests/test_frontier_view_v1.py`

## Purpose

Materialize a read-only renderer contract from an existing governed judgment surface without creating a second source of truth.

The first adapter is deliberately narrow:

```text
Control Tower / relationship_agenda_v1
        ↓ read-only
frontier view compiler
        ↓
artifacts/frontier/v1/runs/<run-id>/frontier.view.v1.json
        ↓ last-known-good pointer
artifacts/frontier/v1/current.json
        ↓ optional atomic export
Event & Institutional Frontier renderer
```

## Why no frontier_decisions_v1 table yet

`relationship_agenda_v1` already owns the judgments required for this slice:

- state;
- priority;
- agenda item / next move;
- why it matters;
- trigger or wait condition;
- evidence;
- refresh time;
- resolution note.

Adding another decision table would duplicate live state.

A future curation table is justified only for source classes that lack an existing governed judgment layer.

## Source authority

The compiler preserves source-native `state` as `source_state`.

It derives only a presentation bucket:

| relationship_agenda_v1 state | Frontier bucket |
|---|---|
| READY | ACTION |
| OPEN | OPEN |
| WAIT | WAITING |
| HOLD | HOLD |
| DONE | CLOSED |
| DROP | CLOSED |
| anything else | OTHER + warning |

Bucket is projection-only. It is not written back to Sheets.

Closed items are excluded from the active published view by default. They remain in `relationship_agenda_v1` and can be included with `--include-closed`.

## View contract

Top level:

```text
schema_version = frontier.view.v1
view_id
generated_at
source
policy
counts
warnings
items[]
view_digest
```

A relationship agenda item includes:

```text
id
kind
bucket
source_state
priority
title
type
summary
why
next_move
trigger
origin_date
people[]
projects[]
institution
location
modality
event_at
deadline_at
evidence[]
source_updated_at
source_refs[]
relation_id?
resolution_note?
```

Optional event/institution fields are present but blank for this adapter so the renderer can accept future item kinds without forcing the source table to pretend it owns event facts.

## Publication safety

Compilation is run-scoped and staged.

A successful published run advances `artifacts/frontier/v1/current.json`. A failed read/compile cannot replace that pointer.

An optional renderer export is written atomically **after** the run succeeds.

This gives Frontier the same last-known-good discipline as Office v2 without coupling Frontier publication to the Office coherent-generation pointer.

## Commands

Compile and publish:

```bash
make frontier-view-v1
```

Publish and export a renderer copy:

```bash
FRONTIER_VIEW_EXPORT_PATH=/path/to/frontier.view.v1.json make frontier-view-v1
```

Shadow compile:

```bash
PYTHONPATH=src python3 src/office_runtime/scripts/compile_frontier_view_v1.py --shadow
```

Contract tests:

```bash
make frontier-view-v1-contracts
```

## Non-goals

This slice does not:

- mutate Control Tower;
- read CRM contact coordinates;
- ingest Google Calendar;
- infer relationship state;
- create relevance scores or expiry dates;
- merge duplicate people across systems;
- deploy the Frontier website;
- create a scheduler/timer.
