from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

ANGLE_SCHEMA = "office_runtime.editorial.angle.v1"
CANDIDATE_SCHEMA = "office_runtime.editorial.candidate.v1"
ANGLE_TYPES = frozenset(
    {"lesson", "artifact", "question", "failure", "tradeoff", "measurement", "field_note", "synthesis"}
)
RISK_CLASSES = frozenset({"low", "medium", "high"})
DISPOSITIONS = frozenset({"stage", "hold", "drop"})
GATE_NAMES = ("disclosure_risk", "repetition_risk", "status_truth_risk")
QUALITY_NAMES = ("evidence", "specificity", "external_usefulness", "novelty", "professional_signal")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class IntelligenceContractError(ValueError):
    pass


def validate_angle_cards(
    *,
    story: Mapping[str, Any],
    raw_output: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    max_angles: int = 8,
) -> list[dict[str, Any]]:
    story_id = _string(story.get("story_id"), "story.story_id")
    story_refs = set(_string_list(story.get("evidence_refs"), "story.evidence_refs"))
    missing_story_refs = story_refs - set(evidence_by_id)
    if missing_story_refs:
        raise IntelligenceContractError(f"story references missing evidence: {sorted(missing_story_refs)}")

    values = raw_output.get("angles")
    if not isinstance(values, list):
        raise IntelligenceContractError("angle producer output requires an angles array")
    if len(values) > max_angles:
        raise IntelligenceContractError(f"angle producer exceeded bounded maximum of {max_angles}")

    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, value in enumerate(values):
        angle = _mapping(value, f"angles[{index}]")
        required = {
            "angle_id",
            "story_id",
            "angle_type",
            "claim",
            "tension_or_hook",
            "transferable_lesson",
            "evidence_refs",
            "audience",
            "career_signals",
            "why_interesting",
            "risk_class",
        }
        missing = required - set(angle)
        if missing:
            raise IntelligenceContractError(f"angle missing keys: {sorted(missing)}")
        if angle["story_id"] != story_id:
            raise IntelligenceContractError("angle story_id does not match input story")
        angle_id = _string(angle["angle_id"], "angle.angle_id")
        if angle_id in seen_ids:
            raise IntelligenceContractError(f"duplicate angle_id {angle_id!r}")
        seen_ids.add(angle_id)
        if angle["angle_type"] not in ANGLE_TYPES:
            raise IntelligenceContractError(f"invalid angle_type {angle['angle_type']!r}")
        if angle["risk_class"] not in RISK_CLASSES:
            raise IntelligenceContractError("invalid angle risk_class")

        refs = set(_string_list(angle["evidence_refs"], "angle.evidence_refs"))
        unknown = refs - set(evidence_by_id)
        if unknown:
            raise IntelligenceContractError(f"angle references unknown evidence: {sorted(unknown)}")
        outside_story = refs - story_refs
        if outside_story:
            raise IntelligenceContractError(
                f"angle references evidence outside its story lineage: {sorted(outside_story)}"
            )
        for key in ("claim", "tension_or_hook", "why_interesting"):
            _string(angle[key], f"angle.{key}")
        _string_list(angle["audience"], "angle.audience")
        _string_list(angle["career_signals"], "angle.career_signals")
        transferable = angle["transferable_lesson"]
        if not isinstance(transferable, str):
            raise IntelligenceContractError("angle.transferable_lesson must be a string")

        normalized = dict(angle)
        normalized["schema_version"] = ANGLE_SCHEMA
        normalized.setdefault("proof_object_refs", [])
        normalized.setdefault("required_status_wording", [])
        normalized.setdefault("counterpoint", "")
        normalized.setdefault("expiry_hint", None)
        validated.append(normalized)
    return validated


def validate_judgments(
    *,
    story: Mapping[str, Any],
    angles: Sequence[Mapping[str, Any]],
    raw_output: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    values = raw_output.get("decisions")
    if not isinstance(values, list):
        raise IntelligenceContractError("editor/judge output requires a decisions array")
    by_angle = {_string(angle.get("angle_id"), "angle.angle_id"): angle for angle in angles}
    if len(values) > len(by_angle):
        raise IntelligenceContractError("judge returned more decisions than supplied angles")

    now = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    judgments: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        decision = _mapping(value, f"decisions[{index}]")
        angle_id = _string(decision.get("angle_id"), "decision.angle_id")
        if angle_id not in by_angle:
            raise IntelligenceContractError(f"judge returned unknown angle_id {angle_id!r}")
        if angle_id in seen:
            raise IntelligenceContractError(f"judge returned duplicate decision for {angle_id!r}")
        seen.add(angle_id)
        angle = by_angle[angle_id]

        disposition = decision.get("machine_disposition")
        if disposition not in DISPOSITIONS:
            raise IntelligenceContractError("invalid machine_disposition")
        risk = decision.get("risk_class")
        if risk not in RISK_CLASSES:
            raise IntelligenceContractError("invalid judge risk_class")
        evidence_refs = _string_list(decision.get("evidence_refs"), "decision.evidence_refs")
        unknown = set(evidence_refs) - set(angle["evidence_refs"])
        if unknown:
            raise IntelligenceContractError(
                f"judge introduced unsupported evidence refs: {sorted(unknown)}"
            )
        quality = _quality(decision.get("quality"))
        gates = _gates(decision.get("gates"))

        reasons: list[str] = []
        story_eligibility = story.get("public_eligibility")
        if story_eligibility is False or (
            isinstance(story_eligibility, str)
            and story_eligibility.lower() in {"private", "restricted", "blocked", "ineligible"}
        ):
            gates["disclosure_risk"] = "FAIL"
            reasons.append("story_not_publicly_eligible")

        draft = decision.get("draft_text")
        if disposition == "stage":
            draft = _string(draft, "decision.draft_text")
        elif draft is not None and not isinstance(draft, str):
            raise IntelligenceContractError("decision.draft_text must be a string or null")

        required_wording = [
            word.lower()
            for word in angle.get("required_status_wording", [])
            if isinstance(word, str) and word.strip()
        ]
        draft_lower = (draft or "").lower()
        if disposition == "stage" and any(word not in draft_lower for word in required_wording):
            gates["status_truth_risk"] = "FAIL"
            reasons.append("required_status_wording_missing")

        failed_gates = [name for name in GATE_NAMES if gates[name] == "FAIL"]
        if failed_gates:
            disposition = "drop"
            reasons.extend(f"hard_gate:{name}" for name in failed_gates)
        elif risk == "high" and disposition == "stage":
            disposition = "hold"
            reasons.append("high_risk_requires_hold")

        normalized_decision = dict(decision)
        normalized_decision["machine_disposition"] = disposition
        normalized_decision["quality"] = quality
        normalized_decision["gates"] = gates
        normalized_decision["deterministic_rejection_reasons"] = sorted(set(reasons))
        judgments.append(normalized_decision)

        if disposition != "stage":
            continue

        family = decision.get("candidate_family", angle["angle_type"])
        if family not in ANGLE_TYPES:
            raise IntelligenceContractError("candidate_family must use the approved angle taxonomy")
        claim = _string(angle["claim"], "angle.claim")
        fingerprint = semantic_fingerprint(
            claim=claim,
            family=family,
            evidence_refs=evidence_refs,
        )
        candidate_id = _candidate_id(
            story_id=_string(story.get("story_id"), "story.story_id"),
            angle_id=angle_id,
            fingerprint=fingerprint,
        )
        work_refs = _work_refs(evidence_refs, evidence_by_id)
        if not work_refs:
            work_refs = list(evidence_refs)

        candidate = {
            "schema_version": CANDIDATE_SCHEMA,
            "candidate_id": candidate_id,
            "profile_id": "dev",
            "text": draft,
            "risk_class": risk,
            "evidence_refs": list(evidence_refs),
            "work_refs": work_refs,
            "story_id": story["story_id"],
            "angle_id": angle_id,
            "candidate_family": family,
            "semantic_fingerprint": fingerprint,
            "language": decision.get("language", "en"),
            "topic_tags": _optional_string_list(decision.get("topic_tags", []), "decision.topic_tags"),
            "career_signals": list(angle.get("career_signals", [])),
            "proof_object_refs": list(angle.get("proof_object_refs", [])),
            "freshness_class": story.get("freshness_class", "recent"),
            "generated_at": now,
            "expires_at": decision.get("expires_at", angle.get("expiry_hint")),
            "machine_disposition": "stage",
            "quality": quality,
            "gates": gates,
            "claim": claim,
            "source_event_refs": list(story.get("evidence_refs", evidence_refs)),
            "repository_refs": list(story.get("repository_refs", [])),
        }
        candidates.append(candidate)
    return judgments, candidates


def semantic_fingerprint(*, claim: str, family: str, evidence_refs: Sequence[str]) -> str:
    tokens = _TOKEN_RE.findall(claim.lower())
    normalized_claim = " ".join(tokens)
    primary_family = "|".join(sorted(_source_family(ref) for ref in evidence_refs))
    payload = json.dumps(
        [family.lower(), normalized_claim, primary_family],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return "sem:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _candidate_id(*, story_id: str, angle_id: str, fingerprint: str) -> str:
    raw = f"{story_id}|{angle_id}|{fingerprint}".encode("utf-8")
    return "cand:" + hashlib.sha256(raw).hexdigest()[:24]


def _source_family(ref: str) -> str:
    parts = ref.split(":")
    return ":".join(parts[:3]) if len(parts) >= 3 else ref


def _work_refs(
    evidence_refs: Sequence[str],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    refs: list[str] = []
    for evidence_id in evidence_refs:
        evidence = evidence_by_id.get(evidence_id, {})
        source_ref = evidence.get("source_ref")
        if isinstance(source_ref, str) and source_ref.strip():
            refs.append(source_ref.strip())
    return list(dict.fromkeys(refs))


def _quality(value: Any) -> dict[str, int]:
    mapping = _mapping(value, "decision.quality")
    quality: dict[str, int] = {}
    for name in QUALITY_NAMES:
        score = mapping.get(name)
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 4:
            raise IntelligenceContractError(f"quality.{name} must be an integer from 0 to 4")
        quality[name] = score
    return quality


def _gates(value: Any) -> dict[str, str]:
    mapping = _mapping(value, "decision.gates")
    gates: dict[str, str] = {}
    for name in GATE_NAMES:
        result = mapping.get(name)
        if result not in {"PASS", "FAIL"}:
            raise IntelligenceContractError(f"gates.{name} must be PASS or FAIL")
        gates[name] = result
    return gates


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IntelligenceContractError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IntelligenceContractError(f"{label} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise IntelligenceContractError(f"{label} must be a non-empty string array")
    return _optional_string_list(value, label)


def _optional_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise IntelligenceContractError(f"{label} must be a string array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise IntelligenceContractError(f"{label} must contain only non-empty strings")
    return [item.strip() for item in value]
