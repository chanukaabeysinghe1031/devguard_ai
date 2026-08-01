"""Domain contracts for Phase 6A.6 Part 3 independent verifier engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.counterfactual_remediation.verification_enums import (
    VerificationConsensusStatus,
    VerificationRunStatus,
    VerifierResultStatus,
)
from app.domain.counterfactual_remediation.verification_versions import (
    CONSENSUS_ENGINE_VERSION,
    VERIFIER_ENGINE_VERSION,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _enum_value(value: Any) -> Any:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else value


def _maybe_to_dict(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    return value


def _list_to_dict(items: list[Any]) -> list[Any]:
    return [_maybe_to_dict(item) for item in items]


@dataclass(slots=True)
class VerifierResult:
    """Outcome of one verifier adapter against a temporary counterfactual workspace."""

    verifier_name: str
    verifier_version: str
    status: VerifierResultStatus | str = VerifierResultStatus.UNKNOWN
    candidate_id: str | None = None
    required: bool = True
    message: str = ""
    findings: list[str] = field(default_factory=list)
    stdout_excerpt: str | None = None
    stderr_excerpt: str | None = None
    returncode: int | None = None
    duration_ms: float | None = None
    tool_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(
        default_factory=lambda: [
            "verifier_validates_temporary_counterfactual_state_only",
            "pass_is_not_proven_root_cause_fix",
            "candidates_are_not_applied",
        ]
    )
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifier_name": self.verifier_name,
            "verifier_version": self.verifier_version,
            "status": _enum_value(self.status),
            "candidate_id": self.candidate_id,
            "required": self.required,
            "message": self.message,
            "findings": list(self.findings),
            "stdout_excerpt": self.stdout_excerpt,
            "stderr_excerpt": self.stderr_excerpt,
            "returncode": self.returncode,
            "duration_ms": self.duration_ms,
            "tool_path": self.tool_path,
            "metadata": dict(self.metadata),
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class VerificationConsensus:
    """Deterministic consensus over verifier results for one candidate."""

    status: VerificationConsensusStatus | str = VerificationConsensusStatus.INCONCLUSIVE
    candidate_id: str | None = None
    artifact_family: str | None = None
    required_verifiers: list[str] = field(default_factory=list)
    passed_verifiers: list[str] = field(default_factory=list)
    failed_verifiers: list[str] = field(default_factory=list)
    warning_verifiers: list[str] = field(default_factory=list)
    unavailable_verifiers: list[str] = field(default_factory=list)
    rationale: str = ""
    blocking_failures: list[str] = field(default_factory=list)
    version: str = CONSENSUS_ENGINE_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "consensus_is_not_llm_derived",
            "verified_means_temporary_state_checks_passed",
            "candidates_are_not_applied",
        ]
    )
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": _enum_value(self.status),
            "candidate_id": self.candidate_id,
            "artifact_family": self.artifact_family,
            "required_verifiers": list(self.required_verifiers),
            "passed_verifiers": list(self.passed_verifiers),
            "failed_verifiers": list(self.failed_verifiers),
            "warning_verifiers": list(self.warning_verifiers),
            "unavailable_verifiers": list(self.unavailable_verifiers),
            "rationale": self.rationale,
            "blocking_failures": list(self.blocking_failures),
            "version": self.version,
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class VerificationRun:
    """One verification pipeline execution for a candidate (or stage summary)."""

    id: str
    organization_id: str
    project_id: str
    incident_id: str
    analysis_id: str
    remediation_run_id: str | None = None
    candidate_id: str | None = None
    hypothesis_id: str | None = None
    status: VerificationRunStatus | str = VerificationRunStatus.PENDING
    consensus: VerificationConsensus | None = None
    results: list[VerifierResult] = field(default_factory=list)
    workspace_root: str | None = None
    selected_verifiers: list[str] = field(default_factory=list)
    rollback_parse_status: str | None = None
    warnings: list[str] = field(default_factory=list)
    error_message: str | None = None
    duration_ms: float | None = None
    engine_version: str = VERIFIER_ENGINE_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "verification_does_not_apply_changes",
            "verification_does_not_prove_root_cause",
            "candidates_remain_unverified_until_consensus",
        ]
    )
    created_at: datetime = field(default_factory=_utc_now)
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "incident_id": self.incident_id,
            "analysis_id": self.analysis_id,
            "remediation_run_id": self.remediation_run_id,
            "candidate_id": self.candidate_id,
            "hypothesis_id": self.hypothesis_id,
            "status": _enum_value(self.status),
            "consensus": _maybe_to_dict(self.consensus),
            "results": _list_to_dict(self.results),
            "workspace_root": self.workspace_root,
            "selected_verifiers": list(self.selected_verifiers),
            "rollback_parse_status": self.rollback_parse_status,
            "warnings": list(self.warnings),
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "engine_version": self.engine_version,
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass(slots=True)
class VerificationReport:
    """Aggregate report for a Part 3 verifier-engine stage."""

    organization_id: str
    project_id: str
    incident_id: str
    analysis_id: str
    remediation_run_id: str | None = None
    status: VerificationRunStatus | str = VerificationRunStatus.PENDING
    runs: list[VerificationRun] = field(default_factory=list)
    candidate_ids_selected: list[str] = field(default_factory=list)
    candidate_ids_verified: list[str] = field(default_factory=list)
    candidate_ids_failed: list[str] = field(default_factory=list)
    candidate_ids_inconclusive: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    engine_version: str = VERIFIER_ENGINE_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "report_summarises_temporary_workspace_checks_only",
            "llms_are_not_verifiers",
            "candidates_are_not_applied",
        ]
    )
    created_at: datetime = field(default_factory=_utc_now)
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "incident_id": self.incident_id,
            "analysis_id": self.analysis_id,
            "remediation_run_id": self.remediation_run_id,
            "status": _enum_value(self.status),
            "runs": _list_to_dict(self.runs),
            "candidate_ids_selected": list(self.candidate_ids_selected),
            "candidate_ids_verified": list(self.candidate_ids_verified),
            "candidate_ids_failed": list(self.candidate_ids_failed),
            "candidate_ids_inconclusive": list(self.candidate_ids_inconclusive),
            "warnings": list(self.warnings),
            "engine_version": self.engine_version,
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
