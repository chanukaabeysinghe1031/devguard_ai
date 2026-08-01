"""Incident resolution application service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.mappers import resolution_to_summary
from app.domain.enums import IncidentStatus
from app.domain.exceptions.business import ResourceNotFoundError
from app.domain.services.incident_transitions import validate_status_transition
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_event import IncidentEvent
from app.infrastructure.database.models.incident_resolution import IncidentResolution
from app.schemas.resolution import (
    ReopenIncidentRequest,
    ReopenIncidentResponse,
    ResolutionSummary,
    ResolveIncidentRequest,
    ResolveIncidentResponse,
)

logger = structlog.get_logger(__name__)


class ResolutionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        resolved_by: UUID,
        body: ResolveIncidentRequest,
    ) -> ResolveIncidentResponse:
        incident = await self._load_incident(organization_id, incident_id)
        validate_status_transition(incident.status, IncidentStatus.RESOLVED)
        now = datetime.now(UTC)
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now

        resolution = IncidentResolution(
            incident_id=incident.id,
            resolved_by=resolved_by,
            resolution_summary=body.resolution_summary,
            confirmed_root_cause=body.confirmed_root_cause,
            resolution_steps=[{"description": s} for s in body.resolution_steps],
            prevention_actions=[{"description": s} for s in body.prevention_actions],
            time_spent_minutes=body.time_spent_minutes,
            ai_recommendation_used=body.ai_recommendation_used,
        )
        self._session.add(resolution)
        await self._record_event(
            incident_id=incident.id,
            actor_id=resolved_by,
            event_type="resolution_added",
            title="Incident resolved",
            description=body.resolution_summary,
        )
        await self._session.flush()
        from app.application.services.notification_service import NotificationService

        await NotificationService(self._session).notify_resolved(
            incident=incident,
            resolved_by=resolved_by,
            resolution_summary=body.resolution_summary,
        )
        logger.info("incident_resolved", incident_id=str(incident.id))
        return ResolveIncidentResponse(
            incident_id=incident.id,
            status=IncidentStatus.RESOLVED.value,
            resolved_at=now,
            resolution=resolution_to_summary(resolution),
        )

    async def reopen(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        actor_id: UUID,
        body: ReopenIncidentRequest,
    ) -> ReopenIncidentResponse:
        incident = await self._load_incident(organization_id, incident_id)
        validate_status_transition(incident.status, IncidentStatus.REOPENED)
        incident.status = IncidentStatus.REOPENED
        incident.resolved_at = None
        incident.closed_at = None
        await self._record_event(
            incident_id=incident.id,
            actor_id=actor_id,
            event_type="status_changed",
            title="Incident reopened",
            description=body.reason,
            metadata={"to": IncidentStatus.REOPENED.value},
        )
        await self._session.flush()
        return ReopenIncidentResponse(
            incident_id=incident.id,
            status=IncidentStatus.REOPENED.value,
            message="Incident reopened successfully.",
        )

    async def list_resolutions(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
    ) -> list[ResolutionSummary]:
        incident = await self._load_incident(organization_id, incident_id)
        stmt = (
            select(IncidentResolution)
            .where(IncidentResolution.incident_id == incident.id)
            .order_by(IncidentResolution.created_at.desc())
        )
        resolutions = list((await self._session.scalars(stmt)).all())
        return [resolution_to_summary(r) for r in resolutions]

    async def _load_incident(self, organization_id: UUID, incident_id: UUID) -> Incident:
        stmt = select(Incident).where(
            Incident.id == incident_id, Incident.organization_id == organization_id
        )
        incident = await self._session.scalar(stmt)
        if incident is None:
            raise ResourceNotFoundError("Incident not found.")
        return incident

    async def _record_event(
        self,
        *,
        incident_id: UUID,
        actor_id: UUID,
        event_type: str,
        title: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        organization_id = await self._session.scalar(
            select(Incident.organization_id).where(Incident.id == incident_id)
        )
        if organization_id is None:
            return
        self._session.add(
            IncidentEvent(
                organization_id=organization_id,
                incident_id=incident_id,
                event_type=event_type,
                actor_type="user",
                actor_user_id=actor_id,
                title=title,
                description=description,
                event_metadata=metadata,
                occurred_at=datetime.now(UTC),
            )
        )
