"""User notification application service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import DeliveryStatus, NotificationType, OrganizationRole
from app.domain.exceptions.business import ResourceNotFoundError
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.notification import Notification
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.schemas.common import build_paginated_response, normalize_pagination
from app.schemas.notification import NotificationListResponse, NotificationResponse

logger = structlog.get_logger(__name__)

_IN_APP_CHANNEL = "in_app"

# System-detected incidents are announced to the people accountable for the org.
_ADMIN_RECIPIENT_ROLES = (
    OrganizationRole.ORGANIZATION_OWNER,
    OrganizationRole.ORGANIZATION_ADMIN,
)


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_notifications(
        self,
        *,
        user_id: UUID,
        page: int,
        page_size: int,
        is_read: bool | None = None,
        severity: str | None = None,
        notification_type: str | None = None,
        incident_id: UUID | None = None,
    ) -> NotificationListResponse:
        page, page_size, offset = normalize_pagination(page, page_size)
        filters = [Notification.user_id == user_id]
        if is_read is not None:
            filters.append(Notification.is_read.is_(is_read))
        if severity:
            filters.append(Notification.severity == severity)
        if notification_type:
            filters.append(Notification.notification_type == NotificationType(notification_type))
        if incident_id:
            filters.append(Notification.incident_id == incident_id)

        total = int(
            await self._session.scalar(
                select(func.count()).select_from(Notification).where(*filters)
            )
            or 0
        )
        unread_count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            )
            or 0
        )
        stmt = (
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = list((await self._session.scalars(stmt)).all())
        paginated = build_paginated_response(
            items=[self._to_response(n) for n in rows],
            page=page,
            page_size=page_size,
            total_items=total,
        )
        return NotificationListResponse(
            items=paginated.items,
            page=paginated.page,
            page_size=paginated.page_size,
            total_items=paginated.total_items,
            total_pages=paginated.total_pages,
            unread_count=unread_count,
        )

    async def mark_read(self, *, user_id: UUID, notification_id: UUID) -> NotificationResponse:
        notification = await self._get_owned(user_id, notification_id)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            notification.delivery_status = DeliveryStatus.READ
            await self._session.flush()
        return self._to_response(notification)

    async def mark_all_read(self, *, user_id: UUID) -> int:
        now = datetime.now(UTC)
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        rows = list((await self._session.scalars(stmt)).all())
        for row in rows:
            row.is_read = True
            row.read_at = now
            row.delivery_status = DeliveryStatus.READ
        await self._session.flush()
        return len(rows)

    async def delete(self, *, user_id: UUID, notification_id: UUID) -> None:
        notification = await self._get_owned(user_id, notification_id)
        await self._session.delete(notification)
        await self._session.flush()

    async def list_organization_recipient_ids(
        self,
        *,
        organization_id: UUID,
        roles: tuple[OrganizationRole, ...] = _ADMIN_RECIPIENT_ROLES,
    ) -> list[UUID]:
        """Active member user ids for the given organization roles."""
        stmt = select(OrganizationMember.user_id).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.is_active.is_(True),
            OrganizationMember.role.in_(roles),
        )
        return list((await self._session.scalars(stmt)).all())

    async def notify_incident_created(
        self,
        *,
        user_id: UUID,
        incident_id: UUID,
        title: str,
        message: str,
        severity: str | None = None,
    ) -> Notification | None:
        """Create an ``incident_created`` notification, skipping duplicates."""
        existing = await self._session.scalar(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.incident_id == incident_id,
                Notification.notification_type == NotificationType.INCIDENT_CREATED,
            )
        )
        if existing is not None:
            return None
        return await self._create(
            user_id=user_id,
            incident_id=incident_id,
            notification_type=NotificationType.INCIDENT_CREATED,
            title=title[:255],
            message=message[:1000],
            severity=severity,
        )

    async def notify_assignment(
        self,
        *,
        incident: Incident,
        assignee_id: UUID,
        actor_id: UUID,
    ) -> None:
        from app.domain.services.incident_transitions import format_incident_number

        number = format_incident_number(incident.incident_number)
        title = f"Assigned to incident {number}"
        message = f"You have been assigned to incident {number}: {incident.title}"
        await self._create(
            user_id=assignee_id,
            incident_id=incident.id,
            notification_type=NotificationType.ASSIGNMENT,
            title=title,
            message=message,
            severity=incident.severity.value,
        )
        if actor_id != assignee_id:
            await self._create(
                user_id=actor_id,
                incident_id=incident.id,
                notification_type=NotificationType.ASSIGNMENT,
                title=f"Incident {number} assigned",
                message=f"Incident {number} was assigned to a team member.",
                severity=incident.severity.value,
            )

    async def notify_resolved(
        self,
        *,
        incident: Incident,
        resolved_by: UUID,
        resolution_summary: str,
    ) -> None:
        from app.domain.services.incident_transitions import format_incident_number

        number = format_incident_number(incident.incident_number)
        title = f"Incident {number} resolved"
        message = (
            resolution_summary[:500] if resolution_summary else f"Incident {number} was resolved."
        )
        recipients: set[UUID] = {resolved_by}
        if incident.current_assignee_id and incident.current_assignee_id != resolved_by:
            recipients.add(incident.current_assignee_id)
        if incident.created_by and incident.created_by not in recipients:
            recipients.add(incident.created_by)
        for user_id in recipients:
            await self._create(
                user_id=user_id,
                incident_id=incident.id,
                notification_type=NotificationType.SYSTEM,
                title=title,
                message=message,
                severity=incident.severity.value,
            )

    async def notify_analysis_completed(
        self,
        *,
        incident: Incident,
        requested_by: UUID | None,
        category: str | None,
        root_cause: str | None,
    ) -> None:
        from app.domain.services.incident_transitions import format_incident_number

        number = format_incident_number(incident.incident_number)
        category_text = category or "unknown category"
        title = "AI analysis completed"
        message = (
            f"Incident {number} was classified as {category_text}."
            if category
            else f"Analysis completed for incident {number}."
        )
        if root_cause:
            message = f"{message} {root_cause[:200]}"
        recipients: set[UUID] = set()
        if requested_by:
            recipients.add(requested_by)
        if incident.current_assignee_id:
            recipients.add(incident.current_assignee_id)
        for user_id in recipients:
            await self._create(
                user_id=user_id,
                incident_id=incident.id,
                notification_type=NotificationType.ANALYSIS_COMPLETED,
                title=title,
                message=message,
                severity=incident.severity.value,
            )

    async def notify_analysis_failed(
        self,
        *,
        incident: Incident,
        requested_by: UUID | None,
        error_message: str | None,
    ) -> None:
        from app.domain.services.incident_transitions import format_incident_number

        number = format_incident_number(incident.incident_number)
        title = "AI analysis failed"
        message = error_message or f"Analysis failed for incident {number}."
        recipients: set[UUID] = set()
        if requested_by:
            recipients.add(requested_by)
        if incident.current_assignee_id:
            recipients.add(incident.current_assignee_id)
        for user_id in recipients:
            await self._create(
                user_id=user_id,
                incident_id=incident.id,
                notification_type=NotificationType.ANALYSIS_FAILED,
                title=title,
                message=message[:500],
                severity=incident.severity.value,
            )

    async def _create(
        self,
        *,
        user_id: UUID,
        incident_id: UUID | None,
        notification_type: NotificationType,
        title: str,
        message: str,
        severity: str | None = None,
    ) -> Notification:
        now = datetime.now(UTC)
        notification = Notification(
            user_id=user_id,
            incident_id=incident_id,
            notification_type=notification_type,
            title=title,
            message=message,
            severity=severity,
            channel=_IN_APP_CHANNEL,
            delivery_status=DeliveryStatus.SENT,
            is_read=False,
            sent_at=now,
        )
        self._session.add(notification)
        await self._session.flush()
        logger.info(
            "notification_created",
            user_id=str(user_id),
            notification_type=notification_type.value,
            incident_id=str(incident_id) if incident_id else None,
        )
        return notification

    async def _get_owned(self, user_id: UUID, notification_id: UUID) -> Notification:
        notification = await self._session.get(Notification, notification_id)
        if notification is None or notification.user_id != user_id:
            raise ResourceNotFoundError("Notification not found.")
        return notification

    @staticmethod
    def _to_response(notification: Notification) -> NotificationResponse:
        ntype = notification.notification_type
        dstatus = notification.delivery_status
        return NotificationResponse(
            id=notification.id,
            notification_type=ntype.value if hasattr(ntype, "value") else str(ntype),
            title=notification.title,
            message=notification.message,
            severity=notification.severity,
            channel=notification.channel,
            delivery_status=dstatus.value if hasattr(dstatus, "value") else str(dstatus),
            is_read=notification.is_read,
            incident_id=notification.incident_id,
            created_at=notification.created_at,
            read_at=notification.read_at,
        )
