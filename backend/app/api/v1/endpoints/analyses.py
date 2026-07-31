"""Analysis run initiation endpoints with pipeline execution scheduling."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_settings_dep
from app.api.deps.access import require_org_reader, require_org_writer
from app.application.services.analysis_artifacts_service import AnalysisArtifactsService
from app.application.services.analysis_execution_service import AnalysisExecutionService
from app.application.services.analysis_run_service import AnalysisRunService
from app.application.services.analysis_task import schedule_analysis_execution
from app.core.config import Settings
from app.infrastructure.storage import build_file_storage
from app.schemas.analysis import (
    AnalysisAcceptedResponse,
    AnalysisRunDetailResponse,
    AnalysisRunListItem,
    AnalysisStatusResponse,
    ArtifactBundleResponse,
    EvidenceListResponse,
    ReanalyseRequest,
    RecommendationListResponse,
    RetrievedSourceListResponse,
    StartAnalysisRequest,
)

router = APIRouter(tags=["Analysis Runs"])


def _service(session: AsyncSession = Depends(get_session)) -> AnalysisRunService:
    return AnalysisRunService(session)


async def _schedule(
    *,
    analysis_run_id: UUID,
    settings: Settings,
    session: AsyncSession,
    background_tasks: BackgroundTasks,
) -> None:
    if settings.analysis_execution_mode == "sync":
        storage = build_file_storage(settings)
        executor = AnalysisExecutionService(
            session=session,
            settings=settings,
            storage=storage,
        )
        await executor.execute(analysis_run_id)
        return
    # BackgroundTasks run after the response is prepared but may execute before
    # the request-scoped session dependency commits. Persist the queued run first
    # so the worker session can load it.
    await session.commit()
    schedule_analysis_execution(
        analysis_run_id,
        settings=settings,
        background_tasks=background_tasks,
    )


@router.post(
    "/incidents/{incident_id}/analyses",
    response_model=AnalysisAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_analysis(
    incident_id: UUID,
    body: StartAnalysisRequest,
    background_tasks: BackgroundTasks,
    ctx: tuple = Depends(require_org_writer),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> AnalysisAcceptedResponse:
    user, organization_id, _ = ctx
    service = AnalysisRunService(session)
    accepted = await service.start_analysis(
        organization_id=organization_id,
        incident_id=incident_id,
        requested_by=user.id,
        body=body,
    )
    await _schedule(
        analysis_run_id=accepted.analysis_run_id,
        settings=settings,
        session=session,
        background_tasks=background_tasks,
    )
    # Refresh status after sync execution so 202 payload reflects completion when sync.
    if settings.analysis_execution_mode == "sync":
        detail = await service.get_detail(
            organization_id=organization_id,
            analysis_run_id=accepted.analysis_run_id,
        )
        return AnalysisAcceptedResponse(
            analysis_run_id=accepted.analysis_run_id,
            incident_id=accepted.incident_id,
            status=detail.status,
            progress_percentage=detail.progress_percentage,
            created_at=accepted.created_at,
        )
    return accepted


@router.post(
    "/incidents/{incident_id}/reanalyse",
    response_model=AnalysisAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reanalyse_incident(
    incident_id: UUID,
    body: ReanalyseRequest,
    background_tasks: BackgroundTasks,
    ctx: tuple = Depends(require_org_writer),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> AnalysisAcceptedResponse:
    user, organization_id, _ = ctx
    service = AnalysisRunService(session)
    accepted = await service.reanalyse(
        organization_id=organization_id,
        incident_id=incident_id,
        requested_by=user.id,
        body=body,
    )
    await _schedule(
        analysis_run_id=accepted.analysis_run_id,
        settings=settings,
        session=session,
        background_tasks=background_tasks,
    )
    if settings.analysis_execution_mode == "sync":
        detail = await service.get_detail(
            organization_id=organization_id,
            analysis_run_id=accepted.analysis_run_id,
        )
        return AnalysisAcceptedResponse(
            analysis_run_id=accepted.analysis_run_id,
            incident_id=accepted.incident_id,
            status=detail.status,
            progress_percentage=detail.progress_percentage,
            created_at=accepted.created_at,
        )
    return accepted


def _artifacts(session: AsyncSession = Depends(get_session)) -> AnalysisArtifactsService:
    return AnalysisArtifactsService(AnalysisRunService(session))


@router.get("/analyses/{analysis_run_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: AnalysisRunService = Depends(_service),
) -> AnalysisStatusResponse:
    _, organization_id, _ = ctx
    return await service.get_status(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get("/analyses/{analysis_run_id}", response_model=AnalysisRunDetailResponse)
async def get_analysis(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: AnalysisRunService = Depends(_service),
) -> AnalysisRunDetailResponse:
    _, organization_id, _ = ctx
    return await service.get_detail(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/evidence",
    response_model=EvidenceListResponse,
)
async def list_analysis_evidence(
    analysis_run_id: UUID,
    page: int = 1,
    page_size: int = 50,
    ctx: tuple = Depends(require_org_reader),
    artifacts: AnalysisArtifactsService = Depends(_artifacts),
) -> EvidenceListResponse:
    _, organization_id, _ = ctx
    return await artifacts.list_evidence(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/analyses/{analysis_run_id}/sources",
    response_model=RetrievedSourceListResponse,
)
async def list_analysis_sources(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    artifacts: AnalysisArtifactsService = Depends(_artifacts),
) -> RetrievedSourceListResponse:
    _, organization_id, _ = ctx
    return await artifacts.list_sources(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/recommendations",
    response_model=RecommendationListResponse,
)
async def list_analysis_recommendations(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    artifacts: AnalysisArtifactsService = Depends(_artifacts),
) -> RecommendationListResponse:
    _, organization_id, _ = ctx
    return await artifacts.list_recommendations(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/artifact-bundle",
    response_model=ArtifactBundleResponse,
)
async def get_analysis_artifact_bundle(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    artifacts: AnalysisArtifactsService = Depends(_artifacts),
) -> ArtifactBundleResponse:
    """Debug/validation endpoint for Phase 6A.1 artifact availability."""
    _, organization_id, _ = ctx
    return await artifacts.get_artifact_bundle(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.post("/analyses/{analysis_run_id}/cancel", response_model=AnalysisRunDetailResponse)
async def cancel_analysis(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_writer),
    service: AnalysisRunService = Depends(_service),
) -> AnalysisRunDetailResponse:
    user, organization_id, _ = ctx
    return await service.cancel(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        actor_id=user.id,
    )


@router.get(
    "/incidents/{incident_id}/analyses",
    response_model=list[AnalysisRunListItem],
)
async def list_incident_analyses(
    incident_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: AnalysisRunService = Depends(_service),
) -> list[AnalysisRunListItem]:
    _, organization_id, _ = ctx
    return await service.list_for_incident(
        organization_id=organization_id,
        incident_id=incident_id,
    )
