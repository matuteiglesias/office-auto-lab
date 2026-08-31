from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

PROFILE_SCHEMA = "office_runtime.editorial.profile.v1"
CANDIDATE_SCHEMA = "office_runtime.editorial.candidate.v1"
SUPPORTED_STRATEGIES = frozenset({"dev_projection", "argentina_econ"})
ARGENTINA_ECON_RELATIONS = frozenset(
    {
        "supports",
        "contextualizes",
        "complicates",
        "contradicts",
        "historicizes",
        "cannot_adjudicate",
    }
)
RISK_CLASSES = frozenset({"low", "medium", "high"})


class ContractError(ValueError):
    pass


def projection_profiles_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "editorial" / "profiles.json"


def load_projection_profiles(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    source = Path(path) if path is not None else projection_profiles_path()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ContractError("profiles document must be an object")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ContractError("profiles document requires a non-empty profiles array")

    validated: dict[str, dict[str, Any]] = {}
    for raw in profiles:
        profile = validate_projection_profile(raw)
        profile_id = profile["profile_id"]
        if profile_id in validated:
            raise ContractError(f"duplicate projection profile {profile_id!r}")
        validated[profile_id] = profile
    return validated


def validate_projection_profile(value: Any) -> dict[str, Any]:
    profile = _mapping(value, "profile")
    required = {
        "schema_version",
        "profile_id",
        "account_key",
        "strategy",
        "public_identity",
        "sources",
        "fallback",
        "publication",
    }
    missing = required - set(profile)
    if missing:
        raise ContractError(f"projection profile missing keys: {sorted(missing)}")
    if profile["schema_version"] != PROFILE_SCHEMA:
        raise ContractError("unsupported projection profile schema_version")

    profile_id = _string(profile["profile_id"], "profile_id")
    _string(profile["account_key"], "account_key")
    strategy = _string(profile["strategy"], "strategy")
    if strategy not in SUPPORTED_STRATEGIES:
        raise ContractError(f"unsupported projection strategy {strategy!r}")

    identity = _mapping(profile["public_identity"], "public_identity")
    _string(identity.get("role"), "public_identity.role")
    handle = identity.get("x_handle")
    handle_env = identity.get("x_handle_env")
    if not _optional_string(handle) and not _optional_string(handle_env):
        raise ContractError("public_identity requires x_handle or x_handle_env")

    sources = _string_list(profile["sources"], "sources")
    publication = _mapping(profile["publication"], "publication")
    if publication.get("default_mode") not in {"dry_run", "publish_if_safe"}:
        raise ContractError("publication.default_mode must be dry_run or publish_if_safe")
    max_posts = publication.get("max_posts_per_day")
    if not isinstance(max_posts, int) or max_posts < 0 or max_posts > 4:
        raise ContractError("publication.max_posts_per_day must be an integer from 0 to 4")
    if publication.get("auto_publish_max_risk") != "low":
        raise ContractError("v1 auto publication may only allow low-risk candidates")

    if strategy == "dev_projection":
        if "github_estate" not in sources:
            raise ContractError("dev_projection requires github_estate source")
        if profile["fallback"] != "historical_dev_work":
            raise ContractError("dev_projection fallback must be historical_dev_work")
    elif strategy == "argentina_econ":
        required_sources = {
            "media_monitor",
            "atlas_economico_ar",
            "owned_economic_artifacts",
            "approved_idea_bank",
            "public_web_context",
        }
        if not required_sources.issubset(set(sources)):
            raise ContractError(
                "argentina_econ requires media, owned evidence, idea-bank and public-context sources"
            )
        if profile["fallback"] != "skip":
            raise ContractError("argentina_econ fallback must be skip")
        relations = profile.get("allowed_relations")
        if set(_string_list(relations, "allowed_relations")) != ARGENTINA_ECON_RELATIONS:
            raise ContractError("argentina_econ relation taxonomy must be complete and exact")

    return dict(profile)


def validate_candidate(value: Any, profile: Mapping[str, Any]) -> dict[str, Any]:
    candidate = _mapping(value, "candidate")
    required = {
        "schema_version",
        "candidate_id",
        "profile_id",
        "text",
        "risk_class",
        "evidence_refs",
    }
    missing = required - set(candidate)
    if missing:
        raise ContractError(f"editorial candidate missing keys: {sorted(missing)}")
    if candidate["schema_version"] != CANDIDATE_SCHEMA:
        raise ContractError("unsupported editorial candidate schema_version")
    _string(candidate["candidate_id"], "candidate_id")
    if candidate["profile_id"] != profile["profile_id"]:
        raise ContractError("candidate profile_id does not match projection profile")
    _string(candidate["text"], "text")
    if candidate["risk_class"] not in RISK_CLASSES:
        raise ContractError("candidate risk_class is invalid")
    _string_list(candidate["evidence_refs"], "evidence_refs")

    strategy = profile["strategy"]
    if strategy == "dev_projection":
        _string_list(candidate.get("work_refs"), "work_refs")
    elif strategy == "argentina_econ":
        _string(candidate.get("current_claim_ref"), "current_claim_ref")
        _string_list(candidate.get("owned_evidence_refs"), "owned_evidence_refs")
        _string_list(candidate.get("approved_idea_refs"), "approved_idea_refs")
        relation = candidate.get("relation")
        if relation not in ARGENTINA_ECON_RELATIONS:
            raise ContractError("argentina_econ candidate relation is invalid")
        if relation == "cannot_adjudicate":
            raise ContractError("cannot_adjudicate is a retrieval outcome, not publishable candidate copy")

    return dict(candidate)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a non-empty string")
    return value.strip()


def _optional_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{label} must be a non-empty string array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContractError(f"{label} must contain only non-empty strings")
    return list(value)
