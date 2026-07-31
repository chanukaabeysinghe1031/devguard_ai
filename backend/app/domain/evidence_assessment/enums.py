"""Enums for Phase 6A.5 Part 3 evidence assessment (candidates only)."""

from __future__ import annotations

from enum import StrEnum


class EvidenceAssessmentType(StrEnum):
    """Candidate evidence labels — never proven/verified truth values."""

    SUPPORT_CANDIDATE = "SUPPORT_CANDIDATE"
    CONTRADICTION_CANDIDATE = "CONTRADICTION_CANDIDATE"
    CONTEXT_ONLY = "CONTEXT_ONLY"
    INSUFFICIENT = "INSUFFICIENT"
    AMBIGUOUS = "AMBIGUOUS"
    UNRELATED = "UNRELATED"


class EvidenceSufficiencyLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class CandidateSelectionStatus(StrEnum):
    TOP_CANDIDATE = "TOP_CANDIDATE"
    TOP_N = "TOP_N"
    UNKNOWN = "UNKNOWN"
    TIE = "TIE"
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
