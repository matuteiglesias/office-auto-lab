"""Governed public-projection capabilities.

This package owns bounded editorial execution inside Office Auto Lab. It does not
own the user's durable editorial constitution, source-product semantics, or the
truth of upstream scientific artifacts.
"""

from .contracts import (
    ARGENTINA_ECON_RELATIONS,
    ContractError,
    load_projection_profiles,
    validate_candidate,
    validate_projection_profile,
)

__all__ = [
    "ARGENTINA_ECON_RELATIONS",
    "ContractError",
    "load_projection_profiles",
    "validate_candidate",
    "validate_projection_profile",
]
