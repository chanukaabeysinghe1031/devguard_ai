"""Helpers to schedule analysis-run execution."""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import BackgroundTasks

from app.core.config import Settings, get_settings
from app.infrastructure.database.session import ensure_session_factory, init_db
from app.infrastructure.storage import build_file_storage

logger = structlog.get_logger(__name__)


async def execute_analysis_run_job(analysis_run_id: UUID) -> None:
    """Open a fresh DB session and execute the analysis pipeline."""
    settings = get_settings()
    init_db(settings)
    session_factory = ensure_session_factory()
    storage = build_file_storage(settings)
    async with session_factory() as session:
        from app.application.services.analysis_execution_service import AnalysisExecutionService

        service = AnalysisExecutionService(
            session=session,
            settings=settings,
            storage=storage,
        )
        await service.execute(analysis_run_id)


def schedule_analysis_execution(
    analysis_run_id: UUID,
    *,
    settings: Settings,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """Schedule sync or background execution based on settings."""
    if settings.analysis_execution_mode == "sync":
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(execute_analysis_run_job(analysis_run_id))
            return
        # Already in async context (e.g. FastAPI sync mode during request).
        loop.create_task(execute_analysis_run_job(analysis_run_id))
        return

    if background_tasks is None:
        logger.warning(
            "analysis_execution_not_scheduled",
            analysis_run_id=str(analysis_run_id),
            reason="missing_background_tasks",
        )
        return

    background_tasks.add_task(execute_analysis_run_job, analysis_run_id)
