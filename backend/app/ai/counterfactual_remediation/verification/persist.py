"""Persistence stub protocol for Phase 6A.6 Part 3 verifier results (ORM later)."""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from app.domain.counterfactual_remediation.verification_models import (
    VerificationReport,
    VerificationRun,
    VerifierResult,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class VerificationPersistRepository(Protocol):
    """ORM repository surface used by VerificationPersistService.persist_report."""

    async def upsert_run(self, run: Any) -> Any: ...


# Alias for draft callers.
VerificationRepositoryProtocol = VerificationPersistRepository


class VerificationPersistService:
    """Optional persistence facade. No-op until VERIFIER_PERSISTENCE_ENABLED + ORM."""

    def __init__(
        self,
        repository: VerificationPersistRepository | None = None,
        *,
        enabled: bool = False,
    ) -> None:
        self._repository = repository
        self._repo = repository
        self._enabled = enabled

    def save_run(self, run: VerificationRun) -> VerificationRun:
        if not self._enabled or self._repository is None:
            return run
        logger.debug("verification persist stub: save_run %s", run.id)
        return run

    def save_results(
        self,
        results: list[VerifierResult],
        *,
        run_id: str,
    ) -> list[VerifierResult]:
        if not self._enabled or self._repository is None:
            return results
        logger.debug(
            "verification persist stub: save_results run=%s count=%s",
            run_id,
            len(results),
        )
        return results

    def save_report(self, report: VerificationReport) -> VerificationReport:
        if not self._enabled or self._repository is None:
            return report
        logger.debug(
            "verification persist stub: save_report analysis=%s runs=%s",
            report.analysis_id,
            len(report.runs),
        )
        return report

    async def persist_report(self, report: VerificationReport) -> None:
        if not self._enabled or self._repository is None:
            return
        for run in report.runs:
            if not run.candidate_id:
                continue
            try:
                await self._repository.upsert_run(run)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "verification_persist_run_failed",
                    extra={"error": type(exc).__name__, "run_id": run.id},
                )


class NoOpVerificationPersistService(VerificationPersistService):
    """Explicit no-op persist used by default in Part 3 engine."""

    def __init__(self) -> None:
        super().__init__(repository=None, enabled=False)


def build_persist_service(settings: Any = None) -> VerificationPersistService:
    enabled = bool(getattr(settings, "verifier_persistence_enabled", False)) if settings else False
    if not enabled:
        return NoOpVerificationPersistService()
    return VerificationPersistService(repository=None, enabled=True)
