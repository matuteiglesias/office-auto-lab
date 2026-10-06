from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .validation import validate_angle_cards, validate_judgments


@dataclass(frozen=True)
class ModelStageOutput:
    """Provider-neutral result from one bounded model stage."""

    payload: Mapping[str, Any]
    provider_run: Mapping[str, Any]


class AngleProducer(Protocol):
    def produce(self, request: Mapping[str, Any]) -> ModelStageOutput:
        """Return zero or more raw structured angles."""


class EditorJudge(Protocol):
    def judge(self, request: Mapping[str, Any]) -> ModelStageOutput:
        """Return structured independent editorial judgments."""


@dataclass(frozen=True)
class IntelligenceResult:
    angles: tuple[Mapping[str, Any], ...]
    judgments: tuple[Mapping[str, Any], ...]
    candidates: tuple[Mapping[str, Any], ...]
    provider_runs: tuple[Mapping[str, Any], ...]


class EditorialIntelligence:
    """Local Office interface around two independent model stages.

    ADK objects and provider-specific response types terminate at the producer/judge
    adapters. Downstream code sees only Office-shaped mappings plus bounded provider
    metadata suitable for run evidence.
    """

    def __init__(self, angle_producer: AngleProducer, editor_judge: EditorJudge) -> None:
        self._angle_producer = angle_producer
        self._editor_judge = editor_judge

    def run_story(
        self,
        *,
        story: Mapping[str, Any],
        evidence_by_id: Mapping[str, Mapping[str, Any]],
        context: Sequence[Mapping[str, Any]] = (),
        policy: Mapping[str, Any],
        recent_themes: Sequence[Mapping[str, Any] | str] = (),
        generated_at: str | None = None,
    ) -> IntelligenceResult:
        producer_request = {
            "story": dict(story),
            "evidence": _evidence_slice(story, evidence_by_id),
            "context": [dict(item) for item in context],
            "policy": dict(policy),
            "recent_themes": [dict(item) if isinstance(item, Mapping) else item for item in recent_themes],
        }
        produced = self._angle_producer.produce(producer_request)
        angles = validate_angle_cards(
            story=story,
            raw_output=produced.payload,
            evidence_by_id=evidence_by_id,
        )
        if not angles:
            return IntelligenceResult(
                angles=(),
                judgments=(),
                candidates=(),
                provider_runs=(dict(produced.provider_run),),
            )

        judge_request = {
            "story": dict(story),
            "evidence": _evidence_slice(story, evidence_by_id),
            "angles": [dict(angle) for angle in angles],
            "context": [dict(item) for item in context],
            "policy": dict(policy),
            "recent_themes": [dict(item) if isinstance(item, Mapping) else item for item in recent_themes],
        }
        judged = self._editor_judge.judge(judge_request)
        judgments, candidates = validate_judgments(
            story=story,
            angles=angles,
            raw_output=judged.payload,
            evidence_by_id=evidence_by_id,
            generated_at=generated_at,
        )
        return IntelligenceResult(
            angles=tuple(angles),
            judgments=tuple(judgments),
            candidates=tuple(candidates),
            provider_runs=(dict(produced.provider_run), dict(judged.provider_run)),
        )


def _evidence_slice(
    story: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    refs = story.get("evidence_refs")
    if not isinstance(refs, list):
        return []
    return [dict(evidence_by_id[ref]) for ref in refs if ref in evidence_by_id]
