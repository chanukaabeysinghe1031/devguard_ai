"""User notification endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.api.deps.access import require_org_reader
from app.application.services.notification_service import NotificationService
from app.schemas.common import MessageResponse
from app.schemas.notification import NotificationListResponse, NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _notification_service(
    session: AsyncSession = Depends(get_session),
) -> NotificationService:
    return NotificationService(session)


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    ctx: tuple = Depends(require_org_reader),
    service: NotificationService = Depends(_notification_service),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_read: bool | None = None,
    severity: str | None = None,
    notification_type: str | None = None,
    incident_id: UUID | None = None,
) -> NotificationListResponse:
    user, organization_id, _ = ctx
    return await service.list_notifications(
        user_id=user.id,
        page=page,
        page_size=page_size,
        is_read=is_read,
        severity=severity,
        notification_type=notification_type,
        incident_id=incident_id,
        organization_id=organization_id,
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: NotificationService = Depends(_notification_service),
) -> NotificationResponse:
    user, _, _ = ctx
    return await service.mark_read(user_id=user.id, notification_id=notification_id)


@router.post("/read-all", response_model=MessageResponse)
async def mark_all_notifications_read(
    ctx: tuple = Depends(require_org_reader),
    service: NotificationService = Depends(_notification_service),
) -> MessageResponse:
    user, organization_id, _ = ctx
    count = await service.mark_all_read(user_id=user.id, organization_id=organization_id)
    return MessageResponse(message=f"Marked {count} notification(s) as read.")


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: NotificationService = Depends(_notification_service),
) -> None:
    user, _, _ = ctx
    await service.delete(user_id=user.id, notification_id=notification_id)
