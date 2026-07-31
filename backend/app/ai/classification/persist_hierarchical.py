"""Persist Phase 6A.3 hierarchical classification results."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.classification.models import HierarchicalClassificationResult
from app.domain.classification.taxonomy_registry import get_taxonomy_registry
from app.infrastructure.database.models.hierarchical_classification import (
    ClassificationCandidateRow,
    ClassificationConfidenceComponentRow,
    ClassificationDisagreementResultRow,
    HierarchicalClassificationResultRow,
    OpenSetAssessmentRow,
    TaxonomyMappingRow,
)


class HierarchicalClassificationPersistService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_taxonomy_mappings_seeded(self) -> int:
        registry = get_taxonomy_registry()
        existing = set(
            (
                await self._session.scalars(
                    select(TaxonomyMappingRow.legacy_category_code).where(
                        TaxonomyMappingRow.mapping_version == registry.mapping_version
                    )
                )
            ).all()
        )
        inserted = 0
        for path in registry.all_paths():
            if path.legacy_category_code in existing:
                continue
            self._session.add(
                TaxonomyMappingRow(
                    legacy_category_code=path.legacy_category_code,
                    level_1_code=path.level_1_code,
                    level_1_label=path.level_1_label,
                    level_2_code=path.level_2_code,
                    level_2_label=path.level_2_label,
                    level_3_code=path.level_3_code,
                    level_3_label=path.level_3_label,
                    mapping_version=path.mapping_version,
                    is_active=path.is_active,
                    notes=path.notes or None,
                )
            )
            inserted += 1
        if inserted:
            await self._session.flush()
        return inserted

    async def persist(
        self, result: HierarchicalClassificationResult
    ) -> HierarchicalClassificationResultRow:
        if not result.organization_id:
            raise ValueError("organization_id required to persist hierarchical classification")
        org_id = UUID(result.organization_id)
        analysis_id = UUID(result.analysis_id)

        # Replace prior enhanced result for this analysis (idempotent re-runs).
        existing = await self._session.scalar(
            select(HierarchicalClassificationResultRow).where(
                HierarchicalClassificationResultRow.organization_id == org_id,
                HierarchicalClassificationResultRow.analysis_run_id == analysis_id,
            )
        )
        if existing is not None:
            await self._session.execute(
                delete(ClassificationConfidenceComponentRow).where(
                    ClassificationConfidenceComponentRow.hierarchical_result_id == existing.id
                )
            )
            await self._session.execute(
                delete(ClassificationDisagreementResultRow).where(
                    ClassificationDisagreementResultRow.hierarchical_result_id == existing.id
                )
            )
            await self._session.execute(
                delete(OpenSetAssessmentRow).where(
                    OpenSetAssessmentRow.hierarchical_result_id == existing.id
                )
            )
            await self._session.execute(
                delete(ClassificationCandidateRow).where(
                    ClassificationCandidateRow.hierarchical_result_id == existing.id
                )
            )
            await self._session.delete(existing)
            await self._session.flush()

        row = HierarchicalClassificationResultRow(
            organization_id=org_id,
            project_id=UUID(result.project_id) if result.project_id else None,
            incident_id=UUID(result.incident_id) if result.incident_id else None,
            analysis_run_id=analysis_id,
            final_legacy_category_code=result.final_legacy_category_code,
            level_1_code=result.level_1_code,
            level_2_code=result.level_2_code,
            level_3_code=result.level_3_code,
            classification_status=result.classification_status.value,
            final_confidence=result.final_confidence,
            mapping_version=result.mapping_version,
            model_versions=dict(result.model_versions),
            evidence_ids=list(result.evidence_ids),
            missing_evidence=list(result.missing_evidence),
            rule_result=result.rule_result.to_dict() if result.rule_result else None,
            learned_result=result.learned_result.to_dict() if result.learned_result else None,
            llm_result=result.llm_result.to_dict() if result.llm_result else None,
            evaluation_export=dict(result.evaluation_export),
            warnings=list(result.warnings),
            duration_ms=result.duration_ms,
        )
        self._session.add(row)
        await self._session.flush()

        for cand in result.top_candidates:
            # Only persist valid frozen codes.
            if cand.category_code and not get_taxonomy_registry().is_valid_category(
                cand.category_code
            ):
                continue
            self._session.add(
                ClassificationCandidateRow(
                    organization_id=org_id,
                    analysis_run_id=analysis_id,
                    hierarchical_result_id=row.id,
                    category_code=cand.category_code,
                    level_1_code=cand.level_1_code,
                    level_2_code=cand.level_2_code,
                    level_3_code=cand.level_3_code,
                    score=float(cand.score),
                    source_classifier=cand.source_classifier,
                    rank=int(cand.rank),
                    supporting_evidence=list(cand.supporting_evidence),
                    contradicting_evidence=list(cand.contradicting_evidence),
                    matched_rules=list(cand.matched_rules),
                )
            )

        if result.open_set_result is not None:
            osr = result.open_set_result
            self._session.add(
                OpenSetAssessmentRow(
                    organization_id=org_id,
                    analysis_run_id=analysis_id,
                    hierarchical_result_id=row.id,
                    status=osr.status.value,
                    unknown_score=osr.unknown_score,
                    maximum_known_score=osr.maximum_known_score,
                    top_two_margin=osr.top_two_margin,
                    rule_coverage=osr.rule_coverage,
                    representation_distance=osr.representation_distance,
                    evidence_coverage=osr.evidence_coverage,
                    disagreement_level=osr.disagreement_level,
                    threshold_version=osr.threshold_version,
                    triggered_conditions=list(osr.triggered_conditions),
                    explanation=osr.explanation,
                )
            )

        if result.disagreement_result is not None:
            dr = result.disagreement_result
            self._session.add(
                ClassificationDisagreementResultRow(
                    organization_id=org_id,
                    analysis_run_id=analysis_id,
                    hierarchical_result_id=row.id,
                    agreement_level=dr.agreement_level.value,
                    agreed_level_1=dr.agreed_level_1,
                    agreed_level_2=dr.agreed_level_2,
                    agreed_level_3=dr.agreed_level_3,
                    conflicting_candidates=list(dr.conflicting_candidates),
                    conflict_type=dr.conflict_type.value,
                    evidence_conflict=dr.evidence_conflict,
                    classifier_conflict=dr.classifier_conflict,
                    category_distance=dr.category_distance,
                    recommended_action=dr.recommended_action.value,
                    additional_evidence_needed=list(dr.additional_evidence_needed),
                    confidence_penalty=dr.confidence_penalty,
                    explanation=dr.explanation,
                )
            )

        if result.confidence_breakdown is not None:
            for comp in result.confidence_breakdown.components:
                self._session.add(
                    ClassificationConfidenceComponentRow(
                        organization_id=org_id,
                        analysis_run_id=analysis_id,
                        hierarchical_result_id=row.id,
                        component_name=comp.component_name,
                        raw_value=comp.raw_value,
                        normalized_value=comp.normalized_value,
                        weight=comp.weight,
                        contribution=comp.contribution,
                        source=comp.source,
                        explanation=comp.explanation,
                    )
                )

        await self._session.flush()
        return row
