"""Persist Phase 6A.4 causal hypothesis runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.hypotheses.dedupe_critic import hypothesis_fingerprint
from app.domain.hypotheses.models import CausalHypothesisRun
from app.infrastructure.database.models.causal_hypotheses import (
    CausalHypothesisRow,
    CausalHypothesisRunRow,
    HypothesisCriticResultRow,
    HypothesisEvidenceLinkRow,
)


class CausalHypothesisPersistService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist(self, run: CausalHypothesisRun) -> CausalHypothesisRunRow:
        org_id = UUID(run.organization_id)
        analysis_id = UUID(run.analysis_id)

        existing = await self._session.scalar(
            select(CausalHypothesisRunRow).where(
                CausalHypothesisRunRow.organization_id == org_id,
                CausalHypothesisRunRow.analysis_run_id == analysis_id,
            )
        )
        if existing is not None:
            # Cascade delete children via ORM delete of run after clearing FKs.
            hyp_ids = list(
                (
                    await self._session.scalars(
                        select(CausalHypothesisRow.id).where(
                            CausalHypothesisRow.hypothesis_run_id == existing.id
                        )
                    )
                ).all()
            )
            if hyp_ids:
                await self._session.execute(
                    delete(HypothesisCriticResultRow).where(
                        HypothesisCriticResultRow.hypothesis_id.in_(hyp_ids)
                    )
                )
                await self._session.execute(
                    delete(HypothesisEvidenceLinkRow).where(
                        HypothesisEvidenceLinkRow.hypothesis_id.in_(hyp_ids)
                    )
                )
                await self._session.execute(
                    delete(CausalHypothesisRow).where(CausalHypothesisRow.id.in_(hyp_ids))
                )
            await self._session.delete(existing)
            await self._session.flush()

        row = CausalHypothesisRunRow(
            organization_id=org_id,
            project_id=UUID(run.project_id) if run.project_id else None,
            incident_id=UUID(run.incident_id) if run.incident_id else None,
            analysis_run_id=analysis_id,
            status=run.status.value,
            deterministic_count=run.deterministic_count,
            llm_count=run.llm_count,
            invalid_reference_count=run.invalid_reference_count,
            duplicate_removed_count=run.duplicate_removed_count,
            generator_version=run.generator_version,
            prompt_version=run.prompt_version,
            duration_ms=run.duration_ms,
            warnings=list(run.warnings),
            truncation_notes=list(run.truncation_notes),
            token_usage=dict(run.token_usage),
            cost_usd=run.cost_usd,
            context_snapshot={
                "hypothesis_count": len(run.hypotheses),
                "status": run.status.value,
            },
        )
        self._session.add(row)
        await self._session.flush()
        run.id = str(row.id)

        for hyp in run.hypotheses:
            hrow = CausalHypothesisRow(
                organization_id=org_id,
                project_id=UUID(run.project_id) if run.project_id else None,
                incident_id=UUID(run.incident_id) if run.incident_id else None,
                analysis_run_id=analysis_id,
                hypothesis_run_id=row.id,
                hypothesis_key=hyp.hypothesis_key,
                rank_placeholder=hyp.rank_placeholder,
                category_code=hyp.category_code,
                level_1_code=hyp.level_1_code,
                level_2_code=hyp.level_2_code,
                level_3_code=hyp.level_3_code,
                title=hyp.title,
                causal_claim=hyp.causal_claim,
                root_cause_node_id=hyp.root_cause_node_id,
                observed_failure_node_id=hyp.observed_failure_node_id,
                affected_artifact_id=hyp.affected_artifact_id,
                affected_artifact_type=hyp.affected_artifact_type,
                affected_path=hyp.affected_path,
                line_start=hyp.line_start,
                line_end=hyp.line_end,
                generator_type=hyp.generator_type.value,
                generator_name=hyp.generator_name,
                generator_version=hyp.generator_version,
                prompt_version=hyp.prompt_version,
                template_id=hyp.template_id,
                generation_confidence=hyp.generation_confidence,
                generation_prior_score=hyp.generation_prior_score,
                status=hyp.status.value,
                path_validation_status=hyp.path_validation_status.value,
                path_validation_warnings=list(hyp.path_validation_warnings),
                causal_path_node_ids=list(hyp.causal_path_node_ids),
                causal_path_edge_ids=list(hyp.causal_path_edge_ids),
                expected_observations=list(hyp.expected_observations),
                falsifying_observations=list(hyp.falsifying_observations),
                proposed_verification_steps=list(hyp.proposed_verification_steps),
                missing_evidence=list(hyp.missing_evidence),
                limitations=list(hyp.limitations),
                warnings=list(hyp.warnings),
                dedupe_fingerprint=hypothesis_fingerprint(hyp),
            )
            self._session.add(hrow)
            await self._session.flush()
            hyp.id = str(hrow.id)

            for link in hyp.evidence_links:
                self._session.add(
                    HypothesisEvidenceLinkRow(
                        organization_id=org_id,
                        analysis_run_id=analysis_id,
                        hypothesis_id=hrow.id,
                        evidence_type=link.evidence_type,
                        evidence_item_id=link.evidence_item_id,
                        graph_node_id=link.graph_node_id,
                        graph_edge_id=link.graph_edge_id,
                        artifact_id=link.artifact_id,
                        source_path=link.source_path,
                        line_start=link.line_start,
                        line_end=link.line_end,
                        relation=link.relation.value,
                        confidence=link.confidence,
                        explanation=link.explanation,
                        extraction_method=link.extraction_method,
                    )
                )

            if hyp.critic is not None:
                c = hyp.critic
                self._session.add(
                    HypothesisCriticResultRow(
                        organization_id=org_id,
                        analysis_run_id=analysis_id,
                        hypothesis_id=hrow.id,
                        decision=c.decision.value,
                        recommended_status=c.recommended_status.value,
                        explanation=c.explanation,
                        contradictions=list(c.contradictions),
                        missing_evidence=list(c.missing_evidence),
                        unsupported_claims=list(c.unsupported_claims),
                        graph_conflicts=list(c.graph_conflicts),
                        temporal_conflicts=list(c.temporal_conflicts),
                        specificity_warning=c.specificity_warning,
                        critic_version=c.critic_version,
                    )
                )

        await self._session.flush()
        return row
