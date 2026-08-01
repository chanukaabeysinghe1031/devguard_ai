"""SQLAlchemy repository for Phase 6A.6 counterfactual remediation persistence."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.counterfactual_remediation.enums import (
    ConstraintSatisfactionStatus,
    ConstraintSeverity,
    ConstraintSourceType,
    CounterfactualCandidateStatus,
    CounterfactualChangeType,
    CounterfactualRemediationRunStatus,
    PreconditionStatus,
    VerifierType,
)
from app.domain.counterfactual_remediation.models import (
    CounterfactualChange,
    CounterfactualPrecondition,
    CounterfactualRemediationCandidate,
    CounterfactualRemediationRun,
    RemediationConstraint,
    RemediationRiskSignal,
    RemediationVerificationRequirement,
)
from app.infrastructure.database.models.counterfactual_remediation import (
    CounterfactualChangeRow,
    CounterfactualRemediationCandidateRow,
    CounterfactualRemediationRunRow,
    RemediationConstraintRow,
    RemediationPreconditionRow,
    RemediationRiskSignalRow,
    RemediationVerificationRequirementRow,
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


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (list, str, int, float, bool)):
        return value
    return str(value)


def _wrap_json_value(value: Any) -> Any:
    """Store arbitrary JSON-serialisable values in JSONB columns."""
    if value is None:
        return None
    if isinstance(value, (dict, list, str, int, float, bool)):
        return value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    return {"value": str(value)}


class CounterfactualRemediationRepositoryImpl:
    """Org-scoped persistence for counterfactual remediation foundation entities.

    Soft-failure safe: write/read helpers log and return None/[] on DB errors
    rather than raising into the analysis pipeline.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ runs

    async def get_run_by_analysis(
        self,
        *,
        organization_id: str | UUID,
        analysis_run_id: str | UUID,
    ) -> CounterfactualRemediationRunRow | None:
        try:
            org_id = _require_uuid(organization_id, field="organization_id")
            analysis_id = _require_uuid(analysis_run_id, field="analysis_run_id")
            return await self._session.scalar(
                select(CounterfactualRemediationRunRow).where(
                    CounterfactualRemediationRunRow.organization_id == org_id,
                    CounterfactualRemediationRunRow.analysis_run_id == analysis_id,
                )
            )
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_get_run_failed error=%s",
                type(exc).__name__,
            )
            return None

    async def create_run(
        self,
        run: CounterfactualRemediationRun,
    ) -> CounterfactualRemediationRun | None:
        """Idempotent get-or-create by (organization_id, analysis_run_id)."""
        try:
            return await self._upsert_run(run)
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_create_run_failed error=%s",
                type(exc).__name__,
            )
            return None

    async def update_run(
        self,
        run: CounterfactualRemediationRun,
    ) -> CounterfactualRemediationRun | None:
        try:
            return await self._upsert_run(run)
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_update_run_failed error=%s",
                type(exc).__name__,
            )
            return None

    async def _upsert_run(
        self,
        run: CounterfactualRemediationRun,
    ) -> CounterfactualRemediationRun:
        org_id = _require_uuid(run.organization_id, field="organization_id")
        analysis_id = _require_uuid(run.analysis_id, field="analysis_id")
        existing = await self._session.scalar(
            select(CounterfactualRemediationRunRow).where(
                CounterfactualRemediationRunRow.organization_id == org_id,
                CounterfactualRemediationRunRow.analysis_run_id == analysis_id,
            )
        )
        status = _enum_str(run.status, CounterfactualRemediationRunStatus.PENDING.value)
        if existing is None:
            row = CounterfactualRemediationRunRow(
                id=_as_uuid(run.id) or uuid.uuid4(),
                organization_id=org_id,
                project_id=_as_uuid(run.project_id),
                incident_id=_as_uuid(run.incident_id),
                analysis_run_id=analysis_id,
                hypothesis_ranking_run_id=run.hypothesis_ranking_run_id,
                status=status,
                selected_hypothesis_ids=list(run.selected_hypothesis_ids),
                selected_hypothesis_count=run.selected_hypothesis_count,
                candidate_count=run.candidate_count,
                safe_candidate_count=run.safe_candidate_count,
                incomplete_candidate_count=run.incomplete_candidate_count,
                rejected_candidate_count=run.rejected_candidate_count,
                started_at=run.started_at,
                completed_at=run.completed_at,
                duration_ms=run.duration_ms,
                context_version=run.context_version,
                constraint_version=run.constraint_version,
                planner_version=run.planner_version,
                template_registry_version=run.template_registry_version,
                snapshot_version=run.snapshot_version,
                configuration_snapshot=dict(run.configuration_snapshot),
                warnings=list(run.warnings),
                errors=list(run.errors),
                limitations=list(run.limitations),
            )
            self._session.add(row)
        else:
            row = existing
            row.project_id = _as_uuid(run.project_id)
            row.incident_id = _as_uuid(run.incident_id)
            row.hypothesis_ranking_run_id = run.hypothesis_ranking_run_id
            row.status = status
            row.selected_hypothesis_ids = list(run.selected_hypothesis_ids)
            row.selected_hypothesis_count = run.selected_hypothesis_count
            row.candidate_count = run.candidate_count
            row.safe_candidate_count = run.safe_candidate_count
            row.incomplete_candidate_count = run.incomplete_candidate_count
            row.rejected_candidate_count = run.rejected_candidate_count
            row.started_at = run.started_at
            row.completed_at = run.completed_at
            row.duration_ms = run.duration_ms
            row.context_version = run.context_version
            row.constraint_version = run.constraint_version
            row.planner_version = run.planner_version
            row.template_registry_version = run.template_registry_version
            row.snapshot_version = run.snapshot_version
            row.configuration_snapshot = dict(run.configuration_snapshot)
            row.warnings = list(run.warnings)
            row.errors = list(run.errors)
            row.limitations = list(run.limitations)

        await self._session.flush()
        run.id = str(row.id)
        return run

    # ------------------------------------------------------------- candidates

    async def create_candidate(
        self,
        candidate: CounterfactualRemediationCandidate,
    ) -> CounterfactualRemediationCandidate | None:
        try:
            row = await self._build_candidate_row(candidate)
            self._session.add(row)
            await self._session.flush()
            candidate.id = str(row.id)
            candidate.remediation_run_id = str(row.remediation_run_id)
            return candidate
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_create_candidate_failed error=%s",
                type(exc).__name__,
            )
            return None

    async def create_candidates_batch(
        self,
        candidates: list[CounterfactualRemediationCandidate],
    ) -> list[CounterfactualRemediationCandidate]:
        if not candidates:
            return []
        saved: list[CounterfactualRemediationCandidate] = []
        try:
            for candidate in candidates:
                row = await self._build_candidate_row(candidate)
                self._session.add(row)
                await self._session.flush()
                candidate.id = str(row.id)
                candidate.remediation_run_id = str(row.remediation_run_id)
                saved.append(candidate)
            return saved
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_create_candidates_batch_failed error=%s count=%s",
                type(exc).__name__,
                len(candidates),
            )
            return saved

    async def _build_candidate_row(
        self,
        candidate: CounterfactualRemediationCandidate,
    ) -> CounterfactualRemediationCandidateRow:
        run_id = _require_uuid(candidate.remediation_run_id, field="remediation_run_id")
        org_id = _require_uuid(candidate.organization_id, field="organization_id")
        analysis_id = _require_uuid(candidate.analysis_id, field="analysis_id")
        change_types = [_enum_str(t) for t in candidate.change_types]
        failure = candidate.expected_failure_condition
        if isinstance(failure, str):
            failure_json: Any = {"text": failure}
        else:
            failure_json = _jsonable(failure)
        return CounterfactualRemediationCandidateRow(
            id=_as_uuid(candidate.id) or uuid.uuid4(),
            remediation_run_id=run_id,
            organization_id=org_id,
            project_id=_as_uuid(candidate.project_id),
            incident_id=_as_uuid(candidate.incident_id),
            analysis_run_id=analysis_id,
            hypothesis_id=_as_uuid(candidate.hypothesis_id),
            candidate_key=candidate.candidate_key or str(uuid.uuid4())[:32],
            title=(candidate.title or "")[:500],
            summary=candidate.summary or "",
            artifact_type=_enum_str(candidate.artifact_type) or None,
            category_code=None,
            affected_artifact_ids=list(candidate.affected_artifact_ids),
            primary_artifact_id=candidate.primary_artifact_id,
            target_paths=list(candidate.target_paths),
            change_types=change_types,
            current_state_snapshot=_jsonable(candidate.current_state_snapshot) or {},
            counterfactual_state_snapshot=_jsonable(candidate.counterfactual_state_snapshot) or {},
            expected_effects=list(candidate.expected_effects),
            expected_preserved_behaviors=list(candidate.expected_preserved_behaviors),
            expected_failure_condition=failure_json,
            assumptions=list(candidate.assumptions),
            limitations=list(candidate.limitations),
            rollback_plan=_jsonable(candidate.rollback_plan) or {},
            risk_summary=[
                _jsonable(item) if not isinstance(item, dict) else dict(item)
                for item in candidate.risk_summary
            ],
            blast_radius_summary=dict(candidate.blast_radius_summary),
            generator_type=candidate.generator_type,
            generator_name=candidate.generator_name,
            generator_version=candidate.generator_version,
            template_id=candidate.template_id,
            template_version=candidate.template_version,
            status=_enum_str(candidate.status, CounterfactualCandidateStatus.DRAFT.value),
        )

    async def list_candidates_by_analysis(
        self,
        *,
        organization_id: str | UUID,
        analysis_run_id: str | UUID,
        hypothesis_id: str | UUID | None = None,
        status: str | None = None,
        artifact_type: str | None = None,
        template_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CounterfactualRemediationCandidateRow]:
        try:
            org_id = _require_uuid(organization_id, field="organization_id")
            analysis_id = _require_uuid(analysis_run_id, field="analysis_run_id")
            stmt = select(CounterfactualRemediationCandidateRow).where(
                CounterfactualRemediationCandidateRow.organization_id == org_id,
                CounterfactualRemediationCandidateRow.analysis_run_id == analysis_id,
            )
            if hypothesis_id is not None:
                hyp_id = _as_uuid(hypothesis_id)
                if hyp_id is not None:
                    stmt = stmt.where(CounterfactualRemediationCandidateRow.hypothesis_id == hyp_id)
            if status:
                stmt = stmt.where(CounterfactualRemediationCandidateRow.status == status)
            if artifact_type:
                stmt = stmt.where(
                    CounterfactualRemediationCandidateRow.artifact_type == artifact_type
                )
            if template_id:
                stmt = stmt.where(CounterfactualRemediationCandidateRow.template_id == template_id)
            stmt = stmt.offset(max(0, offset)).limit(max(1, min(limit, 500)))
            result = await self._session.scalars(stmt)
            return list(result.all())
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_list_candidates_failed error=%s",
                type(exc).__name__,
            )
            return []

    async def get_candidate_by_id(
        self,
        *,
        organization_id: str | UUID,
        candidate_id: str | UUID,
    ) -> CounterfactualRemediationCandidateRow | None:
        try:
            org_id = _require_uuid(organization_id, field="organization_id")
            cand_id = _require_uuid(candidate_id, field="candidate_id")
            return await self._session.scalar(
                select(CounterfactualRemediationCandidateRow).where(
                    CounterfactualRemediationCandidateRow.organization_id == org_id,
                    CounterfactualRemediationCandidateRow.id == cand_id,
                )
            )
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_get_candidate_failed error=%s",
                type(exc).__name__,
            )
            return None

    async def list_constraints_by_analysis(
        self,
        *,
        organization_id: str | UUID,
        analysis_run_id: str | UUID,
        candidate_id: str | UUID | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[RemediationConstraintRow]:
        try:
            org_id = _require_uuid(organization_id, field="organization_id")
            analysis_id = _require_uuid(analysis_run_id, field="analysis_run_id")
            stmt = select(RemediationConstraintRow).where(
                RemediationConstraintRow.organization_id == org_id,
                RemediationConstraintRow.analysis_run_id == analysis_id,
            )
            if candidate_id is not None:
                cand = _as_uuid(candidate_id)
                if cand is not None:
                    stmt = stmt.where(RemediationConstraintRow.candidate_id == cand)
            stmt = stmt.offset(max(0, offset)).limit(max(1, min(limit, 500)))
            return list((await self._session.scalars(stmt)).all())
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_list_constraints_failed error=%s",
                type(exc).__name__,
            )
            return []

    async def list_preconditions_by_candidate(
        self,
        *,
        organization_id: str | UUID,
        analysis_run_id: str | UUID,
        candidate_id: str | UUID,
        limit: int = 200,
        offset: int = 0,
    ) -> list[RemediationPreconditionRow]:
        try:
            org_id = _require_uuid(organization_id, field="organization_id")
            analysis_id = _require_uuid(analysis_run_id, field="analysis_run_id")
            cand = _require_uuid(candidate_id, field="candidate_id")
            stmt = (
                select(RemediationPreconditionRow)
                .where(
                    RemediationPreconditionRow.organization_id == org_id,
                    RemediationPreconditionRow.analysis_run_id == analysis_id,
                    RemediationPreconditionRow.candidate_id == cand,
                )
                .offset(max(0, offset))
                .limit(max(1, min(limit, 500)))
            )
            return list((await self._session.scalars(stmt)).all())
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_list_preconditions_failed error=%s",
                type(exc).__name__,
            )
            return []

    async def list_verification_requirements_by_candidate(
        self,
        *,
        organization_id: str | UUID,
        analysis_run_id: str | UUID,
        candidate_id: str | UUID,
        limit: int = 200,
        offset: int = 0,
    ) -> list[RemediationVerificationRequirementRow]:
        try:
            org_id = _require_uuid(organization_id, field="organization_id")
            analysis_id = _require_uuid(analysis_run_id, field="analysis_run_id")
            cand = _require_uuid(candidate_id, field="candidate_id")
            stmt = (
                select(RemediationVerificationRequirementRow)
                .where(
                    RemediationVerificationRequirementRow.organization_id == org_id,
                    RemediationVerificationRequirementRow.analysis_run_id == analysis_id,
                    RemediationVerificationRequirementRow.candidate_id == cand,
                )
                .offset(max(0, offset))
                .limit(max(1, min(limit, 500)))
            )
            return list((await self._session.scalars(stmt)).all())
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_list_verification_reqs_failed error=%s",
                type(exc).__name__,
            )
            return []

    # --------------------------------------------------------------- changes

    async def create_changes_batch(
        self,
        changes: list[CounterfactualChange],
        *,
        remediation_run_id: str | UUID,
        organization_id: str | UUID,
        analysis_run_id: str | UUID,
        hypothesis_id: str | UUID | None = None,
        candidate_id: str | UUID | None = None,
    ) -> list[CounterfactualChange]:
        if not changes:
            return []
        saved: list[CounterfactualChange] = []
        try:
            run_id = _require_uuid(remediation_run_id, field="remediation_run_id")
            org_id = _require_uuid(organization_id, field="organization_id")
            analysis_id = _require_uuid(analysis_run_id, field="analysis_run_id")
            hyp_id = _as_uuid(hypothesis_id)
            default_cand = _as_uuid(candidate_id)
            for change in changes:
                cand = _as_uuid(change.candidate_id) or default_cand
                if cand is None:
                    continue
                row = CounterfactualChangeRow(
                    id=_as_uuid(change.id) or uuid.uuid4(),
                    remediation_run_id=run_id,
                    candidate_id=cand,
                    organization_id=org_id,
                    analysis_run_id=analysis_id,
                    hypothesis_id=hyp_id,
                    artifact_id=change.artifact_id,
                    artifact_type=_enum_str(change.artifact_type) or None,
                    source_path=change.source_path,
                    line_start=change.line_start,
                    line_end=change.line_end,
                    change_type=_enum_str(
                        change.change_type, CounterfactualChangeType.UNKNOWN.value
                    ),
                    target_entity_id=change.target_entity_id,
                    target_property=change.target_property,
                    original_fragment=change.original_fragment,
                    proposed_fragment=change.proposed_fragment,
                    normalized_diff=change.normalized_diff,
                    expected_effect=change.expected_effect,
                    expected_failure_condition_removed=change.expected_failure_condition_removed,
                    rationale=change.rationale or "",
                    evidence_ids=list(change.evidence_ids),
                    graph_node_ids=list(change.graph_node_ids),
                    graph_edge_ids=list(change.graph_edge_ids),
                    assumptions=list(change.assumptions),
                    limitations=list(change.limitations),
                    change_order=change.change_order,
                    content_hash_before=change.content_hash_before,
                    content_hash_after_candidate=change.content_hash_after_candidate,
                )
                self._session.add(row)
                await self._session.flush()
                change.id = str(row.id)
                change.candidate_id = str(row.candidate_id)
                saved.append(change)
            return saved
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_create_changes_failed error=%s",
                type(exc).__name__,
            )
            return saved

    # ----------------------------------------------------------- constraints

    async def create_constraints_batch(
        self,
        constraints: list[RemediationConstraint],
        *,
        remediation_run_id: str | UUID | None = None,
    ) -> list[RemediationConstraint]:
        if not constraints:
            return []
        saved: list[RemediationConstraint] = []
        try:
            run_id = _as_uuid(remediation_run_id)
            if run_id is None:
                first = constraints[0]
                existing = await self.get_run_by_analysis(
                    organization_id=first.organization_id,
                    analysis_run_id=first.analysis_id,
                )
                if existing is not None:
                    run_id = existing.id
            if run_id is None:
                logger.warning("cf_remediation_constraint_missing_run_id")
                return []
            for constraint in constraints:
                row = RemediationConstraintRow(
                    id=_as_uuid(constraint.id) or uuid.uuid4(),
                    remediation_run_id=run_id,
                    candidate_id=_as_uuid(constraint.candidate_id),
                    organization_id=_require_uuid(
                        constraint.organization_id, field="organization_id"
                    ),
                    project_id=_as_uuid(constraint.project_id),
                    incident_id=_as_uuid(constraint.incident_id),
                    analysis_run_id=_require_uuid(constraint.analysis_id, field="analysis_id"),
                    hypothesis_id=_as_uuid(constraint.hypothesis_id),
                    constraint_key=constraint.constraint_key,
                    constraint_type=_enum_str(constraint.constraint_type, "UNKNOWN"),
                    severity=_enum_str(constraint.severity, ConstraintSeverity.INFORMATIONAL.value),
                    source_type=_enum_str(
                        constraint.source_type, ConstraintSourceType.UNKNOWN.value
                    ),
                    source_artifact_id=constraint.source_artifact_id,
                    source_graph_node_id=constraint.source_graph_node_id,
                    source_graph_edge_id=constraint.source_graph_edge_id,
                    source_evidence_id=constraint.source_evidence_id,
                    source_path=constraint.source_path,
                    line_start=constraint.line_start,
                    line_end=constraint.line_end,
                    description=constraint.description or "",
                    machine_readable_rule=dict(constraint.machine_readable_rule),
                    expected_value=_wrap_json_value(constraint.expected_value),
                    prohibited_value=_wrap_json_value(constraint.prohibited_value),
                    scope=constraint.scope,
                    confidence=float(constraint.confidence or 0.0),
                    extraction_method=constraint.extraction_method,
                    extractor_version=constraint.extractor_version,
                    is_blocking=bool(constraint.is_blocking),
                    is_satisfied=constraint.is_satisfied,
                    satisfaction_status=_enum_str(
                        constraint.satisfaction_status,
                        ConstraintSatisfactionStatus.NOT_EVALUATED.value,
                    ),
                    limitations=list(constraint.limitations),
                )
                self._session.add(row)
                await self._session.flush()
                constraint.id = str(row.id)
                saved.append(constraint)
            return saved
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_create_constraints_failed error=%s",
                type(exc).__name__,
            )
            return saved

    # -------------------------------------------------------- preconditions

    async def create_preconditions_batch(
        self,
        preconditions: list[CounterfactualPrecondition],
        *,
        remediation_run_id: str | UUID,
        organization_id: str | UUID,
        analysis_run_id: str | UUID,
        candidate_id: str | UUID | None = None,
    ) -> list[CounterfactualPrecondition]:
        if not preconditions:
            return []
        saved: list[CounterfactualPrecondition] = []
        try:
            run_id = _require_uuid(remediation_run_id, field="remediation_run_id")
            org_id = _require_uuid(organization_id, field="organization_id")
            analysis_id = _require_uuid(analysis_run_id, field="analysis_run_id")
            default_cand = _as_uuid(candidate_id)
            for pre in preconditions:
                row = RemediationPreconditionRow(
                    id=_as_uuid(pre.id) or uuid.uuid4(),
                    remediation_run_id=run_id,
                    candidate_id=default_cand,
                    organization_id=org_id,
                    analysis_run_id=analysis_id,
                    hypothesis_id=_as_uuid(pre.hypothesis_id),
                    condition_type=pre.condition_type,
                    description=pre.description or "",
                    expected_current_state=_wrap_json_value(pre.expected_current_state),
                    actual_current_state=_wrap_json_value(pre.actual_current_state),
                    status=_enum_str(pre.status, PreconditionStatus.UNKNOWN.value),
                    evidence_ids=list(pre.evidence_ids),
                    artifact_ids=list(pre.artifact_ids),
                    graph_node_ids=list(pre.graph_node_ids),
                    is_required=bool(pre.is_required),
                    limitations=list(pre.limitations),
                )
                self._session.add(row)
                await self._session.flush()
                pre.id = str(row.id)
                saved.append(pre)
            return saved
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_create_preconditions_failed error=%s",
                type(exc).__name__,
            )
            return saved

    # --------------------------------------------- verification requirements

    async def create_verification_requirements_batch(
        self,
        requirements: list[RemediationVerificationRequirement],
        *,
        remediation_run_id: str | UUID,
        organization_id: str | UUID,
        analysis_run_id: str | UUID,
        candidate_id: str | UUID | None = None,
    ) -> list[RemediationVerificationRequirement]:
        if not requirements:
            return []
        saved: list[RemediationVerificationRequirement] = []
        try:
            run_id = _require_uuid(remediation_run_id, field="remediation_run_id")
            org_id = _require_uuid(organization_id, field="organization_id")
            analysis_id = _require_uuid(analysis_run_id, field="analysis_run_id")
            default_cand = _as_uuid(candidate_id)
            for req in requirements:
                cand = _as_uuid(req.candidate_id) or default_cand
                if cand is None:
                    continue
                key = req.requirement_id or str(uuid.uuid4())
                row = RemediationVerificationRequirementRow(
                    id=uuid.uuid4(),
                    remediation_run_id=run_id,
                    candidate_id=cand,
                    organization_id=org_id,
                    analysis_run_id=analysis_id,
                    requirement_key=key[:128],
                    verifier_type=_enum_str(
                        req.verifier_type,
                        VerifierType.COUNTERFACTUAL_FAILURE_CONDITION.value,
                    ),
                    required=bool(req.required),
                    reason=req.reason or "",
                    expected_check=req.expected_check,
                    expected_success_condition=req.expected_success_condition,
                    blocking_on_failure=bool(req.blocking_on_failure),
                    input_artifacts=list(req.input_artifacts),
                    limitations=list(req.limitations),
                )
                self._session.add(row)
                await self._session.flush()
                req.requirement_id = row.requirement_key
                req.candidate_id = str(row.candidate_id)
                saved.append(req)
            return saved
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_create_verification_reqs_failed error=%s",
                type(exc).__name__,
            )
            return saved

    # ---------------------------------------------------------- risk signals

    async def create_risk_signals_batch(
        self,
        signals: list[RemediationRiskSignal],
        *,
        remediation_run_id: str | UUID,
        organization_id: str | UUID,
        analysis_run_id: str | UUID,
        candidate_id: str | UUID,
    ) -> list[RemediationRiskSignal]:
        if not signals:
            return []
        saved: list[RemediationRiskSignal] = []
        try:
            run_id = _require_uuid(remediation_run_id, field="remediation_run_id")
            org_id = _require_uuid(organization_id, field="organization_id")
            analysis_id = _require_uuid(analysis_run_id, field="analysis_run_id")
            cand_id = _require_uuid(candidate_id, field="candidate_id")
            for signal in signals:
                row = RemediationRiskSignalRow(
                    id=uuid.uuid4(),
                    remediation_run_id=run_id,
                    candidate_id=cand_id,
                    organization_id=org_id,
                    analysis_run_id=analysis_id,
                    risk_type=_enum_str(signal.risk_type, "UNKNOWN_SIDE_EFFECT"),
                    severity=_enum_str(signal.severity, ConstraintSeverity.MEDIUM.value),
                    description=signal.description or "",
                    source=signal.source,
                    affected_artifact=signal.affected_artifact,
                    affected_resource=signal.affected_resource,
                    evidence_ids=list(signal.evidence_ids),
                    constraint_ids=list(signal.constraint_ids),
                    mitigation=signal.mitigation,
                    limitations=list(signal.limitations),
                )
                self._session.add(row)
                await self._session.flush()
                saved.append(signal)
            return saved
        except (SQLAlchemyError, ValueError) as exc:
            logger.warning(
                "cf_remediation_create_risk_signals_failed error=%s",
                type(exc).__name__,
            )
            return saved
