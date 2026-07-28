"""Cost-aware budget manager using Decimal for monetary values."""

from __future__ import annotations

from decimal import Decimal

from app.ai.orchestration.models import (
    BudgetUsage,
    CostEstimationStatus,
    ExecutionBudget,
    ProviderUsage,
)


class AIExecutionBudgetManager:
    def __init__(
        self,
        budget: ExecutionBudget,
        *,
        llm_input_cost_per_million: Decimal | None = None,
        llm_output_cost_per_million: Decimal | None = None,
        embedding_cost_per_million: Decimal | None = None,
        local_provider: bool = True,
    ) -> None:
        self.budget = budget
        self.usage = BudgetUsage(
            cost_estimation_status=(
                CostEstimationStatus.NOT_APPLICABLE
                if local_provider
                else CostEstimationStatus.UNAVAILABLE
            ),
            estimated_external_cost_usd=Decimal("0") if local_provider else None,
        )
        self._llm_in = llm_input_cost_per_million
        self._llm_out = llm_output_cost_per_million
        self._embed = embedding_cost_per_million
        self._local = local_provider
        self.provider_usage: list[ProviderUsage] = []

    def can_call_provider(self) -> bool:
        max_calls = self.budget.max_provider_calls
        if max_calls is not None and self.usage.provider_calls_used >= max_calls:
            return False
        return not (
            self.budget.max_estimated_cost_usd is not None
            and self.usage.estimated_external_cost_usd is not None
            and self.usage.estimated_external_cost_usd >= self.budget.max_estimated_cost_usd
        )

    def can_retrieve(self) -> bool:
        max_calls = self.budget.max_retrieval_calls
        return not (max_calls is not None and self.usage.retrieval_calls_used >= max_calls)

    def latency_remaining(self, elapsed_ms: int) -> bool:
        self.usage.elapsed_ms = max(0, elapsed_ms)
        if self.budget.max_latency_ms is None:
            return True
        return elapsed_ms < self.budget.max_latency_ms

    def record_retrieval(self, *, latency_ms: int = 0, success: bool = True) -> None:
        self.usage.retrieval_calls_used += 1
        self.provider_usage.append(
            ProviderUsage(
                provider="vector_store",
                model=None,
                operation="retrieval",
                request_count=1,
                input_tokens=None,
                output_tokens=None,
                estimated_external_cost_usd=Decimal("0") if self._local else None,
                cost_estimation_status=(
                    CostEstimationStatus.NOT_APPLICABLE
                    if self._local
                    else CostEstimationStatus.UNAVAILABLE
                ),
                latency_ms=max(0, latency_ms),
                success=success,
                error_type=None if success else "retrieval_failed",
            )
        )

    def record_reasoning(
        self,
        *,
        provider: str,
        model: str | None,
        latency_ms: int,
        success: bool,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        error_type: str | None = None,
    ) -> None:
        self.usage.provider_calls_used += 1
        if input_tokens is not None:
            self.usage.input_tokens_used += max(0, input_tokens)
        if output_tokens is not None:
            self.usage.output_tokens_used += max(0, output_tokens)

        cost, status = self._estimate_cost(
            operation="reasoning",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider=provider,
        )
        if cost is not None:
            current = self.usage.estimated_external_cost_usd or Decimal("0")
            self.usage.estimated_external_cost_usd = current + cost
            self.usage.cost_estimation_status = status
        elif not self._local:
            self.usage.cost_estimation_status = CostEstimationStatus.UNAVAILABLE

        self.provider_usage.append(
            ProviderUsage(
                provider=provider,
                model=model,
                operation="reasoning",
                request_count=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_external_cost_usd=cost,
                cost_estimation_status=status,
                latency_ms=max(0, latency_ms),
                success=success,
                error_type=error_type,
            )
        )

    def _estimate_cost(
        self,
        *,
        operation: str,
        input_tokens: int | None,
        output_tokens: int | None,
        provider: str,
    ) -> tuple[Decimal | None, CostEstimationStatus]:
        if provider.startswith("local") or self._local:
            return Decimal("0"), CostEstimationStatus.NOT_APPLICABLE
        if operation == "reasoning":
            if self._llm_in is None or self._llm_out is None:
                return None, CostEstimationStatus.UNAVAILABLE
            if input_tokens is None and output_tokens is None:
                return None, CostEstimationStatus.UNAVAILABLE
            cost = Decimal("0")
            if input_tokens is not None:
                cost += (Decimal(input_tokens) / Decimal(1_000_000)) * self._llm_in
            if output_tokens is not None:
                cost += (Decimal(output_tokens) / Decimal(1_000_000)) * self._llm_out
            return cost, CostEstimationStatus.CALCULATED
        if operation == "embedding":
            if self._embed is None or input_tokens is None:
                return None, CostEstimationStatus.UNAVAILABLE
            cost = (Decimal(input_tokens) / Decimal(1_000_000)) * self._embed
            return cost, CostEstimationStatus.CALCULATED
        return None, CostEstimationStatus.UNAVAILABLE
