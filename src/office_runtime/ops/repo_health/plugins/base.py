# plugins/base.py
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


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


class PluginCapability(str, Enum):
    LOCAL_ONLY = "local_only"
    REMOTE_READ = "remote_read"
    REMOTE_EXECUTE = "remote_execute"


_SIDE_EFFECTS_BY_CAPABILITY = {
    PluginCapability.LOCAL_ONLY: "local-only; no remote mutation authority",
    PluginCapability.REMOTE_READ: "remote read-only; no remote mutation authority",
    PluginCapability.REMOTE_EXECUTE: "bounded execution permitted; caller policy and dry-run controls remain authoritative",
}


class BasePlugin:
    """Base contract for one bounded Repo Health capability.

    The descriptor is intentionally repo-local.  It makes the capability seam
    inspectable without creating a universal workflow or plugin schema.
    """

    name: str = "base"
    version: str = "1.0.0"
    capability: PluginCapability | str = PluginCapability.LOCAL_ONLY

    # Common contracts can be overridden by a plugin when its real seam differs.
    input_contract: tuple[str, ...] = ("repo_health.context@1",)
    output_contract: tuple[str, ...] = ("repo_health.plugin-result@1",)
    failure_behavior: str = (
        "return a normalized PASS/FAIL/WARN/NA/ERROR result; malformed plugin output is system_error"
    )
    evidence_contract: tuple[str, ...] = ("result.evidence", "result.meta")

    def capability_descriptor(self) -> Dict[str, Any]:
        """Describe the stable execution seam without exposing implementation internals."""
        capability = PluginCapability(self.capability)
        descriptor = {
            "capability_id": f"repo_health.{self.name}@{self.version}",
            "inputs": list(self.input_contract),
            "outputs": list(self.output_contract),
            "side_effects": _SIDE_EFFECTS_BY_CAPABILITY[capability],
            "failure_behavior": self.failure_behavior,
            "evidence": list(self.evidence_contract),
        }
        self.validate_capability_descriptor(descriptor)
        return descriptor

    @staticmethod
    def validate_capability_descriptor(descriptor: Dict[str, Any]) -> None:
        """Fail closed on incomplete capability metadata."""
        required_scalar = ("capability_id", "side_effects", "failure_behavior")
        for field in required_scalar:
            if not isinstance(descriptor.get(field), str) or not descriptor[field].strip():
                raise ValueError(f"capability descriptor requires non-empty {field!r}")
        for field in ("inputs", "outputs", "evidence"):
            value = descriptor.get(field)
            if not isinstance(value, list) or not value or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                raise ValueError(f"capability descriptor requires non-empty string list {field!r}")

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("plugin must implement run(ctx) -> dict")
