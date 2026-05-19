from __future__ import annotations
import pandas as pd
from .io import is_http_url, check_http

REQ_FRONT = ["project_id", "Title"]
REQ_CARRY = ["project_id", "carry", "horizon", "needs", "principal"]

def validate_required(front: pd.DataFrame, carry: pd.DataFrame) -> list[dict]:
    issues = []
    for c in REQ_FRONT:
        if c not in front.columns:
            issues.append({"severity": "error", "sheet": "front_registry", "field": c, "message": "missing required column"})
    for c in REQ_CARRY:
        if c not in carry.columns:
            issues.append({"severity": "error", "sheet": "carry_state", "field": c, "message": "missing required column"})
    return issues

def _has_any(row: dict, cols: list[str]) -> bool:
    for c in cols:
        v = str(row.get(c, "")).strip()
        if v and v.lower() != "nan":
            return True
    return False

def validate_rows(df: pd.DataFrame, strict: bool = False) -> list[dict]:
    issues = []

    if "project_id" in df.columns:
        dup = df[df["project_id"].duplicated(keep=False)]
        for _, r in dup.iterrows():
            issues.append({"severity": "error", "project_id": r.get("project_id",""), "field": "project_id", "message": "duplicate project_id"})

    contextish = ["text", "Context Brief (next unlock)", "Decision (why)", "Narrative (thinking)"]
    linkish = [c for c in df.columns if any(x in c.lower() for x in ["link", "path", "slug", "repo"])]
    runbookish = [c for c in df.columns if "runbook" in c.lower()]

    for _, r in df.iterrows():
        row = r.to_dict()
        pid = row.get("project_id", "")
        carry = str(row.get("carry", "")).strip()
        principal = str(row.get("principal", "")).strip()
        horizon = str(row.get("horizon", "")).strip()

        for field in ["carry", "horizon", "needs", "principal"]:
            if field in df.columns and not str(row.get(field, "")).strip():
                sev = "error" if strict else "warning"
                issues.append({"severity": sev, "project_id": pid, "field": field, "message": "blank value"})

        if carry in {"Active", "Support-needed", "Escalate"} and not str(row.get("Title", "")).strip():
            issues.append({"severity": "warning", "project_id": pid, "field": "Title", "message": "blank title on live posture"})

        if carry == "Support-needed" and not (_has_any(row, contextish) or _has_any(row, linkish)):
            issues.append({"severity": "warning", "project_id": pid, "field": "context/link", "message": "support-needed item lacks context or links"})

        if carry == "Active" and not (_has_any(row, contextish) or _has_any(row, runbookish)):
            issues.append({"severity": "warning", "project_id": pid, "field": "context/runbook", "message": "active item lacks note, context brief, or runbook"})

        if principal == "Required" and not horizon:
            sev = "error" if strict else "warning"
            issues.append({"severity": sev, "project_id": pid, "field": "horizon", "message": "required item lacks horizon"})

        for k, v in row.items():
            if "link" in str(k).lower():
                v = str(v).strip()
                if not v or v.lower() == "nan":
                    continue
                if is_http_url(v):
                    ok, note = check_http(v)
                    if not ok:
                        issues.append({"severity": "warning", "project_id": pid, "field": k, "message": f"broken link ({note})"})

    return issues
