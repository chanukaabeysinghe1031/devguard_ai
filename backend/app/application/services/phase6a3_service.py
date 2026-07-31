"""Debug/read APIs for Phase 6A.3 hierarchical classification."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.application.services.analysis_run_service import AnalysisRunService
from app.domain.classification.taxonomy_registry import get_taxonomy_registry
from app.domain.exceptions.business import ResourceNotFoundError
from app.infrastructure.database.models.hierarchical_classification import (
    ClassificationCandidateRow,
    ClassificationConfidenceComponentRow,
    ClassificationDisagreementResultRow,
    HierarchicalClassificationResultRow,
    OpenSetAssessmentRow,
)
from app.schemas.phase6a3 import (
    ClassificationCandidateItem,
    ClassificationCandidateListResponse,
    ClassificationConfidenceComponentItem,
    ClassificationConfidenceResponse,
    ClassificationDisagreementResponse,
    FailureTaxonomyResponse,
    HierarchicalClassificationResponse,
    OpenSetAssessmentResponse,
    TaxonomyPathItem,
)


class Phase6A3ClassificationService:
    def __init__(self, run_service: AnalysisRunService) -> None:
        self._runs = run_service
        self._session = run_service._session  # noqa: SLF001

    async def get_hierarchical_classification(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> HierarchicalClassificationResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._session.scalar(
            select(HierarchicalClassificationResultRow).where(
                HierarchicalClassificationResultRow.organization_id == organization_id,
                HierarchicalClassificationResultRow.analysis_run_id == analysis_run_id,
            )
        )
        if row is None:
            raise ResourceNotFoundError(
                "Hierarchical classification not found for this analysis."
            )
        return HierarchicalClassificationResponse(
            id=row.id,
            analysis_run_id=row.analysis_run_id,
            final_legacy_category_code=row.final_legacy_category_code,
            level_1_code=row.level_1_code,
            level_2_code=row.level_2_code,
            level_3_code=row.level_3_code,
            classification_status=row.classification_status,
            final_confidence=row.final_confidence,
            mapping_version=row.mapping_version,
            model_versions=dict(row.model_versions or {}),
            evidence_ids=[str(x) for x in (row.evidence_ids or [])],
            missing_evidence=[str(x) for x in (row.missing_evidence or [])],
            rule_result=row.rule_result,
            learned_result=row.learned_result,
            llm_result=row.llm_result,
            warnings=[str(x) for x in (row.warnings or [])],
            duration_ms=row.duration_ms,
            created_at=row.created_at,
        )

    async def list_classification_candidates(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        source_classifier: str | None = None,
        status: str | None = None,  # reserved / ignored — candidates have no status
        level_1: str | None = None,
        level_2: str | None = None,
        level_3: str | None = None,
    ) -> ClassificationCandidateListResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        filters = [
            ClassificationCandidateRow.organization_id == organization_id,
            ClassificationCandidateRow.analysis_run_id == analysis_run_id,
        ]
        if source_classifier:
            filters.append(ClassificationCandidateRow.source_classifier == source_classifier)
        if level_1:
            filters.append(ClassificationCandidateRow.level_1_code == level_1)
        if level_2:
            filters.append(ClassificationCandidateRow.level_2_code == level_2)
        if level_3:
            filters.append(ClassificationCandidateRow.level_3_code == level_3)
        rows = list(
            (
                await self._session.scalars(
                    select(ClassificationCandidateRow)
                    .where(*filters)
                    .order_by(ClassificationCandidateRow.rank.asc())
                )
            ).all()
        )
        return ClassificationCandidateListResponse(
            items=[
                ClassificationCandidateItem(
                    id=r.id,
                    category_code=r.category_code,
                    level_1_code=r.level_1_code,
                    level_2_code=r.level_2_code,
                    level_3_code=r.level_3_code,
                    score=r.score,
                    source_classifier=r.source_classifier,
                    rank=r.rank,
                    supporting_evidence=[str(x) for x in (r.supporting_evidence or [])],
                    contradicting_evidence=[str(x) for x in (r.contradicting_evidence or [])],
                    matched_rules=[str(x) for x in (r.matched_rules or [])],
                )
                for r in rows
            ],
            total_items=len(rows),
        )

    async def get_open_set_assessment(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> OpenSetAssessmentResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._session.scalar(
            select(OpenSetAssessmentRow).where(
                OpenSetAssessmentRow.organization_id == organization_id,
                OpenSetAssessmentRow.analysis_run_id == analysis_run_id,
            )
        )
        if row is None:
            raise ResourceNotFoundError("Open-set assessment not found for this analysis.")
        return OpenSetAssessmentResponse(
            id=row.id,
            analysis_run_id=row.analysis_run_id,
            status=row.status,
            unknown_score=row.unknown_score,
            maximum_known_score=row.maximum_known_score,
            top_two_margin=row.top_two_margin,
            rule_coverage=row.rule_coverage,
            representation_distance=row.representation_distance,
            evidence_coverage=row.evidence_coverage,
            disagreement_level=row.disagreement_level,
            threshold_version=row.threshold_version,
            triggered_conditions=[str(x) for x in (row.triggered_conditions or [])],
            explanation=row.explanation,
            created_at=row.created_at,
        )

    async def get_classification_disagreement(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> ClassificationDisagreementResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._session.scalar(
            select(ClassificationDisagreementResultRow).where(
                ClassificationDisagreementResultRow.organization_id == organization_id,
                ClassificationDisagreementResultRow.analysis_run_id == analysis_run_id,
            )
        )
        if row is None:
            raise ResourceNotFoundError(
                "Classification disagreement not found for this analysis."
            )
        return ClassificationDisagreementResponse(
            id=row.id,
            analysis_run_id=row.analysis_run_id,
            agreement_level=row.agreement_level,
            agreed_level_1=row.agreed_level_1,
            agreed_level_2=row.agreed_level_2,
            agreed_level_3=row.agreed_level_3,
            conflicting_candidates=[str(x) for x in (row.conflicting_candidates or [])],
            conflict_type=row.conflict_type,
            evidence_conflict=row.evidence_conflict,
            classifier_conflict=row.classifier_conflict,
            category_distance=row.category_distance,
            recommended_action=row.recommended_action,
            additional_evidence_needed=[
                str(x) for x in (row.additional_evidence_needed or [])
            ],
            confidence_penalty=row.confidence_penalty,
            explanation=row.explanation,
            created_at=row.created_at,
        )

    async def get_classification_confidence(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> ClassificationConfidenceResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        parent = await self._session.scalar(
            select(HierarchicalClassificationResultRow).where(
                HierarchicalClassificationResultRow.organization_id == organization_id,
                HierarchicalClassificationResultRow.analysis_run_id == analysis_run_id,
            )
        )
        if parent is None:
            raise ResourceNotFoundError(
                "Classification confidence not found for this analysis."
            )
        rows = list(
            (
                await self._session.scalars(
                    select(ClassificationConfidenceComponentRow)
                    .where(
                        ClassificationConfidenceComponentRow.organization_id
                        == organization_id,
                        ClassificationConfidenceComponentRow.analysis_run_id
                        == analysis_run_id,
                    )
                    .order_by(ClassificationConfidenceComponentRow.component_name.asc())
                )
            ).all()
        )
        return ClassificationConfidenceResponse(
            analysis_run_id=analysis_run_id,
            final_confidence=parent.final_confidence,
            components=[
                ClassificationConfidenceComponentItem(
                    component_name=r.component_name,
                    raw_value=r.raw_value,
                    normalized_value=r.normalized_value,
                    weight=r.weight,
                    contribution=r.contribution,
                    source=r.source,
                    explanation=r.explanation,
                )
                for r in rows
            ],
        )

    def get_failure_taxonomy(
        self,
        *,
        level_1: str | None = None,
        level_2: str | None = None,
        level_3: str | None = None,
    ) -> FailureTaxonomyResponse:
        registry = get_taxonomy_registry()
        paths = registry.children_of(level_1=level_1, level_2=level_2)
        if level_3:
            paths = [p for p in paths if p.level_3_code == level_3]
        return FailureTaxonomyResponse(
            mapping_version=registry.mapping_version,
            paths=[TaxonomyPathItem(**p.to_dict()) for p in paths],
            aliases=dict(registry._aliases),  # noqa: SLF001
            frozen_codes=sorted(registry.to_dict()["frozen_codes"]),
        )
