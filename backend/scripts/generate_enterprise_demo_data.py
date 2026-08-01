#!/usr/bin/env python3
"""Generate a realistic one-month enterprise demo dataset for DevGuard AI.

Idempotent: re-running updates/skips by natural keys and never duplicates demo rows.

Usage (Docker):
  docker compose exec backend python scripts/generate_enterprise_demo_data.py
  docker compose exec backend python scripts/generate_enterprise_demo_data.py --reset

Safety:
  - Refuses production environments
  - Does not modify schema, APIs, or business logic
  - Only inserts/updates demo-scoped rows
  - --reset deletes Acme demo pipelines/incidents/analyses then reseeds
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import random
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

# Allow `python scripts/...` with WORKDIR=/app (backend package root).
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.domain.enums import (
    AnalysisRunStatus,
    CiProvider,
    DeliveryStatus,
    EvidenceType,
    IncidentPriority,
    IncidentSeverity,
    IncidentStatus,
    ModelVersionStatus,
    NotificationType,
    OrganizationRole,
    OrganizationStatus,
    PipelineRunStatus,
    PlatformRole,
    ProjectStatus,
    RecommendationStepType,
    RiskLevel,
)
from app.infrastructure.database.models.analysis_run import AnalysisRun
from app.infrastructure.database.models.causal_hypotheses import (
    CausalHypothesisRow,
    CausalHypothesisRunRow,
    HypothesisEvidenceLinkRow,
)
from app.infrastructure.database.models.counterfactual_remediation import (
    CounterfactualRemediationCandidateRow,
    CounterfactualRemediationRunRow,
)
from app.infrastructure.database.models.evidence_item import EvidenceItem
from app.infrastructure.database.models.failure_category import FailureCategory
from app.infrastructure.database.models.github_installation import GitHubInstallation
from app.infrastructure.database.models.github_repository_connection import (
    GitHubRepositoryConnection,
)
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_assignment import IncidentAssignment
from app.infrastructure.database.models.incident_event import IncidentEvent
from app.infrastructure.database.models.incident_note import IncidentNote
from app.infrastructure.database.models.incident_resolution import IncidentResolution
from app.infrastructure.database.models.model_version import ModelVersion
from app.infrastructure.database.models.notification import Notification
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.database.models.prediction import Prediction
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.recommendation import Recommendation
from app.infrastructure.database.models.recommendation_step import RecommendationStep
from app.infrastructure.database.models.remediation_verification import (
    RemediationVerificationResultRow,
    RemediationVerificationRunRow,
)
from app.infrastructure.database.models.user import User
from app.infrastructure.database.models.webhook_delivery import WebhookDelivery
from app.infrastructure.database.seed import seed_failure_categories
from app.infrastructure.database.session import close_db, ensure_session_factory, init_db

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEMO_MARKER = "enterprise-demo-v1"
ORG_SLUG = "acme-cloud-solutions"
ORG_NAME = "Acme Cloud Solutions"
GITHUB_INSTALLATION_ID = 88_000_042
RNG_SEED = 20260701
PIPELINE_RUN_COUNT = 300
INCIDENT_TARGET = 100
DEMO_PASSWORD = "DemoPass123!"

# Curated roster (deterministic — no Faker dependency required).
USERS: list[dict[str, str]] = [
    {
        "email": "jordan.blake@example.com",
        "full_name": "Jordan Blake",
        "title": "Platform Admin",
        "platform_role": PlatformRole.PLATFORM_ADMIN.value,
        "org_role": OrganizationRole.ORGANIZATION_OWNER.value,
    },
    {
        "email": "ava.chen@example.com",
        "full_name": "Ava Chen",
        "title": "Organization Owner",
        "platform_role": PlatformRole.NONE.value,
        "org_role": OrganizationRole.ORGANIZATION_OWNER.value,
    },
    {
        "email": "marcus.reid@example.com",
        "full_name": "Marcus Reid",
        "title": "Organization Admin",
        "platform_role": PlatformRole.NONE.value,
        "org_role": OrganizationRole.ORGANIZATION_ADMIN.value,
    },
    {
        "email": "priya.nair@example.com",
        "full_name": "Priya Nair",
        "title": "DevOps Lead",
        "platform_role": PlatformRole.NONE.value,
        "org_role": OrganizationRole.ORGANIZATION_ADMIN.value,
    },
    {
        "email": "liam.okafor@example.com",
        "full_name": "Liam Okafor",
        "title": "Senior DevOps Engineer",
        "platform_role": PlatformRole.NONE.value,
        "org_role": OrganizationRole.ENGINEER.value,
    },
    {
        "email": "sofia.martinez@example.com",
        "full_name": "Sofia Martinez",
        "title": "Cloud Engineer",
        "platform_role": PlatformRole.NONE.value,
        "org_role": OrganizationRole.ENGINEER.value,
    },
    {
        "email": "ethan.brooks@example.com",
        "full_name": "Ethan Brooks",
        "title": "Backend Engineer",
        "platform_role": PlatformRole.NONE.value,
        "org_role": OrganizationRole.ENGINEER.value,
    },
    {
        "email": "hana.suzuki@example.com",
        "full_name": "Hana Suzuki",
        "title": "Frontend Engineer",
        "platform_role": PlatformRole.NONE.value,
        "org_role": OrganizationRole.ENGINEER.value,
    },
    {
        "email": "noah.patel@example.com",
        "full_name": "Noah Patel",
        "title": "QA Automation Engineer",
        "platform_role": PlatformRole.NONE.value,
        "org_role": OrganizationRole.ENGINEER.value,
    },
    {
        "email": "maya.rossi@example.com",
        "full_name": "Maya Rossi",
        "title": "SRE",
        "platform_role": PlatformRole.NONE.value,
        "org_role": OrganizationRole.ENGINEER.value,
    },
    {
        "email": "daniel.kim@example.com",
        "full_name": "Daniel Kim",
        "title": "Security Engineer",
        "platform_role": PlatformRole.NONE.value,
        "org_role": OrganizationRole.ENGINEER.value,
    },
    {
        "email": "elena.vogel@example.com",
        "full_name": "Elena Vogel",
        "title": "Viewer",
        "platform_role": PlatformRole.NONE.value,
        "org_role": OrganizationRole.VIEWER.value,
    },
]

PROJECTS: list[dict[str, Any]] = [
    {
        "key": "PORTAL",
        "name": "Customer Portal",
        "repo": "acme-cloud/customer-portal",
        "description": "Customer-facing React portal and BFF services.",
        "environment": "production",
        "region": "eu-west-1",
        "cloud": "aws",
        "workflow": "portal-ci.yml",
        "tags": ["frontend", "bff", "customer"],
    },
    {
        "key": "PAYAPI",
        "name": "Payment API",
        "repo": "acme-cloud/payment-api",
        "description": "Payment orchestration and settlement API.",
        "environment": "production",
        "region": "eu-west-1",
        "cloud": "aws",
        "workflow": "payment-deploy.yml",
        "tags": ["payments", "java", "pci"],
    },
    {
        "key": "IDENT",
        "name": "Identity Service",
        "repo": "acme-cloud/identity-service",
        "description": "OIDC identity and session service.",
        "environment": "staging",
        "region": "eu-central-1",
        "cloud": "aws",
        "workflow": "identity-ci.yml",
        "tags": ["auth", "oidc", "security"],
    },
    {
        "key": "NOTIFY",
        "name": "Notification Service",
        "repo": "acme-cloud/notification-service",
        "description": "Email/SMS/push notification workers.",
        "environment": "production",
        "region": "us-east-1",
        "cloud": "aws",
        "workflow": "notify-ci.yml",
        "tags": ["messaging", "workers"],
    },
    {
        "key": "INFRA",
        "name": "Infrastructure Platform",
        "repo": "acme-cloud/infra-platform",
        "description": "Platform Terraform and GitHub Actions runners.",
        "environment": "production",
        "region": "eu-west-1",
        "cloud": "aws",
        "workflow": "terraform-apply.yml",
        "tags": ["terraform", "platform"],
    },
    {
        "key": "TFMOD",
        "name": "Shared Terraform Modules",
        "repo": "acme-cloud/terraform-modules",
        "description": "Shared IaC modules for VPC, IAM, EKS, RDS.",
        "environment": "shared",
        "region": "eu-west-1",
        "cloud": "aws",
        "workflow": "module-ci.yml",
        "tags": ["terraform", "modules"],
    },
    {
        "key": "MOBILE",
        "name": "Mobile Backend",
        "repo": "acme-cloud/mobile-backend",
        "description": "GraphQL API for iOS/Android clients.",
        "environment": "staging",
        "region": "us-east-1",
        "cloud": "aws",
        "workflow": "mobile-ci.yml",
        "tags": ["mobile", "graphql"],
    },
    {
        "key": "ANALYT",
        "name": "Analytics Platform",
        "repo": "acme-cloud/analytics-platform",
        "description": "Batch and streaming analytics pipelines.",
        "environment": "production",
        "region": "eu-west-2",
        "cloud": "aws",
        "workflow": "analytics-etl.yml",
        "tags": ["data", "etl", "spark"],
    },
]

# Weighted failure catalogue mapped to approved failure category codes.
FAILURE_CATALOGUE: list[dict[str, Any]] = [
    {
        "code": "aws_permission_failure",
        "label": "AWS AccessDenied on deploy role",
        "weight": 14,
        "excerpt": "An error occurred (AccessDenied) when calling the PutObject operation",
        "artifact": "IAM_POLICY",
        "fix": "Grant least-privilege s3:PutObject on the target bucket ARN.",
    },
    {
        "code": "terraform_failure",
        "label": "Terraform provider authentication failed",
        "weight": 8,
        "excerpt": "Error: No valid credential sources found for AWS Provider",
        "artifact": "HCL_FRAGMENT",
        "fix": "Restore AWS provider credentials and re-run terraform plan.",
    },
    {
        "code": "terraform_failure",
        "label": "Terraform undeclared resource reference",
        "weight": 7,
        "excerpt": "Reference to undeclared resource aws_s3_bucket.artifacts",
        "artifact": "HCL_FRAGMENT",
        "fix": "Declare the missing resource or correct the reference name.",
    },
    {
        "code": "terraform_failure",
        "label": "Terraform state lock contention",
        "weight": 5,
        "excerpt": "Error acquiring the state lock; Lock Info: ID=...",
        "artifact": "HCL_FRAGMENT",
        "fix": "Identify lock holder and unlock only after confirming no apply in progress.",
    },
    {
        "code": "terraform_failure",
        "label": "Terraform HCL syntax error",
        "weight": 4,
        "excerpt": "Argument or block definition required; Unexpected attribute",
        "artifact": "HCL_FRAGMENT",
        "fix": "Fix HCL syntax around the reported line and run terraform validate.",
    },
    {
        "code": "docker_failure",
        "label": "Docker COPY source missing",
        "weight": 7,
        "excerpt": "COPY failed: file not found in build context or excluded by .dockerignore",
        "artifact": "DOCKERFILE",
        "fix": "Align COPY path with build context or adjust .dockerignore.",
    },
    {
        "code": "docker_failure",
        "label": "Docker image build failed",
        "weight": 6,
        "excerpt": "executor failed running [/bin/sh -c npm ci]: exit code: 1",
        "artifact": "DOCKERFILE",
        "fix": "Inspect package lock and base image before rebuilding.",
    },
    {
        "code": "deployment_failure",
        "label": "Docker push denied",
        "weight": 5,
        "excerpt": "denied: requested access to the resource is denied",
        "artifact": "WORKFLOW_YAML",
        "fix": "Refresh registry credentials used by the deploy job.",
    },
    {
        "code": "dependency_failure",
        "label": "npm dependency conflict",
        "weight": 6,
        "excerpt": "ERESOLVE unable to resolve dependency tree",
        "artifact": "PACKAGE_JSON",
        "fix": "Align peer dependency versions and regenerate package-lock.json.",
    },
    {
        "code": "dependency_failure",
        "label": "Maven dependency resolution failure",
        "weight": 4,
        "excerpt": "Could not resolve dependencies for project com.acme:payment-api",
        "artifact": "POM_XML",
        "fix": "Verify repository mirrors and dependency versions in pom.xml.",
    },
    {
        "code": "dependency_failure",
        "label": "Gradle plugin resolution failure",
        "weight": 3,
        "excerpt": "Plugin [id: 'com.github.spotbugs'] was not found",
        "artifact": "GRADLE",
        "fix": "Add the plugin repository or pin a published plugin version.",
    },
    {
        "code": "ci_runner_failure",
        "label": "GitHub runner offline",
        "weight": 5,
        "excerpt": "Waiting for a runner to pick up this job... no matching runners",
        "artifact": "WORKFLOW_YAML",
        "fix": "Restore self-hosted runner connectivity or fall back to ubuntu-latest.",
    },
    {
        "code": "configuration_failure",
        "label": "Workflow YAML invalid",
        "weight": 5,
        "excerpt": "Invalid workflow file: .github/workflows/deploy.yml",
        "artifact": "WORKFLOW_YAML",
        "fix": "Correct workflow schema (jobs/on) and re-validate with actionlint.",
    },
    {
        "code": "configuration_failure",
        "label": "Missing GitHub Actions secret",
        "weight": 5,
        "excerpt": "Secret AWS_ROLE_ARN was not found in this repository",
        "artifact": "WORKFLOW_YAML",
        "fix": "Create the missing repository secret in the correct environment.",
    },
    {
        "code": "deployment_failure",
        "label": "Kubernetes image pull backoff",
        "weight": 5,
        "excerpt": "Failed to pull image: ErrImagePull / ImagePullBackOff",
        "artifact": "K8S_MANIFEST",
        "fix": "Verify image tag and pull secret in the target namespace.",
    },
    {
        "code": "deployment_failure",
        "label": "Helm release upgrade failed",
        "weight": 3,
        "excerpt": "UPGRADE FAILED: another operation (install/upgrade/rollback) is in progress",
        "artifact": "HELM",
        "fix": "Wait for or cancel the in-progress Helm operation before retrying.",
    },
    {
        "code": "aws_permission_failure",
        "label": "IAM PassRole denied",
        "weight": 4,
        "excerpt": "User is not authorized to perform: iam:PassRole",
        "artifact": "IAM_POLICY",
        "fix": "Allow iam:PassRole for the specific deploy role ARN only.",
    },
    {
        "code": "aws_permission_failure",
        "label": "S3 bucket policy denies PutObject",
        "weight": 3,
        "excerpt": "Access Denied when writing artifact to s3://acme-releases/",
        "artifact": "IAM_POLICY",
        "fix": "Update bucket policy to allow the CI role principal.",
    },
    {
        "code": "deployment_failure",
        "label": "Lambda update function code failed",
        "weight": 3,
        "excerpt": "CodeStorageExceededException: Code storage limit exceeded",
        "artifact": "WORKFLOW_YAML",
        "fix": "Prune unused Lambda versions before publishing a new package.",
    },
    {
        "code": "configuration_failure",
        "label": "CloudFormation stack update failed",
        "weight": 2,
        "excerpt": "Circular dependency between resources",
        "artifact": "CLOUDFORMATION",
        "fix": "Break the circular DependsOn relationship between stack resources.",
    },
    {
        "code": "security_misconfiguration",
        "label": "Security policy blocked wildcard IAM",
        "weight": 4,
        "excerpt": "Checkov failed: CKV_AWS_1 Ensure IAM policies avoid full admin privileges",
        "artifact": "IAM_POLICY",
        "fix": "Replace Action '*' with explicit least-privilege actions.",
    },
    {
        "code": "network_failure",
        "label": "Egress timeout to package registry",
        "weight": 4,
        "excerpt": "connect ETIMEDOUT registry.npmjs.org:443",
        "artifact": "WORKFLOW_YAML",
        "fix": "Confirm NAT/proxy routes for runners reaching the package registry.",
    },
    {
        "code": "network_failure",
        "label": "Pipeline step timeout",
        "weight": 4,
        "excerpt": "The job has exceeded the maximum execution time of 60 minutes",
        "artifact": "WORKFLOW_YAML",
        "fix": "Split long jobs or raise timeout after confirming no hang.",
    },
    {
        "code": "test_failure",
        "label": "Integration test suite failed",
        "weight": 4,
        "excerpt": "FAILED tests/integration/test_payments.py::test_capture",
        "artifact": "LOG",
        "fix": "Inspect failing assertion and fixture data for the payment flow.",
    },
    {
        "code": "build_failure",
        "label": "TypeScript compile failure",
        "weight": 3,
        "excerpt": "error TS2322: Type 'string | undefined' is not assignable",
        "artifact": "LOG",
        "fix": "Fix the type error reported at the compile location.",
    },
]


@dataclass
class Counts:
    organizations: int = 0
    users: int = 0
    projects: int = 0
    repositories: int = 0
    pipeline_runs: int = 0
    incidents: int = 0
    analyses: int = 0
    hypotheses: int = 0
    retrieval_documents: int = 0
    evidence_items: int = 0
    recommendations: int = 0
    counterfactuals: int = 0
    verifier_results: int = 0
    notifications: int = 0
    webhook_deliveries: int = 0
    events: int = 0
    skipped_pipeline_runs: int = 0
    skipped_incidents: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


@dataclass
class DemoContext:
    rng: random.Random
    now: datetime
    month_ago: datetime
    password_hash: str
    org: Organization | None = None
    users: dict[str, User] = field(default_factory=dict)
    engineers: list[User] = field(default_factory=list)
    projects: dict[str, Project] = field(default_factory=dict)
    categories: dict[str, FailureCategory] = field(default_factory=dict)
    model_version: ModelVersion | None = None
    installation: GitHubInstallation | None = None
    counts: Counts = field(default_factory=Counts)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _weighted_choice(rng: random.Random, items: list[dict[str, Any]]) -> dict[str, Any]:
    weights = [int(i["weight"]) for i in items]
    return rng.choices(items, weights=weights, k=1)[0]


def _business_timestamp(rng: random.Random, start: datetime, end: datetime) -> datetime:
    """Prefer weekday business hours; weekends are less frequent."""
    for _ in range(40):
        span = max(1, int((end - start).total_seconds()))
        ts = start + timedelta(seconds=rng.randint(0, span))
        # Weekend throttle
        if ts.weekday() >= 5 and rng.random() > 0.25:
            continue
        # Prefer 08:00–19:00 UTC business window
        if 8 <= ts.hour <= 19 or rng.random() < 0.2:
            return ts.replace(microsecond=0)
    return (start + timedelta(hours=rng.randint(1, 20 * 24))).replace(microsecond=0)


def _map_status(rng: random.Random, age_days: float) -> IncidentStatus:
    # Older incidents more likely resolved/closed.
    roll = rng.random()
    if age_days > 20:
        return rng.choice(
            [IncidentStatus.RESOLVED, IncidentStatus.CLOSED, IncidentStatus.CLOSED]
        )
    if age_days > 10:
        if roll < 0.55:
            return IncidentStatus.RESOLVED
        if roll < 0.70:
            return IncidentStatus.CLOSED
        if roll < 0.82:
            return IncidentStatus.IN_PROGRESS
        if roll < 0.90:
            return IncidentStatus.OPEN
        return IncidentStatus.ANALYSING
    if roll < 0.22:
        return IncidentStatus.OPEN
    if roll < 0.40:
        return IncidentStatus.IN_PROGRESS
    if roll < 0.52:
        return IncidentStatus.ANALYSING
    if roll < 0.60:
        return IncidentStatus.DETECTED
    if roll < 0.78:
        return IncidentStatus.RESOLVED
    if roll < 0.88:
        return IncidentStatus.CLOSED
    if roll < 0.93:
        return IncidentStatus.ANALYSIS_FAILED
    return IncidentStatus.REOPENED


def _severity_for_failure(code: str, rng: random.Random) -> IncidentSeverity:
    if code in {"aws_permission_failure", "security_misconfiguration"}:
        return rng.choice(
            [IncidentSeverity.CRITICAL, IncidentSeverity.HIGH, IncidentSeverity.HIGH]
        )
    if code in {"terraform_failure", "deployment_failure", "ci_runner_failure"}:
        return rng.choice([IncidentSeverity.HIGH, IncidentSeverity.MEDIUM])
    if code in {"network_failure", "dependency_failure"}:
        return rng.choice([IncidentSeverity.MEDIUM, IncidentSeverity.HIGH])
    return rng.choice([IncidentSeverity.MEDIUM, IncidentSeverity.LOW, IncidentSeverity.MEDIUM])


def _priority_for_severity(sev: IncidentSeverity) -> IncidentPriority:
    return {
        IncidentSeverity.CRITICAL: IncidentPriority.URGENT,
        IncidentSeverity.HIGH: IncidentPriority.HIGH,
        IncidentSeverity.MEDIUM: IncidentPriority.NORMAL,
        IncidentSeverity.LOW: IncidentPriority.LOW,
    }[sev]


async def _ensure_org(session: AsyncSession, ctx: DemoContext) -> Organization:
    existing = await session.scalar(select(Organization).where(Organization.slug == ORG_SLUG))
    if existing:
        existing.name = ORG_NAME
        existing.company_name = ORG_NAME
        existing.industry = "Cloud Software"
        existing.plan = "enterprise"
        existing.status = OrganizationStatus.ACTIVE
        existing.description = (
            f"Enterprise demo tenant ({DEMO_MARKER}). ~120 engineers. Active for ~30 days."
        )
        existing.website = "https://www.example.com"
        existing.country = "United Kingdom"
        existing.timezone = "Europe/London"
        ctx.org = existing
        return existing
    org = Organization(
        name=ORG_NAME,
        slug=ORG_SLUG,
        company_name=ORG_NAME,
        description=f"Enterprise demo tenant ({DEMO_MARKER}). ~120 engineers.",
        website="https://www.example.com",
        industry="Cloud Software",
        country="United Kingdom",
        timezone="Europe/London",
        plan="enterprise",
        status=OrganizationStatus.ACTIVE,
        created_at=ctx.month_ago,
    )
    session.add(org)
    await session.flush()
    ctx.counts.organizations += 1
    ctx.org = org
    return org


async def _ensure_users(session: AsyncSession, ctx: DemoContext) -> None:
    assert ctx.org is not None
    for spec in USERS:
        email = spec["email"].lower()
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=ctx.password_hash,
                full_name=spec["full_name"],
                platform_role=PlatformRole(spec["platform_role"]),
                is_active=True,
                created_at=ctx.month_ago + timedelta(hours=1),
            )
            session.add(user)
            await session.flush()
            ctx.counts.users += 1
        else:
            user.full_name = spec["full_name"]
            user.platform_role = PlatformRole(spec["platform_role"])
            user.is_active = True
            user.password_hash = ctx.password_hash
        ctx.users[email] = user

        member = await session.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == ctx.org.id,
                OrganizationMember.user_id == user.id,
            )
        )
        role = OrganizationRole(spec["org_role"])
        if member is None:
            session.add(
                OrganizationMember(
                    organization_id=ctx.org.id,
                    user_id=user.id,
                    role=role,
                    is_active=True,
                    joined_at=ctx.month_ago + timedelta(hours=2),
                )
            )
        else:
            member.role = role
            member.is_active = True

        if role == OrganizationRole.ENGINEER or role == OrganizationRole.ORGANIZATION_ADMIN:
            ctx.engineers.append(user)
    await session.flush()


async def _ensure_projects(session: AsyncSession, ctx: DemoContext) -> None:
    assert ctx.org is not None
    owner = ctx.users["ava.chen@example.com"]
    for idx, spec in enumerate(PROJECTS):
        project = await session.scalar(
            select(Project).where(
                Project.organization_id == ctx.org.id,
                Project.key == spec["key"],
            )
        )
        if project is None:
            project = Project(
                organization_id=ctx.org.id,
                name=spec["name"],
                key=spec["key"],
                description=spec["description"],
                repository_url=f"https://github.com/{spec['repo']}",
                default_branch="main",
                ci_provider=CiProvider.GITHUB_ACTIONS,
                cloud_provider=spec["cloud"],
                default_environment=spec["environment"],
                status=ProjectStatus.ACTIVE,
                created_by=owner.id,
                created_at=ctx.month_ago + timedelta(hours=3 + idx),
            )
            session.add(project)
            await session.flush()
            ctx.counts.projects += 1
        else:
            project.description = spec["description"]
            project.repository_url = f"https://github.com/{spec['repo']}"
            project.cloud_provider = spec["cloud"]
            project.default_environment = spec["environment"]
            project.status = ProjectStatus.ACTIVE
        ctx.projects[spec["key"]] = project
    await session.flush()


async def _ensure_github(session: AsyncSession, ctx: DemoContext) -> None:
    assert ctx.org is not None
    install = await session.scalar(
        select(GitHubInstallation).where(
            GitHubInstallation.github_installation_id == GITHUB_INSTALLATION_ID
        )
    )
    if install is None:
        install = GitHubInstallation(
            organization_id=ctx.org.id,
            github_installation_id=GITHUB_INSTALLATION_ID,
            github_account_login="acme-cloud",
            account_type="Organization",
            status="active",
            installed_at=ctx.month_ago + timedelta(hours=4),
            permissions_json={"demo_marker": DEMO_MARKER},
        )
        session.add(install)
        await session.flush()
    ctx.installation = install

    for idx, spec in enumerate(PROJECTS):
        project = ctx.projects[spec["key"]]
        conn = await session.scalar(
            select(GitHubRepositoryConnection).where(
                GitHubRepositoryConnection.project_id == project.id,
                GitHubRepositoryConnection.disconnected_at.is_(None),
            )
        )
        repo_id = 9_100_000 + idx
        if conn is None:
            session.add(
                GitHubRepositoryConnection(
                    organization_id=ctx.org.id,
                    project_id=project.id,
                    github_installation_id=install.id,
                    github_repository_id=repo_id,
                    repository_full_name=spec["repo"],
                    repository_url=f"https://github.com/{spec['repo']}",
                    default_branch="main",
                    is_active=True,
                    is_paused=False,
                    auto_create_incidents=True,
                    auto_start_analysis=True,
                    notify_on_failure=True,
                    environment_mapping_json={
                        "demo_marker": DEMO_MARKER,
                        "workflow": spec["workflow"],
                        "region": spec["region"],
                        "pipeline_status": "healthy",
                    },
                    last_successful_sync_at=ctx.month_ago + timedelta(hours=5 + idx),
                )
            )
            ctx.counts.repositories += 1
        else:
            conn.is_active = True
            conn.repository_full_name = spec["repo"]
    await session.flush()


async def _ensure_categories_and_model(session: AsyncSession, ctx: DemoContext) -> None:
    await seed_failure_categories(session)
    rows = (await session.scalars(select(FailureCategory))).all()
    ctx.categories = {r.code: r for r in rows}

    model = await session.scalar(
        select(ModelVersion).where(
            ModelVersion.model_name == "devguard-demo-classifier",
            ModelVersion.version == "1.0.0",
        )
    )
    if model is None:
        model = ModelVersion(
            model_name="devguard-demo-classifier",
            model_type="rules_hybrid",
            version="1.0.0",
            provider="devguard",
            status=ModelVersionStatus.ACTIVE,
            configuration={"demo_marker": DEMO_MARKER},
            metrics={"deterministic": True},
            trained_at=ctx.month_ago,
        )
        session.add(model)
        await session.flush()
    ctx.model_version = model


async def _existing_pipeline_ids(session: AsyncSession) -> set[str]:
    rows = await session.scalars(
        select(PipelineRun.external_run_id).where(
            PipelineRun.external_run_id.is_not(None),
            PipelineRun.external_run_id.like("acme-demo-%"),
        )
    )
    return {r for r in rows.all() if r}


def _pipeline_status(rng: random.Random) -> PipelineRunStatus:
    roll = rng.random()
    if roll < 0.62:
        return PipelineRunStatus.SUCCEEDED
    if roll < 0.88:
        return PipelineRunStatus.FAILED
    if roll < 0.95:
        return PipelineRunStatus.CANCELLED
    return PipelineRunStatus.RUNNING


async def _create_pipeline_runs(
    session: AsyncSession, ctx: DemoContext
) -> list[tuple[PipelineRun, dict[str, Any] | None]]:
    """Return list of (run, failure_spec|None)."""
    existing = await _existing_pipeline_ids(session)
    created: list[tuple[PipelineRun, dict[str, Any] | None]] = []
    project_keys = list(ctx.projects.keys())
    for i in range(PIPELINE_RUN_COUNT):
        key = project_keys[i % len(project_keys)]
        project = ctx.projects[key]
        spec = PROJECTS[i % len(PROJECTS)]
        external_id = f"acme-demo-{key}-{i:04d}"
        if external_id in existing:
            ctx.counts.skipped_pipeline_runs += 1
            run = await session.scalar(
                select(PipelineRun).where(
                    PipelineRun.provider == CiProvider.GITHUB_ACTIONS,
                    PipelineRun.external_run_id == external_id,
                )
            )
            if run is not None:
                created.append((run, None))
            continue

        started = _business_timestamp(ctx.rng, ctx.month_ago, ctx.now - timedelta(hours=1))
        status = _pipeline_status(ctx.rng)
        # Force enough failures for incident volume.
        if i % 3 == 0:
            status = PipelineRunStatus.FAILED
        duration = ctx.rng.randint(90, 2400)
        completed = (
            started + timedelta(seconds=duration)
            if status
            in {
                PipelineRunStatus.SUCCEEDED,
                PipelineRunStatus.FAILED,
                PipelineRunStatus.CANCELLED,
            }
            else None
        )
        failure = _weighted_choice(ctx.rng, FAILURE_CATALOGUE) if status == PipelineRunStatus.FAILED else None
        actor = ctx.rng.choice(list(ctx.users.values()))
        run = PipelineRun(
            project_id=project.id,
            external_run_id=external_id,
            provider=CiProvider.GITHUB_ACTIONS,
            workflow_name=spec["workflow"],
            branch=ctx.rng.choice(["main", "main", "main", "develop", "release/1.8"]),
            commit_sha=_sha(external_id)[:12],
            triggered_by=actor.email,
            environment=spec["environment"],
            status=status,
            started_at=started,
            completed_at=completed,
            duration_seconds=duration if completed else None,
            source_url=(
                f"https://github.com/{spec['repo']}/actions/runs/{9100000 + i}"
            ),
            raw_metadata={
                "demo_marker": DEMO_MARKER,
                "repository": spec["repo"],
                "region": spec["region"],
                "attempt": 1 if ctx.rng.random() > 0.15 else 2,
                "failure_label": failure["label"] if failure else None,
                "failure_code": failure["code"] if failure else None,
            },
            created_at=started,
        )
        session.add(run)
        ctx.counts.pipeline_runs += 1
        created.append((run, failure))
        if len(created) % 50 == 0:
            await session.flush()
    await session.flush()
    return created


async def _incident_for_run(session: AsyncSession, run_id: uuid.UUID) -> Incident | None:
    return await session.scalar(select(Incident).where(Incident.pipeline_run_id == run_id))


def _build_output_summary(
    *,
    failure: dict[str, Any],
    confidence: float,
    diagnosis_status: str,
    hypotheses: list[dict[str, Any]],
    verifier_support: str,
    duration_ms: int,
) -> dict[str, Any]:
    return {
        "demo_marker": DEMO_MARKER,
        "partial": False,
        "warnings": [],
        "classification": {
            "category": failure["code"],
            "confidence": confidence,
            "rank": 1,
        },
        "root_cause_summary": failure["label"],
        "execution_mode": "confidence_routed",
        "effective_execution_mode": "rag_llm",
        "final_confidence": {
            "score": confidence,
            "band": "HIGH" if confidence >= 0.8 else "MEDIUM" if confidence >= 0.6 else "LOW",
        },
        "cost_metrics": {
            "total_usd": round(0.002 + (1.0 - confidence) * 0.01, 5),
            "embedding_tokens": 1200,
            "llm_tokens": 1800,
            "provider": "local+openai",
        },
        "latency_ms": duration_ms,
        "model_versions": {
            "classifier": "devguard-demo-classifier-1.0.0",
            "reasoning": "template+llm",
            "retrieval": "hybrid_static",
            "embedding": "all-MiniLM-L6-v2",
        },
        "causal_hypotheses": {"hypotheses": hypotheses, "status": "COMPLETE"},
        "counterfactual_verification": {
            "status": "COMPLETE",
            "support": verifier_support,
        },
        "final_diagnosis": {
            "status": diagnosis_status,
            "final_category_code": failure["code"],
            "final_summary": failure["label"],
            "root_cause_statement": (
                f"Most likely contributing cause (evidence-based only): {failure['label']}"
            ),
            "confidence": confidence,
            "confidence_band": (
                "HIGH" if confidence >= 0.8 else "MEDIUM" if confidence >= 0.6 else "LOW"
            ),
            "verifier_support": verifier_support,
            "limitations": [
                "final_diagnosis_is_evidence_based_not_mathematical_proof",
                "verified_remediation_is_not_applied_remediation",
            ],
            "decision_version": "final_diagnosis_decision_v1",
            "demo_marker": DEMO_MARKER,
        },
        "artifact_bundle": {
            "artifacts": [
                {"path": ".github/workflows/deploy.yml", "type": "WORKFLOW_YAML"},
                {"path": "infra/main.tf", "type": "TERRAFORM"},
                {"path": "ci/logs/job.log", "type": "LOG"},
            ]
        },
    }


async def _seed_analysis_bundle(
    session: AsyncSession,
    ctx: DemoContext,
    *,
    incident: Incident,
    run: PipelineRun,
    failure: dict[str, Any],
    assignee: User,
    status: IncidentStatus,
) -> None:
    assert ctx.org is not None and ctx.model_version is not None
    category = ctx.categories.get(failure["code"]) or ctx.categories["unknown_failure"]
    started = (run.started_at or incident.detected_at) + timedelta(minutes=2)
    duration_ms = ctx.rng.randint(8_000, 95_000)
    completed = started + timedelta(milliseconds=duration_ms)
    confidence = round(ctx.rng.uniform(0.62, 0.94), 4)

    analysis_status = (
        AnalysisRunStatus.FAILED
        if status == IncidentStatus.ANALYSIS_FAILED
        else AnalysisRunStatus.COMPLETED
        if status
        not in {IncidentStatus.DETECTED, IncidentStatus.ANALYSING}
        or ctx.rng.random() < 0.7
        else AnalysisRunStatus.CLASSIFYING
    )
    if status == IncidentStatus.ANALYSING:
        analysis_status = AnalysisRunStatus.RETRIEVING

    hyp_count = ctx.rng.randint(2, 5)
    hypotheses: list[dict[str, Any]] = []
    for h in range(hyp_count):
        hypotheses.append(
            {
                "id": f"hyp-{h+1}",
                "title": failure["label"] if h == 0 else f"Alternate cause #{h+1}",
                "ranking_score": round(max(0.2, confidence - 0.12 * h), 3),
                "status": ["ACCEPTED", "WEAK", "REJECTED", "CONTRADICTED"][min(h, 3)],
            }
        )

    diagnosis_roll = ctx.rng.random()
    if analysis_status != AnalysisRunStatus.COMPLETED:
        diagnosis_status = "INSUFFICIENT_EVIDENCE"
        verifier_support = "UNAVAILABLE"
    elif diagnosis_roll < 0.45:
        diagnosis_status = "DIAGNOSED"
        verifier_support = "STRONG"
    elif diagnosis_roll < 0.70:
        diagnosis_status = "DIAGNOSED_WITH_WARNINGS"
        verifier_support = "MODERATE"
    elif diagnosis_roll < 0.85:
        diagnosis_status = "INSUFFICIENT_EVIDENCE"
        verifier_support = "WEAK"
    elif diagnosis_roll < 0.93:
        diagnosis_status = "UNKNOWN"
        verifier_support = "UNAVAILABLE"
    else:
        diagnosis_status = "CONFLICTED"
        verifier_support = "WEAK"

    analysis = AnalysisRun(
        incident_id=incident.id,
        pipeline_run_id=run.id,
        requested_by=assignee.id,
        status=analysis_status,
        analysis_type="full",
        started_at=started,
        completed_at=completed if analysis_status == AnalysisRunStatus.COMPLETED else None,
        duration_ms=duration_ms if analysis_status == AnalysisRunStatus.COMPLETED else None,
        current_stage=(
            "completed"
            if analysis_status == AnalysisRunStatus.COMPLETED
            else "retrieving"
            if analysis_status == AnalysisRunStatus.RETRIEVING
            else "failed"
        ),
        progress_percentage=100 if analysis_status == AnalysisRunStatus.COMPLETED else 55,
        input_summary={
            "demo_marker": DEMO_MARKER,
            "repository": (run.raw_metadata or {}).get("repository"),
            "workflow": run.workflow_name,
            "failure_label": failure["label"],
        },
        output_summary=_build_output_summary(
            failure=failure,
            confidence=confidence,
            diagnosis_status=diagnosis_status,
            hypotheses=hypotheses,
            verifier_support=verifier_support,
            duration_ms=duration_ms,
        )
        if analysis_status == AnalysisRunStatus.COMPLETED
        else {"demo_marker": DEMO_MARKER, "status": analysis_status.value},
        error_code="ANALYSIS_FAILED" if analysis_status == AnalysisRunStatus.FAILED else None,
        error_message="Soft-fail demo analysis" if analysis_status == AnalysisRunStatus.FAILED else None,
        created_at=started,
    )
    session.add(analysis)
    await session.flush()
    incident.latest_analysis_run_id = analysis.id
    ctx.counts.analyses += 1

    # Timeline events
    timeline = [
        ("incident_created", "Incident created from GitHub workflow failure", started - timedelta(minutes=3)),
        ("github_webhook", "GitHub webhook received", started - timedelta(minutes=4)),
        ("analysis_queued", "AI analysis queued", started - timedelta(minutes=1)),
        ("analysis_started", "AI analysis started", started),
        ("retrieval_completed", "Knowledge retrieval completed", started + timedelta(minutes=1)),
        ("hypothesis_generated", "Competing hypotheses generated", started + timedelta(minutes=2)),
        ("verification_completed", "Counterfactual verification completed", started + timedelta(minutes=3)),
        ("recommendation_generated", "Remediation recommendation generated", started + timedelta(minutes=4)),
    ]
    if status in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}:
        timeline.append(
            (
                "incident_resolved",
                "Incident resolved",
                incident.resolved_at or completed + timedelta(hours=2),
            )
        )
    for etype, title, when in timeline:
        session.add(
            IncidentEvent(
                organization_id=ctx.org.id,
                incident_id=incident.id,
                event_type=etype,
                actor_type="ai" if "analysis" in etype or "retrieval" in etype else "system",
                actor_user_id=assignee.id if etype == "incident_resolved" else None,
                title=title,
                description=failure["label"],
                event_metadata={"demo_marker": DEMO_MARKER},
                occurred_at=when,
            )
        )
        ctx.counts.events += 1

    if analysis_status != AnalysisRunStatus.COMPLETED:
        return

    prediction = Prediction(
        analysis_run_id=analysis.id,
        failure_category_id=category.id,
        model_version_id=ctx.model_version.id,
        confidence=Decimal(str(confidence)),
        rank=1,
        predicted_label=failure["label"],
        root_cause_summary=failure["label"],
        technical_explanation=failure["excerpt"],
        impact_summary=f"Blocks {incident.environment} deployments for {incident.title}",
        reasoning_metadata={"demo_marker": DEMO_MARKER, "mode": "hybrid"},
    )
    session.add(prediction)
    await session.flush()

    for eidx, excerpt in enumerate(
        [failure["excerpt"], "Masked log context around failing step", "Related workflow job summary"]
    ):
        session.add(
            EvidenceItem(
                analysis_run_id=analysis.id,
                prediction_id=prediction.id,
                evidence_type=EvidenceType.LOG_LINE if eidx == 0 else EvidenceType.CONFIG_SNIPPET,
                raw_excerpt=excerpt,
                normalized_excerpt=excerpt,
                source_name=run.workflow_name or "workflow",
                line_start=40 + eidx * 12,
                line_end=48 + eidx * 12,
                importance_score=Decimal(str(round(confidence - 0.05 * eidx, 4))),
            )
        )
        ctx.counts.evidence_items += 1

    # Retrieval summary is embedded in output_summary (avoids orphan knowledge FKs).
    analysis.output_summary = {
        **(analysis.output_summary or {}),
        "retrieval_result": {
            "demo_marker": DEMO_MARKER,
            "chunks": [
                {
                    "rank": ridx + 1,
                    "title": f"Guidance for {failure['code']}",
                    "similarity": round(0.82 - 0.08 * ridx, 4),
                    "source_type": "documentation" if ridx < 2 else "historical_incident",
                }
                for ridx in range(3)
            ],
        },
    }
    ctx.counts.retrieval_documents += 3

    recommendation = Recommendation(
        analysis_run_id=analysis.id,
        prediction_id=prediction.id,
        root_cause_summary=failure["label"],
        explanation=f"Recommended remediation for {failure['label']}.",
        confidence_score=Decimal(str(confidence)),
        llm_model="demo-structured-v1",
    )
    session.add(recommendation)
    await session.flush()
    ctx.counts.recommendations += 1

    steps = [
        (
            RecommendationStepType.REMEDIATION,
            "Apply least-privilege fix",
            failure["fix"],
            RiskLevel.LOW,
        ),
        (
            RecommendationStepType.VERIFICATION,
            "Re-run pipeline verification",
            "Re-run the failing workflow after the change; confirm green checks.",
            RiskLevel.LOW,
        ),
        (
            RecommendationStepType.PREVENTION,
            "Add guardrail",
            "Add CI policy checks to catch this class of failure earlier.",
            RiskLevel.MEDIUM,
        ),
    ]
    for sidx, (stype, title, action, risk) in enumerate(steps, start=1):
        session.add(
            RecommendationStep(
                recommendation_id=recommendation.id,
                analysis_run_id=analysis.id,
                step_number=sidx,
                step_type=stype,
                title=title,
                action=action,
                explanation=action,
                expected_result="Pipeline recovers without elevating privileges broadly.",
                risk_level=risk,
            )
        )

    # Hypotheses + evidence links
    hyp_run = CausalHypothesisRunRow(
        organization_id=ctx.org.id,
        project_id=incident.project_id,
        incident_id=incident.id,
        analysis_run_id=analysis.id,
        status="COMPLETE",
        deterministic_count=hyp_count,
        llm_count=0,
        generator_version="demo_hypothesis_v1",
        duration_ms=ctx.rng.randint(200, 2000),
        warnings=[],
        truncation_notes=[],
        token_usage={"prompt": 0, "completion": 0},
        context_snapshot={"demo_marker": DEMO_MARKER},
    )
    session.add(hyp_run)
    await session.flush()

    top_hyp: CausalHypothesisRow | None = None
    for hidx, hyp in enumerate(hypotheses):
        row = CausalHypothesisRow(
            organization_id=ctx.org.id,
            project_id=incident.project_id,
            incident_id=incident.id,
            analysis_run_id=analysis.id,
            hypothesis_run_id=hyp_run.id,
            hypothesis_key=f"H{hidx+1:02d}",
            rank_placeholder=hidx + 1,
            category_code=failure["code"],
            title=str(hyp["title"]),
            causal_claim=str(hyp["title"]),
            generator_type="RULE",
            generator_name="demo_rule_generator",
            generator_version="1.0.0",
            generation_confidence=float(hyp["ranking_score"]),
            generation_prior_score=float(hyp["ranking_score"]),
            status=str(hyp["status"]),
            path_validation_status="VALID" if hidx == 0 else "PARTIAL",
            expected_observations=[failure["excerpt"]],
            falsifying_observations=["Unrelated passing canary deploy"],
            proposed_verification_steps=["Inspect IAM/policy diff", "Re-run workflow"],
            missing_evidence=["previous successful plan output"] if hidx > 0 else [],
            limitations=["hypothesis_is_not_proven_root_cause"],
            warnings=[],
        )
        session.add(row)
        await session.flush()
        ctx.counts.hypotheses += 1
        if hidx == 0:
            top_hyp = row
        session.add(
            HypothesisEvidenceLinkRow(
                organization_id=ctx.org.id,
                analysis_run_id=analysis.id,
                hypothesis_id=row.id,
                evidence_type="SUPPORT_CANDIDATE" if hidx == 0 else "CONTRADICTION_CANDIDATE",
                evidence_item_id=f"ev-{hidx+1}",
                source_path=run.workflow_name,
                relation="supports" if hidx == 0 else "contradicts",
                confidence=float(hyp["ranking_score"]),
                explanation="demo evidence link",
                extraction_method="demo_rule",
            )
        )

    # Counterfactuals + verifiers
    cf_run = CounterfactualRemediationRunRow(
        organization_id=ctx.org.id,
        project_id=incident.project_id,
        incident_id=incident.id,
        analysis_run_id=analysis.id,
        status="COMPLETE",
        selected_hypothesis_ids=[str(top_hyp.id)] if top_hyp else [],
        selected_hypothesis_count=1 if top_hyp else 0,
        candidate_count=0,
        safe_candidate_count=0,
        incomplete_candidate_count=0,
        rejected_candidate_count=0,
        started_at=started + timedelta(minutes=3),
        completed_at=completed,
        duration_ms=ctx.rng.randint(300, 3000),
        context_version="demo_cf_v1",
        constraint_version="demo_cf_v1",
        planner_version="demo_cf_v1",
        template_registry_version="demo_cf_v1",
        snapshot_version="demo_cf_v1",
        configuration_snapshot={"demo_marker": DEMO_MARKER},
        warnings=[],
        errors=[],
        limitations=["candidates_are_not_applied"],
    )
    session.add(cf_run)
    await session.flush()

    cand_n = ctx.rng.randint(1, 3)
    cf_run.candidate_count = cand_n
    cf_run.safe_candidate_count = max(1, cand_n - 1)
    verifier_names = [
        ("terraform_validate", "PASS"),
        ("terraform_plan", "PASS"),
        ("actionlint", "PASS"),
        ("checkov", "WARNING"),
        ("opa", "UNAVAILABLE"),
        ("yaml_validator", "PASS"),
        ("hcl_fragment", "PASS"),
        ("json_schema", "PASS"),
    ]
    for cidx in range(cand_n):
        consensus = {
            0: "VERIFIED",
            1: "PARTIALLY_VERIFIED",
            2: "FAILED",
        }.get(cidx, "INCONCLUSIVE")
        if diagnosis_status == "DIAGNOSED" and cidx == 0:
            consensus = "VERIFIED"
        candidate = CounterfactualRemediationCandidateRow(
            remediation_run_id=cf_run.id,
            organization_id=ctx.org.id,
            project_id=incident.project_id,
            incident_id=incident.id,
            analysis_run_id=analysis.id,
            hypothesis_id=top_hyp.id if top_hyp else None,
            candidate_key=f"cand-{cidx+1}",
            title=f"Remediation candidate {cidx+1} for {failure['label']}",
            summary=failure["fix"],
            artifact_type=failure["artifact"],
            category_code=failure["code"],
            target_paths=["infra/iam.tf" if "IAM" in failure["artifact"] else "deploy.yml"],
            change_types=["UPDATE"],
            expected_effects=["Restore successful pipeline"],
            assumptions=["No concurrent infra apply"],
            limitations=["not_applied", "workspace_verification_only"],
            rollback_plan={"rollback_steps": [{"original_fragment": "{}"}]},
            risk_summary=["low blast radius"] if cidx == 0 else ["review required"],
            blast_radius_summary={"level": "LIMITED"},
            generator_type="RULE_TEMPLATE",
            generator_name="demo_rule_template",
            generator_version="1.0.0",
            status="READY_FOR_VERIFICATION",
            rendered_patch=f"# demo patch for {failure['code']}\n",
            patch_format="TEXT_FRAGMENT",
            changed_file_count=1,
            changed_line_count=ctx.rng.randint(2, 18),
            risk_score=0.2 + 0.15 * cidx,
            risk_level="LOW" if cidx == 0 else "MEDIUM",
            priority_score=0.9 - 0.2 * cidx,
            priority_status="PRIORITY_CANDIDATE" if cidx == 0 else "ALTERNATIVE_CANDIDATE",
            validation_status=consensus,
            constraint_status="STRUCTURALLY_COMPLIANT",
            generation_provenance={"demo_marker": DEMO_MARKER, "verification_consensus": consensus},
        )
        session.add(candidate)
        await session.flush()
        ctx.counts.counterfactuals += 1

        vrun = RemediationVerificationRunRow(
            organization_id=ctx.org.id,
            project_id=incident.project_id,
            incident_id=incident.id,
            analysis_run_id=analysis.id,
            remediation_run_id=cf_run.id,
            candidate_id=candidate.id,
            status="COMPLETE",
            consensus_status=consensus,
            configuration_snapshot={"demo_marker": DEMO_MARKER},
            warnings=["checkov_warning"] if consensus == "PARTIALLY_VERIFIED" else [],
            errors=["blocking_fail"] if consensus == "FAILED" else [],
            duration_ms=ctx.rng.randint(100, 2500),
            engine_version="demo_verifier_v1",
            consensus_version="demo_consensus_v1",
            workspace_version="demo_workspace_v1",
            started_at=started + timedelta(minutes=3),
            completed_at=completed,
        )
        session.add(vrun)
        await session.flush()

        for tool, default_status in verifier_names[: ctx.rng.randint(4, 8)]:
            st = default_status
            if consensus == "FAILED" and tool in {"terraform_validate", "json_schema"}:
                st = "FAIL"
            if consensus == "UNAVAILABLE":
                st = "UNAVAILABLE"
            session.add(
                RemediationVerificationResultRow(
                    verification_run_id=vrun.id,
                    organization_id=ctx.org.id,
                    analysis_run_id=analysis.id,
                    candidate_id=candidate.id,
                    verifier_name=tool,
                    verifier_version="demo",
                    status=st,
                    duration_ms=ctx.rng.randint(20, 400),
                    warnings=[],
                    errors=[],
                    findings=[],
                    stdout_truncated=f"{tool} {st}",
                    stderr_truncated="",
                    artifacts_checked=[failure["artifact"]],
                    tool_available=st != "UNAVAILABLE",
                    metadata_json={"demo_marker": DEMO_MARKER},
                )
            )
            ctx.counts.verifier_results += 1


async def _create_incidents_and_analyses(
    session: AsyncSession,
    ctx: DemoContext,
    pipeline_rows: list[tuple[PipelineRun, dict[str, Any] | None]],
) -> None:
    assert ctx.org is not None
    failed_runs: list[tuple[PipelineRun, dict[str, Any]]] = []
    for run, failure in pipeline_rows:
        meta = run.raw_metadata or {}
        if run.status != PipelineRunStatus.FAILED:
            continue
        if failure is None:
            # Reloaded existing run — reconstruct failure from metadata if possible.
            code = meta.get("failure_code") or "unknown_failure"
            label = meta.get("failure_label") or "Unknown pipeline failure"
            failure = next(
                (f for f in FAILURE_CATALOGUE if f["code"] == code and f["label"] == label),
                next((f for f in FAILURE_CATALOGUE if f["code"] == code), FAILURE_CATALOGUE[0]),
            )
            failure = dict(failure)
            failure["label"] = label
        failed_runs.append((run, failure))

    # Prefer diverse failures up to INCIDENT_TARGET (stable order — idempotent).
    failed_runs.sort(key=lambda item: str(item[0].external_run_id or ""))
    selected = failed_runs[:INCIDENT_TARGET]

    for run, failure in selected:
        existing = await _incident_for_run(session, run.id)
        if existing is not None:
            ctx.counts.skipped_incidents += 1
            continue

        project = await session.get(Project, run.project_id)
        assert project is not None
        assignee = ctx.rng.choice(ctx.engineers)
        reporter = ctx.users["priya.nair@example.com"]
        detected = run.started_at or ctx.month_ago
        age_days = (ctx.now - detected).total_seconds() / 86400.0
        status = _map_status(ctx.rng, age_days)
        severity = _severity_for_failure(failure["code"], ctx.rng)
        priority = _priority_for_severity(severity)
        resolved_at = None
        closed_at = None
        if status in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}:
            resolved_at = detected + timedelta(hours=ctx.rng.randint(2, 72))
            if status == IncidentStatus.CLOSED:
                closed_at = resolved_at + timedelta(hours=ctx.rng.randint(1, 24))

        title = f"{project.key}: {failure['label']}"
        incident = Incident(
            organization_id=ctx.org.id,
            project_id=project.id,
            pipeline_run_id=run.id,
            title=title[:255],
            description=(
                f"{failure['label']}\n\n"
                f"Workflow `{run.workflow_name}` on branch `{run.branch}` failed.\n"
                f"Excerpt: {failure['excerpt']}\n"
                f"[{DEMO_MARKER}]"
            ),
            source="github_webhook",
            status=status,
            severity=severity,
            priority=priority,
            environment=run.environment or project.default_environment,
            detected_at=detected,
            acknowledged_at=detected + timedelta(minutes=ctx.rng.randint(5, 90)),
            resolved_at=resolved_at,
            closed_at=closed_at,
            created_by=reporter.id,
            current_assignee_id=assignee.id,
            root_cause_summary=failure["label"]
            if status in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}
            else None,
            impact_summary=f"Impacts {project.name} {run.environment} pipeline.",
            tags=[
                DEMO_MARKER,
                "enterprise-demo",
                failure["code"],
                project.key.lower(),
                (run.environment or "unknown"),
            ],
            created_at=detected,
        )
        session.add(incident)
        await session.flush()
        ctx.counts.incidents += 1

        session.add(
            IncidentAssignment(
                incident_id=incident.id,
                assigned_to=assignee.id,
                assigned_by=reporter.id,
                assigned_at=detected + timedelta(minutes=10),
            )
        )
        session.add(
            IncidentNote(
                incident_id=incident.id,
                author_id=assignee.id,
                note_type="investigation",
                content=(
                    f"Investigating {failure['label']}. "
                    f"Checking {failure['artifact']} artifact and recent IAM/workflow changes."
                ),
            )
        )

        if status in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}:
            session.add(
                IncidentResolution(
                    incident_id=incident.id,
                    resolved_by=assignee.id,
                    resolution_summary=failure["fix"],
                    confirmed_root_cause=failure["label"],
                )
            )

        # Webhook delivery + notifications
        delivery_id = f"demo-wh-{run.external_run_id}"
        existing_wh = await session.scalar(
            select(WebhookDelivery).where(
                WebhookDelivery.provider == "github",
                WebhookDelivery.delivery_id == delivery_id,
            )
        )
        if existing_wh is None:
            session.add(
                WebhookDelivery(
                    organization_id=ctx.org.id,
                    provider="github",
                    delivery_id=delivery_id,
                    event_name="workflow_run",
                    event_action="completed",
                    payload_hash=_sha(delivery_id)[:64],
                    signature_valid=True,
                    processing_status="completed",
                    received_at=detected - timedelta(minutes=1),
                    processed_at=detected,
                    sanitised_snapshot={
                        "demo_marker": DEMO_MARKER,
                        "run_id": run.external_run_id,
                    },
                    related_pipeline_run_id=run.id,
                    related_incident_id=incident.id,
                    installation_id=GITHUB_INSTALLATION_ID,
                )
            )
            ctx.counts.webhook_deliveries += 1

        for ntype, ntitle, nmsg in [
            (
                NotificationType.INCIDENT_CREATED,
                "Incident created",
                f"New incident: {title}",
            ),
            (
                NotificationType.ASSIGNMENT,
                "Incident assigned",
                f"Assigned to {assignee.full_name}",
            ),
            (
                NotificationType.ANALYSIS_COMPLETED,
                "Analysis completed",
                f"AI analysis finished for {title}",
            ),
        ]:
            if ntype == NotificationType.ANALYSIS_COMPLETED and status in {
                IncidentStatus.DETECTED,
                IncidentStatus.ANALYSING,
                IncidentStatus.ANALYSIS_FAILED,
            }:
                continue
            session.add(
                Notification(
                    organization_id=ctx.org.id,
                    user_id=assignee.id,
                    incident_id=incident.id,
                    notification_type=ntype,
                    title=ntitle,
                    message=nmsg[:500],
                    channel="in_app",
                    delivery_status=DeliveryStatus.SENT,
                    is_read=ctx.rng.random() < 0.4,
                    severity=severity.value,
                )
            )
            ctx.counts.notifications += 1

        await _seed_analysis_bundle(
            session,
            ctx,
            incident=incident,
            run=run,
            failure=failure,
            assignee=assignee,
            status=status,
        )

        if ctx.counts.incidents % 20 == 0:
            await session.flush()


async def _count_reports_ready(session: AsyncSession, org_id: uuid.UUID) -> dict[str, int]:
    incidents = await session.scalar(
        select(func.count()).select_from(Incident).where(Incident.organization_id == org_id)
    )
    analyses = await session.scalar(
        select(func.count())
        .select_from(AnalysisRun)
        .join(Incident, Incident.id == AnalysisRun.incident_id)
        .where(Incident.organization_id == org_id)
    )
    pipelines = await session.scalar(
        select(func.count())
        .select_from(PipelineRun)
        .join(Project, Project.id == PipelineRun.project_id)
        .where(Project.organization_id == org_id)
    )
    hypotheses = await session.scalar(
        select(func.count())
        .select_from(CausalHypothesisRow)
        .where(CausalHypothesisRow.organization_id == org_id)
    )
    recommendations = await session.scalar(
        select(func.count())
        .select_from(Recommendation)
        .join(AnalysisRun, AnalysisRun.id == Recommendation.analysis_run_id)
        .join(Incident, Incident.id == AnalysisRun.incident_id)
        .where(Incident.organization_id == org_id)
    )
    evidence = await session.scalar(
        select(func.count())
        .select_from(EvidenceItem)
        .join(AnalysisRun, AnalysisRun.id == EvidenceItem.analysis_run_id)
        .join(Incident, Incident.id == AnalysisRun.incident_id)
        .where(Incident.organization_id == org_id)
    )
    counterfactuals = await session.scalar(
        select(func.count())
        .select_from(CounterfactualRemediationCandidateRow)
        .where(CounterfactualRemediationCandidateRow.organization_id == org_id)
    )
    verifiers = await session.scalar(
        select(func.count())
        .select_from(RemediationVerificationResultRow)
        .where(RemediationVerificationResultRow.organization_id == org_id)
    )
    notifications = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.organization_id == org_id)
    )
    users = await session.scalar(
        select(func.count())
        .select_from(OrganizationMember)
        .where(OrganizationMember.organization_id == org_id)
    )
    projects = await session.scalar(
        select(func.count()).select_from(Project).where(Project.organization_id == org_id)
    )
    repositories = await session.scalar(
        select(func.count())
        .select_from(GitHubRepositoryConnection)
        .where(GitHubRepositoryConnection.organization_id == org_id)
    )
    return {
        "organizations": 1,
        "users": int(users or 0),
        "projects": int(projects or 0),
        "repositories": int(repositories or 0),
        "pipeline_runs": int(pipelines or 0),
        "incidents": int(incidents or 0),
        "analyses": int(analyses or 0),
        "hypotheses": int(hypotheses or 0),
        "evidence_items": int(evidence or 0),
        "recommendations": int(recommendations or 0),
        "counterfactuals": int(counterfactuals or 0),
        "verifier_results": int(verifiers or 0),
        "notifications": int(notifications or 0),
        "reports_populated": 1 if int(incidents or 0) > 0 else 0,
    }


async def purge_demo_operational_data(session: AsyncSession) -> dict[str, int]:
    """Delete Acme demo pipelines/incidents/analyses while keeping org/users/projects.

    Used by ``--reset`` so re-seeds land on a clean, internally consistent month.
    """
    org = await session.scalar(select(Organization).where(Organization.slug == ORG_SLUG))
    if org is None:
        return {"purged_incidents": 0, "purged_pipeline_runs": 0, "purged_notifications": 0}

    incident_ids = list(
        (
            await session.scalars(select(Incident.id).where(Incident.organization_id == org.id))
        ).all()
    )
    # Break circular incident <-> analysis_run FK before cascade delete.
    if incident_ids:
        await session.execute(
            update(Incident)
            .where(Incident.id.in_(incident_ids))
            .values(latest_analysis_run_id=None)
        )
        await session.execute(delete(Incident).where(Incident.id.in_(incident_ids)))

    project_ids = list(
        (
            await session.scalars(select(Project.id).where(Project.organization_id == org.id))
        ).all()
    )
    purged_pipelines = 0
    if project_ids:
        result = await session.execute(
            delete(PipelineRun).where(
                PipelineRun.project_id.in_(project_ids),
                PipelineRun.external_run_id.like("acme-demo-%"),
            )
        )
        purged_pipelines = int(result.rowcount or 0)

    notif_result = await session.execute(
        delete(Notification).where(Notification.organization_id == org.id)
    )
    wh_result = await session.execute(
        delete(WebhookDelivery).where(
            WebhookDelivery.organization_id == org.id,
            WebhookDelivery.delivery_id.like("demo-wh-%"),
        )
    )
    await session.flush()
    return {
        "purged_incidents": len(incident_ids),
        "purged_pipeline_runs": purged_pipelines,
        "purged_notifications": int(notif_result.rowcount or 0),
        "purged_webhooks": int(wh_result.rowcount or 0),
    }


async def generate(session: AsyncSession, *, reset: bool = False) -> dict[str, Any]:
    settings = get_settings()
    if settings.environment == "production" or settings.is_production:
        raise RuntimeError("Refusing to seed enterprise demo data in production.")

    purge_stats: dict[str, int] = {}
    if reset:
        purge_stats = await purge_demo_operational_data(session)
        print(
            "Reset purge: "
            f"incidents={purge_stats.get('purged_incidents', 0)}, "
            f"pipelines={purge_stats.get('purged_pipeline_runs', 0)}, "
            f"notifications={purge_stats.get('purged_notifications', 0)}"
        )

    rng = random.Random(RNG_SEED)
    now = datetime.now(UTC).replace(microsecond=0)
    ctx = DemoContext(
        rng=rng,
        now=now,
        month_ago=now - timedelta(days=30),
        password_hash=hash_password(DEMO_PASSWORD),
    )

    await _ensure_categories_and_model(session, ctx)
    await _ensure_org(session, ctx)
    await _ensure_users(session, ctx)
    await _ensure_projects(session, ctx)
    await _ensure_github(session, ctx)
    pipeline_rows = await _create_pipeline_runs(session, ctx)
    await _create_incidents_and_analyses(session, ctx, pipeline_rows)
    await session.flush()

    assert ctx.org is not None
    report_ready = await _count_reports_ready(session, ctx.org.id)
    return {
        "organization": {"name": ORG_NAME, "slug": ORG_SLUG, "plan": "enterprise"},
        "login_hint": {
            "email": "ava.chen@example.com",
            "password": DEMO_PASSWORD,
            "note": "Demo password shared across demo users; change in non-demo environments.",
        },
        "counts": ctx.counts.as_dict(),
        "dashboard_totals": report_ready,
        "purge": purge_stats,
        "marker": DEMO_MARKER,
    }


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Acme Cloud Solutions enterprise demo data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Purge Acme demo pipelines/incidents/analyses, then reseed (org/users/projects kept).",
    )
    args = parser.parse_args(argv)

    # Keep seed output readable in Docker (SQL echo otherwise floods the console).
    import logging

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

    settings = get_settings()
    init_db(settings)
    from app.infrastructure.database import session as db_session

    if getattr(db_session, "_engine", None) is not None:
        db_session._engine.echo = False
    factory = ensure_session_factory()
    try:
        async with factory() as session:
            try:
                result = await generate(session, reset=args.reset)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await close_db()

    print("\n=== Enterprise demo dataset ready ===")
    print(f"Organization: {result['organization']['name']} ({result['organization']['slug']})")
    print(f"Marker: {result['marker']}")
    print("\nCreated this run:")
    for key, value in result["counts"].items():
        print(f"  {key}: {value}")
    print("\nDashboard totals (org-scoped):")
    for key, value in result["dashboard_totals"].items():
        print(f"  {key}: {value}")
    print("\nDemo login:")
    print(f"  email: {result['login_hint']['email']}")
    print(f"  password: {result['login_hint']['password']}")
    print("\nRe-run is idempotent. Use --reset for a clean reseed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
