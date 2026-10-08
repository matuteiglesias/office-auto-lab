from __future__ import annotations

import json
from pathlib import Path

import pytest

from office_runtime.media_evidence import CompositionError, CompositionRequest, compose_media_selection


def _roots(tmp_path: Path) -> tuple[Path, Path, Path]:
    media = tmp_path / "media"
    kb = tmp_path / "kb"
    store = tmp_path / "store"
    (media / "apps" / "media_watch").mkdir(parents=True)
    (kb / "src" / "kb_artifacts").mkdir(parents=True)
    store.mkdir()
    (media / "SYSTEM.yaml").write_text("repository:\n  github: matuteiglesias/media_monitor\n", encoding="utf-8")
    (kb / "SYSTEM.yaml").write_text("repository:\n  github: matuteiglesias/kb-artifacts\n", encoding="utf-8")
    (media / "apps" / "media_watch" / "evidence_export.py").write_text("# fixture\n", encoding="utf-8")
    (kb / "src" / "kb_artifacts" / "cli.py").write_text("# fixture\n", encoding="utf-8")
    return media, kb, store


def test_plan_is_non_mutating_and_returns_mcp_handoff(tmp_path: Path) -> None:
    media, kb, store = _roots(tmp_path)
    work = tmp_path / "work"
    request = CompositionRequest("media-inflation-20261007", "2026-10-05", "2026-10-07", "inflaci[oó]n")

    plan = compose_media_selection(
        request=request,
        media_monitor_root=media,
        media_store_root=store,
        kb_artifacts_root=kb,
        work_root=work,
        apply=False,
    )

    assert plan["contract"] == "ops.media-evidence-composition-plan@1"
    assert plan["apply"] is False
    assert plan["selection"]["corpus"] == "media-monitor"
    assert plan["handoff"]["mctx_command"] == "mctx evidence media-inflation-20261007"
    assert not work.exists()
    assert not (kb / "artifacts").exists()


@pytest.mark.parametrize(
    "case",
    [
        CompositionRequest("../bad", "2026-10-05", "2026-10-07", "inflacion"),
        CompositionRequest("ok", "2026-10-08", "2026-10-07", "inflacion"),
        CompositionRequest("ok", "2026-10-05", "2026-10-07", ""),
    ],
)
def test_invalid_requests_fail_before_writes(tmp_path: Path, case: CompositionRequest) -> None:
    media, kb, store = _roots(tmp_path)
    with pytest.raises(CompositionError):
        compose_media_selection(
            request=case,
            media_monitor_root=media,
            media_store_root=store,
            kb_artifacts_root=kb,
            work_root=tmp_path / "work",
            apply=False,
        )


def test_wrong_repository_identity_fails_closed(tmp_path: Path) -> None:
    media, kb, store = _roots(tmp_path)
    (media / "SYSTEM.yaml").write_text("repository:\n  github: someone/else\n", encoding="utf-8")
    with pytest.raises(CompositionError, match="unexpected SYSTEM identity"):
        compose_media_selection(
            request=CompositionRequest("selection-a", "2026-10-05", "2026-10-07", "inflacion"),
            media_monitor_root=media,
            media_store_root=store,
            kb_artifacts_root=kb,
            work_root=tmp_path / "work",
            apply=False,
        )


def test_existing_selection_id_is_never_overwritten(tmp_path: Path) -> None:
    media, kb, store = _roots(tmp_path)
    existing = kb / "artifacts" / "runs" / "selection-a"
    existing.mkdir(parents=True)
    with pytest.raises(CompositionError, match="already exists"):
        compose_media_selection(
            request=CompositionRequest("selection-a", "2026-10-05", "2026-10-07", "inflacion"),
            media_monitor_root=media,
            media_store_root=store,
            kb_artifacts_root=kb,
            work_root=tmp_path / "work",
            apply=True,
        )
