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
from app.application.services.phase6a3_service import Phase6A3ClassificationService
from app.application.services.phase6a4_service import Phase6A4HypothesisService
from app.application.services.phase6a5_service import Phase6A5HypothesisRetrievalService
from app.application.services.phase6a6_service import Phase6A6CounterfactualService
from app.application.services.phase6a7_service import Phase6A7FinalDiagnosisService
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
from app.schemas.phase6a3 import (
    ClassificationCandidateListResponse,
    ClassificationConfidenceResponse,
    ClassificationDisagreementResponse,
    FailureTaxonomyResponse,
    HierarchicalClassificationResponse,
    OpenSetAssessmentResponse,
)
from app.schemas.phase6a4 import (
    CausalHypothesisDetailResponse,
    CausalHypothesisListResponse,
    CausalHypothesisRunResponse,
    HypothesisCausalPathResponse,
    HypothesisCriticResponse,
    HypothesisEvidenceListResponse,
)
from app.schemas.phase6a5 import (
    EvidenceAssessmentPayloadResponse,
    HypothesisRetrievalContextResponse,
    HypothesisRetrievalIntelligenceListResponse,
    HypothesisRetrievalPlanResponse,
    HypothesisRetrievalQueryListResponse,
    HypothesisRetrievalRunResponse,
    HypothesisRetrievalSessionDetailResponse,
    HypothesisRetrievalSessionListResponse,
    HypothesisRetrievedItemListResponse,
)
from app.schemas.phase6a6 import (
    CounterfactualChangeListResponse,
    CounterfactualConstraintValidationResponse,
    CounterfactualPatchResponse,
    CounterfactualPrioritisationResponse,
    CounterfactualRemediationCandidateDetailResponse,
    CounterfactualRemediationCandidateListResponse,
    CounterfactualRemediationRunResponse,
    CounterfactualRiskResponse,
    CounterfactualRollbackResponse,
    CounterfactualSideEffectsResponse,
    CounterfactualStateSnapshotResponse,
    RemediationConstraintListResponse,
    RemediationPreconditionListResponse,
    RemediationVerificationRequirementListResponse,
    VerificationConsensusResponse,
    VerificationResultListResponse,
    VerificationRunDetailResponse,
    VerificationRunListResponse,
    VerifierLogsResponse,
)
from app.schemas.phase6a7 import (
    AbstentionDecisionResponse,
    FinalConfidenceResponse,
    FinalDiagnosisResponse,
    FinalExplanationResponse,
    FinalVerifierSummaryResponse,
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


def _phase6a3(session: AsyncSession = Depends(get_session)) -> Phase6A3ClassificationService:
    return Phase6A3ClassificationService(AnalysisRunService(session))


def _phase6a4(session: AsyncSession = Depends(get_session)) -> Phase6A4HypothesisService:
    return Phase6A4HypothesisService(AnalysisRunService(session))


def _phase6a5(session: AsyncSession = Depends(get_session)) -> Phase6A5HypothesisRetrievalService:
    return Phase6A5HypothesisRetrievalService(AnalysisRunService(session))


def _phase6a6(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> Phase6A6CounterfactualService:
    return Phase6A6CounterfactualService(AnalysisRunService(session), settings)


def _phase6a7(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> Phase6A7FinalDiagnosisService:
    return Phase6A7FinalDiagnosisService(session, settings)


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


@router.get(
    "/analyses/{analysis_run_id}/hierarchical-classification",
    response_model=HierarchicalClassificationResponse,
)
async def get_hierarchical_classification(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A3ClassificationService = Depends(_phase6a3),
) -> HierarchicalClassificationResponse:
    """Debug endpoint for Phase 6A.3 hierarchical classification."""
    _, organization_id, _ = ctx
    return await service.get_hierarchical_classification(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/classification-candidates",
    response_model=ClassificationCandidateListResponse,
)
async def list_classification_candidates(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A3ClassificationService = Depends(_phase6a3),
    source_classifier: str | None = None,
    level_1: str | None = None,
    level_2: str | None = None,
    level_3: str | None = None,
) -> ClassificationCandidateListResponse:
    _, organization_id, _ = ctx
    return await service.list_classification_candidates(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        source_classifier=source_classifier,
        level_1=level_1,
        level_2=level_2,
        level_3=level_3,
    )


@router.get(
    "/analyses/{analysis_run_id}/open-set-assessment",
    response_model=OpenSetAssessmentResponse,
)
async def get_open_set_assessment(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A3ClassificationService = Depends(_phase6a3),
) -> OpenSetAssessmentResponse:
    _, organization_id, _ = ctx
    return await service.get_open_set_assessment(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/classification-disagreement",
    response_model=ClassificationDisagreementResponse,
)
async def get_classification_disagreement(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A3ClassificationService = Depends(_phase6a3),
) -> ClassificationDisagreementResponse:
    _, organization_id, _ = ctx
    return await service.get_classification_disagreement(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/classification-confidence",
    response_model=ClassificationConfidenceResponse,
)
async def get_classification_confidence(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A3ClassificationService = Depends(_phase6a3),
) -> ClassificationConfidenceResponse:
    _, organization_id, _ = ctx
    return await service.get_classification_confidence(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get("/failure-taxonomy", response_model=FailureTaxonomyResponse)
async def get_failure_taxonomy(
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A3ClassificationService = Depends(_phase6a3),
    level_1: str | None = None,
    level_2: str | None = None,
    level_3: str | None = None,
) -> FailureTaxonomyResponse:
    """Organization-scoped read of the frozen-category hierarchy mapping."""
    _ = ctx  # auth/org gate only — taxonomy is global and non-secret
    return service.get_failure_taxonomy(
        level_1=level_1,
        level_2=level_2,
        level_3=level_3,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-generation-run",
    response_model=CausalHypothesisRunResponse,
)
async def get_hypothesis_generation_run(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A4HypothesisService = Depends(_phase6a4),
) -> CausalHypothesisRunResponse:
    _, organization_id, _ = ctx
    return await service.get_run(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/causal-hypotheses",
    response_model=CausalHypothesisListResponse,
)
async def list_causal_hypotheses(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A4HypothesisService = Depends(_phase6a4),
    category: str | None = None,
    status: str | None = None,
    generator_type: str | None = None,
    affected_artifact: str | None = None,
) -> CausalHypothesisListResponse:
    """Experimental competing hypotheses — not verified root causes."""
    _, organization_id, _ = ctx
    return await service.list_hypotheses(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        category=category,
        status=status,
        generator_type=generator_type,
        affected_artifact=affected_artifact,
    )


@router.get(
    "/analyses/{analysis_run_id}/causal-hypotheses/{hypothesis_id}",
    response_model=CausalHypothesisDetailResponse,
)
async def get_causal_hypothesis(
    analysis_run_id: UUID,
    hypothesis_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A4HypothesisService = Depends(_phase6a4),
) -> CausalHypothesisDetailResponse:
    _, organization_id, _ = ctx
    return await service.get_hypothesis(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        hypothesis_id=hypothesis_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/causal-hypotheses/{hypothesis_id}/evidence",
    response_model=HypothesisEvidenceListResponse,
)
async def list_hypothesis_evidence(
    analysis_run_id: UUID,
    hypothesis_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A4HypothesisService = Depends(_phase6a4),
) -> HypothesisEvidenceListResponse:
    _, organization_id, _ = ctx
    return await service.list_evidence(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        hypothesis_id=hypothesis_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/causal-hypotheses/{hypothesis_id}/causal-path",
    response_model=HypothesisCausalPathResponse,
)
async def get_hypothesis_causal_path(
    analysis_run_id: UUID,
    hypothesis_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A4HypothesisService = Depends(_phase6a4),
) -> HypothesisCausalPathResponse:
    _, organization_id, _ = ctx
    return await service.get_causal_path(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        hypothesis_id=hypothesis_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/causal-hypotheses/{hypothesis_id}/critic",
    response_model=HypothesisCriticResponse,
)
async def get_hypothesis_critic(
    analysis_run_id: UUID,
    hypothesis_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A4HypothesisService = Depends(_phase6a4),
) -> HypothesisCriticResponse:
    _, organization_id, _ = ctx
    return await service.get_critic(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        hypothesis_id=hypothesis_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-retrieval-run",
    response_model=HypothesisRetrievalRunResponse,
)
async def get_hypothesis_retrieval_run(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> HypothesisRetrievalRunResponse:
    """Experimental hypothesis-directed retrieval run — evidence candidates only."""
    _, organization_id, _ = ctx
    return await service.get_run(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-retrieval-sessions",
    response_model=HypothesisRetrievalSessionListResponse,
)
async def list_hypothesis_retrieval_sessions(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
    status: str | None = None,
) -> HypothesisRetrievalSessionListResponse:
    _, organization_id, _ = ctx
    return await service.list_sessions(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        status=status,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-retrieval-sessions/{session_id}",
    response_model=HypothesisRetrievalSessionDetailResponse,
)
async def get_hypothesis_retrieval_session(
    analysis_run_id: UUID,
    session_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> HypothesisRetrievalSessionDetailResponse:
    _, organization_id, _ = ctx
    return await service.get_session(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        session_id=session_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-retrieval-sessions/{session_id}/context",
    response_model=HypothesisRetrievalContextResponse,
)
async def get_hypothesis_retrieval_context(
    analysis_run_id: UUID,
    session_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> HypothesisRetrievalContextResponse:
    _, organization_id, _ = ctx
    return await service.get_context(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        session_id=session_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-retrieval-sessions/{session_id}/plan",
    response_model=HypothesisRetrievalPlanResponse,
)
async def get_hypothesis_retrieval_plan(
    analysis_run_id: UUID,
    session_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> HypothesisRetrievalPlanResponse:
    _, organization_id, _ = ctx
    return await service.get_plan(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        session_id=session_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-retrieval-sessions/{session_id}/queries",
    response_model=HypothesisRetrievalQueryListResponse,
)
async def list_hypothesis_retrieval_queries(
    analysis_run_id: UUID,
    session_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
    query_type: str | None = None,
) -> HypothesisRetrievalQueryListResponse:
    _, organization_id, _ = ctx
    return await service.list_queries(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        session_id=session_id,
        query_type=query_type,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-retrieval-sessions/{session_id}/items",
    response_model=HypothesisRetrievedItemListResponse,
)
async def list_hypothesis_retrieval_items(
    analysis_run_id: UUID,
    session_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
    page: int = 1,
    page_size: int = 50,
    source_type: str | None = None,
    adapter_name: str | None = None,
    artifact_id: str | None = None,
    graph_node_id: str | None = None,
    historical_incident_id: str | None = None,
    min_retrieval_score: float | None = None,
) -> HypothesisRetrievedItemListResponse:
    """Retrieved items are evidence candidates — not proven support/contradiction."""
    _, organization_id, _ = ctx
    return await service.list_items(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        session_id=session_id,
        page=page,
        page_size=page_size,
        source_type=source_type,
        adapter_name=adapter_name,
        artifact_id=artifact_id,
        graph_node_id=graph_node_id,
        historical_incident_id=historical_incident_id,
        min_retrieval_score=min_retrieval_score,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-retrieval-sessions/{session_id}/intents",
    response_model=HypothesisRetrievalIntelligenceListResponse,
)
async def get_hypothesis_retrieval_intents(
    analysis_run_id: UUID,
    session_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> HypothesisRetrievalIntelligenceListResponse:
    _, organization_id, _ = ctx
    return await service.get_intents(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        session_id=session_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-retrieval-sessions/{session_id}/source-routing",
    response_model=HypothesisRetrievalIntelligenceListResponse,
)
async def get_hypothesis_retrieval_source_routing(
    analysis_run_id: UUID,
    session_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> HypothesisRetrievalIntelligenceListResponse:
    _, organization_id, _ = ctx
    return await service.get_source_routing(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        session_id=session_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-retrieval-sessions/{session_id}/validation-results",
    response_model=HypothesisRetrievalIntelligenceListResponse,
)
async def get_hypothesis_retrieval_validation_results(
    analysis_run_id: UUID,
    session_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> HypothesisRetrievalIntelligenceListResponse:
    _, organization_id, _ = ctx
    return await service.get_validation_results(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        session_id=session_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-retrieval-sessions/{session_id}/follow-ups",
    response_model=HypothesisRetrievalIntelligenceListResponse,
)
async def get_hypothesis_retrieval_follow_ups(
    analysis_run_id: UUID,
    session_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> HypothesisRetrievalIntelligenceListResponse:
    _, organization_id, _ = ctx
    return await service.get_follow_ups(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        session_id=session_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/evidence-assessment",
    response_model=EvidenceAssessmentPayloadResponse,
)
async def get_evidence_assessment(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> EvidenceAssessmentPayloadResponse:
    """Part 3 evidence assessment snapshot — candidates only, not proven causes."""
    _, organization_id, _ = ctx
    return await service.get_evidence_assessment(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/hypothesis-ranking",
    response_model=EvidenceAssessmentPayloadResponse,
)
async def get_hypothesis_ranking(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> EvidenceAssessmentPayloadResponse:
    """RankingScore is not RootCauseConfidence; highest ranked ≠ verified root cause."""
    _, organization_id, _ = ctx
    return await service.get_hypothesis_ranking(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/candidate-hypotheses",
    response_model=EvidenceAssessmentPayloadResponse,
)
async def get_candidate_hypotheses(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> EvidenceAssessmentPayloadResponse:
    """Selected candidate hypotheses only — not final diagnosis."""
    _, organization_id, _ = ctx
    return await service.get_candidate_hypotheses(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/support-analysis",
    response_model=EvidenceAssessmentPayloadResponse,
)
async def get_support_analysis(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> EvidenceAssessmentPayloadResponse:
    """Support candidates per hypothesis — not proven support."""
    _, organization_id, _ = ctx
    return await service.get_support_analysis(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/contradictions",
    response_model=EvidenceAssessmentPayloadResponse,
)
async def get_contradictions(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> EvidenceAssessmentPayloadResponse:
    """Contradiction candidates — not disproof or falsification."""
    _, organization_id, _ = ctx
    return await service.get_contradictions(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/evidence-sufficiency",
    response_model=EvidenceAssessmentPayloadResponse,
)
async def get_evidence_sufficiency(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A5HypothesisRetrievalService = Depends(_phase6a5),
) -> EvidenceAssessmentPayloadResponse:
    """Evidence sufficiency levels — insufficient does not disprove a hypothesis."""
    _, organization_id, _ = ctx
    return await service.get_evidence_sufficiency(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-run",
    response_model=CounterfactualRemediationRunResponse,
)
async def get_counterfactual_remediation_run(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualRemediationRunResponse:
    """Phase 6A.6 Part 1 foundation run — candidates only, unverified."""
    _, organization_id, _ = ctx
    return await service.get_run(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates",
    response_model=CounterfactualRemediationCandidateListResponse,
)
async def list_counterfactual_remediation_candidates(
    analysis_run_id: UUID,
    page: int = 1,
    page_size: int = 50,
    hypothesis: UUID | None = None,
    status: str | None = None,
    generator_type: str | None = None,
    artifact_type: str | None = None,
    risk_level: str | None = None,
    blast_radius: str | None = None,
    priority_status: str | None = None,
    template_id: str | None = None,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualRemediationCandidateListResponse:
    """List counterfactual remediation candidates (unverified; debug flag gated)."""
    _, organization_id, _ = ctx
    return await service.list_candidates(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        page=page,
        page_size=page_size,
        hypothesis_id=hypothesis,
        status=status,
        generator_type=generator_type,
        artifact_type=artifact_type,
        risk_level=risk_level,
        blast_radius=blast_radius,
        priority_status=priority_status,
        template_id=template_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}",
    response_model=CounterfactualRemediationCandidateDetailResponse,
)
async def get_counterfactual_remediation_candidate(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualRemediationCandidateDetailResponse:
    """Candidate detail — skeleton only; not verified or applied."""
    _, organization_id, _ = ctx
    return await service.get_candidate(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/current-state",
    response_model=CounterfactualStateSnapshotResponse,
)
async def get_counterfactual_candidate_current_state(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualStateSnapshotResponse:
    """Redacted current-state snapshot for a remediation candidate."""
    _, organization_id, _ = ctx
    return await service.get_current_state(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/counterfactual-state",
    response_model=CounterfactualStateSnapshotResponse,
)
async def get_counterfactual_candidate_counterfactual_state(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualStateSnapshotResponse:
    """Redacted counterfactual-state snapshot for a remediation candidate."""
    _, organization_id, _ = ctx
    return await service.get_counterfactual_state(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/constraints",
    response_model=RemediationConstraintListResponse,
)
async def list_counterfactual_candidate_constraints(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> RemediationConstraintListResponse:
    """Extracted remediation constraints for a candidate (debug)."""
    _, organization_id, _ = ctx
    return await service.list_constraints(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/preconditions",
    response_model=RemediationPreconditionListResponse,
)
async def list_counterfactual_candidate_preconditions(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> RemediationPreconditionListResponse:
    """Counterfactual preconditions for a candidate (debug)."""
    _, organization_id, _ = ctx
    return await service.list_preconditions(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/verification-requirements",
    response_model=RemediationVerificationRequirementListResponse,
)
async def list_counterfactual_candidate_verification_requirements(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> RemediationVerificationRequirementListResponse:
    """Reserved verification requirements — NOT_RUN in Part 1/2."""
    _, organization_id, _ = ctx
    return await service.list_verification_requirements(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/changes",
    response_model=CounterfactualChangeListResponse,
)
async def list_counterfactual_candidate_changes(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualChangeListResponse:
    """Structured changes for a candidate (fragment bodies redacted to hashes)."""
    _, organization_id, _ = ctx
    return await service.list_changes(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/patch",
    response_model=CounterfactualPatchResponse,
)
async def get_counterfactual_candidate_patch(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualPatchResponse:
    """Rendered patch if present — never returns secret values; not applied."""
    _, organization_id, _ = ctx
    return await service.get_patch(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/risk",
    response_model=CounterfactualRiskResponse,
)
async def get_counterfactual_candidate_risk(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualRiskResponse:
    """Static risk metadata for a candidate."""
    _, organization_id, _ = ctx
    return await service.get_risk(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/side-effects",
    response_model=CounterfactualSideEffectsResponse,
)
async def get_counterfactual_candidate_side_effects(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualSideEffectsResponse:
    """Heuristic side-effect predictions for a candidate."""
    _, organization_id, _ = ctx
    return await service.get_side_effects(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/rollback",
    response_model=CounterfactualRollbackResponse,
)
async def get_counterfactual_candidate_rollback(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualRollbackResponse:
    """Structured rollback plan (not executed)."""
    _, organization_id, _ = ctx
    return await service.get_rollback(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/constraint-validation",
    response_model=CounterfactualConstraintValidationResponse,
)
async def get_counterfactual_candidate_constraint_validation(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualConstraintValidationResponse:
    """Structural constraint validation status — not verifier execution."""
    _, organization_id, _ = ctx
    return await service.get_constraint_validation(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-prioritisation",
    response_model=CounterfactualPrioritisationResponse,
)
async def get_counterfactual_remediation_prioritisation(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> CounterfactualPrioritisationResponse:
    """Candidate prioritisation for later verification — not 'the fix'."""
    _, organization_id, _ = ctx
    return await service.get_prioritisation(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-verification-runs",
    response_model=VerificationRunListResponse,
)
async def list_counterfactual_verification_runs(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> VerificationRunListResponse:
    """Part 3 verification runs — temporary workspace outcomes only."""
    _, organization_id, _ = ctx
    return await service.list_verification_runs(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-verification-runs/{run_id}",
    response_model=VerificationRunDetailResponse,
)
async def get_counterfactual_verification_run(
    analysis_run_id: UUID,
    run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> VerificationRunDetailResponse:
    """Single verification run detail (no apply)."""
    _, organization_id, _ = ctx
    return await service.get_verification_run(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        run_id=run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-verification-results",
    response_model=VerificationResultListResponse,
)
async def list_counterfactual_verification_results(
    analysis_run_id: UUID,
    candidate_id: UUID | None = None,
    verifier: str | None = None,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> VerificationResultListResponse:
    """Per-verifier results; filter by candidate or verifier name."""
    _, organization_id, _ = ctx
    return await service.list_verification_results(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
        verifier_name=verifier,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/verification-consensus",
    response_model=VerificationConsensusResponse,
)
async def get_counterfactual_verification_consensus(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> VerificationConsensusResponse:
    """Deterministic consensus for a candidate — not proven root cause."""
    _, organization_id, _ = ctx
    return await service.get_verification_consensus(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/counterfactual-remediation-candidates/{candidate_id}/verifier-logs",
    response_model=VerifierLogsResponse,
)
async def get_counterfactual_verifier_logs(
    analysis_run_id: UUID,
    candidate_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A6CounterfactualService = Depends(_phase6a6),
) -> VerifierLogsResponse:
    """Truncated/redacted verifier stdout/stderr — no apply path."""
    _, organization_id, _ = ctx
    return await service.get_verifier_logs(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
        candidate_id=candidate_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/final-diagnosis",
    response_model=FinalDiagnosisResponse,
)
async def get_final_diagnosis(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A7FinalDiagnosisService = Depends(_phase6a7),
) -> FinalDiagnosisResponse:
    """Evidence-based final diagnosis — not applied remediation, not mathematical proof."""
    _, organization_id, _ = ctx
    return await service.get_final_diagnosis(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/final-confidence",
    response_model=FinalConfidenceResponse,
)
async def get_final_confidence(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A7FinalDiagnosisService = Depends(_phase6a7),
) -> FinalConfidenceResponse:
    """Heuristic confidence decomposition — not calibrated probability."""
    _, organization_id, _ = ctx
    return await service.get_final_confidence(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/abstention-decision",
    response_model=AbstentionDecisionResponse,
)
async def get_abstention_decision(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A7FinalDiagnosisService = Depends(_phase6a7),
) -> AbstentionDecisionResponse:
    """Abstention is intentional safe behavior when evidence/verifiers are insufficient."""
    _, organization_id, _ = ctx
    return await service.get_abstention_decision(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/final-explanation",
    response_model=FinalExplanationResponse,
)
async def get_final_explanation(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A7FinalDiagnosisService = Depends(_phase6a7),
) -> FinalExplanationResponse:
    """Structured explanation only — no prompts, secrets, or hidden reasoning."""
    _, organization_id, _ = ctx
    return await service.get_final_explanation(
        organization_id=organization_id,
        analysis_run_id=analysis_run_id,
    )


@router.get(
    "/analyses/{analysis_run_id}/final-verifier-summary",
    response_model=FinalVerifierSummaryResponse,
)
async def get_final_verifier_summary(
    analysis_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: Phase6A7FinalDiagnosisService = Depends(_phase6a7),
) -> FinalVerifierSummaryResponse:
    """Aggregated verifier support for the selected remediation candidate."""
    _, organization_id, _ = ctx
    return await service.get_final_verifier_summary(
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
