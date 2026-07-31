"""Enums for Phase 6A.4 competing causal hypotheses."""

from __future__ import annotations

from enum import StrEnum


class HypothesisStatus(StrEnum):
    GENERATED = "GENERATED"
    INVALID = "INVALID"
    DUPLICATE = "DUPLICATE"
    CONTRADICTED = "CONTRADICTED"
    INCOMPLETE = "INCOMPLETE"
    READY_FOR_RANKING = "READY_FOR_RANKING"
    REJECTED = "REJECTED"
    DISABLED = "DISABLED"
    FAILED = "FAILED"
    # VERIFIED intentionally omitted — belongs to Phase 6A.7.


class HypothesisRunStatus(StrEnum):
    DISABLED = "DISABLED"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class HypothesisGeneratorType(StrEnum):
    RULE = "RULE"
    GRAPH_PATTERN = "GRAPH_PATTERN"
    LLM = "LLM"
    HYBRID = "HYBRID"


class HypothesisEvidenceRelation(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    MISSING = "MISSING"
    EXPECTED = "EXPECTED"
    FALSIFYING = "FALSIFYING"
    CONTEXT_ONLY = "CONTEXT_ONLY"


class CriticDecision(StrEnum):
    ACCEPT_FOR_RANKING = "ACCEPT_FOR_RANKING"
    ACCEPT_WITH_WARNINGS = "ACCEPT_WITH_WARNINGS"
    INCOMPLETE = "INCOMPLETE"
    CONTRADICTED = "CONTRADICTED"
    REJECT = "REJECT"


class CausalPathValidationStatus(StrEnum):
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    PARTIAL = "PARTIAL"
    INVALID = "INVALID"
    NOT_APPLICABLE = "NOT_APPLICABLE"
