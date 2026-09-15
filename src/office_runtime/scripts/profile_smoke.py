#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json


IMPORTS_BY_PROFILE = {
    "office": (
        "office_runtime.office.config",
        "office_runtime.office.control_snapshot",
        "office_runtime.office.identity",
        "office_runtime.office.work_items",
        "office_runtime.office.principal",
        "office_runtime.office.execution",
        "office_runtime.office.reentry_v2",
        "office_runtime.office.generation_v2",
        "office_runtime.office.invariants",
        "office_runtime.office.run_records",
        "office_runtime.office.io",
        "office_runtime.staff.preparation_v2",
        "office_runtime.staff.freshness",
        "office_runtime.evidence.git_trace",
        "office_runtime.evidence.fs_trace",
        "office_runtime.ledger",
        "office_runtime.run_logging",
    ),
    "capture": (
        "office_runtime.capture.lifecycle",
        "office_runtime.capture.processing",
        "office_runtime.capture.transcription",
    ),
}
IMPORTS_BY_PROFILE["full"] = tuple(
    dict.fromkeys(
        module
        for profile in ("office", "capture")
        for module in IMPORTS_BY_PROFILE[profile]
    )
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import-smoke one installed Office Runtime dependency profile.")
    parser.add_argument("profile", choices=tuple(IMPORTS_BY_PROFILE))
    args = parser.parse_args()

    imported = []
    for module in IMPORTS_BY_PROFILE[args.profile]:
        importlib.import_module(module)
        imported.append(module)
    print(json.dumps({"status": "ok", "profile": args.profile, "imports": imported}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
