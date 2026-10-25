from __future__ import annotations
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/office_runtime/scripts"))
from dispatch_producer_receipts import safe_receipt, run, DispatchError


def receipt():
    return {
        "contract": "evidence:producer-run-receipt@1",
        "run_id": "office-test:1",
        "producer_id": "producer.local.office-evidence-daily",
        "scheduler_run_id": None,
        "trigger": "schedule",
        "started_at": "2026-10-24T22:00:00Z",
        "finished_at": "2026-10-24T22:00:02Z",
        "stages": {"execution": "success"},
        "outputs": [{"type": "artifact.ops.daily-evidence@1", "state": "valid", "durability": "rebuildable"}],
        "result": {"scheduler_state": "healthy", "execution_state": "healthy", "artifact_state": "healthy", "terminal_state": "not_applicable", "authority_state": "canonical"},
        "evidence_refs": ["local-evidence:sha256:abc"],
        "warnings": [],
    }


def test_valid_and_private_rejection(tmp_path):
    p = tmp_path/"receipt.json"
    p.write_text(json.dumps(receipt()))
    _, digest = safe_receipt(p)
    assert len(digest) == 64
    obj = receipt()
    obj["evidence_refs"] = ["/home/secret/file"]
    p.write_text(json.dumps(obj))
    try:
        safe_receipt(p)
        assert False, "private evidence should be rejected"
    except DispatchError:
        pass


def test_dispatch_only_once_and_no_deletion(tmp_path):
    spool = tmp_path/"spool"
    src = spool/"producer.local.office-evidence-daily"
    src.mkdir(parents=True)
    p = src/"one.json"
    p.write_text(json.dumps(receipt()))
    ledger = tmp_path/"ledger"
    with patch("dispatch_producer_receipts.send") as sender:
        first = run(spool, ledger, gh="gh", dispatch=True, max_batch=20)
        second = run(spool, ledger, gh="gh", dispatch=True, max_batch=20)
        assert first["submitted"] == 1 and first["errors"] == 0
        assert second["submitted"] == 0 and second["already_submitted"] == 1
        sender.assert_called_once()
    assert p.exists()


def test_network_fail_leaves_receipt_for_retry(tmp_path):
    spool = tmp_path/"spool"
    src = spool/"producer.local.office-compile"
    src.mkdir(parents=True)
    p = src/"one.json"
    obj = receipt()
    obj["producer_id"] = "producer.local.office-compile"
    obj["outputs"][0]["type"] = "artifact.ops.office-compiled-surface@1"
    p.write_text(json.dumps(obj))
    ledger = tmp_path/"ledger"
    with patch("dispatch_producer_receipts.send", side_effect=DispatchError("not sent")):
        x = run(spool, ledger, gh="gh", dispatch=True, max_batch=20)
        assert x["errors"] == 1
    assert p.exists() and not list(ledger.glob("*.json"))
