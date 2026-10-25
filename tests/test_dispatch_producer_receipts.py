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
    with patch("dispatch_producer_receipts.remote_runs", return_value={}):
     with patch("dispatch_producer_receipts.send") as sender:
        first = run(spool, ledger, gh="gh", dispatch=True, max_batch=20)
        second = run(spool, ledger, gh="gh", dispatch=True, max_batch=20)
        assert first["submitted"] == 1 and first["errors"] == 0
        assert second["submitted"] == 0 and second["awaiting_remote"] == 1
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
    with patch("dispatch_producer_receipts.remote_runs", return_value={}):
     with patch("dispatch_producer_receipts.send", side_effect=DispatchError("not sent")):
        x = run(spool, ledger, gh="gh", dispatch=True, max_batch=20)
        assert x["errors"] == 1
    assert p.exists() and not list(ledger.glob("*.json"))


def test_remote_success_confirms_exact_receipt(tmp_path):
    from dispatch_producer_receipts import canonical, read_marker
    import hashlib
    spool = tmp_path / "spool"
    src = spool / "producer.local.office-evidence-daily"
    src.mkdir(parents=True)
    path = src / "one.json"
    payload = receipt()
    path.write_text(json.dumps(payload))
    digest = hashlib.sha256(canonical(payload).encode()).hexdigest()
    ledger = tmp_path / "ledger"
    with patch("dispatch_producer_receipts.remote_runs", return_value={}):
        with patch("dispatch_producer_receipts.send") as sender:
            first = run(spool, ledger, gh="gh", dispatch=True, max_batch=20)
    assert first["submitted"] == 1
    from dispatch_producer_receipts import utcnow
    returned = {digest: {
        "id": 12345678, "status": "completed", "conclusion": "success",
        "created_at": utcnow().isoformat(), "url": "https://github.com/example/actions/runs/12345678",
    }}
    with patch("dispatch_producer_receipts.remote_runs", return_value=returned):
        with patch("dispatch_producer_receipts.send") as sender:
            second = run(spool, ledger, gh="gh", dispatch=True, max_batch=20)
            third = run(spool, ledger, gh="gh", dispatch=True, max_batch=20)
            sender.assert_not_called()
    assert second["confirmed"] == 1
    assert third["already_confirmed"] == 1
    assert read_marker(ledger / (digest+".json"))["status"] == "confirmed"
    assert path.exists()


def test_failed_remote_is_retried_with_backoff(tmp_path):
    from dispatch_producer_receipts import canonical, write_marker
    import hashlib
    spool = tmp_path / "spool"
    src = spool / "producer.local.office-evidence-daily"
    src.mkdir(parents=True)
    payload = receipt()
    (src / "one.json").write_text(json.dumps(payload))
    digest = hashlib.sha256(canonical(payload).encode()).hexdigest()
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    write_marker(ledger / (digest + ".json"), {
        "status": "submitted", "receipt_sha256": digest,
        "attempts": 1, "submitted_at": "2026-10-24T20:00:00Z",
    })
    remote = {digest: {
        "id": 11, "status": "completed", "conclusion": "failure",
        "created_at": "2026-10-24T20:00:00Z",
        "url": "https://github.com/example/actions/runs/11",
    }}
    with patch("dispatch_producer_receipts.remote_runs", return_value=remote):
        with patch("dispatch_producer_receipts.failed_stage", return_value="Validate Office producer receipt and export once"):
            with patch("dispatch_producer_receipts.send") as sender:
                summary = run(spool, ledger, gh="gh", dispatch=True, max_batch=20)
                sender.assert_called_once()
    assert summary["retried"] == 1
    assert summary["failed_remote"] == 1
    assert summary["diagnostics"][0]["failed_step"] == "Validate Office producer receipt and export once"


def test_remote_status_error_fails_closed(tmp_path):
    spool = tmp_path / "spool"
    src = spool / "producer.local.office-evidence-daily"
    src.mkdir(parents=True)
    (src / "one.json").write_text(json.dumps(receipt()))
    with patch("dispatch_producer_receipts.remote_runs", side_effect=DispatchError("API refused")):
        with patch("dispatch_producer_receipts.send") as sender:
            summary = run(spool, tmp_path / "ledger", gh="gh", dispatch=True, max_batch=20)
            sender.assert_not_called()
    assert summary["errors"] == 1


def test_github_run_name_mapping():
    from dispatch_producer_receipts import remote_runs
    payload = {"workflow_runs": [
        {"display_title": "office-receipt:"+("a"*64), "id":123,
         "status": "completed", "conclusion": "success",
         "created_at": "2026-10-25T01:00:00Z", "html_url": "https://github.com/example"},
        {"display_title": "office-receipt:"+"invalid", "id":2},
    ]}
    with patch("dispatch_producer_receipts.gh_json", return_value=payload):
        result = remote_runs("gh")
    assert list(result) == ["a"*64]
    assert result["a"*64]["id"] == 123
