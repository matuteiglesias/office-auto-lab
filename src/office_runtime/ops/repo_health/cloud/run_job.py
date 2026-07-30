from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..adapters.gcp import BigQueryHistorySink, GCSRunEvidenceSink, GoogleBigQueryClient
from ..compiler.generate import candidate_to_prepared_block, generate_candidate_blocks, parse_frontier_rows, rollup_projects
from ..plugin_loader import load_plugins_from_folder, select_gcp_plugins
from ..policy import compute_effective_runset
from ..remote import GitHubRepositorySource
from ..run_bundle import JsonlHistorySink, LocalRunEvidenceSink, build_run_bundle, canonical_json

LOCAL_PATH_FIELDS = frozenset({"repo_path", "workdir", "path"})


def validate_cloud_snapshot(snapshot: Mapping[str, Any]) -> None:
    required = {"projects", "capabilities", "plugin_policy", "plugin_prereqs", "producer_commit"}
    missing = required - set(snapshot)
    if missing:
        raise ValueError(f"policy snapshot missing {sorted(missing)}")
    projects = snapshot["projects"]
    if not isinstance(projects, list) or not projects or len(projects) > 3:
        raise ValueError("cloud profile requires 1-3 allowlisted projects")
    for project in projects:
        present = sorted(field for field in LOCAL_PATH_FIELDS if str(project.get(field) or "").strip())
        if present:
            raise ValueError(f"cloud profile rejects local path fields: {present}")
        identity = str(project.get("repository_full_name") or "")
        if identity not in set(snapshot.get("repository_allowlist") or []):
            raise ValueError(f"project repository {identity!r} is not in repository_allowlist")
    requested = {str(row.get("plugin") or "") for row in snapshot["plugin_policy"] if str(row.get("default_mode") or "on").lower() == "on"}
    unsupported = requested - {"activity_remote", "runbook_remote"}
    if unsupported:
        raise ValueError(f"cloud profile rejects unsupported plugins: {sorted(unsupported)}")


def execute_snapshot(snapshot: Mapping[str, Any], *, repository_source: Any, run_id: str | None = None,
                     started_at: datetime | None = None) -> dict[str, Any]:
    validate_cloud_snapshot(snapshot)
    start = started_at or datetime.now(timezone.utc)
    run_id = run_id or os.environ.get("REPO_HEALTH_RUN_ID") or f"rh-{start.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    intents, _debug = compute_effective_runset(
        snapshot["projects"], snapshot["capabilities"], snapshot["plugin_policy"], snapshot["plugin_prereqs"],
        start.date().isoformat(), return_debug=True,
    )
    plugins = select_gcp_plugins(load_plugins_from_folder())
    projects = {str(row["project_id"]): row for row in snapshot["projects"]}
    intent_rows, result_rows, frontier, exceptions = [], [], [], []
    for intent in intents:
        if not intent.scheduled:
            continue
        intent_id = intent.run_id
        intent_rows.append({"intent_id": intent_id, "project_id": intent.project_id, "plugin": intent.plugin, "scheduled": True})
        result_id = hashlib.sha256(f"{run_id}:{intent_id}".encode()).hexdigest()[:24]
        plugin = plugins.get(intent.plugin)
        try:
            if plugin is None:
                raise RuntimeError(f"cloud plugin {intent.plugin!r} is not registered")
            raw = plugin.run({"project": projects[intent.project_id], "repository_source": repository_source, "now": start})
            status = str(raw.get("status") or "ERROR").upper()
            normalized = {"PASS": "ok", "WARN": "warning", "WARNING": "warning", "FAIL": "actionable_failure", "NA": "ineligible", "SKIP": "ineligible"}.get(status, "system_error")
            failed = normalized == "system_error"
            result = {"result_id": result_id, "intent_id": intent_id, "project_id": intent.project_id, "plugin": intent.plugin,
                      "normalized_class": normalized, "bucket": str(raw.get("bucket") or status),
                      "short_diag": str(raw.get("message") or "")[:200], "failed": failed,
                      "evidence": raw.get("evidence", []), "meta": raw.get("meta", {})}
        except Exception as exc:
            result = {"result_id": result_id, "intent_id": intent_id, "project_id": intent.project_id, "plugin": intent.plugin,
                      "normalized_class": "system_error", "bucket": f"EXCEPTION:{type(exc).__name__}",
                      "short_diag": str(exc)[:200], "failed": True, "evidence": [], "meta": {"exception_type": type(exc).__name__}}
        result_rows.append(result)
        frontier.append({key: result[key] for key in ("result_id", "project_id", "plugin", "bucket", "normalized_class", "short_diag")})
        if result["failed"]:
            exceptions.append({"exception_id": f"exception-{result_id}", "result_id": result_id, "category": "plugin_failure", "message": result["short_diag"]})
    issues = parse_frontier_rows(frontier)
    project_ir = rollup_projects(issues)
    candidates = generate_candidate_blocks(start.date().isoformat(), project_ir, issues)
    prepared = []
    result_by_pair = {(row["project_id"], row["plugin"]): row["result_id"] for row in result_rows}
    for candidate in candidates:
        block = candidate_to_prepared_block(start.date().isoformat(), candidate)
        links = sorted({result_by_pair[(trigger["project_id"], trigger["plugin"])] for trigger in block["triggers"] if (trigger["project_id"], trigger["plugin"]) in result_by_pair})
        if links:
            block["source_result_ids"] = links
            prepared.append(block)
    end = datetime.now(timezone.utc)
    policy_bytes = canonical_json(snapshot)
    return build_run_bundle(
        run_id=run_id, started_at=start.isoformat(), ended_at=end.isoformat(), attempt=int(os.environ.get("REPO_HEALTH_ATTEMPT", "1")),
        producer_commit=str(snapshot["producer_commit"]), policy_input_id=str(snapshot.get("policy_input_id") or hashlib.sha256(policy_bytes).hexdigest()[:24]),
        policy_sha256=hashlib.sha256(policy_bytes).hexdigest(), intents=intent_rows, plugin_results=result_rows,
        frontier=frontier, prepared_blocks=prepared, exceptions=exceptions,
    )


def build_gcp_dependencies(project_id: str, bucket: str, dataset: str, allowlist: list[str], github_token: str | None):
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        raise ValueError("cloud profile rejects GOOGLE_APPLICATION_CREDENTIALS file paths; use assigned service identity/ADC")
    import google.auth
    from google.cloud import bigquery, storage

    credentials, adc_project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    effective_project = project_id or adc_project
    if not effective_project:
        raise ValueError("GCP project is required and was not discovered through ADC")
    storage_client = storage.Client(project=effective_project, credentials=credentials)
    bq_client = bigquery.Client(project=effective_project, credentials=credentials)
    return (
        GitHubRepositorySource(allowlist, token=github_token),
        GCSRunEvidenceSink(storage_client, bucket),
        BigQueryHistorySink(GoogleBigQueryClient(bq_client), effective_project, dataset),
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("local", "gcp"), default=os.environ.get("REPO_HEALTH_PROFILE", "local"))
    parser.add_argument("--policy", type=Path, help="frozen policy JSON file; alternatively set REPO_HEALTH_POLICY_JSON")
    parser.add_argument("--out", type=Path, default=Path("out/repo-health-runs"))
    parser.add_argument("--validate-only", action="store_true", help="validate the cloud-safe policy contract without network or writes")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.policy:
        snapshot = json.loads(args.policy.read_text(encoding="utf-8"))
    else:
        raw_policy = os.environ.get("REPO_HEALTH_POLICY_JSON", "").strip()
        if not raw_policy:
            raise ValueError("--policy or REPO_HEALTH_POLICY_JSON is required")
        snapshot = json.loads(raw_policy)
    if args.profile == "gcp":
        source_commit = _required_env("SOURCE_COMMIT")
        if str(snapshot.get("producer_commit") or "") != source_commit:
            raise ValueError("frozen policy producer_commit must match SOURCE_COMMIT/image provenance")
    allowlist = list(snapshot.get("repository_allowlist") or [])
    validate_cloud_snapshot(snapshot)
    if args.validate_only:
        print(json.dumps({"status": "valid", "profile": args.profile, "projects": len(snapshot["projects"])}, sort_keys=True))
        return 0
    if args.profile == "gcp":
        source, evidence, history = build_gcp_dependencies(
            os.environ.get("GOOGLE_CLOUD_PROJECT", ""), _required_env("REPO_HEALTH_GCS_BUCKET"),
            os.environ.get("REPO_HEALTH_BQ_DATASET", "repo_health"), allowlist, os.environ.get("GITHUB_TOKEN"),
        )
    else:
        # Local container execution still uses the read-only GitHub source but local persistence.
        source = GitHubRepositorySource(allowlist, token=os.environ.get("GITHUB_TOKEN"))
        evidence = LocalRunEvidenceSink(args.out)
        history = JsonlHistorySink(args.out / "history.jsonl")
    bundle = execute_snapshot(snapshot, repository_source=source)
    evidence_result = evidence.write(bundle)
    history_result = history.append(bundle)
    print(json.dumps({"run": bundle["run"], "evidence": evidence_result, "history": history_result}, sort_keys=True))
    return 0 if bundle["run"]["status"] in {"success", "partial_success", "empty_success"} else 1


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
