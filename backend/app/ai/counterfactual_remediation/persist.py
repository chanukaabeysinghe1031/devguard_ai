"""Persistence interface/stub for counterfactual remediation (Part 1)."""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from app.ai.counterfactual_remediation.model_types import (
    CounterfactualRemediationCandidate,
    CounterfactualRemediationRun,
    RemediationConstraint,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class CounterfactualRemediationRepository(Protocol):
    async def create_run(self, run: CounterfactualRemediationRun) -> CounterfactualRemediationRun: ...

    async def create_candidate(
        self,
        candidate: CounterfactualRemediationCandidate,
    ) -> CounterfactualRemediationCandidate: ...

    async def create_constraints_batch(
        self,
        constraints: list[RemediationConstraint],
    ) -> list[RemediationConstraint]: ...


class CounterfactualRemediationPersistService:
    """No-op when persistence disabled; optional repository protocol when enabled."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        repository: CounterfactualRemediationRepository | None = None,
    ) -> None:
        self._enabled = enabled
        self._repository = repository

    @property
    def enabled(self) -> bool:
        return self._enabled and self._repository is not None

    async def create_run(
        self,
        run: CounterfactualRemediationRun,
    ) -> CounterfactualRemediationRun | None:
        if not self.enabled:
            logger.debug("counterfactual_persist_skipped create_run")
            return None
        assert self._repository is not None
        return await self._repository.create_run(run)

    async def create_candidate(
        self,
        candidate: CounterfactualRemediationCandidate,
    ) -> CounterfactualRemediationCandidate | None:
        if not self.enabled:
            logger.debug("counterfactual_persist_skipped create_candidate")
            return None
        assert self._repository is not None
        return await self._repository.create_candidate(candidate)

    async def create_constraints_batch(
        self,
        constraints: list[RemediationConstraint],
    ) -> list[RemediationConstraint] | None:
        if not self.enabled:
            logger.debug(
                "counterfactual_persist_skipped create_constraints_batch count=%s",
                len(constraints),
            )
            return None
        assert self._repository is not None
        return await self._repository.create_constraints_batch(constraints)

    async def persist_foundation_result(self, payload: dict[str, Any]) -> None:
        """Optional hook for foundation service — no-op when disabled."""
        if not self.enabled:
            return
        run = payload.get("run")
        if isinstance(run, CounterfactualRemediationRun):
            await self.create_run(run)
        for candidate in payload.get("candidates") or []:
            if isinstance(candidate, CounterfactualRemediationCandidate):
                await self.create_candidate(candidate)
        constraints = payload.get("constraints") or []
        typed = [c for c in constraints if isinstance(c, RemediationConstraint)]
        if typed:
            await self.create_constraints_batch(typed)
