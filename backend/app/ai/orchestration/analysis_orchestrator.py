"""Central analysis orchestrator — Modules 6–8 staged pipeline."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

import structlog

from app.ai.classification.hybrid_classifier import HybridClassifier
from app.ai.evidence.evidence_extractor import EvidenceExtractor
from app.ai.guardrails.output_guardrails import OutputGuardrails
from app.ai.orchestration.adaptive_router import AdaptiveExecutionRouter
from app.ai.orchestration.analysis_context import AnalysisContext, LoadedFile, StageResult
from app.ai.orchestration.budget_manager import AIExecutionBudgetManager
from app.ai.orchestration.confidence_calibrator import RuleBasedConfidenceCalibrator
from app.ai.orchestration.evidence_quality import EvidenceQualityEvaluator
from app.ai.orchestration.final_confidence import FinalConfidenceRecalibrator
from app.ai.orchestration.fusion import DiagnosisFusionService
from app.ai.orchestration.models import (
    ExecutionBudget,
    RetrievalQualityAssessment,
    parse_execution_mode,
)
from app.ai.orchestration.policy import RoutingPolicyConfig
from app.ai.orchestration.retrieval_quality import RetrievalQualityEvaluator
from app.ai.orchestration.uncertainty import UncertaintyEstimator
from app.ai.rag.hybrid_pipeline import HybridRetrievalPipeline
from app.ai.rag.retriever import KnowledgeRetriever
from app.ai.reasoning.root_cause_analyzer import RootCauseAnalyzer
from app.ai.recommendations.recommendation_generator import RecommendationGenerator
from app.domain.enums import AnalysisRunStatus, FileType, RiskLevel
from app.domain.services.file_validation import decode_text_content
from app.domain.services.secret_masker import mask_secrets

logger = structlog.get_logger(__name__)

ProgressCallback = Callable[[AnalysisRunStatus, str, int, list[StageResult]], Any]


class AnalysisOrchestrator:
    """Coordinates stages; scoring formulas live in dedicated services."""

    def __init__(
        self,
        *,
        classifier: HybridClassifier | None = None,
        evidence_extractor: EvidenceExtractor | None = None,
        recommendation_generator: RecommendationGenerator | None = None,
        guardrails: OutputGuardrails | None = None,
        retriever: KnowledgeRetriever | None = None,
        hybrid_retrieval: HybridRetrievalPipeline | None = None,
        root_cause_analyzer: RootCauseAnalyzer | None = None,
        router: AdaptiveExecutionRouter | None = None,
        policy: RoutingPolicyConfig | None = None,
        confidence_calibrator: RuleBasedConfidenceCalibrator | None = None,
        evidence_quality_evaluator: EvidenceQualityEvaluator | None = None,
        uncertainty_estimator: UncertaintyEstimator | None = None,
        retrieval_quality_evaluator: RetrievalQualityEvaluator | None = None,
        fusion_service: DiagnosisFusionService | None = None,
        final_confidence_recalibrator: FinalConfidenceRecalibrator | None = None,
    ) -> None:
        self._classifier = classifier or HybridClassifier()
        self._evidence = evidence_extractor or EvidenceExtractor()
        self._recommendations = recommendation_generator or RecommendationGenerator()
        self._guardrails = guardrails or OutputGuardrails()
        self._retriever = retriever
        self._hybrid_retrieval = hybrid_retrieval
        self._analyzer = root_cause_analyzer
        self._policy = policy or RoutingPolicyConfig(
            enable_rag=True,
            enable_llm=True,
            enable_local_reasoner=True,
        )
        self._router = router or AdaptiveExecutionRouter(self._policy)
        self._calibrator = confidence_calibrator or RuleBasedConfidenceCalibrator()
        self._evidence_quality = evidence_quality_evaluator or EvidenceQualityEvaluator()
        self._uncertainty = uncertainty_estimator or UncertaintyEstimator()
        self._retrieval_quality = retrieval_quality_evaluator or RetrievalQualityEvaluator()
        self._fusion = fusion_service or DiagnosisFusionService()
        self._final_confidence = final_confidence_recalibrator or FinalConfidenceRecalibrator()

    async def run(
        self,
        context: AnalysisContext,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> AnalysisContext:
        pipeline_started = time.perf_counter()

        async def _stage(
            name: str,
            status: AnalysisRunStatus,
            progress: int,
            fn: Callable[[], Any],
            *,
            skip: bool = False,
            skip_reason: str | None = None,
            soft_fail: bool = False,
        ) -> None:
            started = time.perf_counter()
            if skip:
                context.stages.append(
                    StageResult(
                        name=name,
                        status="skipped",
                        duration_ms=0,
                        detail=skip_reason,
                    )
                )
                if on_progress:
                    await _maybe_await(on_progress(status, name, progress, context.stages))
                return
            try:
                result = fn()
                if hasattr(result, "__await__"):
                    await result
                duration = int((time.perf_counter() - started) * 1000)
                context.stages.append(
                    StageResult(name=name, status="completed", duration_ms=duration)
                )
                if on_progress:
                    await _maybe_await(on_progress(status, name, progress, context.stages))
            except Exception as exc:
                duration = int((time.perf_counter() - started) * 1000)
                if soft_fail:
                    context.stages.append(
                        StageResult(
                            name=name,
                            status="failed",
                            duration_ms=duration,
                            detail=str(exc)[:500],
                        )
                    )
                    context.warnings.append(f"{name} failed: {exc}")
                    context.partial = True
                    logger.warning("analysis_stage_soft_fail", stage=name, error=str(exc))
                    if on_progress:
                        await _maybe_await(on_progress(status, name, progress, context.stages))
                    return
                context.stages.append(
                    StageResult(
                        name=name,
                        status="failed",
                        duration_ms=duration,
                        detail=str(exc)[:500],
                    )
                )
                raise

        requested_mode = parse_execution_mode(context.options.get("execution_mode"))
        context.requested_execution_mode = requested_mode
        context.execution_mode = requested_mode.value
        context.effective_execution_mode = requested_mode.value
        risk = _resolve_risk(context)
        context.risk_level = risk.value

        # Request options cannot enable disabled server features; both must allow.
        effective_policy = RoutingPolicyConfig(
            **{
                **self._policy.__dict__,
                "enable_rag": self._policy.enable_rag
                and bool(context.options.get("enable_rag", False)),
                "enable_llm": self._policy.enable_llm
                and bool(context.options.get("enable_llm", False)),
            }
        )
        router = AdaptiveExecutionRouter(effective_policy)

        budget_manager = AIExecutionBudgetManager(
            _build_budget(context, effective_policy),
            llm_input_cost_per_million=_optional_decimal(
                context.options.get("llm_input_cost_usd_per_million_tokens")
            ),
            llm_output_cost_per_million=_optional_decimal(
                context.options.get("llm_output_cost_usd_per_million_tokens")
            ),
            embedding_cost_per_million=_optional_decimal(
                context.options.get("embedding_cost_usd_per_million_tokens")
            ),
            local_provider=str(context.options.get("llm_provider", "local")) == "local",
        )
        context.budget = budget_manager.budget

        await _stage(
            "validating",
            AnalysisRunStatus.PREPROCESSING,
            5,
            lambda: self._validate(context),
        )
        await _stage(
            "masking_secrets",
            AnalysisRunStatus.PREPROCESSING,
            12,
            lambda: self._mask(context),
        )
        await _stage(
            "parsing",
            AnalysisRunStatus.PREPROCESSING,
            18,
            lambda: self._detect_input_type(context),
        )
        await _stage(
            "preprocessing",
            AnalysisRunStatus.PREPROCESSING,
            25,
            lambda: self._normalize(context),
        )
        await _stage(
            "extracting_signals",
            AnalysisRunStatus.CLASSIFYING,
            35,
            lambda: self._extract_signals(context),
        )
        await _stage(
            "classifying",
            AnalysisRunStatus.CLASSIFYING,
            50,
            lambda: self._classifier.classify(context),
        )
        await _stage(
            "extracting_evidence",
            AnalysisRunStatus.CLASSIFYING,
            58,
            lambda: self._evidence.extract(context),
        )

        confidence = self._calibrator.calibrate(context)
        evidence_quality = self._evidence_quality.evaluate(context)
        uncertainty = self._uncertainty.evaluate_baseline(
            context,
            confidence=confidence,
            evidence_quality=evidence_quality,
        )
        context.confidence_assessment = confidence
        context.evidence_quality_assessment = evidence_quality
        context.uncertainty_assessment = uncertainty
        context.confidence_metrics = confidence.to_dict()

        provider_available = self._analyzer is not None
        elapsed_ms = int((time.perf_counter() - pipeline_started) * 1000)
        initial = router.route_initial(
            requested_mode=requested_mode,
            confidence=confidence,
            evidence_quality=evidence_quality,
            uncertainty=uncertainty,
            risk=risk,
            category_code=(
                context.classifications[0].category_code if context.classifications else None
            ),
            budget_manager=budget_manager,
            provider_available=provider_available,
            elapsed_ms=elapsed_ms,
        )
        context.initial_routing_decision = initial
        context.routing_decision = initial.to_dict()

        effective = initial
        if initial.rag_required:
            await _stage(
                "retrieving_knowledge",
                AnalysisRunStatus.RETRIEVING,
                70,
                lambda: self._run_retrieval(context, budget_manager),
                soft_fail=True,
            )
            retrieval_quality = self._retrieval_quality.evaluate(context)
            context.retrieval_quality_assessment = retrieval_quality
            elapsed_ms = int((time.perf_counter() - pipeline_started) * 1000)
            effective = router.route_after_retrieval(
                initial=initial,
                confidence=confidence,
                evidence_quality=evidence_quality,
                uncertainty=uncertainty,
                retrieval_quality=retrieval_quality,
                budget_manager=budget_manager,
                provider_available=provider_available,
                elapsed_ms=elapsed_ms,
            )
            context.post_retrieval_routing_decision = effective
            context.routing_decision = {
                "initial": initial.to_dict(),
                "post_retrieval": effective.to_dict(),
                "selected_route": effective.selected_route.value,
            }
        else:
            context.retrieval_quality_assessment = RetrievalQualityAssessment.not_executed(
                "Retrieval skipped by initial routing decision."
            )
            await _stage(
                "retrieving_knowledge",
                AnalysisRunStatus.RETRIEVING,
                70,
                lambda: None,
                skip=True,
                skip_reason=f"RAG skipped by route '{initial.selected_route.value}'.",
            )

        await _stage(
            "generating_recommendations",
            AnalysisRunStatus.REASONING,
            78,
            lambda: self._recommendations.generate(context),
            skip=not context.generate_recommendations,
            skip_reason="Recommendation generation disabled by options.",
        )

        run_llm = effective.llm_required
        elapsed_ms = int((time.perf_counter() - pipeline_started) * 1000)
        if run_llm and not budget_manager.latency_remaining(elapsed_ms):
            run_llm = False
            context.fallback_used = True
            context.fallback_reason = "Latency budget exhausted before reasoning."
            context.partial = True
        if run_llm and not budget_manager.can_call_provider():
            run_llm = False
            context.fallback_used = True
            context.fallback_reason = "Provider budget exhausted before reasoning."
            context.partial = True

        await _stage(
            "reasoning",
            AnalysisRunStatus.REASONING,
            88,
            lambda: self._run_reasoning(context, budget_manager),
            skip=not run_llm,
            skip_reason=(
                context.fallback_reason
                or f"LLM skipped by route '{effective.selected_route.value}'."
            ),
            soft_fail=True,
        )
        if run_llm and any(s.name == "reasoning" and s.status == "failed" for s in context.stages):
            context.fallback_used = True
            context.fallback_reason = context.fallback_reason or "Reasoning soft-failed."

        await _stage(
            "validating_output",
            AnalysisRunStatus.REASONING,
            92,
            lambda: self._guardrails.validate(context),
        )

        fusion = self._fusion.fuse(
            context,
            confidence=confidence,
            evidence_quality=evidence_quality,
            retrieval_quality=context.retrieval_quality_assessment,
            risk=risk,
        )
        context.fusion_result = fusion
        unsupported = 0
        if context.llm_root_cause:
            cited = set(context.llm_root_cause.get("supporting_evidence_ids") or [])
            known = {f"evidence-{i}" for i in range(1, len(context.evidence) + 1)}
            unsupported = len(cited - known)

        reasoner_conf = None
        if context.llm_root_cause and isinstance(context.llm_root_cause.get("root_cause"), dict):
            try:
                reasoner_conf = float(context.llm_root_cause["root_cause"].get("confidence"))
            except (TypeError, ValueError):
                reasoner_conf = None

        final_conf = self._final_confidence.recalibrate(
            confidence=confidence,
            evidence_quality=evidence_quality,
            retrieval_quality=context.retrieval_quality_assessment,
            fusion=fusion,
            grounding_valid=context.grounding_valid,
            reasoner_confidence=reasoner_conf,
            unsupported_claim_count=unsupported,
            contradiction_count=(
                1
                if (
                    fusion.reasoner_category
                    and not fusion.override_applied
                    and fusion.reasoner_category != fusion.baseline_category
                )
                else 0
            ),
            fallback_used=context.fallback_used,
        )
        context.final_confidence_assessment = final_conf
        if context.classifications:
            context.classifications[0].confidence = final_conf.final_confidence

        context.uncertainty_assessment = self._uncertainty.evaluate_final(
            context,
            confidence=confidence,
            evidence_quality=evidence_quality,
            retrieval_quality=context.retrieval_quality_assessment,
            agreement_status=final_conf.agreement_status,
            unsupported_claims=unsupported,
        )

        total_ms = int((time.perf_counter() - pipeline_started) * 1000)
        budget_manager.usage.elapsed_ms = total_ms
        context.budget_usage = budget_manager.usage
        context.provider_usage = list(budget_manager.provider_usage)
        context.cost_metrics = budget_manager.usage.to_dict()
        context.effective_execution_mode = requested_mode.value
        context.evaluation_metadata = _evaluation_metadata(context, effective, total_ms)

        if on_progress:
            await _maybe_await(
                on_progress(
                    AnalysisRunStatus.REASONING,
                    "persisting",
                    97,
                    context.stages,
                )
            )
        return context

    def _validate(self, context: AnalysisContext) -> None:
        if not context.files:
            raise ValueError("No approved files available for analysis.")
        for loaded in context.files:
            if not loaded.content.strip():
                raise ValueError(f"File '{loaded.original_filename}' is empty after load.")

    def _mask(self, context: AnalysisContext) -> None:
        for loaded in context.files:
            masked, count = mask_secrets(loaded.content)
            loaded.content = masked
            if count:
                context.warnings.append(
                    f"Re-masked {count} secret pattern(s) in {loaded.original_filename}."
                )

    def _detect_input_type(self, context: AnalysisContext) -> None:
        types = {f.file_type for f in context.files}
        if len(types) == 1:
            context.input_type = next(iter(types)).value
        else:
            context.input_type = "mixed"

    def _normalize(self, context: AnalysisContext) -> None:
        parts: list[str] = []
        for loaded in context.files:
            normalized = loaded.content.replace("\r\n", "\n").replace("\r", "\n")
            lines = [line.rstrip() for line in normalized.split("\n")]
            cleaned: list[str] = []
            blank = 0
            for line in lines:
                if line.strip() == "":
                    blank += 1
                    if blank <= 2:
                        cleaned.append("")
                else:
                    blank = 0
                    cleaned.append(line)
            loaded.content = "\n".join(cleaned)
            parts.append(
                f"===== FILE: {loaded.original_filename} ({loaded.file_type.value}) =====\n"
                f"{loaded.content}"
            )
        context.combined_text = "\n\n".join(parts)

    def _extract_signals(self, context: AnalysisContext) -> None:
        text = context.combined_text
        lowered = text.lower()
        provider = None
        if "aws" in lowered or "accessdenied" in lowered or "arn:aws" in lowered:
            provider = "aws"
        elif "terraform" in lowered:
            provider = "terraform"
        elif "docker" in lowered:
            provider = "docker"
        elif "npm" in lowered or "yarn" in lowered:
            provider = "npm"
        context.signals = {
            "line_count": text.count("\n") + 1 if text else 0,
            "char_count": len(text),
            "file_count": len(context.files),
            "input_type": context.input_type,
            "has_error_keyword": "error" in lowered or "failed" in lowered,
            "file_types": sorted({f.file_type.value for f in context.files}),
            "provider": provider,
        }

    def _run_retrieval(
        self,
        context: AnalysisContext,
        budget_manager: AIExecutionBudgetManager,
    ) -> None:
        if self._hybrid_retrieval is None and self._retriever is None:
            raise RuntimeError("RAG enabled but no retriever configured.")
        started = time.perf_counter()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        # Prefer wall time from budget usage when available.
        if budget_manager.usage.elapsed_ms:
            elapsed_ms = budget_manager.usage.elapsed_ms
        try:
            if self._hybrid_retrieval is not None:
                result = self._hybrid_retrieval.retrieve(
                    context,
                    budget_manager=budget_manager,
                    elapsed_ms=elapsed_ms,
                )
                if result.fallback_used and result.fallback_reason:
                    context.warnings.append(result.fallback_reason)
            else:
                assert self._retriever is not None
                self._retriever.retrieve(context)
            budget_manager.record_retrieval(
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=True,
            )
        except Exception:
            budget_manager.record_retrieval(
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=False,
            )
            raise

    async def _run_reasoning(
        self,
        context: AnalysisContext,
        budget_manager: AIExecutionBudgetManager,
    ) -> None:
        if self._analyzer is None:
            raise RuntimeError("LLM enabled but no RootCauseAnalyzer configured.")
        started = time.perf_counter()
        provider = context.reasoning_provider_name or "local-grounded"
        try:
            await self._analyzer.analyze(context)
            budget_manager.record_reasoning(
                provider=provider,
                model=context.reasoning_provider_name,
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=True,
                input_tokens=None,
                output_tokens=None,
            )
        except Exception as exc:
            budget_manager.record_reasoning(
                provider=provider,
                model=context.reasoning_provider_name,
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=False,
                error_type=type(exc).__name__,
            )
            raise


async def _maybe_await(result: Any) -> Any:
    if isinstance(result, Awaitable):
        return await result
    return result


def build_loaded_file(
    *,
    file_id: UUID,
    original_filename: str,
    file_type: FileType,
    raw_bytes: bytes,
    storage_path: str,
) -> LoadedFile:
    """Decode storage bytes into a LoadedFile (expects text already largely masked)."""
    text = decode_text_content(raw_bytes)
    return LoadedFile(
        file_id=file_id,
        original_filename=original_filename,
        file_type=file_type,
        content=text,
        storage_path=storage_path,
    )


def _resolve_risk(context: AnalysisContext) -> RiskLevel:
    server = str(context.options.get("server_risk_level") or "").lower()
    client = str(context.options.get("risk_level") or "medium").lower()
    order = {
        RiskLevel.LOW.value: 0,
        RiskLevel.MEDIUM.value: 1,
        RiskLevel.HIGH.value: 2,
        RiskLevel.CRITICAL.value: 3,
    }
    chosen = client
    if server in order and order[server] > order.get(client, 1):
        chosen = server
    try:
        return RiskLevel(chosen)
    except ValueError:
        return RiskLevel.MEDIUM


def _build_budget(context: AnalysisContext, policy: RoutingPolicyConfig) -> ExecutionBudget:
    req_budget = _optional_decimal(context.options.get("budget_usd"))
    max_budget = policy.max_budget_usd
    effective_budget: Decimal | None
    if req_budget is not None and max_budget is not None:
        effective_budget = min(req_budget, max_budget)
    elif req_budget is not None:
        effective_budget = req_budget
    else:
        effective_budget = max_budget

    req_latency = _optional_int(context.options.get("latency_limit_ms"))
    max_latency = policy.max_latency_ms
    effective_latency = min(req_latency, max_latency) if req_latency is not None else max_latency

    return ExecutionBudget(
        max_provider_calls=policy.max_provider_calls,
        max_input_tokens=_optional_int(context.options.get("max_llm_input_tokens")) or 6000,
        max_output_tokens=_optional_int(context.options.get("max_llm_output_tokens")) or 1500,
        max_estimated_cost_usd=effective_budget,
        max_latency_ms=effective_latency,
        max_retrieval_calls=policy.max_retrieval_calls,
    )


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _evaluation_metadata(context: AnalysisContext, decision, total_ms: int) -> dict[str, Any]:
    primary = context.classifications[0] if context.classifications else None
    return {
        "module": "module_8",
        "research_track": "confidence_and_cost_orchestration",
        "execution_mode": context.requested_execution_mode.value,
        "effective_route": decision.selected_route.value,
        "rag_used": any(
            s.name == "retrieving_knowledge" and s.status == "completed" for s in context.stages
        ),
        "local_reasoner_used": bool(context.reasoning_provider_name)
        and str(context.reasoning_provider_name).startswith("local"),
        "external_llm_used": bool(context.reasoning_provider_name)
        and "openai" in str(context.reasoning_provider_name),
        "fallback_used": context.fallback_used,
        "fallback_reason": context.fallback_reason,
        "baseline_category": (
            context.fusion_result.baseline_category if context.fusion_result else None
        ),
        "final_category": primary.category_code if primary else None,
        "baseline_confidence": (
            context.confidence_assessment.calibrated_confidence
            if context.confidence_assessment
            else None
        ),
        "final_confidence": (
            context.final_confidence_assessment.final_confidence
            if context.final_confidence_assessment
            else None
        ),
        "evidence_quality": (
            context.evidence_quality_assessment.evidence_quality_score
            if context.evidence_quality_assessment
            else None
        ),
        "retrieval_quality": (
            context.retrieval_quality_assessment.retrieval_quality_score
            if context.retrieval_quality_assessment
            else None
        ),
        "uncertainty": (
            context.uncertainty_assessment.uncertainty_score
            if context.uncertainty_assessment
            else None
        ),
        "provider_calls": context.budget_usage.provider_calls_used if context.budget_usage else 0,
        "input_tokens": context.budget_usage.input_tokens_used if context.budget_usage else 0,
        "output_tokens": context.budget_usage.output_tokens_used if context.budget_usage else 0,
        "estimated_external_cost": (
            str(context.budget_usage.estimated_external_cost_usd)
            if context.budget_usage and context.budget_usage.estimated_external_cost_usd is not None
            else None
        ),
        "total_latency_ms": total_ms,
        "stage_latency_ms": {
            s.name: s.duration_ms for s in context.stages if s.duration_ms is not None
        },
        "policy_version": decision.policy_version,
        "configuration_hash": decision.configuration_hash,
    }
