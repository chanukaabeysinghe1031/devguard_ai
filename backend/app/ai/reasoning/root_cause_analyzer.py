"""Root-cause analyzer — LLM reasoning with grounding validation and fallback."""

from __future__ import annotations

from typing import Any

import structlog

from app.ai.orchestration.analysis_context import (
    AnalysisContext,
    RecommendationCandidate,
    RecommendationStepCandidate,
)
from app.ai.rag.citation_builder import mark_used_chunks
from app.ai.reasoning.output_validator import (
    GroundingValidationError,
    validate_recommendation_output,
    validate_root_cause_output,
)
from app.ai.reasoning.prompt_builder import SAFETY_RULES
from app.domain.interfaces.ai_providers import (
    ReasoningProvider,
    RecommendationRequest,
    RootCauseRequest,
)
from app.domain.services.secret_masker import mask_secrets

logger = structlog.get_logger(__name__)


class RootCauseAnalyzer:
    def __init__(self, provider: ReasoningProvider) -> None:
        self._provider = provider

    async def analyze(self, context: AnalysisContext) -> dict[str, Any] | None:
        if not context.classifications:
            context.warnings.append("LLM skipped: no classification available.")
            context.partial = True
            return None

        primary = context.classifications[0]
        evidence_payload = _evidence_payload(context)
        docs_payload = _docs_payload(context)
        request = RootCauseRequest(
            classification_category=primary.category_code,
            classification_confidence=primary.confidence,
            root_cause_summary=primary.root_cause_summary,
            technical_explanation=primary.technical_explanation,
            evidence=evidence_payload,
            retrieved_docs=docs_payload,
            signals=dict(context.signals or {}),
            safety_rules=list(SAFETY_RULES),
        )

        try:
            raw = await self._provider.generate_root_cause(request)
            validated = validate_root_cause_output(raw, context)
        except (GroundingValidationError, ValueError, RuntimeError) as exc:
            context.warnings.append(f"LLM reasoning fallback: {exc}")
            context.partial = True
            context.llm_root_cause = None
            context.grounding_valid = False
            logger.warning("llm_reasoning_fallback", error=str(exc))
            return None

        # Re-mask any accidental secrets in model text.
        summary, _ = mask_secrets(str(validated["summary"]))
        explanation, _ = mask_secrets(str(validated["root_cause"]["explanation"]))
        validated["summary"] = summary
        validated["root_cause"]["explanation"] = explanation

        mark_used_chunks(context, [str(x) for x in validated.get("documentation_chunk_ids") or []])
        primary.root_cause_summary = summary
        primary.technical_explanation = explanation
        primary.confidence = float(validated["root_cause"]["confidence"])
        if validated["root_cause"].get("impact"):
            primary.impact_summary = str(validated.get("impact") or primary.impact_summary)

        context.llm_root_cause = validated
        context.grounding_valid = True
        context.reasoning_provider_name = self._provider.name
        context.model_name = self._provider.name

        if context.generate_recommendations:
            await self._adapt_recommendations(context, validated, evidence_payload, docs_payload)
        return validated

    async def _adapt_recommendations(
        self,
        context: AnalysisContext,
        root_cause: dict[str, Any],
        evidence_payload: list[dict[str, Any]],
        docs_payload: list[dict[str, Any]],
    ) -> None:
        template_steps = []
        if context.recommendation is not None:
            template_steps = [
                {
                    "step_number": step.step_number,
                    "step_type": step.step_type,
                    "title": step.title,
                    "action": step.action,
                    "explanation": step.explanation,
                    "expected_result": step.expected_result,
                    "risk_level": step.risk_level,
                    "difficulty": step.difficulty,
                    "command_template": step.command_template,
                }
                for step in context.recommendation.steps
            ]
        try:
            raw = await self._provider.generate_recommendations(
                RecommendationRequest(
                    root_cause=root_cause,
                    evidence=evidence_payload,
                    retrieved_docs=docs_payload,
                    template_steps=template_steps,
                )
            )
            validated = validate_recommendation_output(raw)
        except (GroundingValidationError, ValueError, RuntimeError) as exc:
            context.warnings.append(f"LLM recommendation adaptation skipped: {exc}")
            return

        steps = [
            RecommendationStepCandidate(
                step_number=int(step["step_number"]),
                step_type=str(step["step_type"]),
                title=str(step["title"]),
                action=str(step["action"]),
                explanation=str(step.get("explanation")),
                expected_result=str(step.get("expected_result")),
                risk_level=str(step.get("risk_level")),
                difficulty=str(step.get("difficulty")),
                command_template=step.get("command_template"),
            )
            for step in validated["steps"]
        ]
        context.recommendation = RecommendationCandidate(
            root_cause_summary=str(root_cause.get("summary") or ""),
            explanation=str(root_cause.get("root_cause", {}).get("explanation") or ""),
            confidence_score=float(root_cause.get("root_cause", {}).get("confidence") or 0.5),
            steps=steps,
            llm_model=self._provider.name,
        )


def _evidence_payload(context: AnalysisContext) -> list[dict[str, Any]]:
    payload = []
    for idx, item in enumerate(context.evidence, start=1):
        evidence_id = f"evidence-{idx}"
        item.metadata = {**(item.metadata or {}), "evidence_id": evidence_id}
        masked, _ = mask_secrets(item.normalized_excerpt)
        payload.append(
            {
                "id": evidence_id,
                "excerpt": masked[:500],
                "explanation": item.explanation,
                "source_name": item.source_name,
                "importance_score": item.importance_score,
            }
        )
    return payload


def _docs_payload(context: AnalysisContext) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": str(chunk.chunk_id),
            "title": chunk.title,
            "provider": chunk.provider,
            "source_url": chunk.source_url,
            "content": chunk.content[:700],
            "similarity_score": chunk.similarity_score,
        }
        for chunk in context.retrieved_chunks
    ]
