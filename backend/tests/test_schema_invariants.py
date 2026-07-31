"""Schema-level invariant tests for the incident-centred domain model (ADR-012).

These tests exercise the ORM models directly (no repositories exist yet for
most of these tables — repository expansion is deferred per the refactoring
plan, R-006) against an isolated, migrated PostgreSQL test database.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.enums import (
    CiProvider,
    EvidenceType,
    IncidentSeverity,
    IncidentStatus,
    IntegrationStatus,
    KnowledgeDocumentStatus,
    OrganizationRole,
    RecommendationStepType,
)
from app.infrastructure.database.models.analysis_run import AnalysisRun
from app.infrastructure.database.models.evidence_item import EvidenceItem
from app.infrastructure.database.models.failure_category import FailureCategory
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.knowledge_chunk import KnowledgeChunk
from app.infrastructure.database.models.knowledge_document import KnowledgeDocument
from app.infrastructure.database.models.model_version import ModelVersion
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.database.models.prediction import Prediction
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.project_integration import ProjectIntegration
from app.infrastructure.database.models.recommendation import Recommendation
from app.infrastructure.database.models.recommendation_step import RecommendationStep
from app.infrastructure.database.models.user import User


async def _create_organization(session, *, slug: str = "acme") -> Organization:
    organization = Organization(name="Acme Corp", slug=slug)
    session.add(organization)
    await session.flush()
    return organization


async def _create_user(session, *, email: str = "engineer@example.com") -> User:
    user = User(
        email=email,
        password_hash="pbkdf2_sha256$deadbeef$abc123",
        full_name="Test Engineer",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_project(
    session,
    organization: Organization,
    creator: User,
    *,
    key: str = "PROJ",
) -> Project:
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


async def _create_incident(session, project: Project, *, title: str = "Build failed") -> Incident:
    incident = Incident(
        organization_id=project.organization_id,
        project_id=project.id,
        title=title,
        source="pipeline",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.DETECTED,
        detected_at=datetime.now(UTC),
    )
    session.add(incident)
    await session.flush()
    return incident


async def _create_model_version(session, *, name: str = "tfidf-logreg") -> ModelVersion:
    model_version = ModelVersion(
        model_name=name,
        model_type="logistic_regression",
        version="1.0.0",
    )
    session.add(model_version)
    await session.flush()
    return model_version


async def _create_failure_category(session, *, code: str = "build_failure") -> FailureCategory:
    category = FailureCategory(code=code, name="Build Failure", description="Build failed.")
    session.add(category)
    await session.flush()
    return category


# ---------------------------------------------------------------------------
# Organization + membership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_organization_membership_role_persists(repository_db_session) -> None:
    organization = await _create_organization(repository_db_session)
    user = await _create_user(repository_db_session)

    membership = OrganizationMember(
        organization_id=organization.id,
        user_id=user.id,
        role=OrganizationRole.ORGANIZATION_OWNER,
    )
    repository_db_session.add(membership)
    await repository_db_session.commit()

    fetched = await repository_db_session.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    assert fetched is not None
    assert fetched.role == OrganizationRole.ORGANIZATION_OWNER
    assert fetched.organization_id == organization.id


@pytest.mark.asyncio
async def test_organization_membership_unique_per_org_and_user(repository_db_session) -> None:
    organization = await _create_organization(repository_db_session)
    user = await _create_user(repository_db_session)

    repository_db_session.add(
        OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.ENGINEER,
        )
    )
    await repository_db_session.commit()

    repository_db_session.add(
        OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.VIEWER,
        )
    )
    with pytest.raises(IntegrityError):
        await repository_db_session.commit()


# ---------------------------------------------------------------------------
# Project ownership under organization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_project_is_owned_by_organization(repository_db_session) -> None:
    organization = await _create_organization(repository_db_session)
    creator = await _create_user(repository_db_session)
    project = await _create_project(repository_db_session, organization, creator)
    await repository_db_session.commit()

    fetched = await repository_db_session.get(Project, project.id)
    assert fetched is not None
    assert fetched.organization_id == organization.id
    assert fetched.created_by == creator.id


@pytest.mark.asyncio
async def test_project_key_unique_within_organization(repository_db_session) -> None:
    organization = await _create_organization(repository_db_session)
    creator = await _create_user(repository_db_session)
    await _create_project(repository_db_session, organization, creator, key="DUP")
    await repository_db_session.commit()

    repository_db_session.add(
        Project(
            organization_id=organization.id,
            name="Another Project",
            key="DUP",
            ci_provider=CiProvider.GITHUB_ACTIONS,
            created_by=creator.id,
        )
    )
    with pytest.raises(IntegrityError):
        await repository_db_session.commit()


# ---------------------------------------------------------------------------
# Incident under project
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incident_belongs_to_project(repository_db_session) -> None:
    organization = await _create_organization(repository_db_session)
    creator = await _create_user(repository_db_session)
    project = await _create_project(repository_db_session, organization, creator)
    incident = await _create_incident(repository_db_session, project)
    await repository_db_session.commit()

    fetched = await repository_db_session.get(Incident, incident.id)
    assert fetched is not None
    assert fetched.project_id == project.id
    assert fetched.incident_number is not None


@pytest.mark.asyncio
async def test_incident_may_reference_pipeline_run(repository_db_session) -> None:
    organization = await _create_organization(repository_db_session)
    creator = await _create_user(repository_db_session)
    project = await _create_project(repository_db_session, organization, creator)

    pipeline_run = PipelineRun(project_id=project.id, provider=CiProvider.GITHUB_ACTIONS)
    repository_db_session.add(pipeline_run)
    await repository_db_session.flush()

    incident = Incident(
        organization_id=project.organization_id,
        project_id=project.id,
        pipeline_run_id=pipeline_run.id,
        title="Pipeline-triggered incident",
        source="pipeline",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.DETECTED,
        detected_at=datetime.now(UTC),
    )
    repository_db_session.add(incident)
    await repository_db_session.commit()

    fetched = await repository_db_session.get(Incident, incident.id)
    assert fetched is not None
    assert fetched.pipeline_run_id == pipeline_run.id


# ---------------------------------------------------------------------------
# Multiple analysis runs per incident
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incident_supports_multiple_analysis_runs(repository_db_session) -> None:
    organization = await _create_organization(repository_db_session)
    creator = await _create_user(repository_db_session)
    project = await _create_project(repository_db_session, organization, creator)
    incident = await _create_incident(repository_db_session, project)

    first_run = AnalysisRun(incident_id=incident.id, analysis_type="full_pipeline")
    second_run = AnalysisRun(incident_id=incident.id, analysis_type="reanalysis")
    repository_db_session.add_all([first_run, second_run])
    await repository_db_session.commit()

    runs = (
        await repository_db_session.scalars(
            select(AnalysisRun).where(AnalysisRun.incident_id == incident.id)
        )
    ).all()
    assert len(runs) == 2
    assert {run.id for run in runs} == {first_run.id, second_run.id}


# ---------------------------------------------------------------------------
# Prediction / evidence / recommendation_steps linked to analysis_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prediction_evidence_and_recommendation_steps_link_to_analysis_run(
    repository_db_session,
) -> None:
    organization = await _create_organization(repository_db_session)
    creator = await _create_user(repository_db_session)
    project = await _create_project(repository_db_session, organization, creator)
    incident = await _create_incident(repository_db_session, project)
    model_version = await _create_model_version(repository_db_session)
    category = await _create_failure_category(repository_db_session)

    analysis_run = AnalysisRun(incident_id=incident.id, analysis_type="full_pipeline")
    repository_db_session.add(analysis_run)
    await repository_db_session.flush()

    prediction = Prediction(
        analysis_run_id=analysis_run.id,
        failure_category_id=category.id,
        model_version_id=model_version.id,
        confidence=0.87,
        predicted_label="build_failure",
    )
    repository_db_session.add(prediction)
    await repository_db_session.flush()

    evidence = EvidenceItem(
        analysis_run_id=analysis_run.id,
        prediction_id=prediction.id,
        evidence_type=EvidenceType.LOG_LINE,
        raw_excerpt="ERROR: compilation failed",
    )
    repository_db_session.add(evidence)

    recommendation = Recommendation(
        analysis_run_id=analysis_run.id,
        prediction_id=prediction.id,
        root_cause_summary="Missing build dependency.",
    )
    repository_db_session.add(recommendation)
    await repository_db_session.flush()

    steps = [
        RecommendationStep(
            recommendation_id=recommendation.id,
            analysis_run_id=analysis_run.id,
            step_number=1,
            step_type=RecommendationStepType.REMEDIATION,
            title="Install missing dependency",
            action="Run the package manager install command.",
        ),
        RecommendationStep(
            recommendation_id=recommendation.id,
            analysis_run_id=analysis_run.id,
            step_number=2,
            step_type=RecommendationStepType.VERIFICATION,
            title="Re-run the build",
            action="Trigger the pipeline again and confirm success.",
        ),
        RecommendationStep(
            recommendation_id=recommendation.id,
            analysis_run_id=analysis_run.id,
            step_number=3,
            step_type=RecommendationStepType.PREVENTION,
            title="Pin dependency versions",
            action="Add a lockfile to prevent drift.",
        ),
    ]
    repository_db_session.add_all(steps)
    await repository_db_session.commit()

    # Column-only refresh does not populate collections; load steps via the
    # async-safe relationship refresh path (lazy="selectin" on the model).
    await repository_db_session.refresh(recommendation, attribute_names=["steps"])
    ordered_step_numbers = [step.step_number for step in recommendation.steps]
    assert ordered_step_numbers == [1, 2, 3]

    fetched_evidence = await repository_db_session.scalar(
        select(EvidenceItem).where(EvidenceItem.analysis_run_id == analysis_run.id)
    )
    assert fetched_evidence is not None
    assert fetched_evidence.prediction_id == prediction.id


@pytest.mark.asyncio
async def test_recommendation_steps_unique_ordering_per_recommendation(
    repository_db_session,
) -> None:
    organization = await _create_organization(repository_db_session)
    creator = await _create_user(repository_db_session)
    project = await _create_project(repository_db_session, organization, creator)
    incident = await _create_incident(repository_db_session, project)

    analysis_run = AnalysisRun(incident_id=incident.id, analysis_type="full_pipeline")
    repository_db_session.add(analysis_run)
    await repository_db_session.flush()

    recommendation = Recommendation(analysis_run_id=analysis_run.id)
    repository_db_session.add(recommendation)
    await repository_db_session.flush()

    repository_db_session.add(
        RecommendationStep(
            recommendation_id=recommendation.id,
            analysis_run_id=analysis_run.id,
            step_number=1,
            step_type=RecommendationStepType.REMEDIATION,
            title="First step",
            action="Do the first thing.",
        )
    )
    await repository_db_session.commit()

    repository_db_session.add(
        RecommendationStep(
            recommendation_id=recommendation.id,
            analysis_run_id=analysis_run.id,
            step_number=1,
            step_type=RecommendationStepType.VERIFICATION,
            title="Duplicate step number",
            action="Should conflict with existing step 1.",
        )
    )
    with pytest.raises(IntegrityError):
        await repository_db_session.commit()


# ---------------------------------------------------------------------------
# Knowledge document -> knowledge chunk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_knowledge_document_has_ordered_chunks(repository_db_session) -> None:
    document = KnowledgeDocument(
        provider="terraform",
        title="Terraform Provisioning Errors",
        status=KnowledgeDocumentStatus.ACTIVE,
        ingested_at=datetime.now(UTC),
    )
    repository_db_session.add(document)
    await repository_db_session.flush()

    chunks = [
        KnowledgeChunk(document_id=document.id, chunk_index=0, content="Chunk zero content."),
        KnowledgeChunk(document_id=document.id, chunk_index=1, content="Chunk one content."),
    ]
    repository_db_session.add_all(chunks)
    await repository_db_session.commit()

    fetched_chunks = (
        await repository_db_session.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document.id)
            .order_by(KnowledgeChunk.chunk_index)
        )
    ).all()
    assert [chunk.chunk_index for chunk in fetched_chunks] == [0, 1]


@pytest.mark.asyncio
async def test_knowledge_chunks_are_deleted_with_document(repository_db_session) -> None:
    document = KnowledgeDocument(
        provider="aws",
        title="AWS IAM Permission Errors",
        status=KnowledgeDocumentStatus.ACTIVE,
        ingested_at=datetime.now(UTC),
    )
    repository_db_session.add(document)
    await repository_db_session.flush()

    repository_db_session.add(
        KnowledgeChunk(document_id=document.id, chunk_index=0, content="Some content.")
    )
    await repository_db_session.commit()

    await repository_db_session.delete(document)
    await repository_db_session.commit()

    remaining = await repository_db_session.scalar(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
    )
    assert remaining is None


# ---------------------------------------------------------------------------
# Project integrations store only a secret reference, never a raw secret
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_project_integration_stores_reference_not_raw_secret(
    repository_db_session,
) -> None:
    organization = await _create_organization(repository_db_session)
    creator = await _create_user(repository_db_session)
    project = await _create_project(repository_db_session, organization, creator)

    integration = ProjectIntegration(
        project_id=project.id,
        provider="github",
        integration_type="source_control",
        external_reference="org/repo",
        encrypted_secret_reference="vault://secrets/data/github-token",
        status=IntegrationStatus.ACTIVE,
    )
    repository_db_session.add(integration)
    await repository_db_session.commit()

    fetched = await repository_db_session.get(ProjectIntegration, integration.id)
    assert fetched is not None
    # The column stores an opaque reference to a secret manager entry, not a
    # raw credential. Structurally this is any string; the *policy* that only
    # references (never plaintext passwords/tokens) are written belongs to the
    # application service layer once implemented. This assertion documents
    # that a typical reference URI round-trips unchanged and is not parsed,
    # hashed, or otherwise mistaken for a raw secret value.
    assert fetched.encrypted_secret_reference == "vault://secrets/data/github-token"
    assert "=" not in fetched.encrypted_secret_reference
