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

from app.domain.enums import WebhookConnectionProcessingStatus, WebhookProcessingStatus
from app.infrastructure.database.models.github_repository_connection import (
    GitHubRepositoryConnection,
)
from app.infrastructure.database.models.webhook_delivery import WebhookDelivery
from app.infrastructure.database.models.webhook_delivery_connection_processing import (
    WebhookDeliveryConnectionProcessing,
)

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
        """Return ``(delivery, created)``; duplicates return the existing row.

        ``organization_id`` is left ``None`` unless explicitly supplied. A
        GitHub App installation is a global identity that may be shared by
        many DevGuard organizations, so no single org can be treated as
        authoritative for the delivery row itself; per-tenant outcomes are
        tracked independently in ``webhook_delivery_connection_processing``.
        """
        existing = await self.get_by_delivery_id(delivery_id=delivery_id, provider=provider)
        if existing is not None:
            return existing, False

        delivery = WebhookDelivery(
            provider=provider,
            delivery_id=delivery_id,
            event_name=event_name,
            event_action=event_action,
            organization_id=organization_id,
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

    # ------------------------------------------------------------------
    # Per-connection fan-out processing (shared-installation multi-tenancy)
    # ------------------------------------------------------------------
    async def get_connection_processing(
        self,
        *,
        delivery: WebhookDelivery,
        connection: GitHubRepositoryConnection,
    ) -> WebhookDeliveryConnectionProcessing | None:
        return await self._session.scalar(
            select(WebhookDeliveryConnectionProcessing).where(
                WebhookDeliveryConnectionProcessing.webhook_delivery_id == delivery.id,
                WebhookDeliveryConnectionProcessing.repository_connection_id == connection.id,
            )
        )

    async def ensure_connection_processing(
        self,
        *,
        delivery: WebhookDelivery,
        connection: GitHubRepositoryConnection,
    ) -> WebhookDeliveryConnectionProcessing:
        """Return the existing row for this (delivery, connection) pair or create one.

        Idempotent under concurrent/replayed processing via the unique
        constraint on ``(webhook_delivery_id, repository_connection_id)``.
        """
        existing = await self.get_connection_processing(delivery=delivery, connection=connection)
        if existing is not None:
            return existing

        processing = WebhookDeliveryConnectionProcessing(
            webhook_delivery_id=delivery.id,
            repository_connection_id=connection.id,
            organization_id=connection.organization_id,
            project_id=connection.project_id,
            status=WebhookConnectionProcessingStatus.PENDING.value,
            attempt_count=0,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(processing)
                await self._session.flush()
        except IntegrityError:
            duplicate = await self.get_connection_processing(
                delivery=delivery, connection=connection
            )
            if duplicate is None:
                raise
            return duplicate
        return processing

    async def mark_connection_processing_started(
        self,
        processing: WebhookDeliveryConnectionProcessing,
    ) -> WebhookDeliveryConnectionProcessing:
        processing.status = WebhookConnectionProcessingStatus.PROCESSING.value
        processing.started_at = datetime.now(UTC)
        processing.attempt_count += 1
        await self._session.flush()
        return processing

    async def mark_connection_processing_skipped(
        self,
        processing: WebhookDeliveryConnectionProcessing,
        reason: str,
    ) -> WebhookDeliveryConnectionProcessing:
        processing.status = WebhookConnectionProcessingStatus.SKIPPED.value
        processing.error_code = reason[:80]
        processing.completed_at = datetime.now(UTC)
        await self._session.flush()
        return processing

    async def mark_connection_processing_completed(
        self,
        processing: WebhookDeliveryConnectionProcessing,
        *,
        pipeline_run_id: UUID | None = None,
        incident_id: UUID | None = None,
    ) -> WebhookDeliveryConnectionProcessing:
        processing.status = WebhookConnectionProcessingStatus.COMPLETE.value
        processing.completed_at = datetime.now(UTC)
        processing.error_code = None
        processing.error_message_sanitized = None
        if pipeline_run_id is not None:
            processing.pipeline_run_id = pipeline_run_id
        if incident_id is not None:
            processing.incident_id = incident_id
        await self._session.flush()
        return processing

    async def mark_connection_processing_failed(
        self,
        processing: WebhookDeliveryConnectionProcessing,
        *,
        error_code: str,
        error_message: str,
        retriable: bool = False,
    ) -> WebhookDeliveryConnectionProcessing:
        processing.status = (
            WebhookConnectionProcessingStatus.RETRYABLE.value
            if retriable
            else WebhookConnectionProcessingStatus.FAILED.value
        )
        processing.error_code = error_code[:80]
        processing.error_message_sanitized = error_message[:_MAX_ERROR_MESSAGE]
        processing.failed_at = datetime.now(UTC)
        await self._session.flush()
        logger.warning(
            "webhook_delivery_connection_processing_failed",
            delivery_id=str(processing.webhook_delivery_id),
            connection_id=str(processing.repository_connection_id),
            error_code=error_code,
            status=processing.status,
        )
        return processing

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

    async def list_for_connection(
        self,
        *,
        connection_id: UUID,
        limit: int = 50,
    ) -> list[tuple[WebhookDelivery, WebhookDeliveryConnectionProcessing]]:
        """Deliveries relevant to one repository connection only.

        Scoped through ``webhook_delivery_connection_processing`` rather than
        the shared delivery's raw ``repository_id`` — the same GitHub
        repository may be connected from more than one organization when the
        underlying installation is shared, and one tenant's activity feed
        must never surface another tenant's processing outcome or incident
        reference.
        """
        stmt = (
            select(WebhookDelivery, WebhookDeliveryConnectionProcessing)
            .join(
                WebhookDeliveryConnectionProcessing,
                WebhookDeliveryConnectionProcessing.webhook_delivery_id == WebhookDelivery.id,
            )
            .where(WebhookDeliveryConnectionProcessing.repository_connection_id == connection_id)
            .order_by(WebhookDelivery.received_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        return list((await self._session.execute(stmt)).all())
