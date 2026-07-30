# Capture owner guide

**Status:** canonical
**Audience:** contributors and agents changing capture lifecycle or processing
**Owner:** `src/office_runtime/capture/`
**Verified against:** `cda8b286cc5db3c840d7f4dad143d62497f18a63`

## Purpose and non-goals

Capture owns semantic processing after raw human-feedback capture: audio
transcription, routing, reviewable artifact/reingest proposals, and a merged
lifecycle view. It does not own raw capture creation, human approval decisions,
or an apply path into Office registries or Sheets.

## Source paths

| Path | Responsibility |
|---|---|
| `capture/transcription.py` | Audio resolution/validation, transcription, dated event append |
| `capture/processing.py` | Structured route, artifact, reingest proposal, staged processing |
| `capture/lifecycle.py` | Stable merge, warnings, review state, compiled observer artifacts |
| `capture/schemas/` | Strict work-block and reingest candidate contracts |
| `capture/__init__.py` | Boundary constants and non-mutating surface inventory |
| `cli.py` | Capture command and option wiring |

## Inputs and outputs

Raw metadata lives in dated `inbox/human_feedback/*.jsonl`; audio resolves below
the configured audio root. Derived events append to dated
`inbox/capture_processing/*.jsonl`. Lifecycle compilation writes
`capture_lifecycle.{json,csv,md}`, `capture_candidates.{json,md}`, and
`block_candidate_stubs.{csv,md}` to the selected output directory. Candidate
schemas require human approval and candidate/proposed status.

## Canonical command surface

The CLI exposes `capture lifecycle`, `transcribe`, `transcribe-pending`, `route`,
`artifactize`, `propose-reingest`, and the staged `process` command. Processing
commands support `--dry-run`; stage commands support `--force`. This is a command
map, not the future operational procedure. Exact flags are in the
[inventory](../documentation_inventory.md#command-surface).

## Invariants

- Raw and derived streams are append-only inputs to lifecycle compilation.
- Event identity connects raw captures to derived stages; stable source order
  breaks timestamp ties.
- Missing stages are absence, while malformed records become warnings so other
  captures can still compile.
- A completed stage is skipped unless forced.
- Dry-run does not append a derived event, although model-backed commands may
  still make an API request.
- Candidate output is reviewable and non-mutating; no capture command applies it
  to Office or Sheets.
- Audio paths must remain inside the configured root and pass type/size checks
  before transcription.

## Dependencies and tests

Lifecycle compilation is local. Transcription/processing require the OpenAI
client and credentials, with configurable model names and audio size/root.
`test_capture_lifecycle.py`, `test_capture_transcription.py`, and
`test_capture_processing.py` cover merge/artifacts, path and size denial,
duplicates, strict schemas, failure events, and staged processing. At the
inspected commit, lifecycle and transcription tests pass, while one realistic
processing ontology test has known target-surface failures; do not describe the
entire component as locally validated.

## Failure modes

Unsupported, oversized, missing, escaping, or ambiguous audio fails before the
API call and is represented as a failure result/event where defined. Model/API
or strict-output validation errors append failure events unless dry-run prevents
the write. Unknown lifecycle events are preserved but not promoted into known
state. Invalid JSONL records produce warnings rather than aborting all captures.
Forced reruns intentionally create another derived event and must be used with
review awareness.

## Extension points

Add lifecycle vocabulary and merge projection in `lifecycle.py`; add a
model-backed stage through the strict structured-output helpers in
`processing.py`; version or extend schemas without weakening recursive strictness.
Any apply operation would cross the current non-mutation boundary and requires a
separate design, authorization, tests, and trust-boundary update.
