import json
import sqlite3
from pathlib import Path

import pytest

from office_runtime.evidence import activity_trace


def _make_places(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript("CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT, title TEXT); CREATE TABLE moz_historyvisits (id INTEGER PRIMARY KEY, place_id INTEGER, visit_date INTEGER, visit_type INTEGER);")
    db.execute("INSERT INTO moz_places VALUES (1, ?, ?)", ("https://example.invalid/?token=SECRET", "Private document title"))
    db.execute("INSERT INTO moz_historyvisits VALUES (1, 1, ?, 1)", (1_700_000_000_000_000,))
    db.commit(); db.close()


def test_snapshot_places_success(tmp_path):
    source = tmp_path / "places.sqlite"; target = tmp_path / "snapshot.sqlite"
    _make_places(source)
    activity_trace.snapshot_places(source, target)
    assert target.exists()
    assert sqlite3.connect(target).execute("select count(*) from moz_historyvisits").fetchone()[0] == 1


def test_direct_firefox_read_uses_one_bounded_query(tmp_path):
    source = tmp_path / "places.sqlite"
    _make_places(source)
    visits = activity_trace.query_firefox_visits(
        source,
        activity_trace._parse_start("2023-11-14T00:00:00+00:00"),
        activity_trace._parse_end_exclusive("2023-11-15T00:00:00+00:00"),
    )
    assert len(visits) == 1
    assert visits[0][1].startswith("https://")


def test_acquisition_reports_direct_and_backup_failure(tmp_path, monkeypatch):
    source = tmp_path / "places.sqlite"
    _make_places(source)
    monkeypatch.setattr(activity_trace, "query_firefox_visits", lambda *args, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("locked")))
    monkeypatch.setattr(activity_trace, "snapshot_places", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("timed out")))
    with pytest.raises(activity_trace.FirefoxAcquisitionError) as exc:
        activity_trace.acquire_firefox_visits(source, activity_trace._parse_start("2023-11-14"), activity_trace._parse_end_exclusive("2023-11-15"))
    assert exc.value.details["direct_read"]["error"] == "OperationalError"
    assert exc.value.details["online_backup"]["error"] == "RuntimeError"


def test_collect_counts_firefox_visits(tmp_path, monkeypatch):
    source = tmp_path / "places.sqlite"; _make_places(source)
    monkeypatch.setattr(activity_trace, "discover_firefox_places", lambda _: source)
    monkeypatch.setattr(activity_trace, "discover_buckets", lambda _: {})
    result = activity_trace.collect_activity(start="2023-11-14", end="2023-11-15", out=tmp_path / "safe.jsonl", raw_root=tmp_path / "raw")
    assert result["firefox_status"] == "ok"
    assert result["counts"]["firefox_visit"] == 1


def test_collect_activity_degrades_locked_firefox_and_redacts(tmp_path, monkeypatch):
    out = tmp_path / "safe.jsonl"; raw = tmp_path / "raw"
    buckets = {"aw-watcher-window_test": {}, "aw-watcher-afk_test": {}}
    def fake_get(url, params, timeout=5.0):
        if url.endswith("/buckets/"): return buckets
        if "window_test" in url: return [{"timestamp": "2026-01-01T00:00:00+00:00", "duration": 2, "data": {"app": "Firefox", "title": "https://example.invalid/?token=SECRET"}}]
        return [{"timestamp": "2026-01-01T00:00:00+00:00", "duration": 2, "data": {"status": "not-afk"}}]
    monkeypatch.setattr(activity_trace, "_api_get", fake_get)
    monkeypatch.setattr(activity_trace, "discover_firefox_places", lambda _: (_ for _ in ()).throw(FileNotFoundError("locked")))
    result = activity_trace.collect_activity(start="2026-01-01T00:00:00+00:00", end="2026-01-01T00:01:00+00:00", out=out, raw_root=raw)
    assert result["status"] == "ok"
    assert result["firefox_status"] == "degraded"
    text = out.read_text()
    assert "SECRET" not in text
    assert "Private document" not in text
    assert any(json.loads(line)["kind"] == "activity_source_health" for line in text.splitlines())


def test_private_root_and_safe_output_boundaries(tmp_path):
    with pytest.raises(ValueError):
        activity_trace.collect_activity(start="2026-01-01", end="2026-01-02", out=tmp_path / "x.jsonl", raw_root=Path(__file__).resolve().parents[1])
