"""Phase 6A.1 artifact bundle, acquisition, classifier, and safety tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.ai.artifacts.github_acquisition import GitHubArtifactAcquisition
from app.ai.artifacts.upload_classifier import classify_upload
from app.ai.artifacts.verifier_status import VerifierState, probe_verifier_tools
from app.core.config import Settings
from app.domain.artifacts.enums import ArtifactKind
from app.domain.enums import FileType
from app.infrastructure.integrations.fake_github_provider import (
    FAKE_HEAD_SHA,
    FAKE_REPOSITORY_FULL_NAME,
    FakeGitHubProvider,
)


def test_upload_classifier_maps_common_types() -> None:
    assert (
        classify_upload(filename="fail.log", file_type=FileType.LOG, content="error")
        == ArtifactKind.EXECUTION_LOG
    )
    assert (
        classify_upload(filename="ci.yml", file_type=FileType.WORKFLOW_YAML, content="name: CI")
        == ArtifactKind.WORKFLOW_YAML
    )
    assert (
        classify_upload(
            filename="main.tf",
            file_type=FileType.TERRAFORM,
            content='resource "a" "b" {}',
        )
        == ArtifactKind.TERRAFORM_FILE
    )
    assert (
        classify_upload(
            filename="plan.json",
            file_type=FileType.JSON,
            content='{"format_version":"1.0","resource_changes":[]}',
        )
        == ArtifactKind.TERRAFORM_PLAN_JSON
    )
    assert (
        classify_upload(
            filename="policy.json",
            file_type=FileType.JSON,
            content='{"Statement":[{"Effect":"Allow","Action":"s3:*"}]}',
        )
        == ArtifactKind.IAM_POLICY_JSON
    )
    assert (
        classify_upload(
            filename="changed_files.json",
            file_type=FileType.JSON,
            content='{"changed_files":[{"filename":"a.py"}]}',
        )
        == ArtifactKind.CHANGED_FILES_METADATA
    )


def test_verifier_tools_never_fake_pass_when_disabled() -> None:
    statuses = probe_verifier_tools(enabled=False)
    assert statuses
    assert all(s.state == VerifierState.DISABLED for s in statuses)
    assert all(
        s.state != VerifierState.AVAILABLE or "PASS" not in (s.detail or "")
        for s in statuses
    )


def test_feature_flags_default_off() -> None:
    settings = Settings(
        PROJECT_NAME="DevGuard AI Test",
        APP_VERSION="1.0.0",
        ENVIRONMENT="development",
        DEBUG=False,
        DATABASE_URL="postgresql+asyncpg://devguard:change_me@localhost:5432/devguard_test",
    )
    assert settings.causal_analysis_enabled is False
    assert settings.artifact_bundle_enabled is False
    assert settings.artifact_parsing_enabled is False
    assert settings.github_artifact_acquisition_enabled is False


@pytest.mark.asyncio
async def test_github_acquisition_disabled_records_missing() -> None:
    settings = Settings(
        PROJECT_NAME="DevGuard AI Test",
        APP_VERSION="1.0.0",
        ENVIRONMENT="development",
        DEBUG=False,
        DATABASE_URL="postgresql+asyncpg://devguard:change_me@localhost:5432/devguard_test",
        GITHUB_ARTIFACT_ACQUISITION_ENABLED=False,
    )
    acquisition = GitHubArtifactAcquisition(FakeGitHubProvider(), settings)
    result = await acquisition.collect(
        installation_id=1,
        repository_full_name=FAKE_REPOSITORY_FULL_NAME,
        run={"id": 41, "head_sha": FAKE_HEAD_SHA, "name": "CI", "workflow_id": 1},
        failed_log_present=True,
    )
    assert result.errors
    assert result.errors[0].code == "disabled"
    assert ArtifactKind.WORKFLOW_YAML.value in result.missing


@pytest.mark.asyncio
async def test_github_acquisition_collects_extended_artifacts() -> None:
    settings = Settings(
        PROJECT_NAME="DevGuard AI Test",
        APP_VERSION="1.0.0",
        ENVIRONMENT="development",
        DEBUG=False,
        DATABASE_URL="postgresql+asyncpg://devguard:change_me@localhost:5432/devguard_test",
        GITHUB_ARTIFACT_ACQUISITION_ENABLED=True,
    )
    provider = FakeGitHubProvider()
    acquisition = GitHubArtifactAcquisition(provider, settings)
    result = await acquisition.collect(
        installation_id=1,
        repository_full_name=FAKE_REPOSITORY_FULL_NAME,
        run={
            "id": 41,
            "head_sha": FAKE_HEAD_SHA,
            "head_branch": "main",
            "name": "CI",
            "workflow_id": 1,
            "conclusion": "failure",
        },
        failed_log_present=True,
    )
    kinds = {a.kind for a in result.artifacts}
    assert ArtifactKind.WORKFLOW_YAML in kinds
    assert ArtifactKind.COMMIT_METADATA in kinds
    assert ArtifactKind.CHANGED_FILES_METADATA in kinds
    assert ArtifactKind.PREVIOUS_SUCCESS_LOG in kinds
    assert "workflow_run_metadata" in result.available
    assert provider.file_reads
    assert all(a.content is not None for a in result.artifacts)
    allowed = {"masked", "not_required", "failed"}
    assert all(a.redaction_status.value in allowed for a in result.artifacts)


@pytest.mark.asyncio
async def test_artifact_bundle_org_isolation(repository_db_session) -> None:
    """Bundles for org A must not be readable via org B queries."""
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.ai.artifacts.bundle_service import ArtifactBundleService
    from app.domain.artifacts.enums import (
        AcquisitionStatus,
        ArtifactKind,
        ArtifactSource,
        RedactionStatus,
    )
    from app.domain.artifacts.models import ArtifactRecord, IncidentArtifactBundle, content_sha256
    from app.domain.enums import CiProvider, IncidentSeverity, IncidentStatus, PlatformRole
    from app.infrastructure.database.models.analysis_artifact_bundle import AnalysisArtifactBundle
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.organization import Organization
    from app.infrastructure.database.models.project import Project
    from app.infrastructure.database.models.user import User

    org = Organization(name="Bundle Org", slug=f"bundle-{uuid4().hex[:8]}")
    user = User(
        email=f"bundle-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        full_name="Owner",
        platform_role=PlatformRole.NONE,
    )
    repository_db_session.add_all([org, user])
    await repository_db_session.flush()
    project = Project(
        organization_id=org.id,
        name="App",
        key="BND",
        ci_provider=CiProvider.GITHUB_ACTIONS,
        created_by=user.id,
    )
    repository_db_session.add(project)
    await repository_db_session.flush()
    incident = Incident(
        organization_id=org.id,
        project_id=project.id,
        title="Fail",
        source="manual",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.DETECTED,
        detected_at=datetime.now(UTC),
    )
    repository_db_session.add(incident)
    await repository_db_session.flush()

    settings = Settings(
        PROJECT_NAME="DevGuard AI Test",
        APP_VERSION="1.0.0",
        ENVIRONMENT="development",
        DEBUG=False,
        DATABASE_URL="postgresql+asyncpg://devguard:change_me@localhost:5432/devguard_test",
        ARTIFACT_BUNDLE_ENABLED=True,
        ARTIFACT_PARSING_ENABLED=False,
    )
    service = ArtifactBundleService(repository_db_session, settings)
    bundle = IncidentArtifactBundle(
        incident_id=str(incident.id),
        organization_id=str(org.id),
        artifacts=[
            ArtifactRecord(
                id=str(uuid4()),
                kind=ArtifactKind.EXECUTION_LOG,
                source=ArtifactSource.UPLOAD,
                filename="a.log",
                content_hash=content_sha256("fail"),
                content="fail",
                acquisition_status=AcquisitionStatus.COLLECTED,
                redaction_status=RedactionStatus.MASKED,
            )
        ],
        available_artifacts=[ArtifactKind.EXECUTION_LOG.value],
    )
    await service.persist_bundle(bundle)
    await repository_db_session.commit()

    other_org = uuid4()
    row = await repository_db_session.scalar(
        select(AnalysisArtifactBundle).where(
            AnalysisArtifactBundle.organization_id == other_org,
            AnalysisArtifactBundle.incident_id == incident.id,
        )
    )
    assert row is None
    own = await service.get_latest_for_incident(organization_id=org.id, incident_id=incident.id)
    assert own is not None
    assert own.organization_id == org.id
