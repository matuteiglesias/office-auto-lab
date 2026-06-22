# Capture processing layer plan

## Boundary

```text
Office Window captures and observes.
Office Auto Lab processes and owns semantic integration.
Raw input is not system state.
Process produces reviewable events.
Apply is later explicit reingest.
```

`office-window` should remain the local/private capture membrane: it records row-linked voice events, writes append-only raw inbox files, and displays lifecycle status. `office-auto-lab` should be the canonical owner of capture processing, ontology, candidate artifacts, lifecycle merge output, and eventual explicit reingest/apply operations.

## Architecture recommendation

The next smallest integration layer should be a non-mutating lifecycle compiler in `office-auto-lab`:

1. Read append-only raw capture metadata from `inbox/human_feedback/YYYY-MM-DD.jsonl`.
2. Read future processing event logs from `inbox/capture_processing/YYYY-MM-DD.jsonl`.
3. Merge both streams by `event_id` into one stable lifecycle view.
4. Write compiled observer artifacts under `artifacts/latest/`.
5. Keep candidate artifacts and reingest proposals reviewable and append-only until a later explicit apply operation.

This keeps `office-window` out of semantic ownership while giving it one stable artifact to display.

## Where merged lifecycle reading should live

Merged lifecycle reading should live in both places only temporarily:

- `office-auto-lab` should be the canonical reader and producer of compiled lifecycle artifacts.
- `office-window` may keep its current raw inbox reader as a fallback while the compiled surface is introduced.
- After migration, `office-window` should prefer `artifacts/latest/capture_lifecycle.json` and only fall back to raw inbox files when that artifact is absent.

## Stable merged lifecycle output

Recommended outputs:

- `artifacts/latest/capture_lifecycle.json`: canonical machine-readable lifecycle state.
- `artifacts/latest/capture_lifecycle.md`: human-readable summary for debugging and review.
- `artifacts/latest/capture_lifecycle.csv`: optional tabular index for lightweight UI tables.

The JSON should be the contract. Markdown and CSV are derived convenience views.

Suggested `capture_lifecycle.json` shape:

```json
{
  "generated_at": "2026-06-22T00:00:00Z",
  "source_roots": {
    "raw_feedback": "inbox/human_feedback",
    "processing_events": "inbox/capture_processing",
    "candidate_artifacts": "inbox/capture_artifacts",
    "reingest_candidates": "inbox/reingest_candidates"
  },
  "captures": [
    {
      "event_id": "cap_fake_001",
      "created_at": "2026-06-22T00:00:00Z",
      "project_id": "FAKE-ALPHA",
      "project_title": "Example Payments Cleanup",
      "audio_path": "inbox/human_feedback_audio/2026-06-22/cap_fake_001.webm",
      "raw_metadata_path": "inbox/human_feedback/2026-06-22.jsonl",
      "latest_stage": "capture.routed",
      "latest_status": "ok",
      "transcript": {
        "status": "absent",
        "text": ""
      },
      "routing": {
        "status": "absent",
        "route": ""
      },
      "candidate_artifacts": [],
      "reingest_candidates": [],
      "approval": {
        "status": "not_requested"
      },
      "timeline": [
        {"stage": "capture.created", "ts": "2026-06-22T00:00:00Z", "status": "ok"}
      ]
    }
  ]
}
```

## Lifecycle merge behavior

Merge behavior should be deterministic and non-mutating:

1. Treat raw capture metadata as `capture.created` only.
2. Treat processing records as append-only lifecycle events keyed by `event_id`.
3. Do not infer approval or apply state from raw input.
4. Sort each capture timeline by timestamp, then by source file path and line number for ties.
5. Preserve unknown processing events in the timeline but do not promote them to known fields.
6. Mark missing audio, transcript, routing, candidates, or reingest proposals as `absent`, not errors.
7. Never write to `front_registry`, `carry_state`, queues, or Google Sheets.
8. If an event is malformed, include a lifecycle warning and continue compiling other captures.

Recommended lifecycle vocabulary:

```text
capture.created
capture.transcribed
capture.routed
capture.artifact_candidate.created
capture.reingest_candidate.created
capture.approved
capture.applied
```

## Proposed file layout

```text
src/office_runtime/capture/
  __init__.py
  lifecycle.py              # future canonical merge reader/writer
  process.py                # future dry-run and later AI-backed processors
  schemas/
    work_block_candidate_stub.schema.json
    reingest_candidate.schema.json

docs/
  capture_processing_layer.md

inbox/
  human_feedback/YYYY-MM-DD.jsonl                 # written by office-window
  human_feedback_audio/YYYY-MM-DD/<event_id>.webm # written by office-window
  capture_processing/YYYY-MM-DD.jsonl             # written by office-auto-lab processors
  capture_artifacts/YYYY-MM-DD/*.md               # reviewable candidates
  reingest_candidates/YYYY-MM-DD.jsonl            # reviewable reingest proposals

artifacts/latest/
  capture_lifecycle.json
  capture_lifecycle.md
  capture_lifecycle.csv
  capture_candidates.csv
  capture_candidates.md
  block_candidate_stubs.csv
```

## Proposed schemas

The initial schemas should be intentionally small and review-oriented:

- `work_block_candidate_stub`: a non-mutating suggestion that human feedback may imply a bounded work block attached to a project row.
- `reingest_candidate`: a non-mutating proposal to make a processed capture visible to Office Auto Lab after review.

A `work_block_candidate_stub` must include:

- `candidate_id`
- `type: work_block_candidate_stub`
- `source_event_id`
- `project_id`
- `project_title`
- `suggested_title`
- `suggested_mode`
- `rationale`
- `evidence_excerpt`
- `proposed_success_evidence`
- `expected_duration_min`
- `status: candidate`
- `requires_human_approval: true`
- `created_at`

A `reingest_candidate` must include:

- `reingest_candidate_id`
- `source_event_id`
- `candidate_type`
- `candidate_ref`
- `project_id`
- `project_title`
- `summary`
- `status: proposed`
- `requires_human_approval: true`
- `created_at`

## Proposed CLI command names

Recommended CLI shape:

```text
office capture lifecycle [--since YYYY-MM-DD] [--out artifacts/latest]
office capture process --event-id <event_id> --dry-run
office capture transcribe --event-id <event_id> --dry-run
office capture route --event-id <event_id> --dry-run
office capture candidate --event-id <event_id> --type work_block_candidate_stub --dry-run
office capture propose-reingest --event-id <event_id> --candidate-id <candidate_id> --dry-run
```

For the next PR, only `office capture lifecycle` should be implemented. The other commands can remain documented stubs until there is a real processor.

## How work block candidate stubs become visible

A row-linked capture can produce a `work_block_candidate_stub`, but that must not mutate a task, queue, or project row. It means only:

```text
Human feedback suggests a possible bounded work block attached to project X.
```

Visibility should happen through derived, non-mutating surfaces:

- Store the reviewable artifact in `inbox/capture_artifacts/YYYY-MM-DD/*.md`.
- Append a proposal to `inbox/reingest_candidates/YYYY-MM-DD.jsonl`.
- Compile `artifacts/latest/capture_candidates.csv` and `artifacts/latest/capture_candidates.md`.
- Compile `artifacts/latest/block_candidate_stubs.csv` for Office-visible review.

Later Office compile/staff processing can read these surfaces as candidate evidence only. Promotion into prepared blocks or tasks requires separate approval and explicit apply/reingest.

## Minimal next PR plan

Recommended next PR:

1. Add `src/office_runtime/capture/lifecycle.py` with a canonical merge reader.
2. Add `office capture lifecycle` CLI support.
3. Generate `capture_lifecycle.json` and `capture_lifecycle.md` under the configured latest artifact directory.
4. Add unit tests with synthetic inbox JSONL fixtures.
5. Keep schemas for `work_block_candidate_stub` and `reingest_candidate` checked into `src/office_runtime/capture/schemas/`.
6. Do not add OpenAI calls or candidate generation yet.

This is the smallest useful executable slice: it lets `office-window` switch from raw inbox merging to a compiled lifecycle artifact without changing processing ownership.

## Explicit non-goals

- No OpenAI calls.
- No API keys or provider configuration.
- No mutation of Google Sheets.
- No mutation of `carry_state`.
- No mutation of `front_registry`.
- No mutation of queue CSVs as a side effect of capture processing.
- No writes into `artifacts/latest` from `office-window`.
- No database, auth, or public deployment.
- No multi-agent framework.
- No automatic conversion of voice captures into tasks.

## Migration path for office-window

1. Keep writing raw audio and raw metadata exactly as today.
2. Keep current raw inbox lifecycle display as a fallback.
3. Add a preference order for display data:
   1. `artifacts/latest/capture_lifecycle.json`
   2. raw `inbox/human_feedback/*.jsonl` fallback
4. Display lifecycle sections from the compiled artifact when present:
   - lifecycle state
   - transcript
   - routing
   - candidate artifacts
   - work block stubs
   - reingest proposals
   - approval/archive status
5. Never let `office-window` write compiled lifecycle artifacts or apply reingest.
6. Add UI affordances later for approval/archive once `office-auto-lab` defines the explicit reingest/apply command.
