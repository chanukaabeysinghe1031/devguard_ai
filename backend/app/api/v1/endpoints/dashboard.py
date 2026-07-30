"""Dashboard aggregation endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.api.deps.access import require_org_reader
from app.application.services.dashboard_service import DashboardService
from app.schemas.dashboard import (
    ActiveAnalysesResponse,
    ActivityResponse,
    DashboardSummaryResponse,
    FailureCategoryDistributionResponse,
    IncidentTrendResponse,
    RecentIncidentsResponse,
    SeverityDistributionResponse,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _dashboard_service(session: AsyncSession = Depends(get_session)) -> DashboardService:
    return DashboardService(session)


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    ctx: tuple = Depends(require_org_reader),
    service: DashboardService = Depends(_dashboard_service),
    project_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> DashboardSummaryResponse:
    _, organization_id, _ = ctx
    return await service.summary(
        organization_id=organization_id,
        project_id=project_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/incident-trend", response_model=IncidentTrendResponse)
async def get_incident_trend(
    ctx: tuple = Depends(require_org_reader),
    service: DashboardService = Depends(_dashboard_service),
    interval: str = Query(default="day"),
    project_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> IncidentTrendResponse:
    _, organization_id, _ = ctx
    return await service.incident_trend(
        organization_id=organization_id,
        interval=interval,
        project_id=project_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/severity-distribution", response_model=SeverityDistributionResponse)
async def get_severity_distribution(
    ctx: tuple = Depends(require_org_reader),
    service: DashboardService = Depends(_dashboard_service),
    project_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> SeverityDistributionResponse:
    _, organization_id, _ = ctx
    return await service.severity_distribution(
        organization_id=organization_id,
        project_id=project_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/failure-categories", response_model=FailureCategoryDistributionResponse)
async def get_failure_categories(
    ctx: tuple = Depends(require_org_reader),
    service: DashboardService = Depends(_dashboard_service),
    project_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> FailureCategoryDistributionResponse:
    _, organization_id, _ = ctx
    return await service.failure_categories(
        organization_id=organization_id,
        project_id=project_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/recent-incidents", response_model=RecentIncidentsResponse)
async def get_recent_incidents(
    ctx: tuple = Depends(require_org_reader),
    service: DashboardService = Depends(_dashboard_service),
    limit: int = Query(default=10, ge=1, le=50),
    project_id: UUID | None = None,
) -> RecentIncidentsResponse:
    _, organization_id, _ = ctx
    return await service.recent_incidents(
        organization_id=organization_id,
        limit=limit,
        project_id=project_id,
    )


@router.get("/active-analyses", response_model=ActiveAnalysesResponse)
async def get_active_analyses(
    ctx: tuple = Depends(require_org_reader),
    service: DashboardService = Depends(_dashboard_service),
    limit: int = Query(default=20, ge=1, le=50),
    project_id: UUID | None = None,
) -> ActiveAnalysesResponse:
    _, organization_id, _ = ctx
    return await service.active_analyses(
        organization_id=organization_id,
        limit=limit,
        project_id=project_id,
    )


@router.get("/activity", response_model=ActivityResponse)
async def get_dashboard_activity(
    ctx: tuple = Depends(require_org_reader),
    service: DashboardService = Depends(_dashboard_service),
    limit: int = Query(default=20, ge=1, le=100),
    project_id: UUID | None = None,
) -> ActivityResponse:
    _, organization_id, _ = ctx
    return await service.activity(
        organization_id=organization_id,
        limit=limit,
        project_id=project_id,
    )
