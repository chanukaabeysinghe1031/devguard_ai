"""SQLAlchemy repository for Phase 6A.6 Part 3 verifier persistence."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.counterfactual_remediation.verification_enums import (
    VerificationConsensusStatus,
    VerificationRunStatus,
    VerifierResultStatus,
)
from app.domain.counterfactual_remediation.verification_models import (
    VerificationConsensus,
    VerificationRun,
    VerifierResult,
)
from app.domain.counterfactual_remediation.verification_versions import (
    CONSENSUS_ENGINE_VERSION,
    TEMP_WORKSPACE_VERSION,
    VERIFIER_ENGINE_VERSION,
)
from app.infrastructure.database.models.remediation_verification import (
    RemediationVerificationResultRow,
    RemediationVerificationRunRow,
)

logger = logging.getLogger(__name__)


def _enum_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value.value if hasattr(value, "value") else value)


def _as_uuid(value: str | UUID | None) -> UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _require_uuid(value: str | UUID, *, field: str) -> UUID:
    parsed = _as_uuid(value)
    if parsed is None:
        raise ValueError(f"Invalid UUID for {field}")
    return parsed


def _duration_int(value: float | int | None) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


class RemediationVerificationRepositoryImpl:
    """Org-scoped CRUD for verification runs/results. Soft-fail safe."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_run(self, run: VerificationRun) -> VerificationRun | None:
        try:
            org_id = _require_uuid(run.organization_id, field="organization_id")
            analysis_id = _require_uuid(run.analysis_id, field="analysis_id")
            candidate_id = _require_uuid(
                run.candidate_id or "", field="candidate_id"
            )
            run_id = _as_uuid(run.id) or uuid.uuid4()

            existing = await self._session.scalar(
                select(RemediationVerificationRunRow).where(
                    RemediationVerificationRunRow.organization_id == org_id,
                    RemediationVerificationRunRow.analysis_run_id == analysis_id,
                    RemediationVerificationRunRow.candidate_id == candidate_id,
                )
            )

            consensus = run.consensus
            consensus_status = (
                _enum_str(consensus.status) if consensus is not None else None
            )
            snapshot = {
                "selected_verifiers": list(run.selected_verifiers),
                "hypothesis_id": run.hypothesis_id,
                "rollback_parse_status": run.rollback_parse_status,
                "consensus": consensus.to_dict() if consensus is not None else None,
                "limitations": list(run.limitations),
            }
            errors: list[Any] = []
            if run.error_message:
                errors.append(run.error_message)

            if existing is None:
                row = RemediationVerificationRunRow(
                    id=run_id,
                    organization_id=org_id,
                    project_id=_as_uuid(run.project_id),
                    incident_id=_as_uuid(run.incident_id),
                    analysis_run_id=analysis_id,
                    remediation_run_id=_as_uuid(run.remediation_run_id),
                    candidate_id=candidate_id,
                    status=_enum_str(run.status, VerificationRunStatus.PENDING.value),
                    consensus_status=consensus_status,
                    configuration_snapshot=snapshot,
                    warnings=list(run.warnings),
                    errors=errors,
                    duration_ms=_duration_int(run.duration_ms),
                    engine_version=run.engine_version or VERIFIER_ENGINE_VERSION,
                    consensus_version=(
                        consensus.version if consensus is not None else CONSENSUS_ENGINE_VERSION
                    ),
                    workspace_version=TEMP_WORKSPACE_VERSION,
                    started_at=run.created_at,
                    completed_at=run.completed_at,
                )
                self._session.add(row)
            else:
                row = existing
                row.status = _enum_str(run.status, VerificationRunStatus.PENDING.value)
                row.consensus_status = consensus_status
                row.configuration_snapshot = snapshot
                row.warnings = list(run.warnings)
                row.errors = errors
                row.duration_ms = _duration_int(run.duration_ms)
                row.engine_version = run.engine_version or VERIFIER_ENGINE_VERSION
                row.consensus_version = (
                    consensus.version if consensus is not None else CONSENSUS_ENGINE_VERSION
                )
                row.workspace_version = TEMP_WORKSPACE_VERSION
                row.remediation_run_id = _as_uuid(run.remediation_run_id)
                row.completed_at = run.completed_at
                row.updated_at = datetime.now(UTC)
                run_id = row.id
                # Replace prior results for this run (latest overwrite).
                await self._session.execute(
                    delete(RemediationVerificationResultRow).where(
                        RemediationVerificationResultRow.verification_run_id == row.id
                    )
                )

            await self._session.flush()

            for result in run.results:
                await self._upsert_result(
                    verification_run_id=run_id,
                    organization_id=org_id,
                    analysis_run_id=analysis_id,
                    candidate_id=candidate_id,
                    result=result,
                )
            await self._session.flush()
            run.id = str(run_id)
            return run
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "remediation_verification_upsert_run_failed",
                extra={"error": type(exc).__name__},
            )
            return None

    async def _upsert_result(
        self,
        *,
        verification_run_id: UUID,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID | None,
        result: VerifierResult,
    ) -> None:
        tool_available = True
        status = _enum_str(result.status, VerifierResultStatus.UNKNOWN.value)
        if status == VerifierResultStatus.UNAVAILABLE.value:
            tool_available = False
        meta = dict(result.metadata or {})
        if "tool_available" in meta:
            tool_available = bool(meta.get("tool_available"))
        artifacts = meta.get("artifacts_checked")
        if not isinstance(artifacts, list):
            artifacts = []
        warnings = list(meta.get("warnings") or [])
        errors = list(meta.get("errors") or [])
        if status == VerifierResultStatus.FAIL.value and result.message:
            errors = errors or [result.message]

        row = RemediationVerificationResultRow(
            id=uuid.uuid4(),
            verification_run_id=verification_run_id,
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
            verifier_name=result.verifier_name,
            verifier_version=result.verifier_version,
            status=status,
            duration_ms=_duration_int(result.duration_ms),
            warnings=warnings,
            errors=errors,
            stdout_truncated=result.stdout_excerpt,
            stderr_truncated=result.stderr_excerpt,
            artifacts_checked=artifacts,
            tool_available=tool_available,
            returncode=result.returncode,
            message=result.message or None,
            findings=list(result.findings),
            metadata_json=meta,
        )
        self._session.add(row)

    async def list_runs_by_analysis(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> list[RemediationVerificationRunRow]:
        try:
            result = await self._session.scalars(
                select(RemediationVerificationRunRow)
                .where(
                    RemediationVerificationRunRow.organization_id == organization_id,
                    RemediationVerificationRunRow.analysis_run_id == analysis_run_id,
                )
                .order_by(RemediationVerificationRunRow.created_at.desc())
            )
            return list(result.all())
        except SQLAlchemyError as exc:
            logger.warning(
                "remediation_verification_list_runs_failed",
                extra={"error": type(exc).__name__},
            )
            return []

    async def get_run(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        run_id: UUID,
    ) -> RemediationVerificationRunRow | None:
        try:
            return await self._session.scalar(
                select(RemediationVerificationRunRow).where(
                    RemediationVerificationRunRow.organization_id == organization_id,
                    RemediationVerificationRunRow.analysis_run_id == analysis_run_id,
                    RemediationVerificationRunRow.id == run_id,
                )
            )
        except SQLAlchemyError as exc:
            logger.warning(
                "remediation_verification_get_run_failed",
                extra={"error": type(exc).__name__},
            )
            return None

    async def get_run_for_candidate(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> RemediationVerificationRunRow | None:
        try:
            return await self._session.scalar(
                select(RemediationVerificationRunRow).where(
                    RemediationVerificationRunRow.organization_id == organization_id,
                    RemediationVerificationRunRow.analysis_run_id == analysis_run_id,
                    RemediationVerificationRunRow.candidate_id == candidate_id,
                )
            )
        except SQLAlchemyError as exc:
            logger.warning(
                "remediation_verification_get_candidate_run_failed",
                extra={"error": type(exc).__name__},
            )
            return None

    async def list_results_by_analysis(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID | None = None,
        verifier_name: str | None = None,
    ) -> list[RemediationVerificationResultRow]:
        try:
            stmt = select(RemediationVerificationResultRow).where(
                RemediationVerificationResultRow.organization_id == organization_id,
                RemediationVerificationResultRow.analysis_run_id == analysis_run_id,
            )
            if candidate_id is not None:
                stmt = stmt.where(
                    RemediationVerificationResultRow.candidate_id == candidate_id
                )
            if verifier_name:
                stmt = stmt.where(
                    RemediationVerificationResultRow.verifier_name == verifier_name
                )
            stmt = stmt.order_by(RemediationVerificationResultRow.created_at.desc())
            result = await self._session.scalars(stmt)
            return list(result.all())
        except SQLAlchemyError as exc:
            logger.warning(
                "remediation_verification_list_results_failed",
                extra={"error": type(exc).__name__},
            )
            return []

    async def list_results_for_run(
        self,
        *,
        organization_id: UUID,
        verification_run_id: UUID,
    ) -> list[RemediationVerificationResultRow]:
        try:
            result = await self._session.scalars(
                select(RemediationVerificationResultRow)
                .where(
                    RemediationVerificationResultRow.organization_id == organization_id,
                    RemediationVerificationResultRow.verification_run_id
                    == verification_run_id,
                )
                .order_by(RemediationVerificationResultRow.verifier_name.asc())
            )
            return list(result.all())
        except SQLAlchemyError as exc:
            logger.warning(
                "remediation_verification_list_run_results_failed",
                extra={"error": type(exc).__name__},
            )
            return []


def consensus_from_row(row: RemediationVerificationRunRow) -> VerificationConsensus | None:
    snapshot = dict(row.configuration_snapshot or {})
    raw = snapshot.get("consensus")
    if not isinstance(raw, dict):
        if row.consensus_status:
            return VerificationConsensus(
                status=VerificationConsensusStatus(row.consensus_status)
                if row.consensus_status
                in {s.value for s in VerificationConsensusStatus}
                else row.consensus_status,
                candidate_id=str(row.candidate_id),
                version=row.consensus_version or CONSENSUS_ENGINE_VERSION,
            )
        return None
    return VerificationConsensus(
        status=raw.get("status") or row.consensus_status or "INCONCLUSIVE",
        candidate_id=raw.get("candidate_id") or str(row.candidate_id),
        artifact_family=raw.get("artifact_family"),
        required_verifiers=list(raw.get("required_verifiers") or []),
        passed_verifiers=list(raw.get("passed_verifiers") or []),
        failed_verifiers=list(raw.get("failed_verifiers") or []),
        warning_verifiers=list(raw.get("warning_verifiers") or []),
        unavailable_verifiers=list(raw.get("unavailable_verifiers") or []),
        rationale=str(raw.get("rationale") or ""),
        blocking_failures=list(raw.get("blocking_failures") or []),
        version=str(raw.get("version") or row.consensus_version or CONSENSUS_ENGINE_VERSION),
        limitations=list(raw.get("limitations") or []),
    )
