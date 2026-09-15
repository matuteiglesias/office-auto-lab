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


def test_smoke_is_core_only_and_legacy_compiler_is_compatibility_only() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    smoke_deps = _target_dependencies("smoke").split()

    assert smoke_deps == ["imports", "control-contracts", "identity-contracts", "work-contracts", "staff-v2-contracts", "principal-contracts", "execution-contracts", "reentry-v2-contracts", "generation-v2-contracts", "editorial-contracts", "runtime-contracts", "repo-scans"]
    assert "src/office_runtime/scripts/repo_contract_scan.sh" in text
    assert "src/office_runtime/scripts/repo_snapshot_protocol.sh" in text
    assert "\ncontrol-contracts:" in text
    assert "tests.test_control_snapshot_v2" in text
    assert "\nidentity-contracts:" in text
    assert "tests.test_identity_resolution_v2" in text
    assert "\nwork-contracts:" in text
    assert "tests.test_work_item_compiler_v1" in text
    assert "\nstaff-v2-contracts:" in text
    assert "tests.test_staff_preparation_v2" in text
    assert "\nprincipal-contracts:" in text
    assert "tests.test_principal_compiler_v2" in text
    assert "\nexecution-contracts:" in text
    assert "tests.test_execution_compiler_v2" in text
    assert "\nreentry-v2-contracts:" in text
    assert "tests.test_reentry_v2" in text
    assert "\ngeneration-v2-contracts:" in text
    assert "tests.test_generation_v2" in text
    assert "\noffice-v2-generate:" in text
    assert "run_generation_v2.py" in text
    assert "\noffice-v2-shadow:" in text
    assert "--shadow" in text
    assert "\ncompat-compile-blocks:" in text
    assert "src/office_runtime/scripts/legacy/compile_blocks.py" in text
    assert "\ncompile-blocks:" not in text


def test_repo_health_is_compatibility_not_active_make_surface() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "\nrepo-health-policy:" not in text
    assert "\nrepo-health-run:" not in text
    assert "\ncompat-repo-health-policy:" in text
    assert "\ncompat-repo-health-run:" in text


def test_broken_parallel_office_entrypoint_is_not_exposed() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "office_runtime.office.main" not in text
    assert "\noffice:" not in text
    assert "\noffice-compile:" in text


def test_office_system_no_longer_produces_repo_health_authority_artifact() -> None:
    text = SYSTEM.read_text(encoding="utf-8")

    assert "artifact:ops.repo-health@1" not in text
    assert "repository health/readiness semantics" in text
    assert "context:github-repositories@1" in text
    assert "lifecycle_classes:" in text
    assert "class: compat" in text
