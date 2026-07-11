"""Idempotent failure category seed data."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TypedDict

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.infrastructure.database.models.failure_category import FailureCategory
from app.infrastructure.database.session import close_db, ensure_session_factory

logger = structlog.get_logger(__name__)


class ApprovedCategory(TypedDict):
    slug: str
    name: str
    description: str


APPROVED_FAILURE_CATEGORIES: tuple[ApprovedCategory, ...] = (
    {
        "slug": "build_failure",
        "name": "Build Failure",
        "description": "Compilation or build process failed.",
    },
    {
        "slug": "test_failure",
        "name": "Test Failure",
        "description": "Unit, integration, or acceptance test failure.",
    },
    {
        "slug": "dependency_failure",
        "name": "Dependency Failure",
        "description": "Missing, unresolved, or incompatible dependencies.",
    },
    {
        "slug": "configuration_failure",
        "name": "Configuration Failure",
        "description": "Invalid YAML, environment, or pipeline configuration.",
    },
    {
        "slug": "terraform_failure",
        "name": "Terraform Failure",
        "description": "Terraform syntax, validation, or plan/apply error.",
    },
    {
        "slug": "docker_failure",
        "name": "Docker Failure",
        "description": "Docker image build or container runtime failure.",
    },
    {
        "slug": "deployment_failure",
        "name": "Deployment Failure",
        "description": "Deployment pipeline or release step failure.",
    },
    {
        "slug": "aws_permission_failure",
        "name": "AWS Permission Failure",
        "description": "IAM policy, role, or AWS permission denial.",
    },
    {
        "slug": "network_failure",
        "name": "Network Failure",
        "description": "Connection timeout, DNS resolution, or network reachability issue.",
    },
    {
        "slug": "security_misconfiguration",
        "name": "Security Misconfiguration",
        "description": "Secrets exposure, insecure policy, or security control misconfiguration.",
    },
    {
        "slug": "unknown_failure",
        "name": "Unknown Failure",
        "description": "Failure could not be classified into a known category.",
    },
)


@dataclass(frozen=True, slots=True)
class SeedResult:
    inserted_count: int
    updated_count: int
    unchanged_count: int
    total_approved_categories: int


async def seed_failure_categories(session: AsyncSession) -> SeedResult:
    """Insert or update approved failure categories without removing custom records."""
    inserted_count = 0
    updated_count = 0
    unchanged_count = 0

    result = await session.execute(select(FailureCategory))
    existing_by_slug = {category.slug: category for category in result.scalars().all()}

    for category_data in APPROVED_FAILURE_CATEGORIES:
        slug = category_data["slug"]
        existing = existing_by_slug.get(slug)

        if existing is None:
            session.add(
                FailureCategory(
                    slug=slug,
                    name=category_data["name"],
                    description=category_data["description"],
                    is_active=True,
                )
            )
            inserted_count += 1
            logger.info("failure_category_inserted", slug=slug, name=category_data["name"])
            continue

        changed_fields: list[str] = []

        if existing.name != category_data["name"]:
            existing.name = category_data["name"]
            changed_fields.append("name")

        if existing.description != category_data["description"]:
            existing.description = category_data["description"]
            changed_fields.append("description")

        if not existing.is_active:
            existing.is_active = True
            changed_fields.append("is_active")

        if changed_fields:
            updated_count += 1
            logger.info(
                "failure_category_updated",
                slug=slug,
                changed_fields=changed_fields,
            )
        else:
            unchanged_count += 1
            logger.debug("failure_category_unchanged", slug=slug)

    return SeedResult(
        inserted_count=inserted_count,
        updated_count=updated_count,
        unchanged_count=unchanged_count,
        total_approved_categories=len(APPROVED_FAILURE_CATEGORIES),
    )


async def run_seed() -> SeedResult:
    """Run the failure category seed inside a managed session and transaction."""
    session_factory = ensure_session_factory()

    async with session_factory() as session:
        try:
            result = await seed_failure_categories(session)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("failure_category_seed_failed")
            raise
        else:
            logger.info(
                "failure_category_seed_completed",
                inserted_count=result.inserted_count,
                updated_count=result.updated_count,
                unchanged_count=result.unchanged_count,
                total_approved_categories=result.total_approved_categories,
            )
            return result


async def _main() -> None:
    settings = get_settings()
    setup_logging(settings)
    try:
        await run_seed()
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(_main())
