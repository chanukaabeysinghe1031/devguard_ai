"""Incident management endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.api.deps.access import require_org_reader, require_org_writer
from app.application.services.incident_note_service import IncidentNoteService
from app.application.services.incident_service import IncidentService
from app.application.services.resolution_service import ResolutionService
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.incident import (
    AcknowledgeResponse,
    IncidentAssignRequest,
    IncidentCreateRequest,
    IncidentDetailResponse,
    IncidentListItem,
    IncidentResponse,
    IncidentStatusChangeRequest,
    IncidentUpdateRequest,
)
from app.schemas.note import NoteCreateRequest, NoteResponse
from app.schemas.resolution import (
    ReopenIncidentRequest,
    ReopenIncidentResponse,
    ResolutionSummary,
    ResolveIncidentRequest,
    ResolveIncidentResponse,
)

router = APIRouter(prefix="/incidents", tags=["Incidents"])


def _incident_service(session: AsyncSession = Depends(get_session)) -> IncidentService:
    return IncidentService(session)


def _note_service(session: AsyncSession = Depends(get_session)) -> IncidentNoteService:
    return IncidentNoteService(session)


def _resolution_service(session: AsyncSession = Depends(get_session)) -> ResolutionService:
    return ResolutionService(session)


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    body: IncidentCreateRequest,
    ctx: tuple = Depends(require_org_writer),
    service: IncidentService = Depends(_incident_service),
) -> IncidentResponse:
    user, organization_id, _ = ctx
    return await service.create(
        organization_id=organization_id,
        created_by=user.id,
        body=body,
    )


@router.get("", response_model=PaginatedResponse[IncidentListItem])
async def list_incidents(
    ctx: tuple = Depends(require_org_reader),
    service: IncidentService = Depends(_incident_service),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
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
    sort_by: str = Query(default="detected_at"),
    sort_order: str = Query(default="desc"),
) -> PaginatedResponse[IncidentListItem]:
    _, organization_id, _ = ctx
    return await service.list_incidents(
        organization_id=organization_id,
        page=page,
        page_size=page_size,
        project_id=project_id,
        pipeline_run_id=pipeline_run_id,
        status=status,
        severity=severity,
        priority=priority,
        environment=environment,
        assignee_id=assignee_id,
        source=source,
        search=search,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident(
    incident_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: IncidentService = Depends(_incident_service),
) -> IncidentDetailResponse:
    _, organization_id, _ = ctx
    return await service.get(organization_id=organization_id, incident_id=incident_id)


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: UUID,
    body: IncidentUpdateRequest,
    ctx: tuple = Depends(require_org_writer),
    service: IncidentService = Depends(_incident_service),
) -> IncidentResponse:
    _, organization_id, _ = ctx
    return await service.update(
        organization_id=organization_id,
        incident_id=incident_id,
        body=body,
    )


@router.post("/{incident_id}/status", response_model=IncidentResponse)
async def change_incident_status(
    incident_id: UUID,
    body: IncidentStatusChangeRequest,
    ctx: tuple = Depends(require_org_writer),
    service: IncidentService = Depends(_incident_service),
) -> IncidentResponse:
    user, organization_id, _ = ctx
    return await service.change_status(
        organization_id=organization_id,
        incident_id=incident_id,
        actor_id=user.id,
        body=body,
    )


@router.post("/{incident_id}/assign", response_model=IncidentResponse)
async def assign_incident(
    incident_id: UUID,
    body: IncidentAssignRequest,
    ctx: tuple = Depends(require_org_writer),
    service: IncidentService = Depends(_incident_service),
) -> IncidentResponse:
    user, organization_id, _ = ctx
    return await service.assign(
        organization_id=organization_id,
        incident_id=incident_id,
        actor_id=user.id,
        user_id=body.user_id,
        reason=body.reason,
    )


@router.post("/{incident_id}/unassign", response_model=MessageResponse)
async def unassign_incident(
    incident_id: UUID,
    ctx: tuple = Depends(require_org_writer),
    service: IncidentService = Depends(_incident_service),
) -> MessageResponse:
    user, organization_id, _ = ctx
    await service.unassign(
        organization_id=organization_id,
        incident_id=incident_id,
        actor_id=user.id,
    )
    return MessageResponse(message="Incident unassigned successfully.")


@router.post("/{incident_id}/acknowledge", response_model=AcknowledgeResponse)
async def acknowledge_incident(
    incident_id: UUID,
    ctx: tuple = Depends(require_org_writer),
    service: IncidentService = Depends(_incident_service),
) -> AcknowledgeResponse:
    user, organization_id, _ = ctx
    return await service.acknowledge(
        organization_id=organization_id,
        incident_id=incident_id,
        actor_id=user.id,
    )


@router.get("/{incident_id}/timeline", response_model=dict)
async def get_incident_timeline(
    incident_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: IncidentService = Depends(_incident_service),
) -> dict:
    _, organization_id, _ = ctx
    items = await service.timeline(organization_id=organization_id, incident_id=incident_id)
    return {"items": items}


@router.post(
    "/{incident_id}/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_incident_note(
    incident_id: UUID,
    body: NoteCreateRequest,
    ctx: tuple = Depends(require_org_writer),
    service: IncidentNoteService = Depends(_note_service),
) -> NoteResponse:
    user, organization_id, _ = ctx
    return await service.create(
        organization_id=organization_id,
        incident_id=incident_id,
        author_id=user.id,
        body=body,
    )


@router.get("/{incident_id}/notes", response_model=list[NoteResponse])
async def list_incident_notes(
    incident_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: IncidentNoteService = Depends(_note_service),
) -> list[NoteResponse]:
    _, organization_id, _ = ctx
    return await service.list_notes(organization_id=organization_id, incident_id=incident_id)


@router.post("/{incident_id}/resolve", response_model=ResolveIncidentResponse)
async def resolve_incident(
    incident_id: UUID,
    body: ResolveIncidentRequest,
    ctx: tuple = Depends(require_org_writer),
    service: ResolutionService = Depends(_resolution_service),
) -> ResolveIncidentResponse:
    user, organization_id, _ = ctx
    return await service.resolve(
        organization_id=organization_id,
        incident_id=incident_id,
        resolved_by=user.id,
        body=body,
    )


@router.post("/{incident_id}/reopen", response_model=ReopenIncidentResponse)
async def reopen_incident(
    incident_id: UUID,
    body: ReopenIncidentRequest,
    ctx: tuple = Depends(require_org_writer),
    service: ResolutionService = Depends(_resolution_service),
) -> ReopenIncidentResponse:
    user, organization_id, _ = ctx
    return await service.reopen(
        organization_id=organization_id,
        incident_id=incident_id,
        actor_id=user.id,
        body=body,
    )


@router.get("/{incident_id}/resolutions", response_model=list[ResolutionSummary])
async def list_incident_resolutions(
    incident_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: ResolutionService = Depends(_resolution_service),
) -> list[ResolutionSummary]:
    _, organization_id, _ = ctx
    return await service.list_resolutions(
        organization_id=organization_id,
        incident_id=incident_id,
    )
