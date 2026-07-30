"""Incident history search — org-scoped historical incident listing."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.services.mappers import _assignee
from app.domain.enums import IncidentSeverity, IncidentStatus
from app.domain.services.incident_transitions import format_incident_number
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_resolution import IncidentResolution
from app.infrastructure.database.models.project import Project
from app.schemas.common import PaginatedResponse, build_paginated_response, normalize_pagination
from app.schemas.history import HistoryIncidentItem
from app.schemas.incident import ProjectSummary


class HistoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_incidents(
        self,
        *,
        organization_id: UUID,
        page: int,
        page_size: int,
        search: str | None = None,
        project_id: UUID | None = None,
        provider: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        environment: str | None = None,
        resolved_by: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: str = "resolved_at",
        sort_order: str = "desc",
    ) -> PaginatedResponse[HistoryIncidentItem]:
        page, page_size, offset = normalize_pagination(page, page_size)
        filters = [Project.organization_id == organization_id]
        if project_id:
            filters.append(Incident.project_id == project_id)
        if severity:
            filters.append(Incident.severity == IncidentSeverity(severity))
        if status:
            filters.append(Incident.status == IncidentStatus(status))
        else:
            filters.append(
                Incident.status.in_(
                    (
                        IncidentStatus.RESOLVED,
                        IncidentStatus.CLOSED,
                        IncidentStatus.FALSE_POSITIVE,
                        IncidentStatus.IGNORED,
                    )
                )
            )
        if environment:
            filters.append(Incident.environment == environment)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(Incident.title.ilike(pattern), Incident.description.ilike(pattern)))
        if date_from:
            filters.append(Incident.detected_at >= date_from)
        if date_to:
            filters.append(Incident.detected_at <= date_to)
        if provider:
            from app.infrastructure.database.models.pipeline_run import PipelineRun

            filters.append(
                Incident.pipeline_run_id.in_(
                    select(PipelineRun.id).where(PipelineRun.provider == provider)
                )
            )
        if resolved_by:
            filters.append(
                Incident.id.in_(
                    select(IncidentResolution.incident_id).where(
                        IncidentResolution.resolved_by == resolved_by
                    )
                )
            )
        if category:
            from app.infrastructure.database.models.failure_category import FailureCategory
            from app.infrastructure.database.models.prediction import Prediction

            filters.append(
                Incident.latest_analysis_run_id.in_(
                    select(Prediction.analysis_run_id)
                    .join(FailureCategory, FailureCategory.id == Prediction.failure_category_id)
                    .where(FailureCategory.code == category, Prediction.rank == 1)
                )
            )

        count_stmt = (
            select(func.count())
            .select_from(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(*filters)
        )
        total = int(await self._session.scalar(count_stmt) or 0)

        order_col = Incident.resolved_at if sort_by == "resolved_at" else Incident.detected_at
        if sort_by == "created_at":
            order_col = Incident.created_at
        order = (
            order_col.desc().nullslast() if sort_order == "desc" else order_col.asc().nullsfirst()
        )

        stmt = (
            select(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(*filters)
            .options(
                selectinload(Incident.project),
                selectinload(Incident.current_assignee),
                selectinload(Incident.latest_analysis_run),
                selectinload(Incident.resolutions),
            )
            .order_by(order)
            .offset(offset)
            .limit(page_size)
        )
        incidents = list((await self._session.scalars(stmt)).all())
        items = [self._to_history_item(inc) for inc in incidents]
        return build_paginated_response(
            items=items, page=page, page_size=page_size, total_items=total
        )

    def _to_history_item(self, incident: Incident) -> HistoryIncidentItem:
        predicted_category, ai_confidence = self._classification(incident)
        resolution_summary = None
        if incident.resolutions:
            latest = max(incident.resolutions, key=lambda r: r.created_at)
            resolution_summary = latest.resolution_summary
        project = incident.project
        return HistoryIncidentItem(
            id=incident.id,
            incident_number=format_incident_number(incident.incident_number),
            title=incident.title,
            project=ProjectSummary(id=project.id, name=project.name, key=project.key),
            severity=incident.severity.value,
            status=incident.status.value,
            environment=incident.environment,
            predicted_category=predicted_category,
            ai_confidence=ai_confidence,
            detected_at=incident.detected_at,
            resolved_at=incident.resolved_at,
            resolution_summary=resolution_summary,
            root_cause_summary=incident.root_cause_summary,
            current_assignee=_assignee(incident.current_assignee),
        )

    @staticmethod
    def _classification(incident: Incident) -> tuple[str | None, float | None]:
        latest = incident.latest_analysis_run
        if latest and latest.output_summary:
            classification = latest.output_summary.get("classification") or {}
            cat = classification.get("category")
            conf = classification.get("confidence")
            if cat:
                return cat, float(conf) if conf is not None else None
        return None, None
