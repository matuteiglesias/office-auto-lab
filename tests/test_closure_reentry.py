from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from office_runtime.office.closure_reentry import ClosureValidationError, compile_reentry, reconcile_closures
from office_runtime.office.render import render_office_summary
from office_runtime.office.config import OfficeConfig
from office_runtime.office import compile as office_compile


def closure(**overrides):
    value = {
        "contract": "artifact:ops.closure@1",
        "front_id": "fcv",
        "status": "partial",
        "evidence": ["git:fcv:abc123"],
        "closure": "Fixture extraction completed; annotation remains.",
        "next_touch": "Run the annotation fixture and inspect the result.",
        "carry_recommendation": "Active",
        "escalation": False,
    }
    value.update(overrides)
    return value


def fronts():
    return pd.DataFrame([
        {"front_id": "fcv", "Title": "FCV"},
        {"project_id": "accounting", "Title": "Accounting"},
    ])


def test_partial_known_front_is_proposal_and_restart_seed(tmp_path: Path):
    source = tmp_path / "closures.json"
    source.write_text(json.dumps(closure()), encoding="utf-8")
    result = compile_reentry(source, fronts(), tmp_path / "out")
    proposal = json.loads((tmp_path / "out" / "reentry_proposals.jsonl").read_text())
    assert result["reconciled"] == 1
    assert proposal["front_reconciliation_status"] == "RECONCILED"
    assert proposal["restart_seed"]["exact_next_touch"].startswith("Run")
    assert proposal["carry_recommendation"] == "Active"
    assert proposal["mutation_performed"] is False


def test_blocked_keeps_blocker_and_escalation(tmp_path: Path):
    source = tmp_path / "closures.json"
    source.write_text(json.dumps(closure(status="blocked", escalation={"required": True, "reason": "Need owner decision"})), encoding="utf-8")
    compile_reentry(source, fronts(), tmp_path / "out")
    review = (tmp_path / "out" / "reentry_review.md").read_text()
    assert "blocked" in review
    assert "Need owner decision" in review


def test_done_has_no_fabricated_restart(tmp_path: Path):
    source = tmp_path / "closures.json"
    source.write_text(json.dumps(closure(status="done", next_touch=None)), encoding="utf-8")
    compile_reentry(source, fronts(), tmp_path / "out")
    proposal = json.loads((tmp_path / "out" / "reentry_proposals.jsonl").read_text())
    assert proposal["restart_seed"] is None
    assert proposal["exact_restart_instruction"] is None


def test_unknown_front_is_preserved_but_not_actionable(tmp_path: Path):
    source = tmp_path / "closures.json"
    source.write_text(json.dumps(closure(front_id="unknown")), encoding="utf-8")
    result = compile_reentry(source, fronts(), tmp_path / "out")
    proposal = json.loads((tmp_path / "out" / "reentry_proposals.jsonl").read_text())
    assert result["unresolved"] == 1
    assert proposal["front_reconciliation_status"] == "UNRESOLVED_FRONT"
    assert proposal["actionable"] is False
    assert proposal["restart_seed"] is None


def test_same_closure_twice_is_idempotent_and_distinct_same_front_survives(tmp_path: Path):
    first = closure(closure_id="one")
    second = closure(closure_id="two", next_touch="Inspect a separate validation report.")
    source = tmp_path / "closures.jsonl"
    source.write_text("\n".join(json.dumps(row) for row in [first, first, second]) + "\n", encoding="utf-8")
    result = compile_reentry(source, fronts(), tmp_path / "out")
    proposals = (tmp_path / "out" / "reentry_proposals.jsonl").read_text().splitlines()
    assert result["closures_read"] == 3
    assert result["closures_normalized"] == 2
    assert len(proposals) == 2


def test_malformed_and_missing_optional_fields_are_visible(tmp_path: Path):
    with pytest.raises(ClosureValidationError, match="next_touch"):
        reconcile_closures([(closure(next_touch=None), "fixture.json")], fronts())
    source = tmp_path / "closures.json"
    source.write_text(json.dumps(closure()), encoding="utf-8")
    compile_reentry(source, fronts(), tmp_path / "out")
    normalized = json.loads((tmp_path / "out" / "normalized_closures.jsonl").read_text())
    assert normalized["horizon_recommendation"] == "not supplied"
    assert normalized["follow_up_spawns"] == "not supplied"


def test_determinism_and_no_absolute_path_leakage(tmp_path: Path):
    source = tmp_path / "private-closures.json"
    source.write_text(json.dumps(closure()), encoding="utf-8")
    one = tmp_path / "one"
    two = tmp_path / "two"
    compile_reentry(source, fronts(), one)
    compile_reentry(source, fronts(), two)
    for filename in ("normalized_closures.jsonl", "reentry_proposals.jsonl", "reentry_review.md", "manifest.json", "qa.json"):
        assert (one / filename).read_bytes() == (two / filename).read_bytes()
        assert str(tmp_path).encode() not in (one / filename).read_bytes()


def test_contract_and_path_scope_fail_closed(tmp_path: Path):
    with pytest.raises(ClosureValidationError, match="unexpected closure contract"):
        reconcile_closures([(closure(contract="wrong"), "fixture.json")], fronts())
    with pytest.raises(ClosureValidationError, match="does not exist"):
        compile_reentry(tmp_path / "missing", fronts(), tmp_path / "out")


def test_office_review_surface_keeps_reentry_advisory():
    text = render_office_summary(
        {"row_counts": {}, "surface_context": {"configured": False}},
        pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), [],
        "## Recent closures / reentry\n\n- Proposed carry posture: Active (proposal only)\n",
    )
    assert "## Recent closures / reentry" in text
    assert "proposal only" in text


def test_normal_office_compile_optionally_surfaces_closures_without_mutating(tmp_path: Path, monkeypatch):
    source = tmp_path / "closures.json"
    source.write_text(json.dumps(closure(front_id="fcv")), encoding="utf-8")
    front = pd.DataFrame([{"project_id": "fcv", "Title": "FCV", "expected": "1", "human_maint": "1", "human_focus": "0", "staff_get": "1", "staff_watch": "1", "staff_post": "0"}])
    carry = pd.DataFrame([{"project_id": "fcv", "carry": "Active", "horizon": "This week", "needs": "Execution", "principal": "No"}])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(office_compile, "read_sheet_values", lambda _sa, _sheet, gid: front if gid == "front" else carry)
    cfg = OfficeConfig("unused", "unused", "front", "carry", "runtime", "support", tmp_path / "out", tmp_path, False, closure_source=source)
    manifest = office_compile.run_compile(cfg)
    summary = (tmp_path / "out" / "latest" / "office_summary.md").read_text()
    assert manifest["closure_reentry"]["reconciled"] == 1
    assert manifest["closure_reentry"]["mutation_performed"] is False
    assert "## Recent closures / reentry" in summary
    assert "proposal only" in summary
