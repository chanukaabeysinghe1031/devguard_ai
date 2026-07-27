"""Idempotent schema seed module.

Two independent, idempotent seed operations:

1. ``seed_failure_categories`` — the 11 approved MVP failure categories, matched
   by stable ``code`` (never by primary key, so re-running is always safe).
2. ``seed_bootstrap`` — an optional, development-only default organization and
   owner user, controlled entirely by ``BOOTSTRAP_*`` environment settings.

Bootstrap passwords are read from the environment and are never logged.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TypedDict

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.domain.enums import OrganizationRole, PlatformRole
from app.infrastructure.database.models.failure_category import FailureCategory
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import close_db, ensure_session_factory

logger = structlog.get_logger(__name__)


class ApprovedCategory(TypedDict):
    code: str
    name: str
    description: str


APPROVED_FAILURE_CATEGORIES: tuple[ApprovedCategory, ...] = (
    {
        "code": "build_failure",
        "name": "Build Failure",
        "description": "Compilation or build process failed.",
    },
    {
        "code": "test_failure",
        "name": "Test Failure",
        "description": "Unit, integration, or acceptance test failure.",
    },
    {
        "code": "dependency_failure",
        "name": "Dependency Failure",
        "description": "Missing, unresolved, or incompatible dependencies.",
    },
    {
        "code": "configuration_failure",
        "name": "Configuration Failure",
        "description": "Invalid YAML, environment, or pipeline configuration.",
    },
    {
        "code": "terraform_failure",
        "name": "Terraform Failure",
        "description": "Terraform syntax, validation, or plan/apply error.",
    },
    {
        "code": "docker_failure",
        "name": "Docker Failure",
        "description": "Docker image build or container runtime failure.",
    },
    {
        "code": "deployment_failure",
        "name": "Deployment Failure",
        "description": "Deployment pipeline or release step failure.",
    },
    {
        "code": "aws_permission_failure",
        "name": "AWS Permission Failure",
        "description": "IAM policy, role, or AWS permission denial.",
    },
    {
        "code": "network_failure",
        "name": "Network Failure",
        "description": "Connection timeout, DNS resolution, or network reachability issue.",
    },
    {
        "code": "security_misconfiguration",
        "name": "Security Misconfiguration",
        "description": "Secrets exposure, insecure policy, or security control misconfiguration.",
    },
    {
        "code": "unknown_failure",
        "name": "Unknown Failure",
        "description": "Failure could not be classified into a known category.",
    },
)


@dataclass(frozen=True, slots=True)
class CategorySeedResult:
    """Outcome of the failure-category seed pass."""

    inserted_count: int
    updated_count: int
    unchanged_count: int
    total_approved_categories: int


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Outcome of the optional development bootstrap seed pass.

    ``enabled`` reflects whether bootstrap ran at all; the remaining flags are
    only meaningful when ``enabled`` is ``True``.
    """

    enabled: bool
    organization_created: bool = False
    owner_created: bool = False
    membership_created: bool = False
    platform_role_updated: bool = False


@dataclass(frozen=True, slots=True)
class SeedResult:
    """Combined result of a full seed run."""

    categories: CategorySeedResult
    bootstrap: BootstrapResult


def _hash_password(password: str) -> str:
    """Hash a password using the shared security helper (bcrypt)."""
    from app.core.security import hash_password

    return hash_password(password)


async def seed_failure_categories(session: AsyncSession) -> CategorySeedResult:
    """Insert or update approved failure categories without removing custom records."""
    inserted_count = 0
    updated_count = 0
    unchanged_count = 0

    result = await session.execute(select(FailureCategory))
    existing_by_code = {category.code: category for category in result.scalars().all()}

    for category_data in APPROVED_FAILURE_CATEGORIES:
        code = category_data["code"]
        existing = existing_by_code.get(code)

        if existing is None:
            session.add(
                FailureCategory(
                    code=code,
                    name=category_data["name"],
                    description=category_data["description"],
                    is_active=True,
                )
            )
            inserted_count += 1
            logger.info("failure_category_inserted", code=code, name=category_data["name"])
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
                code=code,
                changed_fields=changed_fields,
            )
        else:
            unchanged_count += 1
            logger.debug("failure_category_unchanged", code=code)

    return CategorySeedResult(
        inserted_count=inserted_count,
        updated_count=updated_count,
        unchanged_count=unchanged_count,
        total_approved_categories=len(APPROVED_FAILURE_CATEGORIES),
    )


async def seed_bootstrap(session: AsyncSession, settings: Settings) -> BootstrapResult:
    """Idempotently create a default organization, owner user, and membership.

    No-op unless ``settings.bootstrap_enabled`` is ``True``. Never logs the
    plaintext or hashed password value.
    """
    if not settings.bootstrap_enabled:
        logger.debug("bootstrap_seed_skipped_disabled")
        return BootstrapResult(enabled=False)

    if not settings.bootstrap_owner_password:
        raise ValueError("BOOTSTRAP_OWNER_PASSWORD is required when BOOTSTRAP_ENABLED is true.")

    organization_created = False
    owner_created = False
    membership_created = False
    platform_role_updated = False

    organization = await session.scalar(
        select(Organization).where(Organization.slug == settings.bootstrap_org_slug)
    )
    if organization is None:
        organization = Organization(
            name=settings.bootstrap_org_name,
            slug=settings.bootstrap_org_slug,
        )
        session.add(organization)
        await session.flush()
        organization_created = True
        logger.info(
            "bootstrap_organization_created",
            slug=settings.bootstrap_org_slug,
        )

    owner = await session.scalar(
        select(User).where(User.email == settings.bootstrap_owner_email.lower())
    )
    if owner is None:
        owner = User(
            email=settings.bootstrap_owner_email.lower(),
            password_hash=_hash_password(settings.bootstrap_owner_password),
            full_name=settings.bootstrap_owner_full_name,
            platform_role=PlatformRole.NONE,
        )
        session.add(owner)
        await session.flush()
        owner_created = True
        logger.info("bootstrap_owner_created", email=settings.bootstrap_owner_email.lower())

    if not settings.is_production and owner.platform_role != PlatformRole.PLATFORM_ADMIN:
        owner.platform_role = PlatformRole.PLATFORM_ADMIN
        platform_role_updated = True
        logger.info(
            "bootstrap_owner_platform_role_updated",
            email=owner.email,
            platform_role=PlatformRole.PLATFORM_ADMIN.value,
        )

    membership = await session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization.id,
            OrganizationMember.user_id == owner.id,
        )
    )
    if membership is None:
        session.add(
            OrganizationMember(
                organization_id=organization.id,
                user_id=owner.id,
                role=OrganizationRole.ORGANIZATION_OWNER,
            )
        )
        membership_created = True
        logger.info(
            "bootstrap_membership_created",
            organization_slug=organization.slug,
            role=OrganizationRole.ORGANIZATION_OWNER.value,
        )

    return BootstrapResult(
        enabled=True,
        organization_created=organization_created,
        owner_created=owner_created,
        membership_created=membership_created,
        platform_role_updated=platform_role_updated,
    )


async def run_seed() -> SeedResult:
    """Run the full seed pass (categories always; bootstrap when enabled)."""
    settings = get_settings()
    session_factory = ensure_session_factory()

    async with session_factory() as session:
        try:
            categories_result = await seed_failure_categories(session)
            bootstrap_result = await seed_bootstrap(session, settings)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("seed_failed")
            raise

        logger.info(
            "failure_category_seed_completed",
            inserted_count=categories_result.inserted_count,
            updated_count=categories_result.updated_count,
            unchanged_count=categories_result.unchanged_count,
            total_approved_categories=categories_result.total_approved_categories,
        )
        if bootstrap_result.enabled:
            logger.info(
                "bootstrap_seed_completed",
                organization_created=bootstrap_result.organization_created,
                owner_created=bootstrap_result.owner_created,
                membership_created=bootstrap_result.membership_created,
                platform_role_updated=bootstrap_result.platform_role_updated,
            )
        return SeedResult(categories=categories_result, bootstrap=bootstrap_result)


async def _main() -> None:
    settings = get_settings()
    setup_logging(settings)
    try:
        await run_seed()
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(_main())
