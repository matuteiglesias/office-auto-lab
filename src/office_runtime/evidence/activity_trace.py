"""Bounded ActivityWatch + Firefox evidence with a private/raw boundary.

The public JSONL stream intentionally contains only structural observations. Raw
payloads are retained under the operator's XDG state directory for local use.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import multiprocessing
import os
import sqlite3
import tempfile
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


def _parse_start(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result


def _parse_end_exclusive(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if len(value) == 10:
        result += timedelta(days=1)
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


class FirefoxAcquisitionError(RuntimeError):
    def __init__(self, direct_error: Exception, backup_error: Exception):
        self.details = {
            "direct_read": {"error": type(direct_error).__name__, "message": str(direct_error)},
            "online_backup": {"error": type(backup_error).__name__, "message": str(backup_error)},
        }
        super().__init__(f"direct read failed ({type(direct_error).__name__}); online backup failed ({type(backup_error).__name__})")


def private_root() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "office-auto-lab" / "private" / "activity-evidence"


def _assert_safe_output(path: Path) -> None:
    resolved = path.expanduser().resolve()
    if resolved == private_root().resolve() or private_root().resolve() in resolved.parents:
        raise ValueError("activity safe output cannot be inside the private raw root")


def _assert_private_root(path: Path) -> None:
    repo = Path(__file__).resolve().parents[3]
    resolved = path.expanduser().resolve()
    if resolved == repo or repo in resolved.parents:
        raise ValueError("activity private raw root cannot be inside the source repository")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            n += 1
    return n


def _api_get(url: str, params: dict[str, str], timeout: float = 5.0) -> Any:
    query = urllib.parse.urlencode(params)
    target = url.rstrip("/") + ("?" + query if query else "")
    try:
        with urllib.request.urlopen(target, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Werkzeug (used by ActivityWatch) uses 308 for its canonical trailing slash.
        if exc.code in (301, 302, 307, 308) and exc.headers.get("Location"):
            location = exc.headers["Location"]
            if query and "?" not in location:
                location += "?" + query
            with urllib.request.urlopen(location, timeout=timeout) as response:
                return json.load(response)
        raise


def discover_buckets(aw_url: str) -> dict[str, dict[str, Any]]:
    payload = _api_get(aw_url.rstrip("/") + "/buckets/", {})
    if not isinstance(payload, dict):
        raise ValueError("ActivityWatch buckets response is not an object")
    return payload


def _choose_bucket(buckets: dict[str, Any], prefix: str) -> str | None:
    matches = sorted(key for key in buckets if key.startswith(prefix))
    return matches[-1] if matches else None


def _event_bounds(event: dict[str, Any], start: datetime, end: datetime) -> tuple[datetime, datetime] | None:
    try:
        beginning = datetime.fromtimestamp(_timestamp(str(event["timestamp"])), timezone.utc)
        duration = max(0.0, float(event.get("duration", 0.0)))
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    finish = beginning + timedelta(seconds=duration)
    if finish <= start or beginning >= end:
        return None
    return max(beginning, start), min(finish, end)


def _profile_candidates(home: Path | None = None) -> list[Path]:
    home = home or Path.home()
    return [
        home / "snap/firefox/common/.mozilla/firefox/profiles.ini",
        home / ".mozilla/firefox/profiles.ini",
    ]


def discover_firefox_places(profile_ini: Path | None = None) -> Path:
    ini = profile_ini
    if ini is None:
        ini = next((candidate for candidate in _profile_candidates() if candidate.is_file()), None)
    if ini is None:
        raise FileNotFoundError("Firefox profiles.ini not found")
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(ini, encoding="utf-8")
    profiles = []
    for section in parser.sections():
        if not section.lower().startswith("profile") or not parser.has_option(section, "Path"):
            continue
        path = Path(parser.get(section, "Path"))
        if parser.getboolean(section, "IsRelative", fallback=True):
            path = ini.parent / path
        profiles.append((parser.getboolean(section, "Default", fallback=False), path))
    for _, path in sorted(profiles, key=lambda item: item[0], reverse=True):
        places = path / "places.sqlite"
        if places.is_file():
            return places
    raise FileNotFoundError("Firefox profile has no places.sqlite")


def _backup_worker(source: str, destination: str, result_queue: Any) -> None:
    """Run in a process so an uninterruptible SQLite backup can be terminated."""
    source_db = target_db = None
    progress_calls = 0
    last_progress: tuple[int, int, int] | None = None
    try:
        source_db = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=0.5)
        source_db.execute("PRAGMA busy_timeout=500")
        target_db = sqlite3.connect(destination)

        def progress(status: int, remaining: int, total: int) -> None:
            nonlocal progress_calls, last_progress
            progress_calls += 1
            last_progress = (status, remaining, total)

        source_db.backup(target_db, pages=128, sleep=0.2, progress=progress)
        result_queue.put({"status": "ok", "progress_calls": progress_calls, "last_progress": last_progress})
    except (sqlite3.Error, OSError) as exc:
        result_queue.put({"status": "error", "error": type(exc).__name__, "message": str(exc), "progress_calls": progress_calls, "last_progress": last_progress})
    finally:
        if target_db is not None:
            target_db.close()
        if source_db is not None:
            source_db.close()


def snapshot_places(source: Path, destination: Path, *, retries: int = 3, timeout_seconds: float = 10.0) -> dict[str, Any]:
    """Create a bounded, consistent SQLite backup without touching Firefox.

    The worker is a process rather than a thread: SQLite backup can remain
    blocked in native code beyond a Python join timeout. A timed-out worker is
    explicitly terminated and joined before the temporary snapshot is removed.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {"error": "RuntimeError", "message": "backup not attempted"}
    for attempt in range(1, max(1, retries) + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        destination.unlink(missing_ok=True)
        context = multiprocessing.get_context("fork")
        result_queue = context.Queue(maxsize=1)
        worker = context.Process(target=_backup_worker, args=(str(source), str(destination), result_queue))
        started = time.monotonic()
        worker.start()
        worker.join(remaining)
        elapsed = time.monotonic() - started
        if worker.is_alive():
            worker.terminate()
            worker.join(2.0)
            result_queue.close()
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"Firefox SQLite snapshot timed out after {elapsed:.3f}s with no completed backup")
        result: dict[str, Any] = {}
        try:
            result = result_queue.get(timeout=0.2)
        except Exception:
            result = {}
        finally:
            result_queue.close()
        if result.get("status") == "ok" and destination.exists() and destination.stat().st_size:
            result.update({"attempt": attempt, "elapsed_seconds": round(elapsed, 3)})
            return result
        last = result or {"error": "RuntimeError", "message": f"backup worker exited {worker.exitcode}"}
        destination.unlink(missing_ok=True)
        if attempt < retries:
            time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))
    raise RuntimeError(f"Firefox SQLite snapshot unavailable: {last.get('error')}: {last.get('message')}")


def query_firefox_visits(source: Path, start: datetime, end: datetime, *, busy_timeout_ms: int = 1000) -> list[tuple[float, str, str, int]]:
    """Read one bounded query in SQLite's consistent read transaction semantics.

    A single SELECT sees one SQLite snapshot. This is used only when Firefox
    permits a normal read-only connection; no immutable mode or file copying is
    used, so committed WAL content remains part of normal SQLite visibility.
    """
    db = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=busy_timeout_ms / 1000)
    try:
        db.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        query = "SELECT visit_date / 1000000.0, url, title, visit_type FROM moz_historyvisits JOIN moz_places ON moz_places.id = moz_historyvisits.place_id WHERE visit_date >= ? AND visit_date < ? ORDER BY visit_date"
        return list(db.execute(query, (start.timestamp() * 1e6, end.timestamp() * 1e6)))
    finally:
        db.close()


def acquire_firefox_visits(source: Path, start: datetime, end: datetime) -> tuple[list[tuple[float, str, str, int]], dict[str, Any]]:
    """Prefer a bounded direct read; fall back to a bounded online backup."""
    direct_failure: Exception | None = None
    try:
        visits = query_firefox_visits(source, start, end)
        return visits, {"strategy": "direct_read", "status": "ok"}
    except (sqlite3.Error, OSError) as direct_error:
        direct_failure = direct_error
        direct = {"error": type(direct_error).__name__, "message": str(direct_error)}

    try:
        with tempfile.TemporaryDirectory(prefix="office-activity-") as temp:
            snapshot = Path(temp) / "places.sqlite"
            backup = snapshot_places(source, snapshot)
            visits = query_firefox_visits(snapshot, start, end)
    except (sqlite3.Error, OSError, RuntimeError) as backup_error:
        raise FirefoxAcquisitionError(direct_failure or RuntimeError("direct read failed"), backup_error) from backup_error
    return visits, {"strategy": "online_backup", "status": "ok", "direct_read_error": direct, "backup": backup}


def _raw_record(handle: Any, source: str, payload: Any) -> None:
    handle.write(json.dumps({"source": source, "payload": payload}, ensure_ascii=False) + "\n")


def collect_activity(*, start: str, end: str, out: Path, aw_url: str = "http://127.0.0.1:5600/api/0", profile_ini: Path | None = None, raw_root: Path | None = None, timeout: float = 5.0) -> dict[str, Any]:
    start_dt, end_dt = _parse_start(start), _parse_end_exclusive(end)
    _assert_safe_output(out)
    raw_base = (raw_root or private_root()).expanduser().resolve()
    _assert_private_root(raw_base)
    raw_base.mkdir(parents=True, exist_ok=True)
    raw_base.chmod(0o700)
    run_dir = raw_base / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(mode=0o700)
    raw_path = run_dir / "raw.jsonl"
    rows: list[dict[str, Any]] = []
    health: list[dict[str, Any]] = []
    counts = {"activitywatch_window": 0, "activitywatch_afk": 0, "firefox_visit": 0}
    visits: list[float] = []

    with raw_path.open("w", encoding="utf-8") as raw:
        raw_path.chmod(0o600)
        buckets: dict[str, Any] = {}
        try:
            buckets = discover_buckets(aw_url)
            health.append({"kind": "activity_source_health", "source": "activitywatch", "status": "ok", "bucket_count": len(buckets)})
        except Exception as exc:
            health.append({"kind": "activity_source_health", "source": "activitywatch", "status": "failed", "error": type(exc).__name__, "message": str(exc)[:240]})

        for source, prefix, label in (("activitywatch_window", "aw-watcher-window_", "window"), ("activitywatch_afk", "aw-watcher-afk_", "afk")):
            bucket = _choose_bucket(buckets, prefix)
            if not bucket:
                health.append({"kind": "activity_source_health", "source": source, "status": "degraded", "error": "bucket_missing"})
                continue
            try:
                events = _api_get(aw_url.rstrip("/") + f"/buckets/{urllib.parse.quote(bucket, safe='')}/events", {"start": _iso(start_dt), "end": _iso(end_dt)}, timeout)
                if not isinstance(events, list):
                    raise ValueError("events response is not a list")
                for event in events:
                    bounds = _event_bounds(event, start_dt, end_dt)
                    if not bounds:
                        continue
                    beginning, finish = bounds
                    data = event.get("data") if isinstance(event.get("data"), dict) else {}
                    _raw_record(raw, source, event)
                    row = {"kind": "activity_observation", "source": source, "start": _iso(beginning), "end": _iso(finish), "duration_seconds": round((finish - beginning).total_seconds(), 3), "event_id": hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()[:16]}
                    if source == "activitywatch_window":
                        app = str(data.get("app", "")); row.update({"application_class": app[:120], "is_firefox": "firefox" in app.lower() or "firefox" in str(data.get("title", "")).lower()})
                    else:
                        row["afk_status"] = str(data.get("status", "unknown"))[:40]
                    rows.append(row); counts[source] += 1
                health.append({"kind": "activity_source_health", "source": source, "status": "ok", "bucket": bucket, "rows": counts[source]})
            except Exception as exc:
                health.append({"kind": "activity_source_health", "source": source, "status": "degraded", "bucket": bucket, "error": type(exc).__name__, "message": str(exc)[:240]})

        firefox_status = "degraded"
        try:
            places = discover_firefox_places(profile_ini)
            firefox_visits, acquisition = acquire_firefox_visits(places, start_dt, end_dt)
            for timestamp, url, title, visit_type in firefox_visits:
                visits.append(float(timestamp)); counts["firefox_visit"] += 1; _raw_record(raw, "firefox_visit", {"timestamp": timestamp, "url": url, "title": title, "visit_type": visit_type})
            firefox_status = "ok"
            health.append({"kind": "activity_source_health", "source": "firefox", "status": "ok", "profile": str(places), "rows": len(visits), "acquisition": acquisition})
        except Exception as exc:
            row = {"kind": "activity_source_health", "source": "firefox", "status": "degraded", "error": type(exc).__name__, "message": str(exc)[:240]}
            if isinstance(exc, FirefoxAcquisitionError):
                row["acquisition"] = exc.details
            health.append(row)

    # Join only by a boolean; no URL/title crosses into the safe artifact.
    for row in rows:
        row["nearby_firefox_visit"] = bool(row.get("is_firefox") and any(abs(v - _timestamp(row["start"])) <= 300 for v in visits))
    output_rows = [{"kind": "activity_run", "producer": "office_runtime.evidence.activity", "producer_version": "1", "start": _iso(start_dt), "end": _iso(end_dt), "raw_private": str(raw_path), "raw_private_class": "PRIVATE_LOCAL", "counts": counts, "firefox_status": firefox_status}]
    output_rows.extend(health); output_rows.extend(rows)
    n = _write_jsonl(out, output_rows)
    aw_ok = any(x.get("source") == "activitywatch" and x.get("status") == "ok" for x in health)
    status = "ok" if aw_ok else "degraded"
    return {"status": status, "rows_written": n, "counts": counts, "firefox_status": firefox_status, "raw_private": str(raw_path), "out": str(out), "start": start, "end": end, "health": health}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize bounded, sanitized ActivityWatch/Firefox evidence.")
    parser.add_argument("--start", required=True); parser.add_argument("--end", required=True); parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--aw-url", default="http://127.0.0.1:5600/api/0"); parser.add_argument("--profile-ini", type=Path, default=None); parser.add_argument("--raw-root", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    result = collect_activity(**vars(parse_args()))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
