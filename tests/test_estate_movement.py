from __future__ import annotations

import json
import subprocess
from pathlib import Path

from office_runtime.estate_movement import classify, discover_repos, produce, render_markdown


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "example"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    (repo / "SYSTEM.yaml").write_text("id: example\n")
    (repo / "README.md").write_text("example\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feat: add recovery runbook")
    return repo


def test_classification_covers_evidence_labels() -> None:
    evidence = [
        {"kind": "git_commit", "evidence_id": "a", "repo": "x", "subject": "feat: add adapter", "files": []},
        {"kind": "git_commit", "evidence_id": "b", "repo": "x", "subject": "fix: close blocked retry failure", "files": ["docs/operations/failure-recovery.md"]},
        {"kind": "authority_file", "evidence_id": "c", "repo": "projects", "path": "estate/repositories.yaml"},
        {"kind": "run_receipt", "evidence_id": "d", "repo": "x", "status": "ok", "event": "run.end"},
        {"kind": "run_receipt", "evidence_id": "e", "repo": "x", "status": "blocked", "event": "awaiting input"},
    ]
    groups = classify(evidence)
    assert "a" in {item["evidence_id"] for item in groups["NEW"]}
    assert "b" in {item["evidence_id"] for item in groups["CLOSED"]}
    assert "c" in {item["evidence_id"] for item in groups["AUTHORITY CHANGED"]}
    assert "d" in {item["evidence_id"] for item in groups["BECAME TRUE"]}
    assert "e" in {item["evidence_id"] for item in groups["STILL BLOCKED"]}


def test_discovery_keeps_nested_repositories_under_a_git_container(tmp_path: Path) -> None:
    container = tmp_path / "repos"
    container.mkdir()
    _git(container, "init")
    _git(container, "config", "user.email", "test@example.invalid")
    _git(container, "config", "user.name", "Test")
    (container / "container.md").write_text("container\n")
    _git(container, "add", ".")
    _git(container, "commit", "-m", "init container")
    child = _repo(container)
    names = {repo.name for repo in discover_repos([container], max_depth=3)}
    assert {"repos", child.name} <= names


def test_delta_omits_prior_evidence_and_does_not_render_absolute_paths(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    out = tmp_path / "out"
    first = produce(digest_id="first", roots=[repo], start="2000-01-01", end="2100-01-01", out_root=out)
    second = produce(
        digest_id="second", roots=[repo], start="2000-01-01", end="2100-01-01",
        out_root=out, previous_manifest=Path(first["manifest"]),
    )
    manifest = json.loads(Path(second["manifest"]).read_text())
    digest = Path(second["digest"]).read_text()
    evidence = [json.loads(line) for line in (Path(second["out"]) / "evidence.jsonl").read_text().splitlines()]
    assert manifest["new_evidence_count"] == 0
    assert str(tmp_path) not in digest
    assert all("estate-movement" not in item.get("path", "") for item in evidence)
    assert "No new evidence matched" in digest


def test_render_is_deterministic_for_fixed_input() -> None:
    manifest = {
        "window": {"start": "2026-09-12", "end": "2026-09-13"}, "delta_mode": "baseline",
        "new_evidence_count": 1, "evidence_count": 1, "repositories_observed": 1,
        "counts": {"git_commit": 1},
    }
    groups = {key: [] for key in ("NEW", "CLOSED", "BECAME TRUE", "FAILED", "AUTHORITY CHANGED", "RECOVERY IMPROVED", "STILL BLOCKED", "COMPOUNDING CROSSOVERS", "NEXT PULL")}
    groups["NEW"] = [{"evidence_id": "git:example:abc", "repo": "example", "subject": "feat: add item"}]
    assert render_markdown("2026-09-12-evening", manifest, groups) == render_markdown("2026-09-12-evening", manifest, groups)
