"""Build, parse, and persist IncidentArtifactBundle records (Phase 6A.1)."""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.artifacts.parsers.registry import ParserRegistry, build_default_parser_registry
from app.ai.artifacts.upload_classifier import classify_upload
from app.core.config import Settings
from app.domain.artifacts.enums import (
    AcquisitionStatus,
    ArtifactKind,
    ArtifactSource,
    RedactionStatus,
)
from app.domain.artifacts.models import (
    AcquisitionError,
    ArtifactRecord,
    IncidentArtifactBundle,
    StructuredParseResult,
    content_sha256,
)
from app.domain.enums import SecretMaskingStatus
from app.domain.services.secret_masker import mask_secrets
from app.infrastructure.database.models.analysis_artifact_bundle import (
    AnalysisArtifact,
    AnalysisArtifactBundle,
    ArtifactParseResult,
)
from app.infrastructure.database.models.uploaded_file import UploadedFile

logger = structlog.get_logger(__name__)


def _dataclass_to_dict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _dataclass_to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, list):
        return [_dataclass_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    if hasattr(obj, "value"):
        try:
            return obj.value
        except Exception:  # noqa: BLE001
            return str(obj)
    return obj


class ArtifactBundleService:
    """Constructs artifact bundles from uploads and persists parse results."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        registry: ParserRegistry | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._registry = registry or build_default_parser_registry()

    def enabled(self) -> bool:
        return bool(self._settings.artifact_bundle_enabled)

    def parsing_enabled(self) -> bool:
        return bool(self._settings.artifact_parsing_enabled)

    async def build_from_uploaded_files(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        project_id: UUID | None,
        pipeline_run_id: UUID | None,
        analysis_run_id: UUID | None,
        files: list[UploadedFile],
        file_contents: dict[UUID, str],
        context: dict[str, Any] | None = None,
    ) -> IncidentArtifactBundle:
        ctx = context or {}
        artifacts: list[ArtifactRecord] = []
        errors: list[AcquisitionError] = []
        available: list[str] = []
        missing: list[str] = []
        redaction = {"masked_files": 0, "failed_files": 0}

        for uploaded in files:
            content = file_contents.get(uploaded.id, "")
            if len(content) > self._settings.artifact_max_content_chars:
                content = content[: self._settings.artifact_max_content_chars]
                errors.append(
                    AcquisitionError(
                        artifact_kind=ArtifactKind.OTHER,
                        code="content_truncated",
                        message=f"Truncated {uploaded.original_filename} to max chars",
                    )
                )
            kind = classify_upload(
                filename=uploaded.original_filename,
                file_type=uploaded.file_type,
                content=content,
            )
            redaction_status = RedactionStatus.MASKED
            if uploaded.secret_masking_status == SecretMaskingStatus.FAILED:
                redaction_status = RedactionStatus.FAILED
                redaction["failed_files"] += 1
            elif uploaded.secret_masking_status == SecretMaskingStatus.MASKED:
                redaction["masked_files"] += 1
            elif uploaded.secret_masking_status == SecretMaskingStatus.NOT_REQUIRED:
                redaction_status = RedactionStatus.NOT_REQUIRED

            record = ArtifactRecord(
                id=str(uuid.uuid4()),
                kind=kind,
                source=ArtifactSource.UPLOAD,
                filename=uploaded.original_filename,
                content_hash=content_sha256(content) if content else (uploaded.sha256 or ""),
                content=content or None,
                acquisition_status=AcquisitionStatus.COLLECTED,
                redaction_status=redaction_status,
                uploaded_file_id=str(uploaded.id),
                metadata={"file_type": uploaded.file_type.value},
            )
            artifacts.append(record)
            available.append(kind.value)

        expected = {
            ArtifactKind.EXECUTION_LOG,
            ArtifactKind.WORKFLOW_YAML,
            ArtifactKind.TERRAFORM_FILE,
        }
        present = {a.kind for a in artifacts}
        for kind in expected - present:
            missing.append(kind.value)

        quality = {
            "artifact_count": len(artifacts),
            "available_kinds": len(set(available)),
            "missing_kinds": len(missing),
        }
        return IncidentArtifactBundle(
            incident_id=str(incident_id),
            organization_id=str(organization_id),
            project_id=str(project_id) if project_id else None,
            pipeline_run_id=str(pipeline_run_id) if pipeline_run_id else None,
            analysis_run_id=str(analysis_run_id) if analysis_run_id else None,
            provider=ctx.get("provider"),
            repository=ctx.get("repository"),
            commit_sha=ctx.get("commit_sha"),
            branch=ctx.get("branch"),
            workflow_name=ctx.get("workflow_name"),
            workflow_run_id=str(ctx["workflow_run_id"]) if ctx.get("workflow_run_id") else None,
            workflow_run_attempt=ctx.get("workflow_run_attempt"),
            failed_job=ctx.get("failed_job"),
            failed_step=ctx.get("failed_step"),
            artifacts=artifacts,
            available_artifacts=sorted(set(available)),
            missing_artifacts=sorted(set(missing)),
            artifact_collection_errors=errors,
            artifact_quality_scores=quality,
            redaction_summary=redaction,
        )

    def parse_bundle(
        self,
        bundle: IncidentArtifactBundle,
    ) -> dict[str, list[StructuredParseResult]]:
        results: dict[str, list[StructuredParseResult]] = {}
        if not self.parsing_enabled():
            return results
        for artifact in bundle.artifacts:
            if not artifact.content or artifact.acquisition_status != AcquisitionStatus.COLLECTED:
                continue
            parsed = self._registry.parse_all(
                artifact.content,
                filename=artifact.filename,
                kind=artifact.kind,
            )
            results[artifact.id] = parsed
            if parsed:
                artifact.parser_version = parsed[0].parser_version
        return results

    async def persist_bundle(
        self,
        bundle: IncidentArtifactBundle,
        parse_results: dict[str, list[StructuredParseResult]] | None = None,
    ) -> AnalysisArtifactBundle:
        row = AnalysisArtifactBundle(
            organization_id=UUID(bundle.organization_id),
            incident_id=UUID(bundle.incident_id),
            project_id=UUID(bundle.project_id) if bundle.project_id else None,
            pipeline_run_id=UUID(bundle.pipeline_run_id) if bundle.pipeline_run_id else None,
            analysis_run_id=UUID(bundle.analysis_run_id) if bundle.analysis_run_id else None,
            provider=bundle.provider,
            repository=bundle.repository,
            commit_sha=bundle.commit_sha,
            branch=bundle.branch,
            workflow_name=bundle.workflow_name,
            workflow_run_id=bundle.workflow_run_id,
            available_artifacts=list(bundle.available_artifacts),
            missing_artifacts=list(bundle.missing_artifacts),
            collection_errors=[_dataclass_to_dict(e) for e in bundle.artifact_collection_errors],
            quality_scores=dict(bundle.artifact_quality_scores),
            redaction_summary=dict(bundle.redaction_summary),
            bundle_snapshot=_dataclass_to_dict(
                dataclasses.replace(
                    bundle,
                    artifacts=[dataclasses.replace(a, content=None) for a in bundle.artifacts],
                )
            ),
        )
        self._session.add(row)
        await self._session.flush()

        parse_results = parse_results or {}
        for artifact in bundle.artifacts:
            art_row = AnalysisArtifact(
                id=UUID(artifact.id),
                organization_id=UUID(bundle.organization_id),
                bundle_id=row.id,
                uploaded_file_id=(
                    UUID(artifact.uploaded_file_id) if artifact.uploaded_file_id else None
                ),
                artifact_kind=artifact.kind.value,
                source=artifact.source.value,
                filename=artifact.filename,
                content_hash=artifact.content_hash,
                acquisition_status=artifact.acquisition_status.value,
                redaction_status=artifact.redaction_status.value,
                source_uri=artifact.source_uri,
                parser_version=artifact.parser_version,
                artifact_metadata=dict(artifact.metadata),
            )
            self._session.add(art_row)
            await self._session.flush()
            for parsed in parse_results.get(artifact.id, []):
                self._session.add(
                    ArtifactParseResult(
                        organization_id=UUID(bundle.organization_id),
                        artifact_id=art_row.id,
                        parser_name=parsed.parser_name,
                        parser_version=parsed.parser_version,
                        status=parsed.status.value,
                        entities=[_dataclass_to_dict(e) for e in parsed.entities],
                        relationships=[_dataclass_to_dict(r) for r in parsed.relationships],
                        diagnostics=[_dataclass_to_dict(d) for d in parsed.diagnostics],
                        evidence_candidates=[
                            _dataclass_to_dict(e) for e in parsed.evidence_candidates
                        ],
                        warnings=list(parsed.warnings),
                        errors=list(parsed.errors),
                        extraction_quality=parsed.extraction_quality,
                        raw_summary=dict(parsed.raw_summary),
                    )
                )
        await self._session.flush()
        logger.info(
            "artifact_bundle_persisted",
            bundle_id=str(row.id),
            incident_id=bundle.incident_id,
            artifact_count=len(bundle.artifacts),
        )
        return row

    async def get_latest_for_incident(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
    ) -> AnalysisArtifactBundle | None:
        result = await self._session.execute(
            select(AnalysisArtifactBundle)
            .where(
                AnalysisArtifactBundle.organization_id == organization_id,
                AnalysisArtifactBundle.incident_id == incident_id,
            )
            .options(selectinload(AnalysisArtifactBundle.artifacts))
            .order_by(AnalysisArtifactBundle.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


def mask_artifact_text(text: str) -> tuple[str, RedactionStatus]:
    """Apply secret masking; never persist unmasked secrets."""
    try:
        masked, _count = mask_secrets(text)
        return masked, RedactionStatus.MASKED
    except Exception:  # noqa: BLE001
        return text, RedactionStatus.FAILED
