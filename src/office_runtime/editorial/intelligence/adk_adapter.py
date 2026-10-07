from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Literal, Mapping
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field

from .interfaces import EditorialIntelligence, ModelStageOutput

ANGLE_LENSES = "lesson, artifact, question, failure, tradeoff, measurement, field_note, synthesis"


class AngleCardModel(BaseModel):
    angle_id: str
    story_id: str
    angle_type: Literal[
        "lesson", "artifact", "question", "failure", "tradeoff", "measurement", "field_note", "synthesis"
    ]
    claim: str
    tension_or_hook: str
    transferable_lesson: str
    evidence_refs: list[str]
    audience: list[str]
    career_signals: list[str]
    why_interesting: str
    risk_class: Literal["low", "medium", "high"]
    proof_object_refs: list[str] = Field(default_factory=list)
    required_status_wording: list[str] = Field(default_factory=list)
    counterpoint: str = ""
    expiry_hint: str | None = None


class AngleOutputModel(BaseModel):
    angles: list[AngleCardModel] = Field(
        default_factory=list,
        description="Zero to eight defensible angles. Empty is correct when evidence is not interesting enough.",
    )


class QualityModel(BaseModel):
    evidence: int = Field(ge=0, le=4)
    specificity: int = Field(ge=0, le=4)
    external_usefulness: int = Field(ge=0, le=4)
    novelty: int = Field(ge=0, le=4)
    professional_signal: int = Field(ge=0, le=4)


class GatesModel(BaseModel):
    disclosure_risk: Literal["PASS", "FAIL"]
    repetition_risk: Literal["PASS", "FAIL"]
    status_truth_risk: Literal["PASS", "FAIL"]


class JudgmentModel(BaseModel):
    angle_id: str
    machine_disposition: Literal["stage", "hold", "drop"]
    rationale: str
    draft_text: str | None = None
    candidate_family: Literal[
        "lesson", "artifact", "question", "failure", "tradeoff", "measurement", "field_note", "synthesis"
    ]
    evidence_refs: list[str]
    risk_class: Literal["low", "medium", "high"]
    quality: QualityModel
    gates: GatesModel
    topic_tags: list[str] = Field(default_factory=list)
    language: str = "en"
    expires_at: str | None = None


class JudgeOutputModel(BaseModel):
    decisions: list[JudgmentModel] = Field(default_factory=list)


ANGLE_INSTRUCTION = f"""
You are the bounded angle producer for Office Editorial dev staging.

Input is one structured StoryCluster plus exact evidence, bounded project context,
the pinned editorial policy, and recent themes. Return structured angle cards only.
Zero angles is a normal and preferred result when the evidence is boring, trivial,
sensitive, too weak, or already exhausted.

Deliberately inspect these approved lenses: {ANGLE_LENSES}.

For every angle:
- state one concrete externally legible claim;
- cite only supplied evidence IDs;
- explain why someone outside the repository could care;
- identify a transferable mechanism/lesson when there is one;
- preserve status truth exactly (in-progress is not shipped, failed is not fixed);
- surface audience and professional/career signals without inventing technologies;
- include risk constraints and proof objects when relevant.

Do not rewrite PR titles, create changelog copy, invent outcomes, or force thought
leadership. Never expose private/security-sensitive details. Produce at most 8 angles.
""".strip()

JUDGE_INSTRUCTION = """
You are the independent editor/judge for Office Editorial dev staging. You did not
author the supplied angles. Judge them against the original story/evidence, policy,
bounded context, and recent themes.

Aggressively reject:
- unsupported claims or evidence mismatch;
- generic engineering platitudes;
- implementation announcements with no transferable value;
- repetition of recent candidate/post ideas;
- misleading status language;
- private, credential, security-sensitive, or otherwise restricted detail;
- fake certainty and forced thought leadership.

For survivors, draft concise X-ready copy and score exactly five 0-4 dimensions:
evidence, specificity, external_usefulness, novelty, professional_signal.

Record three independent hard gates as PASS/FAIL:
disclosure_risk, repetition_risk, status_truth_risk.
A failed hard gate must never be compensated by scores. Hold high-risk material.

Even for angles you would drop for soft editorial reasons, provide a concise draft_text
when the angle is public-eligible, low/medium risk, and all three hard gates PASS.
This allows an explicitly opt-in acceptance fallback to retain one row for human REVIEW
without overriding safety gates. Keep scores and rationale honest; do not stage unsafe copy.

Use only supplied angle/evidence IDs. In normal operation it is correct to drop every angle.
""".strip()


class _AdkStructuredStage:
    def __init__(
        self,
        *,
        stage: str,
        model: str,
        instruction: str,
        output_schema: type[BaseModel],
    ) -> None:
        self.stage = stage
        self.model = model
        self._agent = LlmAgent(
            name=f"editorial_{stage}",
            model=model,
            instruction=instruction,
            output_schema=output_schema,
            include_contents="none",
        )

    def invoke(self, request: Mapping[str, Any]) -> ModelStageOutput:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._invoke_async(request))
        raise RuntimeError(
            "ADK editorial sync adapter cannot run inside an active asyncio loop; "
            "call it from a worker thread or add an async Office adapter."
        )

    async def _invoke_async(self, request: Mapping[str, Any]) -> ModelStageOutput:
        app_name = f"office_editorial_{self.stage}"
        runner = InMemoryRunner(agent=self._agent, app_name=app_name)
        user_id = "office-editorial"
        session_id = f"{self.stage}-{uuid4().hex}"
        await runner.session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=json.dumps(request, sort_keys=True, ensure_ascii=False))],
        )
        started = time.monotonic()
        final_text: str | None = None
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = "".join(part.text or "" for part in event.content.parts)
        duration_ms = round((time.monotonic() - started) * 1000)
        if not final_text:
            raise RuntimeError(f"ADK {self.stage} returned no final structured response")
        payload = json.loads(final_text)
        if not isinstance(payload, Mapping):
            raise RuntimeError(f"ADK {self.stage} final response was not a JSON object")
        return ModelStageOutput(
            payload=dict(payload),
            provider_run={
                "stage": self.stage,
                "provider": "google-adk",
                "model": self.model,
                "duration_ms": duration_ms,
            },
        )


class AdkAngleProducer:
    def __init__(self, *, model: str) -> None:
        self._stage = _AdkStructuredStage(
            stage="angle_producer",
            model=model,
            instruction=ANGLE_INSTRUCTION,
            output_schema=AngleOutputModel,
        )

    def produce(self, request: Mapping[str, Any]) -> ModelStageOutput:
        return self._stage.invoke(request)


class AdkEditorJudge:
    def __init__(self, *, model: str) -> None:
        self._stage = _AdkStructuredStage(
            stage="editor_judge",
            model=model,
            instruction=JUDGE_INSTRUCTION,
            output_schema=JudgeOutputModel,
        )

    def judge(self, request: Mapping[str, Any]) -> ModelStageOutput:
        return self._stage.invoke(request)


def build_adk_editorial_intelligence(
    *,
    angle_model: str,
    judge_model: str,
    force_one_safe_candidate: bool = False,
) -> EditorialIntelligence:
    """Build two independent ADK LLM stages behind the local Office seam."""

    return EditorialIntelligence(
        angle_producer=AdkAngleProducer(model=angle_model),
        editor_judge=AdkEditorJudge(model=judge_model),
        force_one_safe_candidate=force_one_safe_candidate,
    )
