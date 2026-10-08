"""Read-only consumer boundary for future Milei Mirror clients."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any


def recent_activity(snapshot: Mapping[str, Any], *, now: datetime, hours: int = 48) -> dict[str, Any]:
    """Return evidence and coverage only; no interpretation or mutation."""
    start = now.astimezone(timezone.utc) - timedelta(hours=hours)
    events = []
    for event in snapshot.get("events", []):
        value = event.get("created_at_utc")
        if not isinstance(value, str):
            continue
        try:
            created = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if created >= start:
            events.append(event)
    events.sort(key=lambda item: item.get("created_at_utc", ""))
    return {"window_start": start.isoformat().replace("+00:00", "Z"), "window_end": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "events": events, "coverage": snapshot.get("coverage", "UNKNOWN"), "gaps": snapshot.get("gaps", [])}
