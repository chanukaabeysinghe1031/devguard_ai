"""Incident note application service."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.mappers import note_to_response
from app.domain.enums import OrganizationRole, PlatformRole
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.business import ResourceNotFoundError, ValidationBusinessError
from app.domain.services.incident_transitions import assert_incident_mutable
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_note import IncidentNote
from app.infrastructure.database.models.project import Project
from app.schemas.note import NoteCreateRequest, NoteResponse, NoteUpdateRequest

logger = structlog.get_logger(__name__)

_VALID_NOTE_TYPES = frozenset({"investigation", "resolution", "internal"})


class IncidentNoteService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        author_id: UUID,
        body: NoteCreateRequest,
    ) -> NoteResponse:
        incident = await self._load_incident(organization_id, incident_id)
        assert_incident_mutable(incident.status)
        if body.note_type not in _VALID_NOTE_TYPES:
            raise ValidationBusinessError("Invalid note_type.")

        note = IncidentNote(
            incident_id=incident.id,
            author_id=author_id,
            note_type=body.note_type,
            content=body.content,
            is_pinned=body.is_pinned,
        )
        self._session.add(note)
        await self._session.flush()
        logger.info("incident_note_created", note_id=str(note.id))
        return note_to_response(note)

    async def list_notes(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
    ) -> list[NoteResponse]:
        incident = await self._load_incident(organization_id, incident_id)
        stmt = (
            select(IncidentNote)
            .where(IncidentNote.incident_id == incident.id)
            .order_by(IncidentNote.created_at.desc())
        )
        notes = list((await self._session.scalars(stmt)).all())
        return [note_to_response(note) for note in notes]

    async def update(
        self,
        *,
        organization_id: UUID,
        note_id: UUID,
        actor_id: UUID,
        platform_role: PlatformRole,
        org_role: OrganizationRole | None,
        body: NoteUpdateRequest,
    ) -> NoteResponse:
        note = await self._load_note(organization_id, note_id)
        self._assert_can_modify(note, actor_id, platform_role, org_role)
        if body.content is not None:
            note.content = body.content
        if body.is_pinned is not None:
            note.is_pinned = body.is_pinned
        await self._session.flush()
        return note_to_response(note)

    async def delete(
        self,
        *,
        organization_id: UUID,
        note_id: UUID,
        actor_id: UUID,
        platform_role: PlatformRole,
        org_role: OrganizationRole | None,
    ) -> None:
        note = await self._load_note(organization_id, note_id)
        self._assert_can_modify(note, actor_id, platform_role, org_role, allow_admin=True)
        await self._session.delete(note)
        await self._session.flush()

    def _assert_can_modify(
        self,
        note: IncidentNote,
        actor_id: UUID,
        platform_role: PlatformRole,
        org_role: OrganizationRole | None,
        *,
        allow_admin: bool = False,
    ) -> None:
        if platform_role == PlatformRole.PLATFORM_ADMIN:
            return
        if note.author_id == actor_id:
            return
        if allow_admin and org_role in (
            OrganizationRole.ORGANIZATION_ADMIN,
            OrganizationRole.ORGANIZATION_OWNER,
        ):
            return
        raise AuthorizationError()

    async def _load_incident(self, organization_id: UUID, incident_id: UUID) -> Incident:
        stmt = (
            select(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(Incident.id == incident_id, Project.organization_id == organization_id)
        )
        incident = await self._session.scalar(stmt)
        if incident is None:
            raise ResourceNotFoundError("Incident not found.")
        return incident

    async def _load_note(self, organization_id: UUID, note_id: UUID) -> IncidentNote:
        stmt = (
            select(IncidentNote)
            .join(Incident, Incident.id == IncidentNote.incident_id)
            .join(Project, Project.id == Incident.project_id)
            .where(IncidentNote.id == note_id, Project.organization_id == organization_id)
        )
        note = await self._session.scalar(stmt)
        if note is None:
            raise ResourceNotFoundError("Note not found.")
        return note
