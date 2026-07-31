"""Durable webhook delivery ledger service (ADR-005 §5).

The delivery row is the unit of idempotency and of retry state; there is no
external queue in Phase 5B.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import WebhookProcessingStatus
from app.infrastructure.database.models.webhook_delivery import WebhookDelivery

logger = structlog.get_logger(__name__)

GITHUB_PROVIDER = "github"
_MAX_ERROR_MESSAGE = 1000


class WebhookDeliveryService:
    """Creates and transitions ``webhook_deliveries`` rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_delivery_id(
        self,
        *,
        delivery_id: str,
        provider: str = GITHUB_PROVIDER,
    ) -> WebhookDelivery | None:
        stmt = select(WebhookDelivery).where(
            WebhookDelivery.provider == provider,
            WebhookDelivery.delivery_id == delivery_id,
        )
        return await self._session.scalar(stmt)

    async def create_if_new(
        self,
        *,
        delivery_id: str,
        event_name: str,
        event_action: str | None,
        installation_id: int | None,
        repository_id: int | None,
        payload_hash: str,
        sanitised_snapshot: dict[str, Any] | None,
        signature_valid: bool,
        processing_status: WebhookProcessingStatus = WebhookProcessingStatus.RECEIVED,
        provider: str = GITHUB_PROVIDER,
        organization_id: UUID | None = None,
    ) -> tuple[WebhookDelivery, bool]:
        """Return ``(delivery, created)``; duplicates return the existing row."""
        existing = await self.get_by_delivery_id(delivery_id=delivery_id, provider=provider)
        if existing is not None:
            return existing, False

        resolved_org_id = organization_id
        if resolved_org_id is None and installation_id is not None:
            from app.infrastructure.database.models.github_installation import (
                GitHubInstallation,
            )

            resolved_org_id = await self._session.scalar(
                select(GitHubInstallation.organization_id).where(
                    GitHubInstallation.github_installation_id == installation_id
                )
            )

        delivery = WebhookDelivery(
            provider=provider,
            delivery_id=delivery_id,
            event_name=event_name,
            event_action=event_action,
            organization_id=resolved_org_id,
            installation_id=installation_id,
            repository_id=repository_id,
            payload_hash=payload_hash,
            sanitised_snapshot=sanitised_snapshot,
            signature_valid=signature_valid,
            processing_status=processing_status.value,
            attempt_count=0,
            received_at=datetime.now(UTC),
        )
        try:
            async with self._session.begin_nested():
                self._session.add(delivery)
                await self._session.flush()
        except IntegrityError:
            # Concurrent delivery of the same X-GitHub-Delivery id.
            duplicate = await self.get_by_delivery_id(delivery_id=delivery_id, provider=provider)
            if duplicate is None:
                raise
            return duplicate, False
        return delivery, True

    async def mark_status(
        self,
        delivery: WebhookDelivery,
        status: WebhookProcessingStatus,
    ) -> WebhookDelivery:
        delivery.processing_status = status.value
        await self._session.flush()
        return delivery

    async def mark_processing_started(self, delivery: WebhookDelivery) -> WebhookDelivery:
        delivery.processing_status = WebhookProcessingStatus.FETCHING_METADATA.value
        delivery.processing_started_at = datetime.now(UTC)
        delivery.attempt_count += 1
        await self._session.flush()
        return delivery

    async def mark_ignored(self, delivery: WebhookDelivery, reason: str) -> WebhookDelivery:
        delivery.processing_status = WebhookProcessingStatus.IGNORED.value
        delivery.error_code = reason[:80]
        delivery.processed_at = datetime.now(UTC)
        await self._session.flush()
        logger.info(
            "webhook_delivery_ignored",
            delivery_id=delivery.delivery_id,
            reason=reason,
        )
        return delivery

    async def mark_completed(
        self,
        delivery: WebhookDelivery,
        *,
        pipeline_run_id: UUID | None = None,
        incident_id: UUID | None = None,
    ) -> WebhookDelivery:
        delivery.processing_status = WebhookProcessingStatus.COMPLETED.value
        delivery.processed_at = datetime.now(UTC)
        delivery.error_code = None
        delivery.error_message_sanitized = None
        delivery.next_attempt_at = None
        if pipeline_run_id is not None:
            delivery.related_pipeline_run_id = pipeline_run_id
        if incident_id is not None:
            delivery.related_incident_id = incident_id
        await self._session.flush()
        return delivery

    async def mark_failed(
        self,
        delivery: WebhookDelivery,
        *,
        error_code: str,
        error_message: str,
        retriable: bool = False,
        max_attempts: int = 3,
        retry_delay_seconds: int = 60,
    ) -> WebhookDelivery:
        now = datetime.now(UTC)
        delivery.error_code = error_code[:80]
        delivery.error_message_sanitized = error_message[:_MAX_ERROR_MESSAGE]
        if retriable and delivery.attempt_count < max_attempts:
            delivery.processing_status = WebhookProcessingStatus.RETRYING.value
            delivery.next_attempt_at = now + timedelta(
                seconds=retry_delay_seconds * max(delivery.attempt_count, 1)
            )
        else:
            delivery.processing_status = WebhookProcessingStatus.FAILED.value
            delivery.failed_at = now
            delivery.next_attempt_at = None
        await self._session.flush()
        logger.warning(
            "webhook_delivery_failed",
            delivery_id=delivery.delivery_id,
            error_code=error_code,
            status=delivery.processing_status,
        )
        return delivery

    async def list_for_repository(
        self,
        *,
        repository_id: int,
        limit: int = 50,
        provider: str = GITHUB_PROVIDER,
    ) -> list[WebhookDelivery]:
        stmt = (
            select(WebhookDelivery)
            .where(
                WebhookDelivery.provider == provider,
                WebhookDelivery.repository_id == repository_id,
            )
            .order_by(WebhookDelivery.received_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        return list((await self._session.scalars(stmt)).all())
