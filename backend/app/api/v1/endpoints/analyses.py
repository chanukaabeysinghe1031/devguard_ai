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
from app.application.services.phase6a2_service import Phase6A2ArtifactsService
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
from app.schemas.phase6a2 import (
    EvidenceGraphEdgeListResponse,
    EvidenceGraphNodeListResponse,
    EvidenceGraphSummaryResponse,
    GraphConsistencyResponse,
    TemporalEventListResponse,
    TemporalLocalisationResponse,
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


def _phase6a2(session: AsyncSession = Depends(get_session)) -> Phase6A2ArtifactsService:
    return Phase6A2ArtifactsService(AnalysisRunService(session))


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


@router.get(
    "/analyses/{analysis_run_id}/temporal-localisation",
    response_model=TemporalLocalisationResponse,
)
async def get_temporal_localisation(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A2ArtifactsService = Depends(_phase6a2),
) -> TemporalLocalisationResponse:
    _, organization_id, _ = ctx
    return await service.get_temporal_localisation(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/temporal-events",
    response_model=TemporalEventListResponse,
)
async def list_temporal_events(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A2ArtifactsService = Depends(_phase6a2),
    page: int = 1,
    page_size: int = 100,
    event_type: str | None = None,
) -> TemporalEventListResponse:
    _, organization_id, _ = ctx
    return await service.list_temporal_events(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        page=page,
        page_size=page_size,
        event_type=event_type,
    )


@router.get(
    "/analyses/{analysis_run_id}/evidence-graph",
    response_model=EvidenceGraphSummaryResponse,
)
async def get_evidence_graph(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A2ArtifactsService = Depends(_phase6a2),
) -> EvidenceGraphSummaryResponse:
    _, organization_id, _ = ctx
    return await service.get_evidence_graph(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/evidence-graph/nodes",
    response_model=EvidenceGraphNodeListResponse,
)
async def list_evidence_graph_nodes(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A2ArtifactsService = Depends(_phase6a2),
    page: int = 1,
    page_size: int = 100,
    node_type: str | None = None,
    artifact_id: UUID | None = None,
    source_path: str | None = None,
) -> EvidenceGraphNodeListResponse:
    _, organization_id, _ = ctx
    return await service.list_graph_nodes(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        page=page,
        page_size=page_size,
        node_type=node_type,
        artifact_id=artifact_id,
        source_path=source_path,
    )


@router.get(
    "/analyses/{analysis_run_id}/evidence-graph/edges",
    response_model=EvidenceGraphEdgeListResponse,
)
async def list_evidence_graph_edges(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A2ArtifactsService = Depends(_phase6a2),
    page: int = 1,
    page_size: int = 100,
    edge_type: str | None = None,
    derivation_type: str | None = None,
) -> EvidenceGraphEdgeListResponse:
    _, organization_id, _ = ctx
    return await service.list_graph_edges(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        page=page,
        page_size=page_size,
        edge_type=edge_type,
        derivation_type=derivation_type,
    )


@router.get(
    "/analyses/{analysis_run_id}/graph-consistency",
    response_model=GraphConsistencyResponse,
)
async def get_graph_consistency(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A2ArtifactsService = Depends(_phase6a2),
) -> GraphConsistencyResponse:
    _, organization_id, _ = ctx
    return await service.get_graph_consistency(
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
