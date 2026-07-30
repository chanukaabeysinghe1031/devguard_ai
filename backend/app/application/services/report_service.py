"""Incident report generation and retrieval service."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.services.mappers import note_to_response, timeline_event
from app.domain.services.incident_transitions import format_incident_number
from app.domain.enums import GenerationStatus
from app.domain.exceptions.business import ResourceNotFoundError, ValidationBusinessError
from app.domain.interfaces.storage_provider import FileStorage
from app.infrastructure.database.models.analysis_run import AnalysisRun
from app.infrastructure.database.models.evidence_item import EvidenceItem
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_report import IncidentReport
from app.infrastructure.database.models.incident_resolution import IncidentResolution
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.recommendation import Recommendation
from app.infrastructure.database.models.recommendation_step import RecommendationStep
from app.infrastructure.database.models.retrieved_document import RetrievedDocument
from app.schemas.common import build_paginated_response, normalize_pagination
from app.schemas.report import (
    ReportDetailResponse,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportListItem,
    ReportListResponse,
)

logger = structlog.get_logger(__name__)


class ReportService:
    def __init__(self, session: AsyncSession, storage: FileStorage) -> None:
        self._session = session
        self._storage = storage

    async def generate(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        generated_by: UUID,
        body: ReportGenerateRequest,
    ) -> ReportGenerateResponse:
        if body.format.lower() != "json":
            raise ValidationBusinessError("Only JSON report format is supported currently.")

        incident = await self._load_incident(organization_id, incident_id)
        report_id = uuid4()
        content = await self._build_snapshot(incident, body)
        payload = json.dumps(content, indent=2, default=str).encode("utf-8")
        checksum = hashlib.sha256(payload).hexdigest()

        relative_path = (
            f"org/{organization_id}/"
            f"project/{incident.project_id}/"
            f"incident/{incident.id}/"
            f"reports/{report_id.hex}.json"
        )
        await self._storage.save(relative_path=relative_path, data=payload)

        version = int(
            await self._session.scalar(
                select(func.count())
                .select_from(IncidentReport)
                .where(IncidentReport.incident_id == incident.id)
            )
            or 0
        ) + 1

        report = IncidentReport(
            id=report_id,
            incident_id=incident.id,
            generated_by=generated_by,
            format="json",
            version=version,
            storage_path=relative_path,
            checksum_sha256=checksum,
            generation_status=GenerationStatus.COMPLETED,
        )
        self._session.add(report)
        await self._session.flush()
        logger.info("report_generated", report_id=str(report_id), incident_id=str(incident.id))
        return ReportGenerateResponse(
            report_id=report.id,
            incident_id=incident.id,
            format=report.format,
            generation_status=report.generation_status.value,
        )

    async def list_reports(
        self,
        *,
        organization_id: UUID,
        page: int,
        page_size: int,
        incident_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> ReportListResponse:
        page, page_size, offset = normalize_pagination(page, page_size)
        filters = [Project.organization_id == organization_id]
        if incident_id:
            filters.append(IncidentReport.incident_id == incident_id)
        if project_id:
            filters.append(Incident.project_id == project_id)

        total = int(
            await self._session.scalar(
                select(func.count())
                .select_from(IncidentReport)
                .join(Incident, Incident.id == IncidentReport.incident_id)
                .join(Project, Project.id == Incident.project_id)
                .where(*filters)
            )
            or 0
        )
        stmt = (
            select(IncidentReport, Incident)
            .join(Incident, Incident.id == IncidentReport.incident_id)
            .join(Project, Project.id == Incident.project_id)
            .where(*filters)
            .order_by(IncidentReport.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await self._session.execute(stmt)).all()
        items = [
            ReportListItem(
                id=report.id,
                incident_id=incident.id,
                incident_number=format_incident_number(incident.incident_number),
                incident_title=incident.title,
                format=report.format,
                version=report.version,
                generation_status=report.generation_status.value,
                created_at=report.created_at,
                generated_by=report.generated_by,
            )
            for report, incident in rows
        ]
        paginated = build_paginated_response(
            items=items, page=page, page_size=page_size, total_items=total
        )
        return ReportListResponse(
            items=paginated.items,
            page=paginated.page,
            page_size=paginated.page_size,
            total_items=paginated.total_items,
            total_pages=paginated.total_pages,
        )

    async def get_report(
        self,
        *,
        organization_id: UUID,
        report_id: UUID,
        include_content: bool = True,
    ) -> ReportDetailResponse:
        report, incident = await self._load_report(organization_id, report_id)
        content = None
        if include_content and report.generation_status == GenerationStatus.COMPLETED:
            raw = await self._storage.read(relative_path=report.storage_path)
            content = json.loads(raw.decode("utf-8"))
        return ReportDetailResponse(
            id=report.id,
            incident_id=report.incident_id,
            format=report.format,
            version=report.version,
            generation_status=report.generation_status.value,
            created_at=report.created_at,
            generated_by=report.generated_by,
            download_url=f"/api/v1/reports/{report.id}/download",
            content=content,
        )

    async def download_bytes(
        self,
        *,
        organization_id: UUID,
        report_id: UUID,
    ) -> tuple[IncidentReport, bytes]:
        report, _ = await self._load_report(organization_id, report_id)
        if report.generation_status != GenerationStatus.COMPLETED:
            raise ValidationBusinessError("Report is not ready for download.")
        data = await self._storage.read(relative_path=report.storage_path)
        return report, data

    async def _build_snapshot(
        self,
        incident: Incident,
        body: ReportGenerateRequest,
    ) -> dict:
        snapshot: dict = {
            "generated_at": datetime.now(UTC).isoformat(),
            "incident": {
                "id": str(incident.id),
                "incident_number": format_incident_number(incident.incident_number),
                "title": incident.title,
                "description": incident.description,
                "status": incident.status.value,
                "severity": incident.severity.value,
                "priority": incident.priority.value if incident.priority else None,
                "environment": incident.environment,
                "source": incident.source,
                "detected_at": incident.detected_at.isoformat(),
                "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
                "root_cause_summary": incident.root_cause_summary,
                "impact_summary": incident.impact_summary,
                "tags": incident.tags,
            },
            "project": {
                "id": str(incident.project.id),
                "name": incident.project.name,
                "key": incident.project.key,
            },
        }

        if incident.pipeline_run:
            run = incident.pipeline_run
            snapshot["pipeline_run"] = {
                "id": str(run.id),
                "external_run_id": run.external_run_id,
                "provider": run.provider.value if run.provider else None,
                "workflow_name": run.workflow_name,
                "status": run.status.value,
            }

        latest = incident.latest_analysis_run
        if latest:
            snapshot["analysis"] = {
                "id": str(latest.id),
                "status": latest.status.value,
                "analysis_type": latest.analysis_type,
                "started_at": latest.started_at.isoformat() if latest.started_at else None,
                "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
                "output_summary": latest.output_summary,
            }
            if body.include_evidence:
                snapshot["evidence"] = await self._load_evidence(latest.id)
            if body.include_recommendations:
                snapshot["recommendations"] = await self._load_recommendations(latest.id)
            snapshot["sources"] = await self._load_sources(latest.id)

        if body.include_timeline:
            events = sorted(incident.events, key=lambda e: e.occurred_at)
            snapshot["timeline"] = [timeline_event(e).model_dump() for e in events]

        if body.include_resolution:
            resolutions = sorted(incident.resolutions, key=lambda r: r.created_at, reverse=True)
            snapshot["resolutions"] = [
                {
                    "id": str(r.id),
                    "resolution_summary": r.resolution_summary,
                    "confirmed_root_cause": r.confirmed_root_cause,
                    "resolution_steps": r.resolution_steps,
                    "prevention_actions": r.prevention_actions,
                    "time_spent_minutes": r.time_spent_minutes,
                    "ai_recommendation_used": r.ai_recommendation_used,
                    "created_at": r.created_at.isoformat(),
                }
                for r in resolutions
            ]

        notes = sorted(incident.notes, key=lambda n: n.created_at)
        snapshot["notes"] = [note_to_response(n).model_dump() for n in notes]
        return snapshot

    async def _load_evidence(self, analysis_run_id: UUID) -> list[dict]:
        stmt = (
            select(EvidenceItem)
            .where(EvidenceItem.analysis_run_id == analysis_run_id)
            .order_by(EvidenceItem.importance_score.desc().nullslast())
        )
        items = list((await self._session.scalars(stmt)).all())
        return [
            {
                "id": str(e.id),
                "evidence_type": e.evidence_type.value
                if hasattr(e.evidence_type, "value")
                else str(e.evidence_type),
                "excerpt": e.raw_excerpt,
                "explanation": e.explanation,
                "importance_score": float(e.importance_score)
                if e.importance_score is not None
                else None,
            }
            for e in items
        ]

    async def _load_recommendations(self, analysis_run_id: UUID) -> list[dict]:
        stmt = (
            select(Recommendation)
            .where(Recommendation.analysis_run_id == analysis_run_id)
            .options(selectinload(Recommendation.steps))
        )
        recs = list((await self._session.scalars(stmt)).all())
        result = []
        for rec in recs:
            steps_stmt = (
                select(RecommendationStep)
                .where(RecommendationStep.recommendation_id == rec.id)
                .order_by(RecommendationStep.step_number)
            )
            steps = list((await self._session.scalars(steps_stmt)).all())
            result.append(
                {
                    "id": str(rec.id),
                    "root_cause_summary": rec.root_cause_summary,
                    "explanation": rec.explanation,
                    "confidence_score": float(rec.confidence_score)
                    if rec.confidence_score is not None
                    else None,
                    "steps": [
                        {
                            "step_number": s.step_number,
                            "step_type": s.step_type.value if s.step_type else None,
                            "title": s.title,
                            "action": s.action,
                            "risk_level": s.risk_level.value if s.risk_level else None,
                        }
                        for s in steps
                    ],
                }
            )
        return result

    async def _load_sources(self, analysis_run_id: UUID) -> list[dict]:
        from app.infrastructure.database.models.knowledge_chunk import KnowledgeChunk
        from app.infrastructure.database.models.knowledge_document import KnowledgeDocument

        stmt = (
            select(RetrievedDocument, KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeChunk, KnowledgeChunk.id == RetrievedDocument.knowledge_chunk_id)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(RetrievedDocument.analysis_run_id == analysis_run_id)
            .order_by(RetrievedDocument.rank)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "id": str(doc.id),
                "document_title": document.title,
                "chunk_heading": chunk.heading,
                "similarity_score": float(doc.similarity_score)
                if doc.similarity_score is not None
                else None,
                "rank": doc.rank,
                "used_in_reasoning": doc.used_in_reasoning,
            }
            for doc, chunk, document in rows
        ]

    async def _load_incident(self, organization_id: UUID, incident_id: UUID) -> Incident:
        stmt = (
            select(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(Incident.id == incident_id, Project.organization_id == organization_id)
            .options(
                selectinload(Incident.project),
                selectinload(Incident.pipeline_run),
                selectinload(Incident.latest_analysis_run),
                selectinload(Incident.events),
                selectinload(Incident.notes),
                selectinload(Incident.resolutions),
            )
        )
        incident = await self._session.scalar(stmt)
        if incident is None:
            raise ResourceNotFoundError("Incident not found.")
        return incident

    async def _load_report(
        self,
        organization_id: UUID,
        report_id: UUID,
    ) -> tuple[IncidentReport, Incident]:
        stmt = (
            select(IncidentReport, Incident)
            .join(Incident, Incident.id == IncidentReport.incident_id)
            .join(Project, Project.id == Incident.project_id)
            .where(IncidentReport.id == report_id, Project.organization_id == organization_id)
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            raise ResourceNotFoundError("Report not found.")
        return row[0], row[1]
