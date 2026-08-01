"""Persistence interface for counterfactual remediation (Part 1)."""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from app.ai.counterfactual_remediation.model_types import (
    CounterfactualChange,
    CounterfactualPrecondition,
    CounterfactualRemediationCandidate,
    CounterfactualRemediationRun,
    RemediationConstraint,
    RemediationRiskSignal,
    RemediationVerificationRequirement,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class CounterfactualRemediationRepository(Protocol):
    async def create_run(
        self, run: CounterfactualRemediationRun
    ) -> CounterfactualRemediationRun | None: ...

    async def update_run(
        self, run: CounterfactualRemediationRun
    ) -> CounterfactualRemediationRun | None: ...

    async def create_candidate(
        self,
        candidate: CounterfactualRemediationCandidate,
    ) -> CounterfactualRemediationCandidate | None: ...

    async def create_constraints_batch(
        self,
        constraints: list[RemediationConstraint],
        *,
        remediation_run_id: str | None = None,
    ) -> list[RemediationConstraint]: ...

    async def create_changes_batch(
        self,
        changes: list[CounterfactualChange],
        *,
        remediation_run_id: str,
        organization_id: str,
        analysis_run_id: str,
        hypothesis_id: str | None = None,
        candidate_id: str | None = None,
    ) -> list[CounterfactualChange]: ...

    async def create_preconditions_batch(
        self,
        preconditions: list[CounterfactualPrecondition],
        *,
        remediation_run_id: str,
        organization_id: str,
        analysis_run_id: str,
        candidate_id: str | None = None,
    ) -> list[CounterfactualPrecondition]: ...

    async def create_verification_requirements_batch(
        self,
        requirements: list[RemediationVerificationRequirement],
        *,
        remediation_run_id: str,
        organization_id: str,
        analysis_run_id: str,
        candidate_id: str | None = None,
    ) -> list[RemediationVerificationRequirement]: ...

    async def create_risk_signals_batch(
        self,
        signals: list[RemediationRiskSignal],
        *,
        remediation_run_id: str,
        organization_id: str,
        analysis_run_id: str,
        candidate_id: str,
    ) -> list[RemediationRiskSignal]: ...

    async def list_candidates_by_analysis(
        self,
        *,
        organization_id: str,
        analysis_run_id: str,
        hypothesis_id: str | None = None,
        status: str | None = None,
        artifact_type: str | None = None,
        template_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Any]: ...

    async def get_candidate_by_id(
        self,
        *,
        organization_id: str,
        candidate_id: str,
    ) -> Any | None: ...


class CounterfactualRemediationPersistService:
    """No-op when persistence disabled; uses repository when enabled."""

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

    async def update_run(
        self,
        run: CounterfactualRemediationRun,
    ) -> CounterfactualRemediationRun | None:
        if not self.enabled:
            logger.debug("counterfactual_persist_skipped update_run")
            return None
        assert self._repository is not None
        return await self._repository.update_run(run)

    async def create_candidate(
        self,
        candidate: CounterfactualRemediationCandidate,
    ) -> CounterfactualRemediationCandidate | None:
        if not self.enabled:
            logger.debug("counterfactual_persist_skipped create_candidate")
            return None
        assert self._repository is not None
        return await self._repository.create_candidate(candidate)

    async def update_candidate(
        self,
        candidate: CounterfactualRemediationCandidate,
    ) -> CounterfactualRemediationCandidate | None:
        if not self.enabled:
            logger.debug("counterfactual_persist_skipped update_candidate")
            return None
        assert self._repository is not None
        updater = getattr(self._repository, "update_candidate", None)
        if callable(updater):
            return await updater(candidate)
        return await self._repository.create_candidate(candidate)

    async def persist_generated_candidates(
        self,
        *,
        run: CounterfactualRemediationRun,
        candidates: list[CounterfactualRemediationCandidate],
    ) -> list[CounterfactualRemediationCandidate]:
        """Persist Part 2 generated candidates with changes and risk signals."""
        if not self.enabled:
            return []
        saved: list[CounterfactualRemediationCandidate] = []
        await self.update_run(run)
        for candidate in candidates:
            persisted = await self.update_candidate(candidate)
            if persisted is None:
                continue
            saved.append(persisted)
            if candidate.changes:
                await self.create_changes_batch(
                    list(candidate.changes),
                    remediation_run_id=run.id,
                    organization_id=run.organization_id,
                    analysis_run_id=run.analysis_id,
                    hypothesis_id=candidate.hypothesis_id,
                    candidate_id=candidate.id,
                )
            risk_items = [
                item
                for item in (candidate.risk_summary or [])
                if isinstance(item, RemediationRiskSignal)
            ]
            if risk_items:
                await self.create_risk_signals_batch(
                    risk_items,
                    remediation_run_id=run.id,
                    organization_id=run.organization_id,
                    analysis_run_id=run.analysis_id,
                    candidate_id=candidate.id,
                )
        return saved

    async def create_constraints_batch(
        self,
        constraints: list[RemediationConstraint],
        *,
        remediation_run_id: str | None = None,
    ) -> list[RemediationConstraint] | None:
        if not self.enabled:
            logger.debug(
                "counterfactual_persist_skipped create_constraints_batch count=%s",
                len(constraints),
            )
            return None
        assert self._repository is not None
        return await self._repository.create_constraints_batch(
            constraints,
            remediation_run_id=remediation_run_id,
        )

    async def create_changes_batch(
        self,
        changes: list[CounterfactualChange],
        *,
        remediation_run_id: str,
        organization_id: str,
        analysis_run_id: str,
        hypothesis_id: str | None = None,
        candidate_id: str | None = None,
    ) -> list[CounterfactualChange] | None:
        if not self.enabled:
            logger.debug(
                "counterfactual_persist_skipped create_changes_batch count=%s",
                len(changes),
            )
            return None
        assert self._repository is not None
        return await self._repository.create_changes_batch(
            changes,
            remediation_run_id=remediation_run_id,
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            hypothesis_id=hypothesis_id,
            candidate_id=candidate_id,
        )

    async def create_preconditions_batch(
        self,
        preconditions: list[CounterfactualPrecondition],
        *,
        remediation_run_id: str,
        organization_id: str,
        analysis_run_id: str,
        candidate_id: str | None = None,
    ) -> list[CounterfactualPrecondition] | None:
        if not self.enabled:
            logger.debug(
                "counterfactual_persist_skipped create_preconditions_batch count=%s",
                len(preconditions),
            )
            return None
        assert self._repository is not None
        return await self._repository.create_preconditions_batch(
            preconditions,
            remediation_run_id=remediation_run_id,
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )

    async def create_verification_requirements_batch(
        self,
        requirements: list[RemediationVerificationRequirement],
        *,
        remediation_run_id: str,
        organization_id: str,
        analysis_run_id: str,
        candidate_id: str | None = None,
    ) -> list[RemediationVerificationRequirement] | None:
        if not self.enabled:
            logger.debug(
                "counterfactual_persist_skipped create_verification_requirements count=%s",
                len(requirements),
            )
            return None
        assert self._repository is not None
        return await self._repository.create_verification_requirements_batch(
            requirements,
            remediation_run_id=remediation_run_id,
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )

    async def create_risk_signals_batch(
        self,
        signals: list[RemediationRiskSignal],
        *,
        remediation_run_id: str,
        organization_id: str,
        analysis_run_id: str,
        candidate_id: str,
    ) -> list[RemediationRiskSignal] | None:
        if not self.enabled:
            logger.debug(
                "counterfactual_persist_skipped create_risk_signals_batch count=%s",
                len(signals),
            )
            return None
        assert self._repository is not None
        return await self._repository.create_risk_signals_batch(
            signals,
            remediation_run_id=remediation_run_id,
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )

    async def list_candidates_by_analysis(
        self,
        *,
        organization_id: str,
        analysis_run_id: str,
        hypothesis_id: str | None = None,
        status: str | None = None,
        artifact_type: str | None = None,
        template_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Any] | None:
        if not self.enabled:
            return None
        assert self._repository is not None
        return await self._repository.list_candidates_by_analysis(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            hypothesis_id=hypothesis_id,
            status=status,
            artifact_type=artifact_type,
            template_id=template_id,
            limit=limit,
            offset=offset,
        )

    async def get_candidate_by_id(
        self,
        *,
        organization_id: str,
        candidate_id: str,
    ) -> Any | None:
        if not self.enabled:
            return None
        assert self._repository is not None
        return await self._repository.get_candidate_by_id(
            organization_id=organization_id,
            candidate_id=candidate_id,
        )

    async def persist_foundation_result(self, payload: dict[str, Any]) -> None:
        """Optional hook for foundation service — no-op when disabled."""
        if not self.enabled:
            return
        run = payload.get("run")
        if isinstance(run, CounterfactualRemediationRun):
            await self.create_run(run)
            run_id = run.id
            org_id = run.organization_id
            analysis_id = run.analysis_id
        else:
            run_id = None
            org_id = None
            analysis_id = None

        for candidate in payload.get("candidates") or []:
            if not isinstance(candidate, CounterfactualRemediationCandidate):
                continue
            await self.create_candidate(candidate)
            if run_id and org_id and analysis_id:
                if candidate.changes:
                    await self.create_changes_batch(
                        list(candidate.changes),
                        remediation_run_id=run_id,
                        organization_id=org_id,
                        analysis_run_id=analysis_id,
                        hypothesis_id=candidate.hypothesis_id,
                        candidate_id=candidate.id,
                    )
                if candidate.verification_requirements:
                    await self.create_verification_requirements_batch(
                        list(candidate.verification_requirements),
                        remediation_run_id=run_id,
                        organization_id=org_id,
                        analysis_run_id=analysis_id,
                        candidate_id=candidate.id,
                    )
                risk_items = [
                    item
                    for item in (candidate.risk_summary or [])
                    if isinstance(item, RemediationRiskSignal)
                ]
                if risk_items:
                    await self.create_risk_signals_batch(
                        risk_items,
                        remediation_run_id=run_id,
                        organization_id=org_id,
                        analysis_run_id=analysis_id,
                        candidate_id=candidate.id,
                    )

        constraints = payload.get("constraints") or []
        typed = [c for c in constraints if isinstance(c, RemediationConstraint)]
        if typed:
            await self.create_constraints_batch(
                typed,
                remediation_run_id=run_id,
            )

        preconditions = payload.get("preconditions") or []
        typed_pre = [p for p in preconditions if isinstance(p, CounterfactualPrecondition)]
        if typed_pre and run_id and org_id and analysis_id:
            await self.create_preconditions_batch(
                typed_pre,
                remediation_run_id=run_id,
                organization_id=org_id,
                analysis_run_id=analysis_id,
            )
