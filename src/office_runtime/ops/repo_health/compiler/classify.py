from __future__ import annotations

from typing import Any, Dict

from .spec.load_v0 import load_classify_rules


SEVERITY_MAP = {
    "system_error": "system_error",
    "actionable_failure": "actionable_failure",
    "ineligible": "ineligible",
    "warning": "warning",
    "ok": "ok",
}


def _bucket_prefix(bucket: str) -> str:
    return bucket.split(":", 1)[0] if ":" in bucket else bucket


def _matches_when(when: Dict[str, Any], row: Dict[str, Any]) -> bool:
    bucket = str(row.get("bucket", "")).strip()
    plugin = str(row.get("plugin", "")).strip()
    short_diag = str(row.get("short_diag", "")).strip()

    if "bucket_equals" in when and bucket != when["bucket_equals"]:
        return False
    if "bucket_startswith" in when and not bucket.startswith(when["bucket_startswith"]):
        return False
    if "plugin_equals" in when and plugin != when["plugin_equals"]:
        return False
    if "short_diag_contains_any" in when:
        ok = any(s in short_diag for s in when["short_diag_contains_any"])
        if not ok:
            return False
    return True


def classify_row(row: Dict[str, Any]) -> Dict[str, str]:
    rules = load_classify_rules()
    bucket = str(row.get("bucket", "")).strip()
    plugin = str(row.get("plugin", "")).strip()
    normalized_class = str(row.get("normalized_class", "")).strip()

    severity = SEVERITY_MAP.get(normalized_class, "unknown")

    issue_type = rules.get("default", {}).get("issue_type", "unknown")
    for r in rules.get("rules", []):
        when = r.get("when", {})
        if _matches_when(when, row):
            issue_type = r.get("then", {}).get("issue_type", issue_type)
            break

    bucket_prefix = _bucket_prefix(bucket)
    signature = f"{plugin}|{issue_type}|{bucket_prefix}"

    return {"severity": severity, "issue_type": issue_type, "signature": signature}
