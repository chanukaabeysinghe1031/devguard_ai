"""Seed default failure categories."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import FailureCategorySlug
from app.infrastructure.database.models import FailureCategory
from app.infrastructure.repositories.failure_category_repository import FailureCategoryRepository

DEFAULT_CATEGORIES: list[tuple[str, str, str]] = [
    ("Build Failure", FailureCategorySlug.BUILD_FAILURE, "Compilation or build step failures"),
    ("Test Failure", FailureCategorySlug.TEST_FAILURE, "Unit, integration, or E2E test failures"),
    ("Dependency Failure", FailureCategorySlug.DEPENDENCY_FAILURE, "Package or dependency resolution issues"),
    ("Configuration Failure", FailureCategorySlug.CONFIGURATION_FAILURE, "Misconfigured environment or settings"),
    ("Terraform Failure", FailureCategorySlug.TERRAFORM_FAILURE, "Terraform plan or apply failures"),
    ("Docker Failure", FailureCategorySlug.DOCKER_FAILURE, "Container build or runtime failures"),
    ("Deployment Failure", FailureCategorySlug.DEPLOYMENT_FAILURE, "Deployment step failures"),
    ("AWS Permission Failure", FailureCategorySlug.AWS_PERMISSION_FAILURE, "IAM or AWS permission denied errors"),
    ("Network Failure", FailureCategorySlug.NETWORK_FAILURE, "Connectivity, DNS, or timeout issues"),
    ("Security Misconfiguration", FailureCategorySlug.SECURITY_MISCONFIGURATION, "Security policy or credential issues"),
    ("Unknown Failure", FailureCategorySlug.UNKNOWN_FAILURE, "Unclassified or ambiguous failures"),
]


async def seed_failure_categories(session: AsyncSession) -> int:
    """Insert default failure categories if they do not exist. Returns count created."""
    repo = FailureCategoryRepository(session)
    created = 0
    for name, slug, description in DEFAULT_CATEGORIES:
        existing = await repo.get_by_slug(slug.value)
        if existing is None:
            await repo.create(
                FailureCategory(
                    name=name,
                    slug=slug.value,
                    description=description,
                    is_active=True,
                )
            )
            created += 1
    return created
