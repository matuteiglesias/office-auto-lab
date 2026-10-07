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
    adapters. Downstream code sees only canonical Office contract mappings plus
    bounded provider metadata suitable for run evidence.
    """

    def __init__(
        self,
        angle_producer: AngleProducer,
        editor_judge: EditorJudge,
        *,
        force_one_safe_candidate: bool = False,
    ) -> None:
        self._angle_producer = angle_producer
        self._editor_judge = editor_judge
        self._force_one_safe_candidate = force_one_safe_candidate

    def run_story(
        self,
        *,
        story: Mapping[str, Any] | Any,
        evidence_by_id: Mapping[str, Mapping[str, Any] | Any],
        context: Sequence[Mapping[str, Any] | Any] = (),
        policy: Mapping[str, Any] | Any,
        recent_themes: Sequence[Mapping[str, Any] | str | Any] = (),
        generated_at: str | None = None,
    ) -> IntelligenceResult:
        story_payload = _plain_mapping(story, "story")
        producer_request = {
            "story": story_payload,
            "evidence": _evidence_slice(story_payload, evidence_by_id),
            "context": [_plain_mapping(item, "context") for item in context],
            "policy": _plain_mapping(policy, "policy"),
            "recent_themes": [
                item if isinstance(item, str) else _plain_mapping(item, "recent_theme")
                for item in recent_themes
            ],
        }
        produced = self._angle_producer.produce(producer_request)
        angles = validate_angle_cards(
            story=story_payload,
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
            "story": story_payload,
            "evidence": _evidence_slice(story_payload, evidence_by_id),
            "angles": [dict(angle) for angle in angles],
            "context": [_plain_mapping(item, "context") for item in context],
            "policy": _plain_mapping(policy, "policy"),
            "recent_themes": [
                item if isinstance(item, str) else _plain_mapping(item, "recent_theme")
                for item in recent_themes
            ],
        }
        judged = self._editor_judge.judge(judge_request)
        judgments, candidates = validate_judgments(
            story=story_payload,
            angles=angles,
            raw_output=judged.payload,
            evidence_by_id=evidence_by_id,
            generated_at=generated_at,
            force_one_safe_candidate=self._force_one_safe_candidate,
        )
        return IntelligenceResult(
            angles=tuple(angles),
            judgments=tuple(judgments),
            candidates=tuple(candidates),
            provider_runs=(dict(produced.provider_run), dict(judged.provider_run)),
        )


def _evidence_slice(
    story: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any] | Any],
) -> list[dict[str, Any]]:
    refs = story.get("evidence_refs")
    if not isinstance(refs, list):
        return []
    return [
        _plain_mapping(evidence_by_id[ref], "evidence")
        for ref in refs
        if ref in evidence_by_id
    ]


def _plain_mapping(value: Mapping[str, Any] | Any, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, Mapping):
            return dict(payload)
    raise TypeError(f"{label} must be a mapping or expose to_dict()")
