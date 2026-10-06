"""Editorial intelligence seam for dev staging.

Core validation and batch compilation deliberately do not import Google ADK.
The provider adapter lives in :mod:`adk_adapter` and is optional at import time.
"""

from .batch import (
    BatchCompilation,
    BatchConfig,
    FallbackPool,
    compile_daily_batch,
    failed_daily_batch,
    semantic_fingerprint,
)
from .interfaces import EditorialIntelligence, IntelligenceResult, ModelStageOutput
from .validation import IntelligenceContractError, validate_angle_cards, validate_judgments

__all__ = [
    "BatchCompilation",
    "BatchConfig",
    "EditorialIntelligence",
    "FallbackPool",
    "IntelligenceContractError",
    "IntelligenceResult",
    "ModelStageOutput",
    "compile_daily_batch",
    "failed_daily_batch",
    "semantic_fingerprint",
    "validate_angle_cards",
    "validate_judgments",
]
