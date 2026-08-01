"""Enums for Phase 6A.6 Part 3 independent verifier engine."""

from __future__ import annotations

from enum import StrEnum


class VerifierResultStatus(StrEnum):
    """Outcome of a single verifier adapter execution."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class VerificationConsensusStatus(StrEnum):
    """Deterministic multi-verifier consensus (never LLM-derived)."""

    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNAVAILABLE = "UNAVAILABLE"


class VerificationRunStatus(StrEnum):
    """Lifecycle status of a verification run over one or more candidates."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    DISABLED = "DISABLED"
    TIMED_OUT = "TIMED_OUT"
