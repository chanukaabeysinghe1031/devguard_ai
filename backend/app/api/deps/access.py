"""Organization-scoped resource access helpers."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_session
from app.api.deps.auth import AuthenticatedUser, get_current_user, resolve_organization_membership
from app.domain.enums import OrganizationRole, PlatformRole
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.business import ResourceNotFoundError
from app.infrastructure.database.models.analysis_run import AnalysisRun
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_note import IncidentNote
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.project import Project

WRITE_ROLES = (
    OrganizationRole.ENGINEER,
    OrganizationRole.ORGANIZATION_ADMIN,
    OrganizationRole.ORGANIZATION_OWNER,
)
ADMIN_ROLES = (
    OrganizationRole.ORGANIZATION_ADMIN,
    OrganizationRole.ORGANIZATION_OWNER,
)


async def get_organization_id_header(
    x_organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
) -> UUID:
    if x_organization_id is None:
        raise AuthorizationError("X-Organization-Id header is required.")
    return x_organization_id


async def resolve_org_context(
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    organization_id: UUID = Depends(get_organization_id_header),
) -> tuple[AuthenticatedUser, UUID, OrganizationRole | None]:
    """Resolve caller and organization. Platform admins bypass membership checks."""
    if current_user.platform_role == PlatformRole.PLATFORM_ADMIN:
        org = await session.get(Organization, organization_id)
        if org is None:
            raise ResourceNotFoundError("Organization not found.")
        return current_user, organization_id, None

    membership = await resolve_organization_membership(
        session=session,
        user_id=current_user.id,
        organization_id=organization_id,
    )
    return current_user, organization_id, membership.role


def _assert_role(role: OrganizationRole | None, allowed: tuple[OrganizationRole, ...]) -> None:
    if role is None:
        return
    if role not in allowed:
        raise AuthorizationError()


async def require_org_reader(
    ctx: tuple[AuthenticatedUser, UUID, OrganizationRole | None] = Depends(resolve_org_context),
) -> tuple[AuthenticatedUser, UUID, OrganizationRole | None]:
    return ctx


async def require_org_writer(
    ctx: tuple[AuthenticatedUser, UUID, OrganizationRole | None] = Depends(resolve_org_context),
) -> tuple[AuthenticatedUser, UUID, OrganizationRole | None]:
    user, org_id, role = ctx
    _assert_role(role, WRITE_ROLES)
    return user, org_id, role


async def require_org_admin(
    ctx: tuple[AuthenticatedUser, UUID, OrganizationRole | None] = Depends(resolve_org_context),
) -> tuple[AuthenticatedUser, UUID, OrganizationRole | None]:
    user, org_id, role = ctx
    _assert_role(role, ADMIN_ROLES)
    return user, org_id, role


async def load_project_in_org(
    session: AsyncSession,
    *,
    project_id: UUID,
    organization_id: UUID,
) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.organization_id != organization_id:
        raise ResourceNotFoundError("Project not found.")
    return project


async def load_incident_in_org(
    session: AsyncSession,
    *,
    incident_id: UUID,
    organization_id: UUID,
) -> Incident:
    stmt = (
        select(Incident)
        .where(Incident.id == incident_id)
        .options(
            selectinload(Incident.project),
            selectinload(Incident.pipeline_run),
            selectinload(Incident.current_assignee),
            selectinload(Incident.latest_analysis_run),
        )
    )
    incident = await session.scalar(stmt)
    if incident is None or incident.project.organization_id != organization_id:
        raise ResourceNotFoundError("Incident not found.")
    return incident


async def load_pipeline_run_in_org(
    session: AsyncSession,
    *,
    pipeline_run_id: UUID,
    organization_id: UUID,
) -> tuple[object, Project]:
    from app.infrastructure.database.models.pipeline_run import PipelineRun

    stmt = (
        select(PipelineRun)
        .where(PipelineRun.id == pipeline_run_id)
        .options(selectinload(PipelineRun.project))
    )
    run = await session.scalar(stmt)
    if run is None or run.project.organization_id != organization_id:
        raise ResourceNotFoundError("Pipeline run not found.")
    return run, run.project


async def load_note_in_org(
    session: AsyncSession,
    *,
    note_id: UUID,
    organization_id: UUID,
) -> IncidentNote:
    stmt = (
        select(IncidentNote)
        .where(IncidentNote.id == note_id)
        .options(selectinload(IncidentNote.incident).selectinload(Incident.project))
    )
    note = await session.scalar(stmt)
    if note is None or note.incident.project.organization_id != organization_id:
        raise ResourceNotFoundError("Note not found.")
    return note


async def load_analysis_run_in_org(
    session: AsyncSession,
    *,
    analysis_run_id: UUID,
    organization_id: UUID,
) -> AnalysisRun:
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.id == analysis_run_id)
        .options(selectinload(AnalysisRun.incident).selectinload(Incident.project))
    )
    run = await session.scalar(stmt)
    if run is None or run.incident.project.organization_id != organization_id:
        raise ResourceNotFoundError("Analysis run not found.")
    return run
