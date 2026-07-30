"""Scheduling helpers for webhook delivery processing (ADR-005 §5).

Durable state lives on ``webhook_deliveries``; FastAPI ``BackgroundTasks`` is
the executor. Tests use the synchronous path.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infrastructure.database.session import ensure_session_factory, init_db
from app.infrastructure.integrations.factory import get_github_provider
from app.infrastructure.storage import build_file_storage

logger = structlog.get_logger(__name__)


def _build_service(session: AsyncSession, settings: Settings):
    from app.application.services.github_ingestion_service import GitHubIngestionService

    return GitHubIngestionService(
        session=session,
        settings=settings,
        provider=get_github_provider(settings),
        storage=build_file_storage(settings),
    )


async def process_webhook_delivery_job(delivery_row_id: UUID) -> None:
    """Open a fresh DB session and run ingestion for one delivery."""
    settings = get_settings()
    init_db(settings)
    session_factory = ensure_session_factory()
    async with session_factory() as session:
        service = _build_service(session, settings)
        try:
            await service.process_delivery_id(delivery_row_id)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("webhook_delivery_job_failed", delivery_row_id=str(delivery_row_id))
            raise


async def run_or_schedule_delivery_processing(
    delivery_row_id: UUID,
    *,
    settings: Settings,
    session: AsyncSession,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """Process inline (sync mode) or hand off after the delivery row is durable."""
    if settings.github_webhook_processing_mode == "sync":
        service = _build_service(session, settings)
        await service.process_delivery_id(delivery_row_id, background_tasks=background_tasks)
        return

    # The worker uses its own session, so the delivery row must be committed first.
    await session.commit()
    if background_tasks is None:
        logger.warning(
            "webhook_processing_not_scheduled",
            delivery_row_id=str(delivery_row_id),
            reason="missing_background_tasks",
        )
        return
    background_tasks.add_task(process_webhook_delivery_job, delivery_row_id)
