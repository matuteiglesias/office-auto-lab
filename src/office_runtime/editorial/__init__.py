"""Governed public-projection capabilities.

This package owns bounded editorial execution inside Office Auto Lab. It does not
own the user's durable editorial constitution, source-product semantics, or the
truth of upstream scientific artifacts.
"""

from .contracts import (
    ACTIVITY_EVIDENCE_SCHEMA,
    ANGLE_SCHEMA,
    ARGENTINA_ECON_RELATIONS,
    CANDIDATE_SCHEMA,
    DAILY_BATCH_SCHEMA,
    RUN_BUNDLE_SCHEMA,
    STORY_CLUSTER_SCHEMA,
    ActivityEvidence,
    AngleCard,
    ContractError,
    DailyBatch,
    DevCandidate,
    EditorialRunBundle,
    PolicyIdentity,
    StoryCluster,
    load_projection_profiles,
    validate_activity_evidence,
    validate_angle,
    validate_candidate,
    validate_daily_batch,
    validate_dev_candidate,
    validate_policy_identity,
    validate_projection_profile,
    validate_story_cluster,
)

__all__ = [
    "ACTIVITY_EVIDENCE_SCHEMA",
    "ANGLE_SCHEMA",
    "ARGENTINA_ECON_RELATIONS",
    "CANDIDATE_SCHEMA",
    "DAILY_BATCH_SCHEMA",
    "RUN_BUNDLE_SCHEMA",
    "STORY_CLUSTER_SCHEMA",
    "ActivityEvidence",
    "AngleCard",
    "ContractError",
    "DailyBatch",
    "DevCandidate",
    "EditorialRunBundle",
    "PolicyIdentity",
    "StoryCluster",
    "load_projection_profiles",
    "validate_activity_evidence",
    "validate_angle",
    "validate_candidate",
    "validate_daily_batch",
    "validate_dev_candidate",
    "validate_policy_identity",
    "validate_projection_profile",
    "validate_story_cluster",
]
