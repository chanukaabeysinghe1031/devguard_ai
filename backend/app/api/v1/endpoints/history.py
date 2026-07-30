"""Incident history search endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.api.deps.access import require_org_reader
from app.application.services.history_service import HistoryService
from app.schemas.common import PaginatedResponse
from app.schemas.history import HistoryIncidentItem

router = APIRouter(prefix="/history", tags=["History"])


def _history_service(session: AsyncSession = Depends(get_session)) -> HistoryService:
    return HistoryService(session)


@router.get("/incidents", response_model=PaginatedResponse[HistoryIncidentItem])
async def search_incident_history(
    ctx: tuple = Depends(require_org_reader),
    service: HistoryService = Depends(_history_service),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    project_id: UUID | None = None,
    provider: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    environment: str | None = None,
    resolved_by: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str = Query(default="resolved_at"),
    sort_order: str = Query(default="desc"),
) -> PaginatedResponse[HistoryIncidentItem]:
    _, organization_id, _ = ctx
    return await service.list_incidents(
        organization_id=organization_id,
        page=page,
        page_size=page_size,
        search=search,
        project_id=project_id,
        provider=provider,
        category=category,
        severity=severity,
        status=status,
        environment=environment,
        resolved_by=resolved_by,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
