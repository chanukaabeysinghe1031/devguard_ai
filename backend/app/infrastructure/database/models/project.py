"""Project (monitored software project/application) model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import CiProvider, ProjectStatus
from app.infrastructure.database.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPrimaryKeyMixin,
)
from app.infrastructure.database.enums import ci_provider_enum, project_status_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.organization import Organization
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.project_integration import ProjectIntegration
    from app.infrastructure.database.models.uploaded_file import UploadedFile
    from app.infrastructure.database.models.user import User


class Project(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """A monitored software project or application, scoped to an organization."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_projects_organization_key"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    key: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    repository_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ci_provider: Mapped[CiProvider] = mapped_column(ci_provider_enum, nullable=False)
    cloud_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        project_status_enum,
        nullable=False,
        default=ProjectStatus.ACTIVE,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="projects")
    creator: Mapped[User] = relationship(back_populates="created_projects")
    integrations: Mapped[list[ProjectIntegration]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    pipeline_runs: Mapped[list[PipelineRun]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    incidents: Mapped[list[Incident]] = relationship(back_populates="project")
    uploaded_files: Mapped[list[UploadedFile]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
