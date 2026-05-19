from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _sanitize(value: Any) -> str:
    text = str(value)
    return " ".join(text.replace("\n", " ").replace("\r", " ").split())


class RunLogger:
    def __init__(self, module: str, run_id: str, log_root: str | Path = "artifacts/logs") -> None:
        self.module = _sanitize(module)
        self.run_id = _sanitize(run_id)
        root = Path(log_root)
        runs_dir = root / "runs"
        events_dir = root / "events"
        runs_dir.mkdir(parents=True, exist_ok=True)
        events_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{self.module}_{self.run_id}"
        self.run_log_path = runs_dir / f"{stem}.log"
        self.event_log_path = events_dir / f"{stem}.jsonl"

    def event(self, event: str, level: str = "INFO", **fields: Any) -> None:
        now = datetime.now().astimezone()
        clean_fields = {str(k): v for k, v in fields.items() if v is not None}
        payload = {
            "ts": now.isoformat(),
            "level": str(level).upper(),
            "event": _sanitize(event),
            "module": self.module,
            "run_id": self.run_id,
            **clean_fields,
        }
        with self.event_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

        kv = " ".join(f"{_sanitize(k)}={_sanitize(v)}" for k, v in clean_fields.items())
        line = f"{now.strftime('%H:%M:%S')} {payload['level']} {payload['event']}"
        if kv:
            line = f"{line} {kv}"
        with self.run_log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def info(self, message: str, **fields: Any) -> None:
        self.event(message, level="INFO", **fields)

    def warning(self, message: str, **fields: Any) -> None:
        self.event(message, level="WARNING", **fields)

    def error(self, message: str, **fields: Any) -> None:
        self.event(message, level="ERROR", **fields)
