"""Dashboard aggregation application service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.services.mappers import incident_list_item
from app.domain.enums import AnalysisRunStatus, IncidentSeverity, IncidentStatus, PipelineRunStatus
from app.domain.services.incident_transitions import format_incident_number
from app.infrastructure.database.models.analysis_run import AnalysisRun
from app.infrastructure.database.models.failure_category import FailureCategory
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_event import IncidentEvent
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.database.models.prediction import Prediction
from app.infrastructure.database.models.project import Project
from app.schemas.dashboard import (
    ActiveAnalysesResponse,
    ActiveAnalysisItem,
    ActivityItem,
    ActivityResponse,
    DashboardSummaryResponse,
    FailureCategoryDistributionResponse,
    FailureCategoryItem,
    IncidentTrendItem,
    IncidentTrendResponse,
    RecentIncidentsResponse,
    SeverityDistributionResponse,
)

_OPEN_STATUSES = (
    IncidentStatus.DETECTED,
    IncidentStatus.ANALYSING,
    IncidentStatus.OPEN,
    IncidentStatus.IN_PROGRESS,
    IncidentStatus.ANALYSIS_FAILED,
    IncidentStatus.REOPENED,
)

_ACTIVE_ANALYSIS_STATUSES = (
    AnalysisRunStatus.QUEUED,
    AnalysisRunStatus.PREPROCESSING,
    AnalysisRunStatus.CLASSIFYING,
    AnalysisRunStatus.RETRIEVING,
    AnalysisRunStatus.REASONING,
)


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _incident_filters(
        self,
        *,
        organization_id: UUID,
        project_id: UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list:
        filters = [Project.organization_id == organization_id]
        if project_id:
            filters.append(Incident.project_id == project_id)
        if date_from:
            filters.append(Incident.detected_at >= date_from)
        if date_to:
            filters.append(Incident.detected_at <= date_to)
        return filters

    async def summary(
        self,
        *,
        organization_id: UUID,
        project_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> DashboardSummaryResponse:
        inc_filters = self._incident_filters(
            organization_id=organization_id,
            project_id=project_id,
            date_from=date_from,
            date_to=date_to,
        )
        open_count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(Incident)
                .join(Project, Project.id == Incident.project_id)
                .where(*inc_filters, Incident.status.in_(_OPEN_STATUSES))
            )
            or 0
        )
        critical_count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(Incident)
                .join(Project, Project.id == Incident.project_id)
                .where(
                    *inc_filters,
                    Incident.severity == IncidentSeverity.CRITICAL,
                    Incident.status.in_(_OPEN_STATUSES),
                )
            )
            or 0
        )

        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        resolved_today = int(
            await self._session.scalar(
                select(func.count())
                .select_from(Incident)
                .join(Project, Project.id == Incident.project_id)
                .where(
                    Project.organization_id == organization_id,
                    Incident.resolved_at.is_not(None),
                    Incident.resolved_at >= today_start,
                    *([Incident.project_id == project_id] if project_id else []),
                )
            )
            or 0
        )

        active_analyses = int(
            await self._session.scalar(
                select(func.count())
                .select_from(AnalysisRun)
                .join(Incident, Incident.id == AnalysisRun.incident_id)
                .join(Project, Project.id == Incident.project_id)
                .where(
                    Project.organization_id == organization_id,
                    AnalysisRun.status.in_(_ACTIVE_ANALYSIS_STATUSES),
                    *([Incident.project_id == project_id] if project_id else []),
                )
            )
            or 0
        )

        run_filters = [Project.organization_id == organization_id]
        if project_id:
            run_filters.append(PipelineRun.project_id == project_id)
        if date_from:
            run_filters.append(PipelineRun.created_at >= date_from)
        if date_to:
            run_filters.append(PipelineRun.created_at <= date_to)

        failed_deployments = int(
            await self._session.scalar(
                select(func.count())
                .select_from(PipelineRun)
                .join(Project, Project.id == PipelineRun.project_id)
                .where(*run_filters, PipelineRun.status == PipelineRunStatus.FAILED)
            )
            or 0
        )
        successful_deployments = int(
            await self._session.scalar(
                select(func.count())
                .select_from(PipelineRun)
                .join(Project, Project.id == PipelineRun.project_id)
                .where(*run_filters, PipelineRun.status == PipelineRunStatus.SUCCEEDED)
            )
            or 0
        )

        total_deployments = failed_deployments + successful_deployments
        deployment_success_rate = (
            round(successful_deployments / total_deployments * 100, 2)
            if total_deployments
            else None
        )

        avg_minutes = await self._session.scalar(
            select(
                func.avg(func.extract("epoch", Incident.resolved_at - Incident.detected_at) / 60.0)
            )
            .select_from(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(
                *inc_filters,
                Incident.resolved_at.is_not(None),
            )
        )

        return DashboardSummaryResponse(
            open_incidents=open_count,
            critical_incidents=critical_count,
            active_analyses=active_analyses,
            resolved_today=resolved_today,
            failed_deployments=failed_deployments,
            successful_deployments=successful_deployments,
            average_resolution_minutes=round(float(avg_minutes), 1) if avg_minutes else None,
            deployment_success_rate=deployment_success_rate,
        )

    async def incident_trend(
        self,
        *,
        organization_id: UUID,
        interval: str = "day",
        project_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> IncidentTrendResponse:
        if interval not in {"day", "week", "month"}:
            interval = "day"
        if date_to is None:
            date_to = datetime.now(UTC)
        if date_from is None:
            date_from = date_to - timedelta(days=30)

        trunc_unit = "week" if interval == "week" else ("month" if interval == "month" else "day")
        inc_filters = self._incident_filters(
            organization_id=organization_id,
            project_id=project_id,
            date_from=date_from,
            date_to=date_to,
        )

        detected_period = cast(func.date_trunc(trunc_unit, Incident.detected_at), Date).label(
            "period"
        )
        detected_stmt = (
            select(detected_period, func.count().label("cnt"))
            .select_from(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(*inc_filters)
            .group_by(detected_period)
            .order_by(detected_period)
        )
        detected_rows = (await self._session.execute(detected_stmt)).all()
        detected_map = {str(row.period): int(row.cnt) for row in detected_rows}

        resolved_filters = [
            Project.organization_id == organization_id,
            Incident.resolved_at.is_not(None),
            Incident.resolved_at >= date_from,
            Incident.resolved_at <= date_to,
        ]
        if project_id:
            resolved_filters.append(Incident.project_id == project_id)

        resolved_period = cast(func.date_trunc(trunc_unit, Incident.resolved_at), Date).label(
            "period"
        )
        resolved_stmt = (
            select(resolved_period, func.count().label("cnt"))
            .select_from(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(*resolved_filters)
            .group_by(resolved_period)
            .order_by(resolved_period)
        )
        resolved_rows = (await self._session.execute(resolved_stmt)).all()
        resolved_map = {str(row.period): int(row.cnt) for row in resolved_rows}

        all_periods = sorted(set(detected_map) | set(resolved_map))
        items = [
            IncidentTrendItem(
                period=period,
                incident_count=detected_map.get(period, 0),
                resolved_count=resolved_map.get(period, 0),
            )
            for period in all_periods
        ]
        return IncidentTrendResponse(interval=interval, items=items)

    async def severity_distribution(
        self,
        *,
        organization_id: UUID,
        project_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SeverityDistributionResponse:
        inc_filters = self._incident_filters(
            organization_id=organization_id,
            project_id=project_id,
            date_from=date_from,
            date_to=date_to,
        )
        stmt = (
            select(Incident.severity, func.count())
            .join(Project, Project.id == Incident.project_id)
            .where(*inc_filters)
            .group_by(Incident.severity)
        )
        rows = (await self._session.execute(stmt)).all()
        counts = {sev.value if hasattr(sev, "value") else str(sev): cnt for sev, cnt in rows}
        return SeverityDistributionResponse(
            critical=int(counts.get("critical", 0)),
            high=int(counts.get("high", 0)),
            medium=int(counts.get("medium", 0)),
            low=int(counts.get("low", 0)),
        )

    async def failure_categories(
        self,
        *,
        organization_id: UUID,
        project_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> FailureCategoryDistributionResponse:
        inc_filters = self._incident_filters(
            organization_id=organization_id,
            project_id=project_id,
            date_from=date_from,
            date_to=date_to,
        )
        stmt = (
            select(FailureCategory.code, func.count())
            .select_from(Prediction)
            .join(AnalysisRun, AnalysisRun.id == Prediction.analysis_run_id)
            .join(Incident, Incident.id == AnalysisRun.incident_id)
            .join(Project, Project.id == Incident.project_id)
            .join(FailureCategory, FailureCategory.id == Prediction.failure_category_id)
            .where(*inc_filters, Prediction.rank == 1)
            .group_by(FailureCategory.code)
            .order_by(func.count().desc())
        )
        rows = (await self._session.execute(stmt)).all()
        items = [FailureCategoryItem(category=code, count=int(cnt)) for code, cnt in rows]
        return FailureCategoryDistributionResponse(items=items)

    async def recent_incidents(
        self,
        *,
        organization_id: UUID,
        limit: int = 10,
        project_id: UUID | None = None,
    ) -> RecentIncidentsResponse:
        limit = min(max(1, limit), 50)
        filters = [Project.organization_id == organization_id]
        if project_id:
            filters.append(Incident.project_id == project_id)
        stmt = (
            select(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(*filters)
            .options(
                selectinload(Incident.project),
                selectinload(Incident.current_assignee),
                selectinload(Incident.latest_analysis_run),
            )
            .order_by(Incident.detected_at.desc())
            .limit(limit)
        )
        incidents = list((await self._session.scalars(stmt)).all())
        items = []
        for inc in incidents:
            category, confidence = self._classification_from_incident(inc)
            items.append(
                incident_list_item(inc, predicted_category=category, ai_confidence=confidence)
            )
        return RecentIncidentsResponse(items=items)

    async def active_analyses(
        self,
        *,
        organization_id: UUID,
        project_id: UUID | None = None,
        limit: int = 20,
    ) -> ActiveAnalysesResponse:
        limit = min(max(1, limit), 50)
        filters = [
            Project.organization_id == organization_id,
            AnalysisRun.status.in_(_ACTIVE_ANALYSIS_STATUSES),
        ]
        if project_id:
            filters.append(Incident.project_id == project_id)
        stmt = (
            select(AnalysisRun)
            .join(Incident, Incident.id == AnalysisRun.incident_id)
            .join(Project, Project.id == Incident.project_id)
            .where(*filters)
            .options(selectinload(AnalysisRun.incident))
            .order_by(AnalysisRun.created_at.desc())
            .limit(limit)
        )
        runs = list((await self._session.scalars(stmt)).all())
        items = [
            ActiveAnalysisItem(
                id=run.id,
                incident_id=run.incident_id,
                incident_number=format_incident_number(run.incident.incident_number),
                incident_title=run.incident.title,
                status=run.status.value,
                current_stage=run.current_stage,
                progress_percentage=run.progress_percentage,
                started_at=run.started_at,
            )
            for run in runs
        ]
        return ActiveAnalysesResponse(items=items)

    async def activity(
        self,
        *,
        organization_id: UUID,
        limit: int = 20,
        project_id: UUID | None = None,
    ) -> ActivityResponse:
        limit = min(max(1, limit), 100)
        filters = [Project.organization_id == organization_id]
        if project_id:
            filters.append(Incident.project_id == project_id)
        stmt = (
            select(IncidentEvent, Incident)
            .join(Incident, Incident.id == IncidentEvent.incident_id)
            .join(Project, Project.id == Incident.project_id)
            .where(*filters)
            .order_by(IncidentEvent.occurred_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        items = [
            ActivityItem(
                id=event.id,
                incident_id=incident.id,
                incident_number=format_incident_number(incident.incident_number),
                event_type=event.event_type,
                title=event.title,
                description=event.description,
                occurred_at=event.occurred_at,
                actor_user_id=event.actor_user_id,
            )
            for event, incident in rows
        ]
        return ActivityResponse(items=items)

    @staticmethod
    def _classification_from_incident(incident: Incident) -> tuple[str | None, float | None]:
        latest = incident.latest_analysis_run
        if latest and latest.output_summary:
            classification = latest.output_summary.get("classification") or {}
            category = classification.get("category")
            confidence = classification.get("confidence")
            if category:
                return category, float(confidence) if confidence is not None else None
        return None, None
