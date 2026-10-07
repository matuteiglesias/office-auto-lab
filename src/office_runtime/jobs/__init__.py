"""Read-only job-search preparation sidecar."""

from .action_packet import CONTRACT, JobPacketError, compile_action_packet

__all__ = ["CONTRACT", "JobPacketError", "compile_action_packet"]
