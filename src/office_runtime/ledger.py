from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


def _sanitize(value: Any) -> str:
    text = str(value)
    return " ".join(text.replace("\n", " ").replace("\r", " ").split())


def _iter_pairs(data: Mapping[str, Any] | None):
    if not data:
        return
    for key, value in data.items():
        if value is None:
            continue
        yield _sanitize(key), _sanitize(value)


def append_ledger(
    module: str,
    status: str,
    run_id: str | None = None,
    metrics: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, str] | None = None,
    log_root: str | Path = "artifacts/logs",
) -> Path:
    now = datetime.now().astimezone()
    day_dir = Path(log_root) / "daily"
    day_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = day_dir / f"{now.date().isoformat()}.ledger.log"

    parts = [now.strftime("%H:%M"), _sanitize(module), _sanitize(status)]

    for key, value in _iter_pairs(metrics):
        parts.append(f"{key}={value}")

    artifact_items = list(_iter_pairs(artifacts)) if artifacts else []
    if len(artifact_items) == 1:
        _, value = artifact_items[0]
        parts.append(f"out={value}")
    else:
        for key, value in artifact_items:
            parts.append(f"artifact={key}:{value}")

    if run_id:
        parts.append(f"run={_sanitize(run_id)}")

    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(" ".join(parts) + "\n")

    return ledger_path
