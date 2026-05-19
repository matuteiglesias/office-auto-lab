# plugins/base.py
from __future__ import annotations

from typing import Any, Dict, Optional, List


# Plugin output contract (v1)
# A plugin MUST return a dict with at least:
#   - status: "PASS"|"FAIL"|"WARN"|"NA"|"ERROR"
#   - message: short human diagnostic
# Optional but encouraged:
#   - bucket: machine-friendly category (small vocabulary per plugin)
#   - evidence: list[str] compact pointers
#   - meta: dict JSON-serializable structured details
#
# Runner normalization should treat unknown / malformed outputs as system_error.

def result(
    *,
    status: str,
    message: str,
    bucket: Optional[str] = None,
    evidence: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "status": str(status).upper().strip(),
        "message": (message or "").strip(),
    }
    if bucket is not None:
        out["bucket"] = str(bucket).strip()
    if evidence is not None:
        out["evidence"] = evidence
    if meta is not None:
        out["meta"] = meta
    return out


class BasePlugin:
    name: str = "base" 
    version: str = "1.0.0"

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("plugin must implement run(ctx) -> dict")