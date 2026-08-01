"""Debug/read APIs for Phase 6A.4 competing causal hypotheses."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select

from app.application.services.analysis_run_service import AnalysisRunService
from app.domain.exceptions.business import ResourceNotFoundError
from app.infrastructure.database.models.causal_hypotheses import (
    CausalHypothesisRow,
    CausalHypothesisRunRow,
    HypothesisCriticResultRow,
    HypothesisEvidenceLinkRow,
)
from app.schemas.phase6a4 import (
    CausalHypothesisDetailResponse,
    CausalHypothesisListItem,
    CausalHypothesisListResponse,
    CausalHypothesisRunResponse,
    HypothesisCausalPathResponse,
    HypothesisCriticResponse,
    HypothesisEvidenceLinkItem,
    HypothesisEvidenceListResponse,
)


class Phase6A4HypothesisService:
    def __init__(self, run_service: AnalysisRunService) -> None:
        self._runs = run_service
        self._session = run_service._session  # noqa: SLF001

    async def get_run(
        self, *, organization_id: UUID, analysis_run_id: UUID
    ) -> CausalHypothesisRunResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._session.scalar(
            select(CausalHypothesisRunRow).where(
                CausalHypothesisRunRow.organization_id == organization_id,
                CausalHypothesisRunRow.analysis_run_id == analysis_run_id,
            )
        )
        if row is None:
            raise ResourceNotFoundError("Hypothesis generation run not found.")
        return CausalHypothesisRunResponse(
            id=row.id,
            analysis_run_id=row.analysis_run_id,
            status=row.status,
            deterministic_count=row.deterministic_count,
            llm_count=row.llm_count,
            invalid_reference_count=row.invalid_reference_count,
            duplicate_removed_count=row.duplicate_removed_count,
            generator_version=row.generator_version,
            prompt_version=row.prompt_version,
            duration_ms=row.duration_ms,
            warnings=[str(x) for x in (row.warnings or [])],
            truncation_notes=[str(x) for x in (row.truncation_notes or [])],
            created_at=row.created_at,
        )

    async def list_hypotheses(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        category: str | None = None,
        status: str | None = None,
        generator_type: str | None = None,
        affected_artifact: str | None = None,
    ) -> CausalHypothesisListResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        filters = [
            CausalHypothesisRow.organization_id == organization_id,
            CausalHypothesisRow.analysis_run_id == analysis_run_id,
        ]
        if category:
            filters.append(CausalHypothesisRow.category_code == category)
        if status:
            filters.append(CausalHypothesisRow.status == status)
        if generator_type:
            filters.append(CausalHypothesisRow.generator_type == generator_type)
        if affected_artifact:
            filters.append(CausalHypothesisRow.affected_path == affected_artifact)
        rows = list(
            (
                await self._session.scalars(
                    select(CausalHypothesisRow)
                    .where(*filters)
                    .order_by(CausalHypothesisRow.rank_placeholder.asc())
                )
            ).all()
        )
        items: list[CausalHypothesisListItem] = []
        for r in rows:
            support = int(
                await self._session.scalar(
                    select(func.count())
                    .select_from(HypothesisEvidenceLinkRow)
                    .where(
                        HypothesisEvidenceLinkRow.hypothesis_id == r.id,
                        HypothesisEvidenceLinkRow.relation == "SUPPORTS",
                    )
                )
                or 0
            )
            contra = int(
                await self._session.scalar(
                    select(func.count())
                    .select_from(HypothesisEvidenceLinkRow)
                    .where(
                        HypothesisEvidenceLinkRow.hypothesis_id == r.id,
                        HypothesisEvidenceLinkRow.relation == "CONTRADICTS",
                    )
                )
                or 0
            )
            critic = await self._session.scalar(
                select(HypothesisCriticResultRow).where(
                    HypothesisCriticResultRow.hypothesis_id == r.id
                )
            )
            items.append(
                CausalHypothesisListItem(
                    id=r.id,
                    hypothesis_key=r.hypothesis_key,
                    rank_placeholder=r.rank_placeholder,
                    category_code=r.category_code,
                    title=r.title,
                    causal_claim=r.causal_claim,
                    status=r.status,
                    generator_type=r.generator_type,
                    template_id=r.template_id,
                    generation_prior_score=r.generation_prior_score,
                    generation_confidence=r.generation_confidence,
                    path_validation_status=r.path_validation_status,
                    affected_path=r.affected_path,
                    supporting_evidence_count=support,
                    contradicting_evidence_count=contra,
                    missing_evidence=[str(x) for x in (r.missing_evidence or [])],
                    critic_decision=critic.decision if critic else None,
                )
            )
        return CausalHypothesisListResponse(items=items, total_items=len(items))

    async def get_hypothesis(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        hypothesis_id: UUID,
    ) -> CausalHypothesisDetailResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._session.scalar(
            select(CausalHypothesisRow).where(
                CausalHypothesisRow.organization_id == organization_id,
                CausalHypothesisRow.analysis_run_id == analysis_run_id,
                CausalHypothesisRow.id == hypothesis_id,
            )
        )
        if row is None:
            raise ResourceNotFoundError("Causal hypothesis not found.")
        return CausalHypothesisDetailResponse(
            id=row.id,
            analysis_run_id=row.analysis_run_id,
            hypothesis_key=row.hypothesis_key,
            rank_placeholder=row.rank_placeholder,
            category_code=row.category_code,
            level_1_code=row.level_1_code,
            level_2_code=row.level_2_code,
            level_3_code=row.level_3_code,
            title=row.title,
            causal_claim=row.causal_claim,
            root_cause_node_id=row.root_cause_node_id,
            observed_failure_node_id=row.observed_failure_node_id,
            affected_artifact_id=row.affected_artifact_id,
            affected_artifact_type=row.affected_artifact_type,
            affected_path=row.affected_path,
            line_start=row.line_start,
            line_end=row.line_end,
            generator_type=row.generator_type,
            generator_name=row.generator_name,
            generator_version=row.generator_version,
            prompt_version=row.prompt_version,
            template_id=row.template_id,
            generation_confidence=row.generation_confidence,
            generation_prior_score=row.generation_prior_score,
            status=row.status,
            path_validation_status=row.path_validation_status,
            path_validation_warnings=[str(x) for x in (row.path_validation_warnings or [])],
            causal_path_node_ids=[str(x) for x in (row.causal_path_node_ids or [])],
            causal_path_edge_ids=[str(x) for x in (row.causal_path_edge_ids or [])],
            expected_observations=[str(x) for x in (row.expected_observations or [])],
            falsifying_observations=[str(x) for x in (row.falsifying_observations or [])],
            proposed_verification_steps=[str(x) for x in (row.proposed_verification_steps or [])],
            missing_evidence=[str(x) for x in (row.missing_evidence or [])],
            limitations=[str(x) for x in (row.limitations or [])],
            warnings=[str(x) for x in (row.warnings or [])],
            created_at=row.created_at,
        )

    async def list_evidence(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        hypothesis_id: UUID,
    ) -> HypothesisEvidenceListResponse:
        await self.get_hypothesis(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            hypothesis_id=hypothesis_id,
        )
        rows = list(
            (
                await self._session.scalars(
                    select(HypothesisEvidenceLinkRow).where(
                        HypothesisEvidenceLinkRow.organization_id == organization_id,
                        HypothesisEvidenceLinkRow.analysis_run_id == analysis_run_id,
                        HypothesisEvidenceLinkRow.hypothesis_id == hypothesis_id,
                    )
                )
            ).all()
        )
        return HypothesisEvidenceListResponse(
            items=[
                HypothesisEvidenceLinkItem(
                    id=r.id,
                    evidence_type=r.evidence_type,
                    relation=r.relation,
                    confidence=r.confidence,
                    explanation=r.explanation,
                    evidence_item_id=r.evidence_item_id,
                    graph_node_id=r.graph_node_id,
                    graph_edge_id=r.graph_edge_id,
                    artifact_id=r.artifact_id,
                    source_path=r.source_path,
                    line_start=r.line_start,
                    line_end=r.line_end,
                    extraction_method=r.extraction_method,
                )
                for r in rows
            ],
            total_items=len(rows),
        )

    async def get_causal_path(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        hypothesis_id: UUID,
    ) -> HypothesisCausalPathResponse:
        detail = await self.get_hypothesis(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            hypothesis_id=hypothesis_id,
        )
        return HypothesisCausalPathResponse(
            hypothesis_id=detail.id,
            path_validation_status=detail.path_validation_status,
            path_validation_warnings=detail.path_validation_warnings,
            node_ids=detail.causal_path_node_ids,
            edge_ids=detail.causal_path_edge_ids,
            root_cause_node_id=detail.root_cause_node_id,
            observed_failure_node_id=detail.observed_failure_node_id,
        )

    async def get_critic(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        hypothesis_id: UUID,
        critic_decision: str | None = None,
    ) -> HypothesisCriticResponse:
        await self.get_hypothesis(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            hypothesis_id=hypothesis_id,
        )
        row = await self._session.scalar(
            select(HypothesisCriticResultRow).where(
                HypothesisCriticResultRow.organization_id == organization_id,
                HypothesisCriticResultRow.analysis_run_id == analysis_run_id,
                HypothesisCriticResultRow.hypothesis_id == hypothesis_id,
            )
        )
        if row is None:
            raise ResourceNotFoundError("Hypothesis critic result not found.")
        if critic_decision and row.decision != critic_decision:
            raise ResourceNotFoundError("Hypothesis critic result not found.")
        return HypothesisCriticResponse(
            hypothesis_id=row.hypothesis_id,
            decision=row.decision,
            recommended_status=row.recommended_status,
            explanation=row.explanation,
            contradictions=[str(x) for x in (row.contradictions or [])],
            missing_evidence=[str(x) for x in (row.missing_evidence or [])],
            unsupported_claims=[str(x) for x in (row.unsupported_claims or [])],
            graph_conflicts=[str(x) for x in (row.graph_conflicts or [])],
            temporal_conflicts=[str(x) for x in (row.temporal_conflicts or [])],
            specificity_warning=row.specificity_warning,
            critic_version=row.critic_version,
            created_at=row.created_at,
        )
