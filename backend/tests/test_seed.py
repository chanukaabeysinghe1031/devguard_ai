"""Seed module tests (isolated test database): failure categories + bootstrap."""

from __future__ import annotations

import uuid

import pytest
import structlog
from sqlalchemy import func, select

from app.core.config import Settings
from app.domain.enums import OrganizationRole, PlatformRole
from app.infrastructure.database.models.failure_category import FailureCategory
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.user import User
from app.infrastructure.database.seed import (
    APPROVED_FAILURE_CATEGORIES,
    BootstrapResult,
    seed_bootstrap,
    seed_failure_categories,
)

BOOTSTRAP_PASSWORD = "correct-horse-battery-staple"


def _bootstrap_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "PROJECT_NAME": "DevGuard AI Test",
        "APP_VERSION": "1.0.0",
        "ENVIRONMENT": "development",
        "DEBUG": False,
        "DATABASE_URL": "postgresql+asyncpg://devguard:change_me@localhost:5432/devguard_test",
        "BOOTSTRAP_ENABLED": True,
        "BOOTSTRAP_ORG_NAME": "DevGuard Default",
        "BOOTSTRAP_ORG_SLUG": "default",
        "BOOTSTRAP_OWNER_EMAIL": "owner@devguard.local",
        "BOOTSTRAP_OWNER_PASSWORD": BOOTSTRAP_PASSWORD,
        "BOOTSTRAP_OWNER_FULL_NAME": "DevGuard Owner",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Failure category seed tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_seed_inserts_approved_categories(db_session) -> None:
    expected = len(APPROVED_FAILURE_CATEGORIES)
    result = await seed_failure_categories(db_session)
    await db_session.commit()

    assert result.inserted_count == expected
    assert result.updated_count == 0
    assert result.unchanged_count == 0
    assert result.total_approved_categories == expected

    count = await db_session.scalar(select(func.count()).select_from(FailureCategory))
    assert count == expected


@pytest.mark.asyncio
async def test_second_seed_is_idempotent(db_session) -> None:
    first = await seed_failure_categories(db_session)
    await db_session.commit()
    second = await seed_failure_categories(db_session)
    await db_session.commit()

    expected = len(APPROVED_FAILURE_CATEGORIES)
    assert first.inserted_count == expected
    assert second.inserted_count == 0
    assert second.updated_count == 0
    assert second.unchanged_count == expected

    count = await db_session.scalar(select(func.count()).select_from(FailureCategory))
    assert count == expected


@pytest.mark.asyncio
async def test_seed_updates_outdated_description(db_session) -> None:
    db_session.add(
        FailureCategory(
            code="build_failure",
            name="Build Failure",
            description="Outdated description.",
            is_active=True,
        )
    )
    await db_session.commit()

    result = await seed_failure_categories(db_session)
    await db_session.commit()

    assert result.inserted_count == len(APPROVED_FAILURE_CATEGORIES) - 1
    assert result.updated_count == 1
    assert result.unchanged_count == 0

    category = await db_session.scalar(
        select(FailureCategory).where(FailureCategory.code == "build_failure")
    )
    assert category is not None
    assert category.description == "Compilation or build process failed."


@pytest.mark.asyncio
async def test_seed_preserves_custom_category(db_session) -> None:
    custom_id = uuid.uuid4()
    db_session.add(
        FailureCategory(
            id=custom_id,
            code="custom_runtime_issue",
            name="Custom Runtime Issue",
            description="User-defined category.",
            is_active=True,
        )
    )
    await db_session.commit()

    result = await seed_failure_categories(db_session)
    await db_session.commit()

    expected = len(APPROVED_FAILURE_CATEGORIES)
    assert result.inserted_count == expected

    custom = await db_session.scalar(select(FailureCategory).where(FailureCategory.id == custom_id))
    assert custom is not None
    assert custom.code == "custom_runtime_issue"

    total = await db_session.scalar(select(func.count()).select_from(FailureCategory))
    assert total == expected + 1


@pytest.mark.asyncio
async def test_approved_categories_have_unique_codes(db_session) -> None:
    await seed_failure_categories(db_session)
    await db_session.commit()

    codes = (
        await db_session.scalars(select(FailureCategory.code).order_by(FailureCategory.code))
    ).all()
    assert len(codes) == len(set(codes))


@pytest.mark.asyncio
async def test_all_approved_categories_are_active(db_session) -> None:
    await seed_failure_categories(db_session)
    await db_session.commit()

    approved_codes = {category["code"] for category in APPROVED_FAILURE_CATEGORIES}
    categories = (
        await db_session.scalars(
            select(FailureCategory).where(FailureCategory.code.in_(approved_codes))
        )
    ).all()

    assert len(categories) == len(APPROVED_FAILURE_CATEGORIES)
    assert all(category.is_active for category in categories)


@pytest.mark.asyncio
async def test_approved_category_names_and_codes(db_session) -> None:
    await seed_failure_categories(db_session)
    await db_session.commit()

    categories = {
        category.code: category.name
        for category in (
            await db_session.scalars(select(FailureCategory).order_by(FailureCategory.code))
        ).all()
    }

    for approved in APPROVED_FAILURE_CATEGORIES:
        assert categories[approved["code"]] == approved["name"]


# ---------------------------------------------------------------------------
# Bootstrap seed tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bootstrap_disabled_by_default_is_noop(db_session) -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://devguard:change_me@localhost:5432/devguard_test",
    )
    assert settings.bootstrap_enabled is False

    result = await seed_bootstrap(db_session, settings)
    await db_session.commit()

    assert result == BootstrapResult(enabled=False)
    org_count = await db_session.scalar(select(func.count()).select_from(Organization))
    user_count = await db_session.scalar(select(func.count()).select_from(User))
    assert org_count == 0
    assert user_count == 0


@pytest.mark.asyncio
async def test_bootstrap_creates_org_owner_and_membership(db_session) -> None:
    settings = _bootstrap_settings()

    result = await seed_bootstrap(db_session, settings)
    await db_session.commit()

    assert result.enabled is True
    assert result.organization_created is True
    assert result.owner_created is True
    assert result.membership_created is True
    assert result.platform_role_updated is True

    organization = await db_session.scalar(
        select(Organization).where(Organization.slug == "default")
    )
    assert organization is not None
    assert organization.name == "DevGuard Default"

    owner = await db_session.scalar(select(User).where(User.email == "owner@devguard.local"))
    assert owner is not None
    assert owner.platform_role == PlatformRole.PLATFORM_ADMIN
    assert owner.password_hash != BOOTSTRAP_PASSWORD
    assert owner.password_hash.startswith("$2")  # bcrypt
    from app.core.security import verify_password

    assert verify_password(BOOTSTRAP_PASSWORD, owner.password_hash)

    membership = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization.id,
            OrganizationMember.user_id == owner.id,
        )
    )
    assert membership is not None
    assert membership.role == OrganizationRole.ORGANIZATION_OWNER


@pytest.mark.asyncio
async def test_bootstrap_is_idempotent(db_session) -> None:
    settings = _bootstrap_settings()

    first = await seed_bootstrap(db_session, settings)
    await db_session.commit()
    second = await seed_bootstrap(db_session, settings)
    await db_session.commit()

    assert first.organization_created is True
    assert first.owner_created is True
    assert first.membership_created is True

    assert second.organization_created is False
    assert second.owner_created is False
    assert second.membership_created is False
    assert second.platform_role_updated is False

    org_count = await db_session.scalar(select(func.count()).select_from(Organization))
    user_count = await db_session.scalar(select(func.count()).select_from(User))
    membership_count = await db_session.scalar(select(func.count()).select_from(OrganizationMember))
    assert org_count == 1
    assert user_count == 1
    assert membership_count == 1


@pytest.mark.asyncio
async def test_bootstrap_missing_password_raises(db_session) -> None:
    settings = _bootstrap_settings(BOOTSTRAP_OWNER_PASSWORD="")

    with pytest.raises(ValueError, match="BOOTSTRAP_OWNER_PASSWORD"):
        await seed_bootstrap(db_session, settings)


@pytest.mark.asyncio
async def test_bootstrap_never_logs_password(db_session) -> None:
    settings = _bootstrap_settings()

    with structlog.testing.capture_logs() as captured_logs:
        await seed_bootstrap(db_session, settings)
    await db_session.commit()

    for entry in captured_logs:
        for value in entry.values():
            assert BOOTSTRAP_PASSWORD not in str(value)
