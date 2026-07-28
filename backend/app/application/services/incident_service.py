"""Incident lifecycle application service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.services.mappers import (
    incident_detail,
    incident_list_item,
    incident_to_response,
    timeline_event,
)
from app.domain.enums import IncidentPriority, IncidentSeverity, IncidentStatus, ProjectStatus
from app.domain.exceptions.business import ResourceNotFoundError, ValidationBusinessError
from app.domain.services.incident_transitions import (
    assert_incident_mutable,
    validate_status_transition,
)
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_assignment import IncidentAssignment
from app.infrastructure.database.models.incident_event import IncidentEvent
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.database.models.project import Project
from app.schemas.common import PaginatedResponse, build_paginated_response, normalize_pagination
from app.schemas.incident import (
    AcknowledgeResponse,
    IncidentCreateRequest,
    IncidentDetailResponse,
    IncidentListItem,
    IncidentResponse,
    IncidentStatusChangeRequest,
    IncidentUpdateRequest,
    TimelineEventResponse,
)

logger = structlog.get_logger(__name__)

_OPEN_STATUSES = (
    IncidentStatus.DETECTED,
    IncidentStatus.ANALYSING,
    IncidentStatus.OPEN,
    IncidentStatus.IN_PROGRESS,
    IncidentStatus.ANALYSIS_FAILED,
    IncidentStatus.REOPENED,
)


class IncidentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        created_by: UUID,
        body: IncidentCreateRequest,
    ) -> IncidentResponse:
        project = await self._get_writable_project(organization_id, body.project_id)
        if body.pipeline_run_id is not None:
            run = await self._session.get(PipelineRun, body.pipeline_run_id)
            if run is None or run.project_id != project.id:
                raise ValidationBusinessError("Pipeline run does not belong to the project.")

        try:
            severity = IncidentSeverity(body.severity)
            priority = IncidentPriority(body.priority) if body.priority else None
        except ValueError as exc:
            raise ValidationBusinessError("Invalid severity or priority.") from exc

        now = datetime.now(UTC)
        incident = Incident(
            project_id=project.id,
            pipeline_run_id=body.pipeline_run_id,
            title=body.title.strip(),
            description=body.description,
            source=body.source,
            status=IncidentStatus.DETECTED,
            severity=severity,
            priority=priority,
            environment=body.environment,
            detected_at=now,
            created_by=created_by,
        )
        self._session.add(incident)
        await self._session.flush()
        await self._record_event(
            incident=incident,
            event_type="incident_created",
            actor_type="user",
            actor_user_id=created_by,
            title="Incident created",
            description=body.description,
        )
        logger.info("incident_created", incident_id=str(incident.id))
        return incident_to_response(incident)

    async def list_incidents(
        self,
        *,
        organization_id: UUID,
        page: int,
        page_size: int,
        project_id: UUID | None = None,
        pipeline_run_id: UUID | None = None,
        status: str | None = None,
        severity: str | None = None,
        priority: str | None = None,
        environment: str | None = None,
        assignee_id: UUID | None = None,
        source: str | None = None,
        search: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: str = "detected_at",
        sort_order: str = "desc",
    ) -> PaginatedResponse[IncidentListItem]:
        page, page_size, offset = normalize_pagination(page, page_size)
        filters = [Project.organization_id == organization_id]
        if project_id:
            filters.append(Incident.project_id == project_id)
        if pipeline_run_id:
            filters.append(Incident.pipeline_run_id == pipeline_run_id)
        if status:
            filters.append(Incident.status == IncidentStatus(status))
        if severity:
            filters.append(Incident.severity == IncidentSeverity(severity))
        if priority:
            filters.append(Incident.priority == IncidentPriority(priority))
        if environment:
            filters.append(Incident.environment == environment)
        if assignee_id:
            filters.append(Incident.current_assignee_id == assignee_id)
        if source:
            filters.append(Incident.source == source)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(Incident.title.ilike(pattern), Incident.description.ilike(pattern)))
        if date_from:
            filters.append(Incident.detected_at >= date_from)
        if date_to:
            filters.append(Incident.detected_at <= date_to)

        count_stmt = (
            select(func.count())
            .select_from(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(*filters)
        )
        total = int(await self._session.scalar(count_stmt) or 0)

        order_col = Incident.detected_at if sort_by != "created_at" else Incident.created_at
        order = order_col.desc() if sort_order == "desc" else order_col.asc()
        stmt = (
            select(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(*filters)
            .options(
                selectinload(Incident.project),
                selectinload(Incident.current_assignee),
            )
            .order_by(order)
            .offset(offset)
            .limit(page_size)
        )
        incidents = list((await self._session.scalars(stmt)).all())
        items = [incident_list_item(inc) for inc in incidents]
        return build_paginated_response(
            items=items, page=page, page_size=page_size, total_items=total
        )

    async def get(self, *, organization_id: UUID, incident_id: UUID) -> IncidentDetailResponse:
        incident = await self._load_incident(organization_id, incident_id)
        return incident_detail(incident)

    async def update(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        body: IncidentUpdateRequest,
    ) -> IncidentResponse:
        incident = await self._load_incident(organization_id, incident_id)
        assert_incident_mutable(incident.status)
        if body.title is not None:
            incident.title = body.title.strip()
        if body.severity is not None:
            incident.severity = IncidentSeverity(body.severity)
        if body.priority is not None:
            incident.priority = IncidentPriority(body.priority)
        if body.tags is not None:
            incident.tags = body.tags
        await self._session.flush()
        return incident_to_response(incident)

    async def change_status(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        actor_id: UUID,
        body: IncidentStatusChangeRequest,
    ) -> IncidentResponse:
        incident = await self._load_incident(organization_id, incident_id)
        target = IncidentStatus(body.status)
        previous = incident.status
        validate_status_transition(previous, target)
        incident.status = target
        now = datetime.now(UTC)
        if target == IncidentStatus.RESOLVED:
            incident.resolved_at = now
        if target == IncidentStatus.CLOSED:
            incident.closed_at = now
        await self._record_event(
            incident=incident,
            event_type="status_changed",
            actor_type="user",
            actor_user_id=actor_id,
            title=f"Status changed to {target.value}",
            description=body.comment,
            metadata={"from": previous.value, "to": target.value},
        )
        await self._session.flush()
        return incident_to_response(incident)

    async def assign(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        actor_id: UUID,
        user_id: UUID,
        reason: str | None,
    ) -> IncidentResponse:
        incident = await self._load_incident(organization_id, incident_id)
        assert_incident_mutable(incident.status)
        await self._ensure_org_member(organization_id, user_id)
        incident.current_assignee_id = user_id
        self._session.add(
            IncidentAssignment(
                incident_id=incident.id,
                assigned_to=user_id,
                assigned_by=actor_id,
                reason=reason,
            )
        )
        await self._record_event(
            incident=incident,
            event_type="assigned",
            actor_type="user",
            actor_user_id=actor_id,
            title="Incident assigned",
            description=reason,
            metadata={"assigned_to": str(user_id)},
        )
        await self._session.flush()
        return incident_to_response(incident)

    async def unassign(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        actor_id: UUID,
    ) -> None:
        incident = await self._load_incident(organization_id, incident_id)
        assert_incident_mutable(incident.status)
        if incident.current_assignee_id is None:
            return
        now = datetime.now(UTC)
        active = await self._session.scalar(
            select(IncidentAssignment).where(
                IncidentAssignment.incident_id == incident.id,
                IncidentAssignment.unassigned_at.is_(None),
            )
        )
        if active is not None:
            active.unassigned_at = now
        incident.current_assignee_id = None
        await self._record_event(
            incident=incident,
            event_type="unassigned",
            actor_type="user",
            actor_user_id=actor_id,
            title="Incident unassigned",
        )
        await self._session.flush()

    async def acknowledge(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        actor_id: UUID,
    ) -> AcknowledgeResponse:
        incident = await self._load_incident(organization_id, incident_id)
        now = datetime.now(UTC)
        incident.acknowledged_at = now
        await self._record_event(
            incident=incident,
            event_type="acknowledged",
            actor_type="user",
            actor_user_id=actor_id,
            title="Incident acknowledged",
        )
        await self._session.flush()
        return AcknowledgeResponse(acknowledged_at=now)

    async def timeline(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
    ) -> list[TimelineEventResponse]:
        incident = await self._load_incident(organization_id, incident_id)
        stmt = (
            select(IncidentEvent)
            .where(IncidentEvent.incident_id == incident.id)
            .order_by(IncidentEvent.occurred_at.asc())
        )
        events = list((await self._session.scalars(stmt)).all())
        return [timeline_event(event) for event in events]

    async def _load_incident(self, organization_id: UUID, incident_id: UUID) -> Incident:
        stmt = (
            select(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(Incident.id == incident_id, Project.organization_id == organization_id)
            .options(
                selectinload(Incident.project),
                selectinload(Incident.pipeline_run),
                selectinload(Incident.current_assignee),
                selectinload(Incident.latest_analysis_run),
            )
        )
        incident = await self._session.scalar(stmt)
        if incident is None:
            raise ResourceNotFoundError("Incident not found.")
        return incident

    async def _get_writable_project(
        self,
        organization_id: UUID,
        project_id: UUID,
    ) -> Project:
        project = await self._session.get(Project, project_id)
        if project is None or project.organization_id != organization_id:
            raise ResourceNotFoundError("Project not found.")
        if project.status == ProjectStatus.ARCHIVED:
            raise ValidationBusinessError("Cannot create incidents for an archived project.")
        return project

    async def _ensure_org_member(self, organization_id: UUID, user_id: UUID) -> None:
        member = await self._session.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active.is_(True),
            )
        )
        if member is None:
            raise ValidationBusinessError("Assignee must be an active organization member.")

    async def _record_event(
        self,
        *,
        incident: Incident,
        event_type: str,
        actor_type: str,
        title: str,
        actor_user_id: UUID | None = None,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._session.add(
            IncidentEvent(
                incident_id=incident.id,
                event_type=event_type,
                actor_type=actor_type,
                actor_user_id=actor_user_id,
                title=title,
                description=description,
                event_metadata=metadata,
                occurred_at=datetime.now(UTC),
            )
        )
