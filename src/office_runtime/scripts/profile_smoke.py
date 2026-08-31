#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json


IMPORTS_BY_PROFILE = {
    "office": (
        "office_runtime.office.compile",
        "office_runtime.office.config",
        "office_runtime.office.io",
        "office_runtime.office.render",
        "office_runtime.office.validate",
        "office_runtime.staff.bundles",
        "office_runtime.staff.briefs",
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
    "repo-health": (
        "office_runtime.ops.repo_health.policy",
        "office_runtime.ops.repo_health.runner",
        "office_runtime.ops.repo_health.plugin_loader",
        "office_runtime.ops.repo_health.remote.source",
        "office_runtime.ops.repo_health.run_bundle.model",
        "office_runtime.ops.repo_health.run_bundle.ports",
        "office_runtime.ops.repo_health.adapters.gcp.bigquery",
        "office_runtime.ops.repo_health.adapters.gcp.storage",
        "office_runtime.ops.repo_health.cloud.run_job",
    ),
    "legacy-auto-checker": (
        "gspread",
        "google_auth_oauthlib",
        "requests_oauthlib",
        "oauthlib",
        "pandas",
    ),
}
IMPORTS_BY_PROFILE["full"] = tuple(
    dict.fromkeys(
        module
        for profile in ("office", "capture", "repo-health")
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
