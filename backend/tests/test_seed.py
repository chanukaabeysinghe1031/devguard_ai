"""Failure category seed tests (isolated test database)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.infrastructure.database.models.failure_category import FailureCategory
from app.infrastructure.database.seed import (
    APPROVED_FAILURE_CATEGORIES,
    seed_failure_categories,
)


@pytest.mark.asyncio
async def test_first_seed_inserts_11_categories(db_session) -> None:
    result = await seed_failure_categories(db_session)
    await db_session.commit()

    assert result.inserted_count == 11
    assert result.updated_count == 0
    assert result.unchanged_count == 0
    assert result.total_approved_categories == 11

    count = await db_session.scalar(select(func.count()).select_from(FailureCategory))
    assert count == 11


@pytest.mark.asyncio
async def test_second_seed_is_idempotent(db_session) -> None:
    first = await seed_failure_categories(db_session)
    await db_session.commit()
    second = await seed_failure_categories(db_session)
    await db_session.commit()

    assert first.inserted_count == 11
    assert second.inserted_count == 0
    assert second.updated_count == 0
    assert second.unchanged_count == 11

    count = await db_session.scalar(select(func.count()).select_from(FailureCategory))
    assert count == 11


@pytest.mark.asyncio
async def test_seed_updates_outdated_description(db_session) -> None:
    db_session.add(
        FailureCategory(
            slug="build_failure",
            name="Build Failure",
            description="Outdated description.",
            is_active=True,
        )
    )
    await db_session.commit()

    result = await seed_failure_categories(db_session)
    await db_session.commit()

    assert result.inserted_count == 10
    assert result.updated_count == 1
    assert result.unchanged_count == 0

    category = await db_session.scalar(
        select(FailureCategory).where(FailureCategory.slug == "build_failure")
    )
    assert category is not None
    assert category.description == "Compilation or build process failed."


@pytest.mark.asyncio
async def test_seed_preserves_custom_category(db_session) -> None:
    custom_id = uuid.uuid4()
    db_session.add(
        FailureCategory(
            id=custom_id,
            slug="custom_runtime_issue",
            name="Custom Runtime Issue",
            description="User-defined category.",
            is_active=True,
        )
    )
    await db_session.commit()

    result = await seed_failure_categories(db_session)
    await db_session.commit()

    assert result.inserted_count == 11

    custom = await db_session.scalar(
        select(FailureCategory).where(FailureCategory.id == custom_id)
    )
    assert custom is not None
    assert custom.slug == "custom_runtime_issue"

    total = await db_session.scalar(select(func.count()).select_from(FailureCategory))
    assert total == 12


@pytest.mark.asyncio
async def test_approved_categories_have_unique_slugs(db_session) -> None:
    await seed_failure_categories(db_session)
    await db_session.commit()

    slugs = (
        await db_session.scalars(select(FailureCategory.slug).order_by(FailureCategory.slug))
    ).all()
    assert len(slugs) == len(set(slugs))


@pytest.mark.asyncio
async def test_all_approved_categories_are_active(db_session) -> None:
    await seed_failure_categories(db_session)
    await db_session.commit()

    approved_slugs = {category["slug"] for category in APPROVED_FAILURE_CATEGORIES}
    categories = (
        await db_session.scalars(
            select(FailureCategory).where(FailureCategory.slug.in_(approved_slugs))
        )
    ).all()

    assert len(categories) == 11
    assert all(category.is_active for category in categories)


@pytest.mark.asyncio
async def test_approved_category_names_and_slugs(db_session) -> None:
    await seed_failure_categories(db_session)
    await db_session.commit()

    categories = {
        category.slug: category.name
        for category in (
            await db_session.scalars(select(FailureCategory).order_by(FailureCategory.slug))
        ).all()
    }

    for approved in APPROVED_FAILURE_CATEGORIES:
        assert categories[approved["slug"]] == approved["name"]
