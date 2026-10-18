"""Read-only public X activity observer SIDECAR (Phase A, no publication)."""

from .normalize import normalize_page
from .qualification import qualify

__all__ = ["normalize_page", "qualify"]
