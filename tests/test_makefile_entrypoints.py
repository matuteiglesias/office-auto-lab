from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = REPO_ROOT / "Makefile"
SYSTEM = REPO_ROOT / "SYSTEM.yaml"


def _recipe_paths() -> set[str]:
    text = MAKEFILE.read_text(encoding="utf-8")
    return set(
        re.findall(
            r"(?:bash|python3)\s+((?:src|scripts)/[^\s]+\.(?:py|sh))",
            text,
        )
    )


def _target_dependencies(target: str) -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(target)}:\s*([^\n]*)$", text, flags=re.MULTILINE)
    assert match is not None, f"missing make target {target}"
    return match.group(1).strip()


def test_all_file_entrypoints_referenced_by_make_exist() -> None:
    paths = _recipe_paths()
    assert paths
    missing = sorted(path for path in paths if not (REPO_ROOT / path).is_file())
    assert missing == []


def test_smoke_is_the_single_supported_office_surface() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    smoke_deps = _target_dependencies("smoke").split()

    assert smoke_deps == [
        "imports",
        "control-contracts",
        "identity-contracts",
        "work-contracts",
        "staff-v2-contracts",
        "principal-contracts",
        "execution-contracts",
        "reentry-v2-contracts",
        "generation-v2-contracts",
        "run-record-contracts",
        "freshness-contracts",
        "editorial-contracts",
        "runtime-contracts",
        "repo-scans",
    ]
    assert "src/office_runtime/scripts/repo_contract_scan.sh" in text
    assert "src/office_runtime/scripts/repo_snapshot_protocol.sh" in text
    for target in (
        "control-contracts",
        "identity-contracts",
        "work-contracts",
        "staff-v2-contracts",
        "principal-contracts",
        "execution-contracts",
        "reentry-v2-contracts",
        "generation-v2-contracts",
        "run-record-contracts",
        "freshness-contracts",
        "runtime-health-v2",
        "office-v2-generate",
        "office-v2-shadow",
    ):
        assert f"\n{target}:" in text


def test_legacy_make_and_dependency_surfaces_are_gone() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    for target in (
        "daily",
        "office-compile",
        "office-reentry",
        "staff-bundles",
        "staff-briefs",
        "compat-compile-blocks",
        "compat-repo-health-policy",
        "compat-repo-health-run",
        "repo-health-policy",
        "repo-health-run",
    ):
        assert f"\n{target}:" not in text

    assert not (REPO_ROOT / "src/office_runtime/scripts/legacy").exists()
    assert not (REPO_ROOT / "src/office_runtime/ops/repo_health").exists()
    assert not (REPO_ROOT / "src/office_runtime/staff/bundles.py").exists()
    assert not (REPO_ROOT / "src/office_runtime/staff/briefs.py").exists()
    assert not (REPO_ROOT / "src/office_runtime/office/compile.py").exists()
    assert not (REPO_ROOT / "src/office_runtime/office/closure_reentry.py").exists()


def test_system_declaration_has_no_compat_product_surface() -> None:
    text = SYSTEM.read_text(encoding="utf-8")

    assert "artifact:ops.repo-health@1" not in text
    assert "repository health/readiness semantics" in text
    assert "context:github-repositories@1" in text
    assert "class: compat" not in text
    assert "legacy producer-local review projection" not in text
