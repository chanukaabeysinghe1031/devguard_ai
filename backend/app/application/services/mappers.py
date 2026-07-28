"""Response mappers for business API schemas."""

from __future__ import annotations

from typing import Any

from app.domain.services.incident_transitions import format_incident_number
from app.infrastructure.database.models.analysis_run import AnalysisRun
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_note import IncidentNote
from app.infrastructure.database.models.incident_resolution import IncidentResolution
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.user import User
from app.schemas.analysis import (
    AnalysisOrchestrationSummary,
    AnalysisRunDetailResponse,
    AnalysisRunListItem,
)
from app.schemas.incident import (
    AssigneeSummary,
    IncidentDetailResponse,
    IncidentListItem,
    IncidentResponse,
    LatestAnalysisSummary,
    PipelineRunSummary,
    ProjectSummary,
    TimelineEventResponse,
)
from app.schemas.note import NoteResponse
from app.schemas.organization import MembershipResponse, OrganizationResponse
from app.schemas.pipeline_run import PipelineRunResponse
from app.schemas.project import (
    ProjectDetailResponse,
    ProjectListItem,
    ProjectResponse,
    ProjectStatistics,
)
from app.schemas.resolution import ResolutionSummary


def organization_to_response(org: Organization) -> OrganizationResponse:
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        plan=org.plan,
        status=org.status.value,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


def membership_to_response(member: OrganizationMember, user: User) -> MembershipResponse:
    return MembershipResponse(
        id=member.id,
        user_id=member.user_id,
        email=user.email,
        full_name=user.full_name,
        role=member.role.value,
        is_active=member.is_active,
        joined_at=member.joined_at,
    )


def project_to_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        key=project.key,
        description=project.description,
        repository_url=project.repository_url,
        default_branch=project.default_branch,
        ci_provider=project.ci_provider.value,
        cloud_provider=project.cloud_provider,
        default_environment=project.default_environment,
        status=project.status.value,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def project_list_item(
    project: Project,
    *,
    open_incident_count: int = 0,
    last_pipeline_run_at: Any = None,
) -> ProjectListItem:
    return ProjectListItem(
        id=project.id,
        name=project.name,
        key=project.key,
        ci_provider=project.ci_provider.value,
        cloud_provider=project.cloud_provider,
        status=project.status.value,
        open_incident_count=open_incident_count,
        last_pipeline_run_at=last_pipeline_run_at,
    )


def project_detail(
    project: Project,
    statistics: ProjectStatistics,
) -> ProjectDetailResponse:
    base = project_to_response(project)
    return ProjectDetailResponse(**base.model_dump(), statistics=statistics)


def pipeline_run_to_response(run: PipelineRun, *, incident_count: int = 0) -> PipelineRunResponse:
    return PipelineRunResponse(
        id=run.id,
        project_id=run.project_id,
        external_run_id=run.external_run_id,
        provider=run.provider.value,
        workflow_name=run.workflow_name,
        branch=run.branch,
        commit_sha=run.commit_sha,
        triggered_by=run.triggered_by,
        environment=run.environment,
        status=run.status.value,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_seconds,
        source_url=run.source_url,
        incident_count=incident_count,
        created_at=run.created_at,
    )


def incident_to_response(incident: Incident) -> IncidentResponse:
    tags = incident.tags if isinstance(incident.tags, list) else None
    return IncidentResponse(
        id=incident.id,
        incident_number=format_incident_number(incident.incident_number),
        project_id=incident.project_id,
        pipeline_run_id=incident.pipeline_run_id,
        title=incident.title,
        description=incident.description,
        source=incident.source,
        status=incident.status.value,
        severity=incident.severity.value,
        priority=incident.priority.value if incident.priority else None,
        environment=incident.environment,
        detected_at=incident.detected_at,
        acknowledged_at=incident.acknowledged_at,
        resolved_at=incident.resolved_at,
        closed_at=incident.closed_at,
        created_at=incident.created_at,
        tags=tags,
    )


def _assignee(user: User | None) -> AssigneeSummary | None:
    if user is None:
        return None
    return AssigneeSummary(id=user.id, email=user.email, full_name=user.full_name)


def incident_list_item(
    incident: Incident,
    *,
    predicted_category: str | None = None,
    ai_confidence: float | None = None,
) -> IncidentListItem:
    project = incident.project
    return IncidentListItem(
        id=incident.id,
        incident_number=format_incident_number(incident.incident_number),
        title=incident.title,
        project=ProjectSummary(id=project.id, name=project.name),
        severity=incident.severity.value,
        status=incident.status.value,
        environment=incident.environment,
        predicted_category=predicted_category,
        ai_confidence=ai_confidence,
        detected_at=incident.detected_at,
        current_assignee=_assignee(incident.current_assignee),
    )


def incident_detail(incident: Incident) -> IncidentDetailResponse:
    base = incident_to_response(incident)
    project = incident.project
    pipeline = incident.pipeline_run
    latest = incident.latest_analysis_run
    latest_summary = None
    if latest is not None:
        classification = None
        root_cause = None
        if latest.output_summary:
            classification = latest.output_summary.get("classification")
            root_cause = latest.output_summary.get("root_cause_summary")
        latest_summary = LatestAnalysisSummary(
            id=latest.id,
            status=latest.status.value,
            classification=classification,
            root_cause_summary=root_cause,
        )
    return IncidentDetailResponse(
        **base.model_dump(),
        project=ProjectSummary(id=project.id, name=project.name, key=project.key),
        pipeline_run=(
            PipelineRunSummary(
                id=pipeline.id,
                external_run_id=pipeline.external_run_id,
                provider=pipeline.provider.value if pipeline.provider else None,
                workflow_name=pipeline.workflow_name,
                source_url=pipeline.source_url,
            )
            if pipeline
            else None
        ),
        latest_analysis=latest_summary,
        current_assignee=_assignee(incident.current_assignee),
    )


def note_to_response(note: IncidentNote) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        incident_id=note.incident_id,
        author_id=note.author_id,
        note_type=note.note_type,
        content=note.content,
        is_pinned=note.is_pinned,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _string_list_from_jsonb(value: list[Any] | None) -> list[str] | None:
    if not value:
        return None
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and "description" in item:
            result.append(str(item["description"]))
    return result or None


def resolution_to_summary(resolution: IncidentResolution) -> ResolutionSummary:
    return ResolutionSummary(
        id=resolution.id,
        resolution_summary=resolution.resolution_summary,
        confirmed_root_cause=resolution.confirmed_root_cause,
        resolution_steps=_string_list_from_jsonb(resolution.resolution_steps),
        prevention_actions=_string_list_from_jsonb(resolution.prevention_actions),
        time_spent_minutes=resolution.time_spent_minutes,
        ai_recommendation_used=resolution.ai_recommendation_used,
        created_at=resolution.created_at,
    )


def analysis_list_item(run: AnalysisRun) -> AnalysisRunListItem:
    return AnalysisRunListItem(
        id=run.id,
        incident_id=run.incident_id,
        status=run.status.value,
        analysis_type=run.analysis_type,
        progress_percentage=run.progress_percentage,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def analysis_detail(run: AnalysisRun) -> AnalysisRunDetailResponse:
    summary = run.output_summary or {}
    classification = summary.get("classification")
    root_cause = None
    if summary.get("root_cause_summary"):
        root_cause = {
            "summary": summary.get("root_cause_summary"),
            "confidence": (classification or {}).get("confidence"),
        }
    confidence = summary.get("confidence_metrics") or {}
    uncertainty = summary.get("uncertainty") or {}
    evidence_quality = summary.get("evidence_quality") or {}
    routing = summary.get("routing_decision") or {}
    selected_route = None
    if isinstance(routing, dict):
        selected_route = (
            routing.get("selected_route")
            or ((routing.get("post_retrieval") or {}).get("selected_route"))
            or ((routing.get("initial") or {}).get("selected_route"))
        )
    orchestration = AnalysisOrchestrationSummary(
        requested_execution_mode=summary.get("execution_mode"),
        effective_execution_mode=summary.get("effective_execution_mode"),
        selected_route=selected_route,
        confidence=(
            (summary.get("final_confidence") or {}).get("final_confidence")
            or confidence.get("calibrated_confidence")
        ),
        confidence_band=confidence.get("confidence_band"),
        uncertainty_score=uncertainty.get("uncertainty_score"),
        uncertainty_level=uncertainty.get("uncertainty_level"),
        evidence_quality_score=evidence_quality.get("evidence_quality_score"),
        retrieval_used=bool((summary.get("evaluation_metadata") or {}).get("rag_used")),
        reasoning_used=bool(
            (summary.get("evaluation_metadata") or {}).get("local_reasoner_used")
            or (summary.get("evaluation_metadata") or {}).get("external_llm_used")
        ),
        fallback_used=bool(summary.get("fallback_used")),
        fallback_reason=summary.get("fallback_reason"),
        routing_policy_version=((summary.get("evaluation_metadata") or {}).get("policy_version")),
        provider_usage_summary=list(summary.get("provider_usage") or []),
        cost_summary=summary.get("budget_usage") or summary.get("cost_metrics"),
        latency_summary={
            "total_latency_ms": (summary.get("evaluation_metadata") or {}).get("total_latency_ms"),
            "stage_latency_ms": (summary.get("evaluation_metadata") or {}).get("stage_latency_ms"),
        },
        retrieval_mode=summary.get("retrieval_mode"),
        candidates_considered=(summary.get("retrieval_result") or {}).get("candidates_considered"),
        results_selected=(summary.get("retrieval_result") or {}).get("results_selected"),
        duplicate_count=(summary.get("retrieval_result") or {}).get("duplicate_count"),
        historical_results_used=(summary.get("retrieval_result") or {}).get(
            "historical_selected_count"
        ),
        retrieval_quality_score=(summary.get("retrieval_quality") or {}).get(
            "retrieval_quality_score"
        ),
        retrieval_configuration_hash=summary.get("retrieval_configuration_hash"),
        retrieval_fallback_used=bool((summary.get("retrieval_result") or {}).get("fallback_used")),
        retrieval_fallback_reason=(summary.get("retrieval_result") or {}).get("fallback_reason"),
    )
    return AnalysisRunDetailResponse(
        id=run.id,
        incident_id=run.incident_id,
        status=run.status.value,
        analysis_type=run.analysis_type,
        duration_ms=run.duration_ms,
        progress_percentage=run.progress_percentage,
        current_stage=run.current_stage,
        input_summary=run.input_summary,
        output_summary=run.output_summary,
        error_code=run.error_code,
        error_message=run.error_message,
        created_at=run.created_at,
        completed_at=run.completed_at,
        classification=classification if isinstance(classification, dict) else None,
        root_cause=root_cause,
        evidence_count=int(summary.get("evidence_count") or 0),
        recommendation_count=int(summary.get("recommendation_count") or 0),
        model_versions=summary.get("model_versions"),
        orchestration=orchestration,
    )


def timeline_event(event: Any) -> TimelineEventResponse:
    return TimelineEventResponse(
        id=event.id,
        event_type=event.event_type,
        actor_type=event.actor_type,
        title=event.title,
        description=event.description,
        occurred_at=event.occurred_at,
    )
