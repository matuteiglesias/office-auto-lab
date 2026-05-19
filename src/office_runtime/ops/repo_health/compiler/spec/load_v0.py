from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def _spec_dir() -> Path:
    return Path(__file__).resolve().parent / "v0"


def load_json(name: str) -> Dict[str, Any]:
    p = _spec_dir() / name
    if not p.exists():
        raise FileNotFoundError(f"missing spec file: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def load_enums() -> Dict[str, Any]:
    return load_json("enums.json")


def load_operator_registry() -> Dict[str, Any]:
    return load_json("operator_registry.json")


def load_archetypes() -> Dict[str, Any]:
    return load_json("archetypes.json")


def load_classify_rules() -> Dict[str, Any]:
    return load_json("classify_rules.json")


def load_prepared_block_schema() -> Dict[str, Any]:
    return load_json("prepared_block.schema.json")
