from pathlib import Path

import pandas as pd
import pytest

from office_runtime.office.compile import canonicalize_front_identity, _merge
from office_runtime.office.repo_context import enrich_with_repo_context, load_repo_context


def test_legacy_project_id_becomes_front_id():
    df = pd.DataFrame([{"project_id": "front-a", "Title": "A"}])
    out = canonicalize_front_identity(df)
    assert out.loc[0, "front_id"] == "front-a"
    assert out.loc[0, "project_id"] == "front-a"


def test_front_id_only_keeps_legacy_alias():
    df = pd.DataFrame([{"front_id": "front-a", "Title": "A"}])
    out = canonicalize_front_identity(df)
    assert out.loc[0, "front_id"] == "front-a"
    assert out.loc[0, "project_id"] == "front-a"


def test_conflicting_front_and_project_id_fails_closed():
    df = pd.DataFrame([{"front_id": "front-a", "project_id": "front-b"}])
    with pytest.raises(ValueError, match="front_id/project_id conflict"):
        canonicalize_front_identity(df)


def test_merge_uses_front_identity_and_preserves_legacy_projection():
    front = pd.DataFrame([{"front_id": "front-a", "Title": "A"}])
    carry = pd.DataFrame([{"project_id": "front-a", "carry": "Active"}])
    merged, unmatched_front, unmatched_carry = _merge(front, carry)
    assert merged["front_id"].tolist() == ["front-a"]
    assert merged["project_id"].tolist() == ["front-a"]
    assert unmatched_front.empty
    assert unmatched_carry.empty


def test_repo_context_is_advisory_and_allows_front_without_repo():
    df = pd.DataFrame(
        [
            {"front_id": "front-a", "repo_ids": "repo.one;repo.unknown", "carry": "Active"},
            {"front_id": "front-b", "repo_ids": "", "carry": "Escalate"},
        ]
    )
    payload = {
        "contract": "context:github-repositories@1",
        "generated_at": "2026-09-01T00:00:00Z",
        "repositories": {"repo.one": {"github": "owner/one", "readiness": "ready"}},
    }
    out, summary = enrich_with_repo_context(df, payload)
    assert out.loc[0, "repo_context_status"] == "partial"
    assert out.loc[1, "repo_context_status"] == "none"
    assert out["carry"].tolist() == ["Active", "Escalate"]
    assert summary["known_repo_refs"] == 1
    assert summary["unknown_repo_refs"] == 1


def test_missing_repo_context_is_nonfatal():
    df = pd.DataFrame([{"front_id": "front-a", "repo_ids": "repo.one"}])
    out, summary = enrich_with_repo_context(df, None)
    assert out.loc[0, "repo_context_status"] == "context-unavailable"
    assert summary["repo_refs"] == 1


def test_wrong_repo_context_contract_fails(tmp_path: Path):
    path = tmp_path / "repo-context.json"
    path.write_text('{"contract":"wrong","repositories":{}}', encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected repository context contract"):
        load_repo_context(path)
