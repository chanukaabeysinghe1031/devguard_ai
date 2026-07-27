"""Standalone incident note update/delete endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.api.deps.access import require_org_writer
from app.application.services.incident_note_service import IncidentNoteService
from app.schemas.note import NoteResponse, NoteUpdateRequest

router = APIRouter(prefix="/notes", tags=["Incident Notes"])


def _service(session: AsyncSession = Depends(get_session)) -> IncidentNoteService:
    return IncidentNoteService(session)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    body: NoteUpdateRequest,
    ctx: tuple = Depends(require_org_writer),
    service: IncidentNoteService = Depends(_service),
) -> NoteResponse:
    user, organization_id, role = ctx
    return await service.update(
        organization_id=organization_id,
        note_id=note_id,
        actor_id=user.id,
        platform_role=user.platform_role,
        org_role=role,
        body=body,
    )


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    ctx: tuple = Depends(require_org_writer),
    service: IncidentNoteService = Depends(_service),
) -> None:
    user, organization_id, role = ctx
    await service.delete(
        organization_id=organization_id,
        note_id=note_id,
        actor_id=user.id,
        platform_role=user.platform_role,
        org_role=role,
    )
