"""Repository-owned composition adapter for Editorial Dev Staging v1."""

from __future__ import annotations

import contextlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from .context import load_pinned_policy_file
from .contracts import (
    ActivityEvidence,
    AngleCard,
    DailyBatch,
    PolicyIdentity,
    StoryCluster,
    load_projection_profiles,
)
from .evidence.github import GitHubEvidenceClient, GitHubHTTPError, GitHubRESTTransport
from .intelligence import EditorialIntelligence, compile_daily_batch, failed_daily_batch
from .intelligence.adk_adapter import build_adk_editorial_intelligence
from .run_bundle import build_run_bundle
from .story import cluster_stories

_PR_REF = re.compile(r"^(?P<repo>[^/ #]+/[^# ]+)#(?P<number>[1-9][0-9]*)$")
_DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[3] / "config" / "editorial" / "dev-constitution.md"
_POLICY_AUTHORITY = "weekly-ops-governance"
_POLICY_SOURCE_REF = "github:matuteiglesias/weekly-ops-governance:docs/05_full_context/editorial-dev-constitution-v1.md"
_POLICY_SOURCE_REVISION = "3a9628f5c60593f826effdea10b9eb7e45540698"
_POLICY_SHA256 = "fe12a92328dffb91d57c3b1d7d21b496e3a735435e1f379cc977f0497806a60e"
_DEFAULT_MAX_MODEL_STORIES = 12
_HARD_MAX_MODEL_STORIES = 12


class EditorialProducerError(RuntimeError):
    """A bounded producer configuration or source failure."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _policy() -> tuple[PolicyIdentity, str]:
    repo_root = Path(__file__).resolve().parents[3]
    path = Path(os.environ.get("EDITORIAL_POLICY_PATH", str(_DEFAULT_POLICY_PATH)))
    if not path.is_absolute():
        path = repo_root / path
    try:
        relative_path = path.resolve().relative_to(repo_root)
    except ValueError as exc:
        raise EditorialProducerError("EDITORIAL_POLICY_PATH must remain inside the repository") from exc
    pinned = load_pinned_policy_file(
        repo_root,
        relative_path,
        authority=os.environ.get("EDITORIAL_POLICY_AUTHORITY", _POLICY_AUTHORITY),
        source_ref=os.environ.get("EDITORIAL_POLICY_SOURCE_REF", _POLICY_SOURCE_REF),
        source_revision=os.environ.get("EDITORIAL_POLICY_SOURCE_REVISION", _POLICY_SOURCE_REVISION),
        expected_sha256=os.environ.get("EDITORIAL_POLICY_SHA256", _POLICY_SHA256),
    )
    return pinned.identity, pinned.text


def _model_names() -> tuple[str, str]:
    shared = os.environ.get("EDITORIAL_MODEL", "").strip()
    angle = os.environ.get("EDITORIAL_ANGLE_MODEL", shared).strip()
    judge = os.environ.get("EDITORIAL_JUDGE_MODEL", shared).strip()
    if not angle or not judge:
        raise EditorialProducerError(
            "EDITORIAL_ANGLE_MODEL and EDITORIAL_JUDGE_MODEL (or EDITORIAL_MODEL) are required"
        )
    return angle, judge


@contextlib.contextmanager
def _model_credentials() -> Iterator[None]:
    configured = os.environ.get("EDITORIAL_MODEL_API_KEY")
    had_google_key = "GOOGLE_API_KEY" in os.environ
    previous = os.environ.get("GOOGLE_API_KEY")
    if configured and not had_google_key:
        os.environ["GOOGLE_API_KEY"] = configured
    try:
        yield
    finally:
        if configured and not had_google_key:
            if previous is None:
                os.environ.pop("GOOGLE_API_KEY", None)
            else:
                os.environ["GOOGLE_API_KEY"] = previous


def _parse_pr(pr_ref: str) -> tuple[str, int]:
    match = _PR_REF.fullmatch(pr_ref.strip())
    if not match:
        raise EditorialProducerError("pr_ref must use exact owner/repo#PR syntax")
    return match.group("repo"), int(match.group("number"))


def _retrieval_for_pr(repository_ref: str, pr_number: int, evidence: ActivityEvidence) -> dict[str, Any]:
    pr_ref = f"{repository_ref}#{pr_number}"
    return {
        "mode": "exact_pr",
        "pr_ref": pr_ref,
        "intended_sources": [f"github_pr:{pr_ref}"],
        "actual_sources": ["github_pr"],
        "time_windows": [{"scope": repository_ref, "pr_ref": pr_ref, "since": None, "until": None}],
        "failures": [],
        "scope_status": "complete",
        "evidence_ids": [evidence.evidence_id],
    }


def _retrieval_for_window(request: Mapping[str, Any], retrievals: list[Any]) -> dict[str, Any]:
    inventory = [
        {"repository": item.repository_ref, **dict(source)}
        for item in retrievals
        for source in item.inventory
    ]
    return {
        "mode": "lookback",
        "repositories": [item.repository_ref for item in retrievals],
        "intended_sources": sorted({source["source"] for source in inventory}),
        "actual_sources": sorted({source["source"] for source in inventory if source.get("status") == "reached"}),
        "time_windows": [{"scope": item.repository_ref, "since": request.get("since"), "until": request.get("until")} for item in retrievals],
        "failures": [failure.to_dict() for item in retrievals for failure in item.failures],
        "scope_status": "complete" if all(item.scope_status == "complete" for item in retrievals) else "degraded",
        "inventory": inventory,
    }


def _angle_card(value: Mapping[str, Any]) -> AngleCard:
    return AngleCard(
        angle_id=str(value["angle_id"]),
        story_id=str(value["story_id"]),
        angle_type=str(value["angle_type"]),
        claim=str(value["claim"]),
        tension_or_hook=str(value["tension_or_hook"]),
        transferable_lesson=str(value["transferable_lesson"]),
        evidence_refs=tuple(value["evidence_refs"]),
        audience=tuple(value["audience"]),
        career_signals=tuple(value.get("career_signals", [])),
        why_interesting=str(value["why_interesting"]),
        risk_class=str(value["risk_class"]),
        proof_object_refs=tuple(value.get("proof_object_refs", [])),
        required_status_wording=tuple(value.get("required_status_wording", [])),
        counterpoint=value.get("counterpoint"),
        expiry_hint=value.get("expiry_hint"),
    )


def _repositories(request: Mapping[str, Any]) -> list[str]:
    configured = os.environ.get("EDITORIAL_REPOSITORIES", "")
    repositories = [item.strip() for item in configured.split(",") if item.strip()]
    if not repositories:
        raise EditorialProducerError(
            "lookback staging requires EDITORIAL_REPOSITORIES; exact PR mode does not"
        )
    if len(repositories) != len(set(repositories)):
        raise EditorialProducerError("EDITORIAL_REPOSITORIES must not contain duplicates")
    return repositories


def _max_model_stories() -> int:
    raw = os.environ.get("EDITORIAL_MAX_STORIES_PER_RUN", str(_DEFAULT_MAX_MODEL_STORIES)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise EditorialProducerError("EDITORIAL_MAX_STORIES_PER_RUN must be an integer") from exc
    if value < 1 or value > _HARD_MAX_MODEL_STORIES:
        raise EditorialProducerError(
            f"EDITORIAL_MAX_STORIES_PER_RUN must be between 1 and {_HARD_MAX_MODEL_STORIES}"
        )
    return value


def _parse_event_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise EditorialProducerError("evidence event_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _select_model_stories(
    stories: tuple[StoryCluster, ...],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    limit: int,
) -> tuple[StoryCluster, ...]:
    eligibility_rank = {"eligible": 0, "unknown": 1, "restricted": 2}
    freshness_rank = {"timely": 0, "recent": 1, "evergreen": 2}

    def priority(story: StoryCluster) -> tuple[int, int, float, str]:
        latest = max(
            _parse_event_time(str(evidence_by_id[ref]["event_at"]))
            for ref in story.evidence_refs
        )
        return (
            eligibility_rank.get(story.public_eligibility, 3),
            freshness_rank.get(story.freshness_class, 3),
            -latest.timestamp(),
            story.story_id,
        )

    return tuple(sorted(stories, key=priority)[:limit])


def produce_bundle(request: Mapping[str, Any]) -> Mapping[str, Any]:
    """Produce one validated run bundle for the staging runtime request."""
    if request.get("profile_id") != "dev":
        raise EditorialProducerError("Editorial producer only supports profile_id='dev'")

    started_at = _now()
    policy, policy_text = _policy()
    token = os.environ.get("EDITORIAL_ESTATE_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    client = GitHubEvidenceClient(GitHubRESTTransport(token=token))
    evidence: tuple[ActivityEvidence, ...]
    retrieval: dict[str, Any]

    pr_ref = request.get("pr_ref")
    try:
        if isinstance(pr_ref, str) and pr_ref.strip():
            repository_ref, number = _parse_pr(pr_ref)
            item = client.fetch_pull_request(repository_ref, number, observed_at=started_at)
            evidence = (item,)
            retrieval = _retrieval_for_pr(repository_ref, number, item)
        else:
            since, until = request.get("since"), request.get("until")
            if not isinstance(since, str) or not isinstance(until, str):
                raise EditorialProducerError("lookback requests require since and until")
            retrievals = [
                client.retrieve_repository_activity(
                    repository,
                    since=since,
                    until=until,
                    observed_at=started_at,
                )
                for repository in _repositories(request)
            ]
            evidence = tuple(item for result in retrievals for item in result.evidence)
            retrieval = _retrieval_for_window(request, retrievals)
    except (GitHubHTTPError, EditorialProducerError) as exc:
        finished_at = _now()
        retrieval = {
            "mode": "exact_pr" if pr_ref else "lookback",
            "pr_ref": pr_ref,
            "intended_sources": ["github_pr"] if pr_ref else [],
            "actual_sources": [],
            "time_windows": [],
            "failures": [{"source_ref": str(pr_ref or "configured repositories"), "failure_kind": type(exc).__name__, "status": "unknown"}],
            "scope_status": "unknown",
        }
        failed = failed_daily_batch(batch_date=finished_at[:10], reason="evidence retrieval failed")
        return build_run_bundle(
            profile_id="dev", started_at=started_at, finished_at=finished_at,
            policy=policy, retrieval=retrieval, batch=DailyBatch.from_mapping(failed.batch),
            errors=({"stage": "retrieval", "kind": type(exc).__name__, "status": "failed"},),
            status="FAILED",
        ).to_dict()

    stories = cluster_stories(evidence, as_of=started_at)
    evidence_by_id = {item.evidence_id: item.to_dict() for item in evidence}
    max_model_stories = _max_model_stories()
    model_stories = _select_model_stories(stories, evidence_by_id, max_model_stories)
    retrieval["story_count"] = len(stories)
    retrieval["model_story_limit"] = max_model_stories
    retrieval["model_story_count"] = len(model_stories)
    retrieval["model_story_omitted_count"] = max(0, len(stories) - len(model_stories))
    context = ({"context_id": "policy", "policy": policy_text},)
    provider_runs: list[Mapping[str, Any]] = []
    angles: list[AngleCard] = []
    candidates: list[Mapping[str, Any]] = []
    errors: list[Mapping[str, Any]] = []

    try:
        angle_model, judge_model = _model_names()
        with _model_credentials():
            intelligence = build_adk_editorial_intelligence(
                angle_model=angle_model,
                judge_model=judge_model,
            )
            for story in model_stories:
                result = intelligence.run_story(
                    story=story.to_dict(),
                    evidence_by_id=evidence_by_id,
                    context=context,
                    policy=policy.to_dict(),
                    generated_at=started_at,
                )
                angles.extend(_angle_card(item) for item in result.angles)
                candidates.extend(
                    {**dict(candidate), "source_tier": "1"}
                    for candidate in result.candidates
                )
                provider_runs.extend(result.provider_runs)
    except Exception as exc:  # provider/model failure is retained in canonical evidence
        finished_at = _now()
        errors.append({"stage": "intelligence", "kind": type(exc).__name__, "status": "failed"})
        failed = failed_daily_batch(batch_date=finished_at[:10], reason="intelligence stage failed")
        return build_run_bundle(
            profile_id="dev", started_at=started_at, finished_at=finished_at,
            policy=policy, retrieval=retrieval, evidence=evidence, stories=stories,
            angles=angles, provider_runs=provider_runs, errors=errors,
            batch=DailyBatch.from_mapping(failed.batch), status="FAILED",
        ).to_dict()

    finished_at = _now()
    compilation = compile_daily_batch(
        primary_candidates=candidates,
        batch_date=finished_at[:10],
        profile_id="dev",
    )
    batch = DailyBatch.from_mapping(compilation.batch)
    return build_run_bundle(
        profile_id="dev", started_at=started_at, finished_at=finished_at,
        policy=policy, retrieval=retrieval, evidence=evidence, stories=stories,
        angles=angles, candidates=candidates, batch=batch,
        provider_runs=provider_runs, errors=errors,
        status=batch.payload["inventory_status"],
    ).to_dict()
