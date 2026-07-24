"""Repository integration tests (isolated test database)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.entities.failure_category import FailureCategoryEntity
from app.domain.entities.pipeline_run import PipelineRunEntity
from app.domain.entities.user import UserEntity
from app.domain.enums import CiProvider, PipelineRunStatus, PlatformRole
from app.domain.exceptions.repository import DuplicateEntityError
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.user import User
from app.infrastructure.database.seed import APPROVED_FAILURE_CATEGORIES, seed_failure_categories
from app.infrastructure.repositories.failure_category_repository import (
    SQLAlchemyFailureCategoryRepository,
)
from app.infrastructure.repositories.pipeline_run_repository import (
    SQLAlchemyPipelineRunRepository,
)
from app.infrastructure.repositories.user_repository import SQLAlchemyUserRepository


def _sample_user(**overrides: object) -> UserEntity:
    defaults: dict[str, object] = {
        "id": None,
        "email": "engineer@example.com",
        "password_hash": "pbkdf2_sha256$deadbeef$abc123",
        "full_name": "Test Engineer",
        "platform_role": PlatformRole.NONE,
    }
    defaults.update(overrides)
    return UserEntity(**defaults)  # type: ignore[arg-type]


async def _create_project(session, *, key: str = "PROJ") -> Project:
    """Create the organization + creator user + project scaffolding required
    by a project-owned pipeline run."""
    organization = Organization(name="Acme Corp", slug=f"acme-{key.lower()}")
    session.add(organization)
    await session.flush()

    creator = User(
        email=f"creator-{key.lower()}@example.com",
        password_hash="pbkdf2_sha256$deadbeef$abc123",
        full_name="Project Creator",
    )
    session.add(creator)
    await session.flush()

    project = Project(
        organization_id=organization.id,
        name="Sample Project",
        key=key,
        ci_provider=CiProvider.GITHUB_ACTIONS,
        created_by=creator.id,
    )
    session.add(project)
    await session.flush()
    return project


# ---------------------------------------------------------------------------
# User repository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_repository_add_and_retrieve(repository_db_session) -> None:
    repo = SQLAlchemyUserRepository(repository_db_session)
    created = await repo.add(_sample_user())
    await repository_db_session.commit()

    fetched = await repo.get_by_id(created.id)  # type: ignore[arg-type]
    assert fetched is not None
    assert fetched.email == "engineer@example.com"
    assert fetched.full_name == "Test Engineer"
    assert fetched.platform_role == PlatformRole.NONE


@pytest.mark.asyncio
async def test_user_repository_get_by_email_case_insensitive(repository_db_session) -> None:
    repo = SQLAlchemyUserRepository(repository_db_session)
    await repo.add(_sample_user(email="Engineer@Example.com"))
    await repository_db_session.commit()

    fetched = await repo.get_by_email("engineer@example.com")
    assert fetched is not None
    assert fetched.email == "Engineer@Example.com"


@pytest.mark.asyncio
async def test_user_repository_duplicate_email_raises(repository_db_session) -> None:
    repo = SQLAlchemyUserRepository(repository_db_session)
    await repo.add(_sample_user(email="duplicate@example.com"))
    await repository_db_session.commit()

    with pytest.raises(DuplicateEntityError):
        await repo.add(_sample_user(email="DUPLICATE@example.com"))


@pytest.mark.asyncio
async def test_user_repository_deactivate_sets_inactive(repository_db_session) -> None:
    repo = SQLAlchemyUserRepository(repository_db_session)
    created = await repo.add(_sample_user())
    await repository_db_session.commit()

    deactivated = await repo.deactivate(created.id)  # type: ignore[arg-type]
    await repository_db_session.commit()

    assert deactivated.is_active is False
    refetched = await repo.get_by_id(created.id)  # type: ignore[arg-type]
    assert refetched is not None
    assert refetched.is_active is False


@pytest.mark.asyncio
async def test_user_repository_list_pagination(repository_db_session) -> None:
    repo = SQLAlchemyUserRepository(repository_db_session)
    for index in range(3):
        await repo.add(_sample_user(email=f"user{index}@example.com"))
    await repository_db_session.commit()

    page = await repo.list(offset=1, limit=1)
    assert len(page) == 1


@pytest.mark.asyncio
async def test_user_repository_platform_admin_role_persists(repository_db_session) -> None:
    repo = SQLAlchemyUserRepository(repository_db_session)
    created = await repo.add(_sample_user(platform_role=PlatformRole.PLATFORM_ADMIN))
    await repository_db_session.commit()

    fetched = await repo.get_by_id(created.id)  # type: ignore[arg-type]
    assert fetched is not None
    assert fetched.platform_role == PlatformRole.PLATFORM_ADMIN


# ---------------------------------------------------------------------------
# Failure category repository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failure_category_repository_get_by_code(repository_db_session) -> None:
    await seed_failure_categories(repository_db_session)
    await repository_db_session.commit()

    repo = SQLAlchemyFailureCategoryRepository(repository_db_session)
    category = await repo.get_by_code("build_failure")

    assert category is not None
    assert category.name == "Build Failure"
    assert category.is_active is True


@pytest.mark.asyncio
async def test_failure_category_repository_list_active_returns_11_approved(
    repository_db_session,
) -> None:
    await seed_failure_categories(repository_db_session)
    await repository_db_session.commit()

    repo = SQLAlchemyFailureCategoryRepository(repository_db_session)
    active = await repo.list_active(limit=100)

    assert len(active) == 11
    assert {category.code for category in active} == {
        category["code"] for category in APPROVED_FAILURE_CATEGORIES
    }


@pytest.mark.asyncio
async def test_failure_category_repository_duplicate_code_raises(repository_db_session) -> None:
    repo = SQLAlchemyFailureCategoryRepository(repository_db_session)
    await repo.add(
        FailureCategoryEntity(
            id=None,
            name="Build Failure",
            code="build_failure",
            description="Duplicate seed code.",
        )
    )
    await repository_db_session.commit()

    with pytest.raises(DuplicateEntityError):
        await repo.add(
            FailureCategoryEntity(
                id=None,
                name="Another Build Failure",
                code="build_failure",
                description="Conflicting code.",
            )
        )


@pytest.mark.asyncio
async def test_failure_category_repository_preserves_custom_category(
    repository_db_session,
) -> None:
    await seed_failure_categories(repository_db_session)
    await repository_db_session.commit()

    repo = SQLAlchemyFailureCategoryRepository(repository_db_session)
    custom = await repo.add(
        FailureCategoryEntity(
            id=None,
            name="Custom Runtime Issue",
            code="custom_runtime_issue",
            description="User-defined category.",
        )
    )
    await repository_db_session.commit()

    seeded = await repo.get_by_code("build_failure")
    assert seeded is not None
    assert custom.code == "custom_runtime_issue"
    assert len(await repo.list(limit=100)) == 12


# ---------------------------------------------------------------------------
# Pipeline run repository (project-owned, no user_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_run_repository_add_and_retrieve(repository_db_session) -> None:
    project = await _create_project(repository_db_session, key="ADD")

    repo = SQLAlchemyPipelineRunRepository(repository_db_session)
    created = await repo.add(
        PipelineRunEntity(
            id=None,
            project_id=project.id,
            provider=CiProvider.GITHUB_ACTIONS,
            workflow_name="ci-build",
        )
    )
    await repository_db_session.commit()

    fetched = await repo.get_by_id(created.id)  # type: ignore[arg-type]
    assert fetched is not None
    assert fetched.project_id == project.id
    assert fetched.workflow_name == "ci-build"
    assert fetched.status == PipelineRunStatus.QUEUED


@pytest.mark.asyncio
async def test_pipeline_run_repository_list_by_project_orders_desc(repository_db_session) -> None:
    project = await _create_project(repository_db_session, key="ORD")

    repo = SQLAlchemyPipelineRunRepository(repository_db_session)
    older = await repo.add(
        PipelineRunEntity(
            id=None,
            project_id=project.id,
            provider=CiProvider.GITHUB_ACTIONS,
            workflow_name="older-run",
        )
    )
    await repository_db_session.flush()

    older_model = await repository_db_session.get(PipelineRun, older.id)
    assert older_model is not None
    older_model.created_at = datetime.now(UTC) - timedelta(hours=1)
    await repository_db_session.flush()

    newer = await repo.add(
        PipelineRunEntity(
            id=None,
            project_id=project.id,
            provider=CiProvider.GITHUB_ACTIONS,
            workflow_name="newer-run",
        )
    )
    await repository_db_session.commit()

    runs = await repo.list_by_project(project.id, limit=10)
    assert [run.workflow_name for run in runs] == ["newer-run", "older-run"]
    assert runs[0].id == newer.id


@pytest.mark.asyncio
async def test_pipeline_run_repository_list_by_status(repository_db_session) -> None:
    project = await _create_project(repository_db_session, key="STA")

    repo = SQLAlchemyPipelineRunRepository(repository_db_session)
    await repo.add(
        PipelineRunEntity(
            id=None,
            project_id=project.id,
            provider=CiProvider.GITHUB_ACTIONS,
            status=PipelineRunStatus.QUEUED,
        )
    )
    await repo.add(
        PipelineRunEntity(
            id=None,
            project_id=project.id,
            provider=CiProvider.GITHUB_ACTIONS,
            status=PipelineRunStatus.SUCCEEDED,
        )
    )
    await repository_db_session.commit()

    queued = await repo.list_by_status(PipelineRunStatus.QUEUED)
    assert len(queued) == 1
    assert queued[0].status == PipelineRunStatus.QUEUED


@pytest.mark.asyncio
async def test_pipeline_run_repository_pagination(repository_db_session) -> None:
    project = await _create_project(repository_db_session, key="PAG")

    repo = SQLAlchemyPipelineRunRepository(repository_db_session)
    for index in range(3):
        await repo.add(
            PipelineRunEntity(
                id=None,
                project_id=project.id,
                provider=CiProvider.GITHUB_ACTIONS,
                workflow_name=f"run-{index}",
            )
        )
    await repository_db_session.commit()

    page = await repo.list(offset=1, limit=1)
    assert len(page) == 1


@pytest.mark.asyncio
async def test_pipeline_run_repository_foreign_keys_remain_valid(repository_db_session) -> None:
    project = await _create_project(repository_db_session, key="FK")

    repo = SQLAlchemyPipelineRunRepository(repository_db_session)
    created = await repo.add(
        PipelineRunEntity(
            id=None,
            project_id=project.id,
            provider=CiProvider.GITHUB_ACTIONS,
        )
    )
    await repository_db_session.commit()

    model = await repository_db_session.get(PipelineRun, created.id)
    assert model is not None
    assert model.project_id == project.id
