"""Capture-processing boundary constants for Office Auto Lab.

Office Window captures raw human feedback and observes lifecycle surfaces.
Office Auto Lab owns semantic processing, reviewable candidates, and eventual
explicit reingest/apply operations.
"""

CAPTURE_LIFECYCLE_EVENTS = (
    "capture.created",
    "capture.transcribed",
    "capture.routed",
    "capture.artifact_candidate.created",
    "capture.reingest_candidate.created",
    "capture.approved",
    "capture.applied",
)

NON_MUTATING_CAPTURE_SURFACES = (
    "artifacts/latest/capture_lifecycle.json",
    "artifacts/latest/capture_lifecycle.md",
    "artifacts/latest/capture_lifecycle.csv",
    "artifacts/latest/capture_candidates.csv",
    "artifacts/latest/capture_candidates.md",
    "artifacts/latest/block_candidate_stubs.csv",
    "inbox/capture_artifacts/YYYY-MM-DD/*.md",
    "inbox/reingest_candidates/YYYY-MM-DD.jsonl",
)
