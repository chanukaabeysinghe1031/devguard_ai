"""Repository integration tests (isolated test database)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.entities.failure_category import FailureCategoryEntity
from app.domain.entities.pipeline_run import PipelineRunEntity
from app.domain.entities.user import UserEntity
from app.domain.enums import FileType, PipelineRunStatus, UserRole
from app.domain.exceptions.repository import DuplicateEntityError
from app.infrastructure.database.models.uploaded_file import UploadedFile
from app.infrastructure.database.models.user import User
from app.infrastructure.database.seed import APPROVED_FAILURE_CATEGORIES, seed_failure_categories
from app.infrastructure.repositories.failure_category_repository import (
    SQLAlchemyFailureCategoryRepository,
)
from app.infrastructure.repositories.pipeline_run_repository import SQLAlchemyPipelineRunRepository
from app.infrastructure.repositories.user_repository import SQLAlchemyUserRepository


def _sample_user(**overrides: object) -> UserEntity:
    defaults = {
        "id": None,
        "email": "analyst@example.com",
        "hashed_password": "hashed-secret",
        "full_name": "Test Analyst",
        "role": UserRole.ANALYST,
        "is_active": True,
    }
    defaults.update(overrides)
    return UserEntity(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_user_repository_add_and_retrieve(repository_db_session) -> None:
    repo = SQLAlchemyUserRepository(repository_db_session)
    created = await repo.add(_sample_user())
    await repository_db_session.commit()

    fetched = await repo.get_by_id(created.id)  # type: ignore[arg-type]
    assert fetched is not None
    assert fetched.email == "analyst@example.com"
    assert fetched.full_name == "Test Analyst"


@pytest.mark.asyncio
async def test_user_repository_get_by_email_case_insensitive(repository_db_session) -> None:
    repo = SQLAlchemyUserRepository(repository_db_session)
    await repo.add(_sample_user(email="Analyst@Example.com"))
    await repository_db_session.commit()

    fetched = await repo.get_by_email("analyst@example.com")
    assert fetched is not None
    assert fetched.email == "Analyst@Example.com"


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
async def test_failure_category_repository_get_by_slug(repository_db_session) -> None:
    await seed_failure_categories(repository_db_session)
    await repository_db_session.commit()

    repo = SQLAlchemyFailureCategoryRepository(repository_db_session)
    category = await repo.get_by_slug("build_failure")

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
    assert {category.slug for category in active} == {
        category["slug"] for category in APPROVED_FAILURE_CATEGORIES
    }


@pytest.mark.asyncio
async def test_failure_category_repository_duplicate_slug_raises(repository_db_session) -> None:
    repo = SQLAlchemyFailureCategoryRepository(repository_db_session)
    await repo.add(
        FailureCategoryEntity(
            id=None,
            name="Build Failure",
            slug="build_failure",
            description="Duplicate seed slug.",
        )
    )
    await repository_db_session.commit()

    with pytest.raises(DuplicateEntityError):
        await repo.add(
            FailureCategoryEntity(
                id=None,
                name="Another Build Failure",
                slug="build_failure",
                description="Conflicting slug.",
            )
        )


@pytest.mark.asyncio
async def test_failure_category_repository_preserves_custom_category(repository_db_session) -> None:
    await seed_failure_categories(repository_db_session)
    await repository_db_session.commit()

    repo = SQLAlchemyFailureCategoryRepository(repository_db_session)
    custom = await repo.add(
        FailureCategoryEntity(
            id=None,
            name="Custom Runtime Issue",
            slug="custom_runtime_issue",
            description="User-defined category.",
        )
    )
    await repository_db_session.commit()

    seeded = await repo.get_by_slug("build_failure")
    assert seeded is not None
    assert custom.slug == "custom_runtime_issue"
    assert len(await repo.list(limit=100)) == 12


@pytest.mark.asyncio
async def test_pipeline_run_repository_add_and_retrieve(repository_db_session) -> None:
    user = User(
        email="runner@example.com",
        hashed_password="hashed",
        full_name="Pipeline Runner",
        role=UserRole.ANALYST,
    )
    repository_db_session.add(user)
    await repository_db_session.flush()

    uploaded_file = UploadedFile(
        user_id=user.id,
        filename="build.log",
        stored_path="/tmp/build.log",
        file_type=FileType.LOG,
        mime_type="text/plain",
        size_bytes=128,
        checksum_sha256="abc123",
        platform="github",
    )
    repository_db_session.add(uploaded_file)
    await repository_db_session.flush()

    repo = SQLAlchemyPipelineRunRepository(repository_db_session)
    created = await repo.add(
        PipelineRunEntity(
            id=None,
            user_id=user.id,
            uploaded_file_id=uploaded_file.id,
            platform="github",
            pipeline_name="ci-build",
        )
    )
    await repository_db_session.commit()

    fetched = await repo.get_by_id(created.id)  # type: ignore[arg-type]
    assert fetched is not None
    assert fetched.user_id == user.id
    assert fetched.uploaded_file_id == uploaded_file.id
    assert fetched.pipeline_name == "ci-build"


@pytest.mark.asyncio
async def test_pipeline_run_repository_list_by_user_orders_desc(repository_db_session) -> None:
    from app.infrastructure.database.models.pipeline_run import PipelineRun

    user = User(
        email="ordered@example.com",
        hashed_password="hashed",
        full_name="Ordered User",
        role=UserRole.ANALYST,
    )
    repository_db_session.add(user)
    await repository_db_session.flush()

    uploaded_file = UploadedFile(
        user_id=user.id,
        filename="build.log",
        stored_path="/tmp/build.log",
        file_type=FileType.LOG,
        mime_type="text/plain",
        size_bytes=128,
        checksum_sha256="abc123",
        platform="github",
    )
    repository_db_session.add(uploaded_file)
    await repository_db_session.flush()

    repo = SQLAlchemyPipelineRunRepository(repository_db_session)
    older = await repo.add(
        PipelineRunEntity(
            id=None,
            user_id=user.id,
            uploaded_file_id=uploaded_file.id,
            platform="github",
            pipeline_name="older-run",
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
            user_id=user.id,
            uploaded_file_id=uploaded_file.id,
            platform="github",
            pipeline_name="newer-run",
        )
    )
    await repository_db_session.commit()

    runs = await repo.list_by_user(user.id, limit=10)
    assert [run.pipeline_name for run in runs] == ["newer-run", "older-run"]
    assert runs[0].id == newer.id


@pytest.mark.asyncio
async def test_pipeline_run_repository_list_by_status(repository_db_session) -> None:
    user = User(
        email="status@example.com",
        hashed_password="hashed",
        full_name="Status User",
        role=UserRole.ANALYST,
    )
    repository_db_session.add(user)
    await repository_db_session.flush()

    uploaded_file = UploadedFile(
        user_id=user.id,
        filename="build.log",
        stored_path="/tmp/build.log",
        file_type=FileType.LOG,
        mime_type="text/plain",
        size_bytes=128,
        checksum_sha256="abc123",
        platform="github",
    )
    repository_db_session.add(uploaded_file)
    await repository_db_session.flush()

    repo = SQLAlchemyPipelineRunRepository(repository_db_session)
    await repo.add(
        PipelineRunEntity(
            id=None,
            user_id=user.id,
            uploaded_file_id=uploaded_file.id,
            platform="github",
            status=PipelineRunStatus.PENDING,
        )
    )
    await repo.add(
        PipelineRunEntity(
            id=None,
            user_id=user.id,
            uploaded_file_id=uploaded_file.id,
            platform="github",
            status=PipelineRunStatus.COMPLETED,
        )
    )
    await repository_db_session.commit()

    pending = await repo.list_by_status(PipelineRunStatus.PENDING)
    assert len(pending) == 1
    assert pending[0].status == PipelineRunStatus.PENDING


@pytest.mark.asyncio
async def test_pipeline_run_repository_pagination(repository_db_session) -> None:
    user = User(
        email="paginate@example.com",
        hashed_password="hashed",
        full_name="Paginate User",
        role=UserRole.ANALYST,
    )
    repository_db_session.add(user)
    await repository_db_session.flush()

    uploaded_file = UploadedFile(
        user_id=user.id,
        filename="build.log",
        stored_path="/tmp/build.log",
        file_type=FileType.LOG,
        mime_type="text/plain",
        size_bytes=128,
        checksum_sha256="abc123",
        platform="github",
    )
    repository_db_session.add(uploaded_file)
    await repository_db_session.flush()

    repo = SQLAlchemyPipelineRunRepository(repository_db_session)
    for index in range(3):
        await repo.add(
            PipelineRunEntity(
                id=None,
                user_id=user.id,
                uploaded_file_id=uploaded_file.id,
                platform="github",
                pipeline_name=f"run-{index}",
            )
        )
    await repository_db_session.commit()

    page = await repo.list(offset=1, limit=1)
    assert len(page) == 1


@pytest.mark.asyncio
async def test_pipeline_run_repository_foreign_keys_remain_valid(repository_db_session) -> None:
    user = User(
        email="fk@example.com",
        hashed_password="hashed",
        full_name="FK User",
        role=UserRole.ANALYST,
    )
    repository_db_session.add(user)
    await repository_db_session.flush()

    uploaded_file = UploadedFile(
        user_id=user.id,
        filename="build.log",
        stored_path="/tmp/build.log",
        file_type=FileType.LOG,
        mime_type="text/plain",
        size_bytes=128,
        checksum_sha256="abc123",
        platform="github",
    )
    repository_db_session.add(uploaded_file)
    await repository_db_session.flush()

    repo = SQLAlchemyPipelineRunRepository(repository_db_session)
    created = await repo.add(
        PipelineRunEntity(
            id=None,
            user_id=user.id,
            uploaded_file_id=uploaded_file.id,
            platform="github",
        )
    )
    await repository_db_session.commit()

    from app.infrastructure.database.models.pipeline_run import PipelineRun

    model = await repository_db_session.get(PipelineRun, created.id)
    assert model is not None
    assert model.user_id == user.id
    assert model.uploaded_file_id == uploaded_file.id
