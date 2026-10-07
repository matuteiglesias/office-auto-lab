from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from office_runtime.editorial.contracts import (
    ANGLE_SCHEMA,
    CANDIDATE_SCHEMA,
    ANGLE_TYPES,
    CANDIDATE_FAMILIES,
    QUALITY_DIMENSIONS,
    RISK_CLASSES,
    ContractError,
    validate_angle,
    validate_dev_candidate,
    validate_story_cluster,
)

DISPOSITIONS = frozenset({"stage", "hold", "drop"})
GATE_NAMES = ("disclosure_risk", "repetition_risk", "status_truth_risk")
QUALITY_NAMES = QUALITY_DIMENSIONS
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_COMPLETION_RE = re.compile(
    r"\b(shipped|merged|released|launched|completed|deployed|in production|went live)\b",
    re.IGNORECASE,
)
_COMPLETED_STATUSES = frozenset({"completed", "merged", "released"})
_NONCOMPLETED_STATUSES = frozenset(
    {"in_progress", "failed", "waiting", "dropped", "superseded", "unknown"}
)
_DEV_PROFILE = {"profile_id": "dev", "strategy": "dev_projection"}


class IntelligenceContractError(ValueError):
    pass


def validate_angle_cards(
    *,
    story: Mapping[str, Any] | Any,
    raw_output: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any] | Any],
    max_angles: int = 8,
) -> list[dict[str, Any]]:
    story_payload = _canonical_story(story)
    story_id = story_payload["story_id"]
    story_refs = set(story_payload["evidence_refs"])
    missing_story_refs = story_refs - set(evidence_by_id)
    if missing_story_refs:
        raise IntelligenceContractError(
            f"story references missing evidence: {sorted(missing_story_refs)}"
        )

    values = raw_output.get("angles")
    if not isinstance(values, list):
        raise IntelligenceContractError("angle producer output requires an angles array")
    if len(values) > max_angles:
        raise IntelligenceContractError(
            f"angle producer exceeded bounded maximum of {max_angles}"
        )

    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, value in enumerate(values):
        angle = dict(_mapping(value, f"angles[{index}]"))
        angle["schema_version"] = ANGLE_SCHEMA
        angle.setdefault("proof_object_refs", [])
        angle.setdefault("required_status_wording", [])
        angle.setdefault("counterpoint", None)
        angle.setdefault("expiry_hint", None)
        try:
            normalized = validate_angle(angle)
        except ContractError as exc:
            raise IntelligenceContractError(str(exc)) from exc

        if normalized["story_id"] != story_id:
            raise IntelligenceContractError("angle story_id does not match input story")
        angle_id = normalized["angle_id"]
        if angle_id in seen_ids:
            raise IntelligenceContractError(f"duplicate angle_id {angle_id!r}")
        seen_ids.add(angle_id)

        refs = set(normalized["evidence_refs"])
        unknown = refs - set(evidence_by_id)
        if unknown:
            raise IntelligenceContractError(
                f"angle references unknown evidence: {sorted(unknown)}"
            )
        outside_story = refs - story_refs
        if outside_story:
            raise IntelligenceContractError(
                f"angle references evidence outside its story lineage: {sorted(outside_story)}"
            )
        validated.append(normalized)
    return validated


def validate_judgments(
    *,
    story: Mapping[str, Any] | Any,
    angles: Sequence[Mapping[str, Any]],
    raw_output: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any] | Any],
    generated_at: str | None = None,
    force_one_safe_candidate: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    story_payload = _canonical_story(story)
    values = raw_output.get("decisions")
    if not isinstance(values, list):
        raise IntelligenceContractError("editor/judge output requires a decisions array")

    by_angle: dict[str, dict[str, Any]] = {}
    for raw_angle in angles:
        try:
            angle = validate_angle(dict(raw_angle))
        except ContractError as exc:
            raise IntelligenceContractError(str(exc)) from exc
        by_angle[angle["angle_id"]] = angle
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
        outside_angle = set(evidence_refs) - set(angle["evidence_refs"])
        if outside_angle:
            raise IntelligenceContractError(
                f"judge introduced unsupported evidence refs: {sorted(outside_angle)}"
            )
        unknown = set(evidence_refs) - set(evidence_by_id)
        if unknown:
            raise IntelligenceContractError(
                f"judge references missing evidence: {sorted(unknown)}"
            )

        quality = _quality(decision.get("quality"))
        gates = _gates(decision.get("gates"))
        reasons: list[str] = []

        if story_payload["public_eligibility"] != "eligible":
            gates["disclosure_risk"] = "fail"
            reasons.append("story_not_publicly_eligible")

        draft = decision.get("draft_text")
        if disposition == "stage":
            draft = _string(draft, "decision.draft_text")
        elif draft is not None and not isinstance(draft, str):
            raise IntelligenceContractError("decision.draft_text must be a string or null")

        statuses = {
            _evidence_payload(evidence_by_id[ref]).get("status")
            for ref in evidence_refs
            if ref in evidence_by_id
        }
        if disposition == "stage" and _status_truth_violation(
            draft or "",
            statuses=statuses,
            required_wording=angle.get("required_status_wording", []),
        ):
            gates["status_truth_risk"] = "fail"
            reasons.append("deterministic_status_truth_violation")

        failed_gates = [name for name in GATE_NAMES if gates[name] == "fail"]
        if failed_gates:
            disposition = "drop"
            reasons.extend(f"hard_gate:{name}" for name in failed_gates)
        elif risk == "high" and disposition == "stage":
            disposition = "hold"
            reasons.append("high_risk_requires_hold")

        expiry = decision.get("expires_at") or angle.get("expiry_hint")
        if (
            disposition == "stage"
            and story_payload["freshness_class"] == "timely"
            and not _nonempty_string(expiry)
        ):
            disposition = "drop"
            reasons.append("timely_candidate_missing_expiry")

        normalized_decision = dict(decision)
        normalized_decision["machine_disposition"] = disposition
        normalized_decision["quality"] = quality
        normalized_decision["gates"] = dict(gates)
        normalized_decision["deterministic_rejection_reasons"] = sorted(set(reasons))
        judgments.append(normalized_decision)

        if disposition != "stage":
            continue

        family = decision.get("candidate_family", angle["angle_type"])
        if family not in ANGLE_TYPES:
            raise IntelligenceContractError(
                "candidate_family must use the approved angle taxonomy"
            )
        canonical_family = family.upper()
        if canonical_family not in CANDIDATE_FAMILIES:
            raise IntelligenceContractError("candidate_family is not contract-supported")

        claim = angle["claim"]
        fingerprint = semantic_fingerprint(
            claim=claim,
            family=family,
            evidence_refs=evidence_refs,
        )
        candidate_id = _candidate_id(
            story_id=story_payload["story_id"],
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
            "story_id": story_payload["story_id"],
            "angle_id": angle_id,
            "candidate_family": canonical_family,
            "semantic_fingerprint": fingerprint,
            "language": decision.get("language", "en"),
            "topic_tags": _optional_string_list(
                decision.get("topic_tags", []),
                "decision.topic_tags",
            ),
            "career_signals": list(angle.get("career_signals", [])),
            "proof_object_refs": list(angle.get("proof_object_refs", [])),
            "freshness_class": story_payload["freshness_class"],
            "generated_at": now,
            "expires_at": expiry,
            "machine_disposition": "stage",
            "quality": quality,
            "disclosure_risk": gates["disclosure_risk"],
            "repetition_risk": gates["repetition_risk"],
            "status_truth_risk": gates["status_truth_risk"],
            "claim": claim,
            "source_event_refs": list(story_payload["evidence_refs"]),
            "repository_refs": list(story_payload["repository_refs"]),
        }
        try:
            candidate = validate_dev_candidate(candidate, _DEV_PROFILE)
        except ContractError as exc:
            raise IntelligenceContractError(str(exc)) from exc
        candidates.append(candidate)
    if force_one_safe_candidate and not candidates:
        forced = _force_one_safe_candidate(
            story_payload=story_payload,
            by_angle=by_angle,
            judgments=judgments,
            evidence_by_id=evidence_by_id,
            generated_at=now,
        )
        if forced is not None:
            forced_angle_id, forced_candidate = forced
            warning = (
                "FORCED_PIPELINE_ACCEPTANCE: no candidate survived the judge's soft editorial "
                "selection; one hard-gate-safe candidate was retained only to exercise the "
                "staging pipeline and requires human REVIEW."
            )
            for judgment in judgments:
                if judgment.get("angle_id") == forced_angle_id:
                    judgment["machine_disposition"] = "stage"
                    judgment["forced_pipeline_acceptance"] = True
                    judgment["editorial_warning"] = warning
                    reasons = list(judgment.get("deterministic_rejection_reasons", []))
                    reasons.append("forced_pipeline_acceptance_soft_override")
                    judgment["deterministic_rejection_reasons"] = sorted(set(reasons))
                    break
            forced_candidate["forced_pipeline_acceptance"] = True
            forced_candidate["editorial_warning"] = warning
            candidates.append(forced_candidate)

    return judgments, candidates


def _force_one_safe_candidate(
    *,
    story_payload: Mapping[str, Any],
    by_angle: Mapping[str, Mapping[str, Any]],
    judgments: Sequence[Mapping[str, Any]],
    evidence_by_id: Mapping[str, Mapping[str, Any] | Any],
    generated_at: str,
) -> tuple[str, dict[str, Any]] | None:
    if story_payload.get("public_eligibility") != "eligible":
        return None

    eligible: list[tuple[tuple[int, int, str], Mapping[str, Any], Mapping[str, Any], str]] = []
    for judgment in judgments:
        angle_id = judgment.get("angle_id")
        angle = by_angle.get(str(angle_id))
        if angle is None:
            continue
        gates = judgment.get("gates")
        if not isinstance(gates, Mapping) or any(gates.get(name) != "pass" for name in GATE_NAMES):
            continue
        risk = judgment.get("risk_class")
        if risk not in {"low", "medium"}:
            continue

        evidence_refs = judgment.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            continue
        if not set(evidence_refs).issubset(set(angle.get("evidence_refs", []))):
            continue
        if any(ref not in evidence_by_id for ref in evidence_refs):
            continue

        draft = judgment.get("draft_text")
        if not isinstance(draft, str) or not draft.strip():
            claim = angle.get("claim")
            lesson = angle.get("transferable_lesson")
            pieces = [
                item.strip()
                for item in (claim, lesson)
                if isinstance(item, str) and item.strip()
            ]
            draft = " ".join(dict.fromkeys(pieces)).strip()
        if not draft:
            continue

        statuses = {
            _evidence_payload(evidence_by_id[ref]).get("status")
            for ref in evidence_refs
            if ref in evidence_by_id
        }
        if _status_truth_violation(
            draft,
            statuses=statuses,
            required_wording=angle.get("required_status_wording", []),
        ):
            continue

        expiry = judgment.get("expires_at") or angle.get("expiry_hint")
        if story_payload.get("freshness_class") == "timely" and not _nonempty_string(expiry):
            expiry = _forced_acceptance_expiry(generated_at)
        if story_payload.get("freshness_class") == "timely" and not _nonempty_string(expiry):
            continue

        quality = judgment.get("quality")
        if not isinstance(quality, Mapping):
            continue
        quality_total = sum(
            int(quality.get(name, 0))
            for name in QUALITY_NAMES
            if isinstance(quality.get(name, 0), int)
        )
        draft_bonus = 1 if isinstance(judgment.get("draft_text"), str) and judgment.get("draft_text", "").strip() else 0
        risk_rank = 1 if risk == "low" else 0
        eligible.append(((quality_total, draft_bonus + risk_rank, str(angle_id)), judgment, angle, draft))

    if not eligible:
        return None

    _, decision, angle, draft = sorted(eligible, key=lambda item: item[0], reverse=True)[0]
    family = decision.get("candidate_family", angle["angle_type"])
    if family not in ANGLE_TYPES:
        return None
    canonical_family = str(family).upper()
    if canonical_family not in CANDIDATE_FAMILIES:
        return None

    evidence_refs = list(decision["evidence_refs"])
    claim = str(angle["claim"])
    fingerprint = semantic_fingerprint(
        claim=claim,
        family=str(family),
        evidence_refs=evidence_refs,
    )
    candidate_id = _candidate_id(
        story_id=str(story_payload["story_id"]),
        fingerprint=fingerprint,
    )
    work_refs = _work_refs(evidence_refs, evidence_by_id) or evidence_refs
    expiry = decision.get("expires_at") or angle.get("expiry_hint")
    if story_payload.get("freshness_class") == "timely" and not _nonempty_string(expiry):
        expiry = _forced_acceptance_expiry(generated_at)
    candidate = {
        "schema_version": CANDIDATE_SCHEMA,
        "candidate_id": candidate_id,
        "profile_id": "dev",
        "text": draft,
        "risk_class": decision["risk_class"],
        "evidence_refs": evidence_refs,
        "work_refs": work_refs,
        "story_id": story_payload["story_id"],
        "angle_id": angle["angle_id"],
        "candidate_family": canonical_family,
        "semantic_fingerprint": fingerprint,
        "language": decision.get("language", "en"),
        "topic_tags": _optional_string_list(
            decision.get("topic_tags", []),
            "decision.topic_tags",
        ),
        "career_signals": list(angle.get("career_signals", [])),
        "proof_object_refs": list(angle.get("proof_object_refs", [])),
        "freshness_class": story_payload["freshness_class"],
        "generated_at": generated_at,
        "expires_at": expiry,
        "machine_disposition": "stage",
        "quality": dict(decision["quality"]),
        "disclosure_risk": "pass",
        "repetition_risk": "pass",
        "status_truth_risk": "pass",
        "claim": claim,
        "source_event_refs": list(story_payload["evidence_refs"]),
        "repository_refs": list(story_payload["repository_refs"]),
    }
    try:
        candidate = validate_dev_candidate(candidate, _DEV_PROFILE)
    except ContractError:
        return None
    return str(angle["angle_id"]), candidate


def _forced_acceptance_expiry(generated_at: str) -> str:
    """Give the opt-in acceptance fallback a bounded, explicit timely expiry."""

    parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    return (parsed + timedelta(days=1)).isoformat().replace("+00:00", "Z")


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


def _candidate_id(*, story_id: str, fingerprint: str) -> str:
    raw = f"{story_id}|{fingerprint}".encode("utf-8")
    return "cand:" + hashlib.sha256(raw).hexdigest()[:24]


def _canonical_story(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload = _object_payload(value, "story")
    try:
        return validate_story_cluster(payload)
    except ContractError as exc:
        raise IntelligenceContractError(str(exc)) from exc


def _evidence_payload(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    return _object_payload(value, "evidence")


def _object_payload(value: Mapping[str, Any] | Any, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, Mapping):
            return dict(payload)
    raise IntelligenceContractError(f"{label} must be a mapping or expose to_dict()")


def _source_family(ref: str) -> str:
    parts = ref.split(":")
    return ":".join(parts[:3]) if len(parts) >= 3 else ref


def _work_refs(
    evidence_refs: Sequence[str],
    evidence_by_id: Mapping[str, Mapping[str, Any] | Any],
) -> list[str]:
    refs: list[str] = []
    for evidence_id in evidence_refs:
        evidence = _evidence_payload(evidence_by_id.get(evidence_id, {}))
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
            raise IntelligenceContractError(
                f"quality.{name} must be an integer from 0 to 4"
            )
        quality[name] = score
    return quality


def _gates(value: Any) -> dict[str, str]:
    mapping = _mapping(value, "decision.gates")
    gates: dict[str, str] = {}
    for name in GATE_NAMES:
        result = mapping.get(name)
        if not isinstance(result, str):
            raise IntelligenceContractError(f"gates.{name} must be PASS or FAIL")
        normalized = result.strip().lower()
        if normalized not in {"pass", "fail", "hold", "unknown"}:
            raise IntelligenceContractError(
                f"gates.{name} must be PASS/FAIL or a canonical gate state"
            )
        gates[name] = normalized
    return gates


def _status_truth_violation(
    draft: str,
    *,
    statuses: set[Any],
    required_wording: Sequence[Any],
) -> bool:
    normalized_statuses = {item for item in statuses if isinstance(item, str)}
    if (
        normalized_statuses & _NONCOMPLETED_STATUSES
        and not normalized_statuses & _COMPLETED_STATUSES
        and _COMPLETION_RE.search(draft)
    ):
        return True

    lowered = draft.lower()
    for phrase in required_wording:
        if not isinstance(phrase, str) or not phrase.strip():
            continue
        words = phrase.lower().split()
        if 1 <= len(words) <= 4 and phrase.lower() not in lowered:
            return True
    return False


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


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
