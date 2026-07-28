"""Two-stage adaptive execution router (no provider calls)."""

from __future__ import annotations

from decimal import Decimal

from app.ai.orchestration.budget_manager import AIExecutionBudgetManager
from app.ai.orchestration.models import (
    HIGH_RISK_CATEGORIES,
    ConfidenceAssessment,
    EvidenceQualityAssessment,
    ExecutionMode,
    ExecutionRoute,
    RetrievalQualityAssessment,
    RoutingDecision,
    UncertaintyAssessment,
    parse_execution_mode,
)
from app.ai.orchestration.policy import RoutingPolicyConfig
from app.domain.enums import RiskLevel


class AdaptiveExecutionRouter:
    """Decides what may execute; never calls providers."""

    def __init__(self, policy: RoutingPolicyConfig) -> None:
        policy.validate()
        self._policy = policy
        self._hash = policy.configuration_hash()

    def route_for_mode(
        self,
        mode: ExecutionMode,
        *,
        confidence: ConfidenceAssessment,
        evidence_quality: EvidenceQualityAssessment,
        uncertainty: UncertaintyAssessment,
        risk: RiskLevel,
        stage: str = "initial",
        retrieval_quality: RetrievalQualityAssessment | None = None,
    ) -> RoutingDecision:
        if mode == ExecutionMode.RULES_ONLY:
            route = ExecutionRoute.DETERMINISTIC_ONLY
            return self._decision(
                stage=stage,
                route=route,
                reasons=["Manual/experimental mode rules_only."],
                confidence=confidence,
                evidence_quality=evidence_quality,
                uncertainty=uncertainty,
                retrieval_quality=retrieval_quality,
                rag=False,
                llm=False,
                local=False,
                external=False,
            )
        if mode == ExecutionMode.RULES_RAG:
            return self._decision(
                stage=stage,
                route=ExecutionRoute.DETERMINISTIC_WITH_RAG,
                reasons=["Manual/experimental mode rules_rag."],
                confidence=confidence,
                evidence_quality=evidence_quality,
                uncertainty=uncertainty,
                retrieval_quality=retrieval_quality,
                rag=True,
                llm=False,
                local=False,
                external=False,
            )
        if mode == ExecutionMode.LLM_ONLY:
            return self._decision(
                stage=stage,
                route=ExecutionRoute.LOCAL_REASONING
                if self._policy.enable_local_reasoner
                else ExecutionRoute.EXTERNAL_LLM_WITHOUT_RAG,
                reasons=["Manual/experimental mode llm_only."],
                confidence=confidence,
                evidence_quality=evidence_quality,
                uncertainty=uncertainty,
                retrieval_quality=retrieval_quality,
                rag=False,
                llm=True,
                local=self._policy.enable_local_reasoner,
                external=self._policy.enable_external_llm,
            )
        # rag_llm
        return self._decision(
            stage=stage,
            route=ExecutionRoute.RAG_WITH_LOCAL_REASONING
            if self._policy.enable_local_reasoner
            else ExecutionRoute.RAG_WITH_EXTERNAL_LLM,
            reasons=["Manual/experimental mode rag_llm."],
            confidence=confidence,
            evidence_quality=evidence_quality,
            uncertainty=uncertainty,
            retrieval_quality=retrieval_quality,
            rag=True,
            llm=True,
            local=self._policy.enable_local_reasoner,
            external=self._policy.enable_external_llm,
        )

    def route_initial(
        self,
        *,
        requested_mode: ExecutionMode,
        confidence: ConfidenceAssessment,
        evidence_quality: EvidenceQualityAssessment,
        uncertainty: UncertaintyAssessment,
        risk: RiskLevel,
        category_code: str | None,
        budget_manager: AIExecutionBudgetManager,
        provider_available: bool,
        elapsed_ms: int,
    ) -> RoutingDecision:
        if requested_mode != ExecutionMode.CONFIDENCE_ROUTED:
            decision = self.route_for_mode(
                requested_mode,
                confidence=confidence,
                evidence_quality=evidence_quality,
                uncertainty=uncertainty,
                risk=risk,
                stage="initial",
            )
            return self._apply_flags_and_budget(
                decision,
                budget_manager=budget_manager,
                provider_available=provider_available,
                elapsed_ms=elapsed_ms,
                allow_rag_check=True,
            )

        conf = confidence.calibrated_confidence
        evid = evidence_quality.evidence_quality_score
        unc = uncertainty.uncertainty_score
        high_risk = risk in {RiskLevel.HIGH, RiskLevel.CRITICAL} or (
            category_code in HIGH_RISK_CATEGORIES
        )
        reasons: list[str] = []

        if (
            conf >= self._policy.confidence_high_threshold
            and unc < self._policy.uncertainty_medium_threshold
            and evid >= self._policy.min_evidence_quality_for_deterministic
        ):
            if high_risk and self._policy.high_risk_requires_validation:
                reasons.append("High confidence but high-risk requires validation via RAG.")
                route = ExecutionRoute.DETERMINISTIC_WITH_RAG
                rag, llm = True, False
            else:
                reasons.append("High confidence, low uncertainty, strong evidence.")
                route = ExecutionRoute.DETERMINISTIC_ONLY
                rag, llm = False, False
        elif conf >= self._policy.confidence_medium_threshold:
            reasons.append("Medium confidence; retrieve documentation for grounding.")
            route = ExecutionRoute.DETERMINISTIC_WITH_RAG
            rag, llm = True, False
            if unc >= self._policy.uncertainty_medium_threshold:
                reasons.append("Uncertainty suggests local reasoning after retrieval.")
                route = ExecutionRoute.RAG_WITH_LOCAL_REASONING
                llm = True
        else:
            reasons.append("Low confidence/ambiguity; grounded reasoning preferred.")
            route = ExecutionRoute.RAG_WITH_LOCAL_REASONING
            rag, llm = True, True
            if self._policy.enable_external_llm and provider_available:
                route = ExecutionRoute.RAG_WITH_EXTERNAL_LLM

        decision = self._decision(
            stage="initial",
            route=route,
            reasons=reasons,
            confidence=confidence,
            evidence_quality=evidence_quality,
            uncertainty=uncertainty,
            retrieval_quality=None,
            rag=rag,
            llm=llm,
            local=self._policy.enable_local_reasoner,
            external=self._policy.enable_external_llm,
        )
        return self._apply_flags_and_budget(
            decision,
            budget_manager=budget_manager,
            provider_available=provider_available,
            elapsed_ms=elapsed_ms,
            allow_rag_check=True,
        )

    def route_after_retrieval(
        self,
        *,
        initial: RoutingDecision,
        confidence: ConfidenceAssessment,
        evidence_quality: EvidenceQualityAssessment,
        uncertainty: UncertaintyAssessment,
        retrieval_quality: RetrievalQualityAssessment,
        budget_manager: AIExecutionBudgetManager,
        provider_available: bool,
        elapsed_ms: int,
    ) -> RoutingDecision:
        reasons = list(initial.decision_reasons)
        route = initial.selected_route
        rag = False  # already executed
        llm = initial.llm_required
        rq = retrieval_quality.retrieval_quality_score

        if not retrieval_quality.retrieval_executed:
            reasons.append("Retrieval marked not executed.")
            llm = False
            route = ExecutionRoute.SAFE_FALLBACK
        elif rq is not None and rq < self._policy.min_retrieval_quality_for_reasoning:
            reasons.append("Weak retrieval quality; avoid unsupported external reasoning.")
            if initial.llm_required and self._policy.enable_local_reasoner:
                route = ExecutionRoute.LOCAL_REASONING
                llm = True
            else:
                route = ExecutionRoute.SAFE_FALLBACK
                llm = False
        elif retrieval_quality.documents_selected == 0:
            reasons.append("Empty retrieval; use deterministic fallback.")
            route = ExecutionRoute.SAFE_FALLBACK
            llm = False
        elif initial.llm_required:
            reasons.append("Strong enough retrieval; reasoning may proceed.")
            llm = True

        decision = self._decision(
            stage="post_retrieval",
            route=route,
            reasons=reasons,
            confidence=confidence,
            evidence_quality=evidence_quality,
            uncertainty=uncertainty,
            retrieval_quality=retrieval_quality,
            rag=rag,
            llm=llm,
            local=self._policy.enable_local_reasoner,
            external=self._policy.enable_external_llm,
        )
        return self._apply_flags_and_budget(
            decision,
            budget_manager=budget_manager,
            provider_available=provider_available,
            elapsed_ms=elapsed_ms,
            allow_rag_check=False,
        )

    def _apply_flags_and_budget(
        self,
        decision: RoutingDecision,
        *,
        budget_manager: AIExecutionBudgetManager,
        provider_available: bool,
        elapsed_ms: int,
        allow_rag_check: bool,
    ) -> RoutingDecision:
        reasons = list(decision.decision_reasons)
        rag = decision.rag_required and self._policy.enable_rag
        llm = decision.llm_required and self._policy.enable_llm
        local = decision.local_reasoning_allowed and self._policy.enable_local_reasoner
        external = decision.external_reasoning_allowed and self._policy.enable_external_llm

        if allow_rag_check and rag and not budget_manager.can_retrieve():
            rag = False
            reasons.append("Retrieval budget exhausted.")
        if llm and not budget_manager.can_call_provider():
            llm = False
            reasons.append("Provider call budget exhausted.")
        if llm and not budget_manager.latency_remaining(elapsed_ms):
            llm = False
            reasons.append("Latency budget exhausted before expensive stage.")
        if llm and not provider_available and not local:
            llm = False
            reasons.append("Provider unavailable; safe fallback.")
        if external and not provider_available:
            external = False
            reasons.append("External provider unavailable.")

        route = decision.selected_route
        if not rag and not llm:
            route = ExecutionRoute.DETERMINISTIC_ONLY
        elif rag and not llm:
            route = ExecutionRoute.DETERMINISTIC_WITH_RAG
        elif llm and not rag:
            route = (
                ExecutionRoute.LOCAL_REASONING if local else ExecutionRoute.EXTERNAL_LLM_WITHOUT_RAG
            )
        elif llm and rag:
            route = (
                ExecutionRoute.RAG_WITH_LOCAL_REASONING
                if local
                else ExecutionRoute.RAG_WITH_EXTERNAL_LLM
            )

        return RoutingDecision(
            decision_stage=decision.decision_stage,
            selected_route=route,
            decision_reasons=reasons,
            baseline_confidence=decision.baseline_confidence,
            calibrated_confidence=decision.calibrated_confidence,
            uncertainty_score=decision.uncertainty_score,
            evidence_quality_score=decision.evidence_quality_score,
            retrieval_quality_score=decision.retrieval_quality_score,
            expected_cost_usd=decision.expected_cost_usd,
            expected_latency_ms=decision.expected_latency_ms,
            rag_required=rag,
            llm_required=llm,
            local_reasoning_allowed=local,
            external_reasoning_allowed=external,
            fallback_route=ExecutionRoute.SAFE_FALLBACK,
            policy_name=self._policy.policy_name,
            policy_version=self._policy.policy_version,
            configuration_hash=self._hash,
        )

    def _decision(
        self,
        *,
        stage: str,
        route: ExecutionRoute,
        reasons: list[str],
        confidence: ConfidenceAssessment,
        evidence_quality: EvidenceQualityAssessment,
        uncertainty: UncertaintyAssessment,
        retrieval_quality: RetrievalQualityAssessment | None,
        rag: bool,
        llm: bool,
        local: bool,
        external: bool,
    ) -> RoutingDecision:
        return RoutingDecision(
            decision_stage=stage,
            selected_route=route,
            decision_reasons=reasons,
            baseline_confidence=confidence.raw_confidence,
            calibrated_confidence=confidence.calibrated_confidence,
            uncertainty_score=uncertainty.uncertainty_score,
            evidence_quality_score=evidence_quality.evidence_quality_score,
            retrieval_quality_score=(
                retrieval_quality.retrieval_quality_score if retrieval_quality else None
            ),
            expected_cost_usd=None,
            expected_latency_ms=None,
            rag_required=rag,
            llm_required=llm,
            local_reasoning_allowed=local,
            external_reasoning_allowed=external,
            fallback_route=ExecutionRoute.SAFE_FALLBACK,
            policy_name=self._policy.policy_name,
            policy_version=self._policy.policy_version,
            configuration_hash=self._hash,
        )


# Backward-compatible alias used by older imports/tests.
class ConfidenceCostRouter(AdaptiveExecutionRouter):
    """Deprecated alias retained for Module 8 migration of tests."""

    def __init__(self, policy: RoutingPolicyConfig | None = None) -> None:
        super().__init__(policy or RoutingPolicyConfig())

    def route(self, context, *, provider_available: bool):  # type: ignore[no-untyped-def]
        # Minimal shim for old unit tests; prefer route_initial/route_after_retrieval.
        mode = parse_execution_mode(context.options.get("execution_mode"))
        from app.ai.orchestration.confidence_calibrator import RuleBasedConfidenceCalibrator
        from app.ai.orchestration.evidence_quality import EvidenceQualityEvaluator
        from app.ai.orchestration.uncertainty import UncertaintyEstimator

        conf = RuleBasedConfidenceCalibrator().calibrate(context)
        evid = EvidenceQualityEvaluator().evaluate(context)
        unc = UncertaintyEstimator().evaluate_baseline(
            context, confidence=conf, evidence_quality=evid
        )
        budget = AIExecutionBudgetManager(
            type(self)._empty_budget(),  # noqa: SLF001
            local_provider=True,
        )
        risk = RiskLevel(str(context.options.get("risk_level", "medium")))
        decision = self.route_initial(
            requested_mode=mode,
            confidence=conf,
            evidence_quality=evid,
            uncertainty=unc,
            risk=risk,
            category_code=(
                context.classifications[0].category_code if context.classifications else None
            ),
            budget_manager=budget,
            provider_available=provider_available,
            elapsed_ms=0,
        )
        context.execution_mode = mode.value
        context.routing_decision = decision.to_dict()
        context.confidence_metrics = conf.to_dict()
        return {
            "mode": mode.value,
            "enable_rag": decision.rag_required,
            "enable_llm": decision.llm_required,
            "reason": "; ".join(decision.decision_reasons),
        }

    @staticmethod
    def _empty_budget():
        from app.ai.orchestration.models import ExecutionBudget

        return ExecutionBudget(
            max_provider_calls=2,
            max_retrieval_calls=2,
            max_latency_ms=30_000,
            max_estimated_cost_usd=Decimal("1.00"),
        )
