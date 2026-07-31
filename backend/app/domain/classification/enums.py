"""Enums for Phase 6A.3 hierarchical classification."""

from __future__ import annotations

from enum import StrEnum


class ClassificationStatus(StrEnum):
    KNOWN = "KNOWN"
    KNOWN_LOW_CONFIDENCE = "KNOWN_LOW_CONFIDENCE"
    UNCERTAIN = "UNCERTAIN"
    UNKNOWN = "UNKNOWN"
    CONFLICTED = "CONFLICTED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


class OpenSetStatus(StrEnum):
    KNOWN = "KNOWN"
    UNCERTAIN = "UNCERTAIN"
    UNKNOWN = "UNKNOWN"


class AgreementLevel(StrEnum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    SEVERE = "SEVERE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ClassificationConflictType(StrEnum):
    SAME_DOMAIN_DIFFERENT_SUBCATEGORY = "SAME_DOMAIN_DIFFERENT_SUBCATEGORY"
    DIFFERENT_DOMAIN = "DIFFERENT_DOMAIN"
    RULE_VS_MODEL = "RULE_VS_MODEL"
    LOG_VS_GRAPH = "LOG_VS_GRAPH"
    TEMPORAL_VS_SEMANTIC = "TEMPORAL_VS_SEMANTIC"
    KNOWN_VS_UNKNOWN = "KNOWN_VS_UNKNOWN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NONE = "NONE"


class DisagreementRecommendedAction(StrEnum):
    ACCEPT = "ACCEPT"
    LOWER_CONFIDENCE = "LOWER_CONFIDENCE"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    TRIGGER_TARGETED_RETRIEVAL_LATER = "TRIGGER_TARGETED_RETRIEVAL_LATER"
    MARK_UNCERTAIN = "MARK_UNCERTAIN"
    MARK_UNKNOWN = "MARK_UNKNOWN"


# Alias kept for clarity in docs/APIs.
ClassificationRecommendedAction = DisagreementRecommendedAction
