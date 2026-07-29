"""Read APIs for analysis evidence, retrieved sources, and recommendations."""

from __future__ import annotations

from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.application.services.analysis_run_service import AnalysisRunService
from app.infrastructure.database.models.evidence_item import EvidenceItem
from app.infrastructure.database.models.knowledge_chunk import KnowledgeChunk
from app.infrastructure.database.models.knowledge_document import KnowledgeDocument
from app.infrastructure.database.models.recommendation import Recommendation
from app.infrastructure.database.models.recommendation_step import RecommendationStep
from app.infrastructure.database.models.retrieved_document import RetrievedDocument
from app.infrastructure.database.models.uploaded_file import UploadedFile
from app.schemas.analysis import (
    EvidenceItemResponse,
    EvidenceListResponse,
    RecommendationItemResponse,
    RecommendationListResponse,
    RetrievedSourceListResponse,
    RetrievedSourceResponse,
)


class AnalysisArtifactsService:
    """Load persisted diagnosis artifacts for an org-scoped analysis run."""

    def __init__(self, run_service: AnalysisRunService) -> None:
        self._runs = run_service
        self._session = run_service._session  # noqa: SLF001 - shared unit of work

    async def list_evidence(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> EvidenceListResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        total = int(
            await self._session.scalar(
                select(func.count())
                .select_from(EvidenceItem)
                .where(EvidenceItem.analysis_run_id == analysis_run_id)
            )
            or 0
        )
        stmt = (
            select(EvidenceItem, UploadedFile)
            .outerjoin(UploadedFile, UploadedFile.id == EvidenceItem.uploaded_file_id)
            .where(EvidenceItem.analysis_run_id == analysis_run_id)
            .order_by(EvidenceItem.importance_score.desc().nullslast())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self._session.execute(stmt)).all()
        items: list[EvidenceItemResponse] = []
        for evidence, uploaded in rows:
            source_file = None
            if uploaded is not None:
                source_file = {
                    "id": str(uploaded.id),
                    "name": uploaded.original_filename,
                }
            elif evidence.source_name:
                source_file = {"id": None, "name": evidence.source_name}
            items.append(
                EvidenceItemResponse(
                    id=evidence.id,
                    evidence_type=evidence.evidence_type.value
                    if hasattr(evidence.evidence_type, "value")
                    else str(evidence.evidence_type),
                    source_file=source_file,
                    line_start=evidence.line_start,
                    line_end=evidence.line_end,
                    importance_score=float(evidence.importance_score)
                    if evidence.importance_score is not None
                    else None,
                    excerpt=evidence.raw_excerpt,
                    explanation=evidence.explanation,
                )
            )
        return EvidenceListResponse(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=max(1, ceil(total / page_size)) if total else 1,
        )

    async def list_sources(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> RetrievedSourceListResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        stmt = (
            select(RetrievedDocument, KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeChunk, KnowledgeChunk.id == RetrievedDocument.knowledge_chunk_id)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(RetrievedDocument.analysis_run_id == analysis_run_id)
            .order_by(RetrievedDocument.rank.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        items: list[RetrievedSourceResponse] = []
        for retrieved, chunk, document in rows:
            preview = chunk.content[:280] + ("..." if len(chunk.content) > 280 else "")
            meta = chunk.chunk_metadata or {}
            items.append(
                RetrievedSourceResponse(
                    id=retrieved.id,
                    rank=retrieved.rank,
                    similarity_score=float(retrieved.similarity_score)
                    if retrieved.similarity_score is not None
                    else None,
                    used_in_reasoning=bool(retrieved.used_in_reasoning),
                    document={
                        "title": document.title,
                        "provider": document.provider,
                        "source_url": document.source_url,
                        "technology": meta.get("technology") or document.provider,
                        "source_type": meta.get("source_type") or "documentation",
                    },
                    chunk={
                        "heading": chunk.heading,
                        "content_preview": preview,
                        "section": chunk.heading,
                    },
                )
            )
        return RetrievedSourceListResponse(items=items)

    async def list_recommendations(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> RecommendationListResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        stmt = (
            select(Recommendation)
            .where(Recommendation.analysis_run_id == analysis_run_id)
            .options(selectinload(Recommendation.steps))
            .order_by(Recommendation.created_at.asc())
        )
        recommendations = list((await self._session.scalars(stmt)).all())
        items: list[RecommendationItemResponse] = []
        summary = None
        confidence = None
        llm_model = None
        for rec in recommendations:
            summary = summary or rec.root_cause_summary or rec.explanation
            confidence = (
                float(rec.confidence_score) if rec.confidence_score is not None else confidence
            )
            llm_model = llm_model or rec.llm_model
            steps: list[RecommendationStep] = list(rec.steps or [])
            if not steps and rec.legacy_remediation_steps:
                for idx, legacy in enumerate(rec.legacy_remediation_steps, start=1):
                    items.append(
                        RecommendationItemResponse(
                            id=rec.id,
                            step_number=idx,
                            title=str(legacy.get("title") or f"Step {idx}"),
                            action=str(legacy.get("action") or legacy.get("step") or ""),
                            explanation=legacy.get("explanation"),
                            expected_result=legacy.get("expected_result"),
                            risk_level=legacy.get("risk_level"),
                            difficulty=legacy.get("difficulty"),
                            prevention_type=legacy.get("prevention_type")
                            or legacy.get("step_type"),
                        )
                    )
                continue
            for step in steps:
                items.append(
                    RecommendationItemResponse(
                        id=step.id,
                        step_number=step.step_number,
                        title=step.title,
                        action=step.action,
                        explanation=step.explanation,
                        expected_result=step.expected_result,
                        risk_level=step.risk_level.value
                        if getattr(step, "risk_level", None) is not None
                        and hasattr(step.risk_level, "value")
                        else (str(step.risk_level) if getattr(step, "risk_level", None) else None),
                        difficulty=step.difficulty,
                        prevention_type=step.step_type.value
                        if hasattr(step.step_type, "value")
                        else str(step.step_type),
                        accepted=step.accepted,
                        completed=bool(step.completed),
                    )
                )
        return RecommendationListResponse(
            items=items,
            summary=summary,
            confidence_score=confidence,
            llm_model=llm_model,
        )
