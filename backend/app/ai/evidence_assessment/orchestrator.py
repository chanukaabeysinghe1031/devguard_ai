"""Evidence assessment orchestrator (Phase 6A.5 Part 3)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.evidence_assessment.candidate_selection import HypothesisCandidateSelector
from app.ai.evidence_assessment.contradiction_analyzer import HypothesisContradictionAnalyzer
from app.ai.evidence_assessment.item_assessor import EvidenceItemAssessor
from app.ai.evidence_assessment.persist import EvidenceAssessmentPersistService
from app.ai.evidence_assessment.ranking import HypothesisRankingEngine
from app.ai.evidence_assessment.sufficiency import EvidenceSufficiencyAssessor
from app.ai.evidence_assessment.support_analyzer import HypothesisSupportAnalyzer
from app.ai.evidence_assessment.versions import (
    CANDIDATE_SELECTION_VERSION,
    CONTRADICTION_ANALYSIS_VERSION,
    EVIDENCE_ASSESSMENT_VERSION,
    EVIDENCE_SUFFICIENCY_VERSION,
    HYPOTHESIS_RANKING_VERSION,
    SUPPORT_ANALYSIS_VERSION,
)
from app.ai.orchestration.analysis_context import AnalysisContext
from app.core.config import Settings
from app.domain.evidence_assessment.models import EvidenceAssessmentRun
from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalSourceType,
    RetrievalItemRelation,
)
from app.domain.hypothesis_retrieval.models import HypothesisRetrievedItem
from app.infrastructure.database.models.hypothesis_retrieval import (
    HypothesisRetrievalRunRow,
    HypothesisRetrievalSessionRow,
    HypothesisRetrievedItemRow,
)


class EvidenceAssessmentOrchestrator:
    """Soft-fail Part 3 pipeline. Master flag OFF = no-op."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._item_assessor = EvidenceItemAssessor()
        self._support = HypothesisSupportAnalyzer()
        self._contradiction = HypothesisContradictionAnalyzer()
        self._sufficiency = EvidenceSufficiencyAssessor()
        self._ranker = HypothesisRankingEngine(
            tie_epsilon=settings.ranking_tie_epsilon,
        )
        self._selector = HypothesisCandidateSelector()

    async def run(
        self,
        session: AsyncSession,
        context: AnalysisContext,
    ) -> EvidenceAssessmentRun | None:
        if not self._settings.hypothesis_evidence_assessment_enabled:
            return None
        if context.organization_id is None:
            return None

        started = datetime.now(UTC)
        org_id = context.organization_id
        analysis_id = context.analysis_run_id
        if analysis_id is None:
            return None

        run_row = await session.scalar(
            select(HypothesisRetrievalRunRow).where(
                HypothesisRetrievalRunRow.organization_id == org_id,
                HypothesisRetrievalRunRow.analysis_run_id == analysis_id,
            )
        )
        if run_row is None:
            return EvidenceAssessmentRun(
                analysis_id=str(analysis_id),
                organization_id=str(org_id),
                status="NO_RETRIEVAL",
                warnings=["hypothesis_retrieval_run_not_found"],
                configuration_snapshot=self._config_snapshot(),
            )

        sessions = list(
            (
                await session.scalars(
                    select(HypothesisRetrievalSessionRow)
                    .where(
                        HypothesisRetrievalSessionRow.retrieval_run_id == run_row.id,
                        HypothesisRetrievalSessionRow.organization_id == org_id,
                    )
                    .order_by(HypothesisRetrievalSessionRow.created_at.asc())
                )
            ).all()
        )

        assessment_run = EvidenceAssessmentRun(
            analysis_id=str(analysis_id),
            organization_id=str(org_id),
            retrieval_run_id=str(run_row.id),
            status="RUNNING",
            configuration_snapshot=self._config_snapshot(),
        )

        support_by: dict[str, Any] = {}
        contradiction_by: dict[str, Any] = {}
        sufficiency_by: dict[str, Any] = {}
        hypothesis_keys: dict[str, str] = {}
        generation_priors: dict[str, float] = {}
        mean_relevance: dict[str, float] = {}
        parser_confidence: dict[str, float] = {}
        hypothesis_ids: list[str] = []

        for sess in sessions:
            hid = str(sess.hypothesis_id)
            hypothesis_ids.append(hid)
            hypothesis_keys[hid] = sess.hypothesis_key
            generation_priors[hid] = float(sess.hypothesis_prior_score_snapshot or 0.0)

            item_rows = list(
                (
                    await session.scalars(
                        select(HypothesisRetrievedItemRow)
                        .where(
                            HypothesisRetrievedItemRow.session_id == sess.id,
                            HypothesisRetrievedItemRow.organization_id == org_id,
                        )
                        .order_by(HypothesisRetrievedItemRow.global_session_order.asc())
                    )
                ).all()
            )
            items = [_row_to_item(r) for r in item_rows]
            validation_map = _validation_map_from_metrics(dict(sess.metrics or {}))

            item_assessments = self._item_assessor.assess_many(
                items,
                hypothesis_id=hid,
                max_assessments=self._settings.max_evidence_assessments_per_hypothesis,
                validation_by_item=validation_map,
            )
            assessment_run.item_assessments.extend(item_assessments)

            support = self._support.analyze(hypothesis_id=hid, assessments=item_assessments)
            support_by[hid] = support
            assessment_run.support_by_hypothesis[hid] = support

            if self._settings.contradiction_analysis_enabled:
                contradiction = self._contradiction.analyze(
                    hypothesis_id=hid, assessments=item_assessments
                )
            else:
                contradiction = self._contradiction.analyze(hypothesis_id=hid, assessments=[])
            contradiction_by[hid] = contradiction
            assessment_run.contradiction_by_hypothesis[hid] = contradiction

            ctx_snap = dict(sess.context_snapshot or {})
            if self._settings.evidence_sufficiency_enabled:
                sufficiency = self._sufficiency.assess(
                    hypothesis_id=hid,
                    assessments=item_assessments,
                    items=items,
                    context=ctx_snap,
                )
            else:
                sufficiency = self._sufficiency.assess(
                    hypothesis_id=hid,
                    assessments=[],
                    items=[],
                    context={},
                )
            sufficiency_by[hid] = sufficiency
            assessment_run.sufficiency_by_hypothesis[hid] = sufficiency

            if item_assessments:
                mean_relevance[hid] = sum(a.relevance_score for a in item_assessments) / len(
                    item_assessments
                )
            else:
                mean_relevance[hid] = 0.0
            parser_confidence[hid] = _parser_confidence(ctx_snap)

            assessment_run.hypothesis_assessments[hid] = {
                "hypothesis_id": hid,
                "hypothesis_key": sess.hypothesis_key,
                "item_assessments": [a.to_dict() for a in item_assessments],
                "support": support.to_dict(),
                "contradiction": contradiction.to_dict(),
                "sufficiency": sufficiency.to_dict(),
                "mean_relevance": mean_relevance[hid],
            }

        if self._settings.hypothesis_ranking_enabled and hypothesis_ids:
            ranking = self._ranker.rank(
                analysis_id=str(analysis_id),
                organization_id=str(org_id),
                hypothesis_ids=hypothesis_ids,
                hypothesis_keys=hypothesis_keys,
                support_by_id=support_by,
                contradiction_by_id=contradiction_by,
                sufficiency_by_id=sufficiency_by,
                generation_priors=generation_priors,
                mean_relevance_by_id=mean_relevance,
                parser_confidence_by_id=parser_confidence,
            )
            assessment_run.ranking = ranking
            assessment_run.warnings.extend(ranking.warnings)

            if self._settings.candidate_selection_enabled:
                selection = self._selector.select(
                    ranking,
                    max_candidates=self._settings.max_candidate_hypotheses,
                    min_ranking_score_for_top=self._settings.min_ranking_score_for_top_candidate,
                    tie_epsilon=self._settings.ranking_tie_epsilon,
                )
                assessment_run.candidate_selection = selection
                assessment_run.warnings.extend(selection.warnings)

        assessment_run.status = "COMPLETE"
        ended = datetime.now(UTC)
        assessment_run.duration_ms = int((ended - started).total_seconds() * 1000)

        if self._settings.hypothesis_retrieval_persistence_enabled:
            await EvidenceAssessmentPersistService(session).persist(assessment_run)

        return assessment_run

    def _config_snapshot(self) -> dict[str, Any]:
        s = self._settings
        return {
            "hypothesis_evidence_assessment_enabled": s.hypothesis_evidence_assessment_enabled,
            "evidence_sufficiency_enabled": s.evidence_sufficiency_enabled,
            "contradiction_analysis_enabled": s.contradiction_analysis_enabled,
            "hypothesis_ranking_enabled": s.hypothesis_ranking_enabled,
            "candidate_selection_enabled": s.candidate_selection_enabled,
            "max_evidence_assessments_per_hypothesis": s.max_evidence_assessments_per_hypothesis,
            "max_candidate_hypotheses": s.max_candidate_hypotheses,
            "min_ranking_score_for_top_candidate": s.min_ranking_score_for_top_candidate,
            "ranking_tie_epsilon": s.ranking_tie_epsilon,
            "versions": {
                "evidence_assessment": EVIDENCE_ASSESSMENT_VERSION,
                "evidence_sufficiency": EVIDENCE_SUFFICIENCY_VERSION,
                "contradiction_analysis": CONTRADICTION_ANALYSIS_VERSION,
                "support_analysis": SUPPORT_ANALYSIS_VERSION,
                "hypothesis_ranking": HYPOTHESIS_RANKING_VERSION,
                "candidate_selection": CANDIDATE_SELECTION_VERSION,
            },
        }


def _row_to_item(row: HypothesisRetrievedItemRow) -> HypothesisRetrievedItem:
    try:
        source_type = HypothesisRetrievalSourceType(row.source_type)
    except ValueError:
        source_type = HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE
    try:
        relation = RetrievalItemRelation(row.relation_candidate)
    except ValueError:
        relation = RetrievalItemRelation.UNKNOWN
    return HypothesisRetrievedItem(
        id=str(row.id),
        source_type=source_type,
        source_system=row.source_system,
        text_excerpt=row.text_excerpt,
        query_id=row.primary_query_id,
        hypothesis_id=str(row.hypothesis_id),
        session_id=str(row.session_id),
        source_id=row.source_id,
        document_id=row.document_id,
        chunk_id=row.chunk_id,
        artifact_id=row.artifact_id,
        graph_node_id=row.graph_node_id,
        graph_edge_id=row.graph_edge_id,
        temporal_event_id=row.temporal_event_id,
        historical_incident_id=row.historical_incident_id,
        title=row.title,
        normalized_text_hash=row.normalized_text_hash,
        source_path=row.source_path,
        line_start=row.line_start,
        line_end=row.line_end,
        repository=row.repository,
        commit_sha=row.commit_sha,
        source_timestamp=row.source_timestamp,
        retrieval_score=float(row.retrieval_score or 0.0),
        lexical_score=row.lexical_score,
        vector_score=row.vector_score,
        historical_score=row.historical_score,
        graph_distance=row.graph_distance,
        adapter_name=row.adapter_name,
        adapter_version=row.adapter_version,
        embedding_model_version=row.embedding_model_version,
        relation_candidate=relation,
        rank_within_query=row.rank_within_query,
        global_session_order=row.global_session_order,
        metadata=dict(row.item_metadata or {}),
        redaction_status=row.redaction_status,
    )


def _validation_map_from_metrics(metrics: dict[str, Any]) -> dict[str, str]:
    raw_intel = metrics.get("intelligence")
    intelligence = raw_intel if isinstance(raw_intel, dict) else {}
    results = intelligence.get("validation_results") or metrics.get("validation_results") or []
    out: dict[str, str] = {}
    if not isinstance(results, list):
        return out
    for entry in results:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("item_key") or entry.get("item_id") or "")
        status = entry.get("status")
        if key and status:
            out[key] = str(status)
    return out


def _parser_confidence(context: dict[str, Any]) -> float:
    evidence = context.get("parser_evidence")
    if isinstance(evidence, list) and evidence:
        scores: list[float] = []
        for item in evidence:
            if isinstance(item, dict) and item.get("confidence") is not None:
                try:
                    scores.append(float(item["confidence"]))
                except (TypeError, ValueError):
                    continue
        if scores:
            return max(0.0, min(1.0, sum(scores) / len(scores)))
    return 0.5
