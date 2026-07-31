"""Analysis run initiation service (contract only — no AI execution)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.mappers import analysis_detail, analysis_list_item
from app.domain.enums import AnalysisRunStatus, FileValidationStatus, IncidentStatus
from app.domain.exceptions.business import (
    ConflictError,
    ResourceNotFoundError,
    ValidationBusinessError,
)
from app.infrastructure.database.models.analysis_run import AnalysisRun
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_event import IncidentEvent
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.uploaded_file import UploadedFile
from app.schemas.analysis import (
    AnalysisAcceptedResponse,
    AnalysisRunDetailResponse,
    AnalysisRunListItem,
    AnalysisStageResponse,
    AnalysisStatusResponse,
    ReanalyseRequest,
    StartAnalysisRequest,
)

logger = structlog.get_logger(__name__)

_CANCELLABLE = frozenset(
    {
        AnalysisRunStatus.QUEUED,
        AnalysisRunStatus.PREPROCESSING,
    }
)


class AnalysisRunService:
    """Creates queued analysis_run records without executing the AI pipeline."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start_analysis(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        requested_by: UUID | None,
        body: StartAnalysisRequest,
        system_initiated: bool = False,
    ) -> AnalysisAcceptedResponse:
        """Queue an analysis run.

        Automated ingestion (ADR-005) sets ``system_initiated`` so the timeline
        records a system actor while ``requested_by`` still identifies the user
        accountable for the connection and receives completion notifications.
        """
        incident = await self._load_incident(organization_id, incident_id)
        if incident.status in (IncidentStatus.CLOSED, IncidentStatus.IGNORED):
            raise ValidationBusinessError("Cannot analyse a closed or ignored incident.")

        await self._validate_analysis_file_ids(
            incident_id=incident.id,
            file_ids=body.file_ids,
        )

        run = AnalysisRun(
            incident_id=incident.id,
            pipeline_run_id=incident.pipeline_run_id,
            requested_by=requested_by,
            status=AnalysisRunStatus.QUEUED,
            analysis_type=body.analysis_type,
            progress_percentage=0,
            current_stage="queued",
            input_summary={
                "file_ids": [str(fid) for fid in body.file_ids],
                "options": body.options.model_dump(),
            },
        )
        self._session.add(run)
        await self._session.flush()
        incident.latest_analysis_run_id = run.id
        await self._record_event(
            incident_id=incident.id,
            actor_id=None if system_initiated else requested_by,
            title="Analysis queued",
            description=(
                "Analysis run started automatically after CI failure ingestion."
                if system_initiated
                else "Analysis run accepted and queued."
            ),
            metadata={"analysis_run_id": str(run.id)},
        )
        await self._session.flush()
        logger.info("analysis_run_queued", analysis_run_id=str(run.id))
        return AnalysisAcceptedResponse(
            analysis_run_id=run.id,
            incident_id=incident.id,
            status=run.status.value,
            progress_percentage=run.progress_percentage,
            created_at=run.created_at or datetime.now(UTC),
        )

    async def reanalyse(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        requested_by: UUID | None,
        body: ReanalyseRequest,
    ) -> AnalysisAcceptedResponse:
        return await self.start_analysis(
            organization_id=organization_id,
            incident_id=incident_id,
            requested_by=requested_by,
            body=StartAnalysisRequest(
                analysis_type="full",
                file_ids=body.file_ids,
            ),
        )

    async def get_status(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> AnalysisStatusResponse:
        run = await self._load_run(organization_id, analysis_run_id)
        stages_raw = (run.output_summary or {}).get("stages") or []
        stages = [
            AnalysisStageResponse(
                name=str(item.get("name", "")),
                status=str(item.get("status", "completed")),
                duration_ms=item.get("duration_ms"),
            )
            for item in stages_raw
            if isinstance(item, dict)
        ]
        return AnalysisStatusResponse(
            id=run.id,
            incident_id=run.incident_id,
            status=run.status.value,
            current_stage=run.current_stage,
            progress_percentage=run.progress_percentage,
            started_at=run.started_at,
            estimated_remaining_seconds=None,
            stages=stages,
        )

    async def get_detail(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> AnalysisRunDetailResponse:
        run = await self._load_run(organization_id, analysis_run_id)
        return analysis_detail(run)

    async def cancel(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        actor_id: UUID,
    ) -> AnalysisRunDetailResponse:
        run = await self._load_run(organization_id, analysis_run_id)
        if run.status not in _CANCELLABLE:
            raise ConflictError(
                "Analysis cannot be cancelled in its current state.",
                error_code="ANALYSIS_NOT_CANCELLABLE",
            )
        run.status = AnalysisRunStatus.FAILED
        run.error_code = "CANCELLED"
        run.error_message = "Cancelled by user."
        run.completed_at = datetime.now(UTC)
        await self._session.flush()
        logger.info("analysis_run_cancelled", analysis_run_id=str(run.id))
        return analysis_detail(run)

    async def list_for_incident(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
    ) -> list[AnalysisRunListItem]:
        await self._load_incident(organization_id, incident_id)
        stmt = (
            select(AnalysisRun)
            .where(AnalysisRun.incident_id == incident_id)
            .order_by(AnalysisRun.created_at.desc())
        )
        runs = list((await self._session.scalars(stmt)).all())
        return [analysis_list_item(run) for run in runs]

    async def _validate_analysis_file_ids(
        self,
        *,
        incident_id: UUID,
        file_ids: list[UUID],
    ) -> None:
        if not file_ids:
            return
        unique_ids = list(dict.fromkeys(file_ids))
        stmt = select(UploadedFile).where(
            UploadedFile.id.in_(unique_ids),
            UploadedFile.incident_id == incident_id,
        )
        found = list((await self._session.scalars(stmt)).all())
        if len(found) != len(unique_ids):
            raise ValidationBusinessError(
                "One or more file_ids are invalid or do not belong to this incident.",
                error_code="INVALID_ANALYSIS_FILES",
            )
        for uploaded in found:
            if uploaded.validation_status != FileValidationStatus.VALID:
                raise ValidationBusinessError(
                    f"File '{uploaded.original_filename}' is not valid for analysis.",
                    error_code="INVALID_ANALYSIS_FILES",
                )

    async def _load_incident(self, organization_id: UUID, incident_id: UUID) -> Incident:
        stmt = (
            select(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(Incident.id == incident_id, Project.organization_id == organization_id)
        )
        incident = await self._session.scalar(stmt)
        if incident is None:
            raise ResourceNotFoundError("Incident not found.")
        return incident

    async def _load_run(self, organization_id: UUID, analysis_run_id: UUID) -> AnalysisRun:
        stmt = (
            select(AnalysisRun)
            .join(Incident, Incident.id == AnalysisRun.incident_id)
            .join(Project, Project.id == Incident.project_id)
            .where(AnalysisRun.id == analysis_run_id, Project.organization_id == organization_id)
        )
        run = await self._session.scalar(stmt)
        if run is None:
            raise ResourceNotFoundError("Analysis run not found.")
        return run

    async def _record_event(
        self,
        *,
        incident_id: UUID,
        actor_id: UUID | None,
        title: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        organization_id = await self._session.scalar(
            select(Incident.organization_id).where(Incident.id == incident_id)
        )
        if organization_id is None:
            return
        self._session.add(
            IncidentEvent(
                organization_id=organization_id,
                incident_id=incident_id,
                event_type="analysis_queued",
                actor_type="user" if actor_id is not None else "system",
                actor_user_id=actor_id,
                title=title,
                description=description,
                event_metadata=metadata,
                occurred_at=datetime.now(UTC),
            )
        )
