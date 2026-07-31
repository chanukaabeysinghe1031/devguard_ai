"""Phase 5C migration 010 — denormalized organization_id invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.domain.enums import (
    CiProvider,
    IncidentSeverity,
    IncidentStatus,
    InvitationStatus,
    OrganizationRole,
    PlatformRole,
)
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_event import IncidentEvent
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.organization_invitation import OrganizationInvitation
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.user import User


@pytest.mark.asyncio
async def test_incident_requires_organization_id_matching_project(repository_db_session) -> None:
    org = Organization(name="Acme", slug=f"acme-{uuid4().hex[:8]}", company_name="Acme Ltd")
    user = User(
        email=f"owner-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        full_name="Owner",
        platform_role=PlatformRole.NONE,
    )
    repository_db_session.add_all([org, user])
    await repository_db_session.flush()

    project = Project(
        organization_id=org.id,
        name="App",
        key="APP",
        ci_provider=CiProvider.GITHUB_ACTIONS,
        created_by=user.id,
    )
    repository_db_session.add(project)
    await repository_db_session.flush()

    incident = Incident(
        organization_id=org.id,
        project_id=project.id,
        title="Fail",
        source="manual",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.DETECTED,
        detected_at=datetime.now(UTC),
    )
    repository_db_session.add(incident)
    await repository_db_session.flush()

    event = IncidentEvent(
        organization_id=org.id,
        incident_id=incident.id,
        event_type="incident_created",
        actor_type="user",
        title="Created",
        occurred_at=datetime.now(UTC),
    )
    repository_db_session.add(event)
    await repository_db_session.commit()

    loaded = await repository_db_session.scalar(select(Incident).where(Incident.id == incident.id))
    assert loaded is not None
    assert loaded.organization_id == org.id


@pytest.mark.asyncio
async def test_organization_invitation_persists_pending_link_invite(repository_db_session) -> None:
    org = Organization(name="Invite Co", slug=f"inv-{uuid4().hex[:8]}")
    user = User(
        email=f"admin-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        full_name="Admin",
        platform_role=PlatformRole.NONE,
    )
    repository_db_session.add_all([org, user])
    await repository_db_session.flush()

    invite = OrganizationInvitation(
        organization_id=org.id,
        email="engineer@example.com",
        role=OrganizationRole.ENGINEER,
        token_hash="a" * 64,
        status=InvitationStatus.PENDING,
        invited_by=user.id,
        expires_at=datetime.now(UTC),
    )
    repository_db_session.add(invite)
    await repository_db_session.commit()

    loaded = await repository_db_session.get(OrganizationInvitation, invite.id)
    assert loaded is not None
    assert loaded.status == InvitationStatus.PENDING
    assert loaded.role == OrganizationRole.ENGINEER
