"""Reasoning providers — local grounded (deterministic) and optional OpenAI."""

from __future__ import annotations

from typing import Any

from app.ai.reasoning.prompt_builder import (
    PROMPT_VERSION,
    SAFETY_RULES,
    build_recommendation_prompt,
    build_root_cause_prompt,
)
from app.ai.reasoning.response_parser import parse_json_response
from app.domain.interfaces.ai_providers import (
    ReasoningProvider,
    RecommendationRequest,
    RootCauseRequest,
)


class LocalGroundedReasoningProvider(ReasoningProvider):
    """Deterministic grounded reasoning for offline / test execution.

    Produces structured output strictly from classifier, evidence, and retrieved docs.
    """

    @property
    def name(self) -> str:
        return f"local-grounded-{PROMPT_VERSION}"

    async def generate_root_cause(self, request: RootCauseRequest) -> dict[str, Any]:
        evidence_ids = [str(item.get("id")) for item in request.evidence[:3] if item.get("id")]
        doc_ids = [
            str(item.get("chunk_id")) for item in request.retrieved_docs[:3] if item.get("chunk_id")
        ]
        doc_snippets = " ".join(
            str(item.get("content") or "")[:180] for item in request.retrieved_docs[:2]
        )
        explanation = request.technical_explanation
        if doc_snippets:
            explanation = (
                f"{request.technical_explanation} Supporting documentation notes: "
                f"{doc_snippets[:300]}"
            )
        confidence = min(0.95, max(0.4, request.classification_confidence))
        if request.retrieved_docs:
            confidence = min(0.97, confidence + 0.03)
        if not evidence_ids:
            raise ValueError("No evidence available for grounded reasoning.")
        return {
            "summary": request.root_cause_summary,
            "root_cause": {
                "category": request.classification_category,
                "explanation": explanation[:1200],
                "confidence": round(confidence, 4),
            },
            "supporting_evidence_ids": evidence_ids,
            "documentation_chunk_ids": doc_ids,
            "alternative_causes": [],
            "impact": (
                "The affected pipeline or infrastructure step did not complete successfully."
            ),
            "prompt_version": PROMPT_VERSION,
            "provider": self.name,
        }

    async def generate_recommendations(
        self,
        request: RecommendationRequest,
    ) -> dict[str, Any]:
        steps = list(request.template_steps)
        if request.retrieved_docs and steps:
            tip = str(request.retrieved_docs[0].get("content") or "")[:200]
            steps[0] = {
                **steps[0],
                "explanation": (
                    f"{steps[0].get('explanation', steps[0].get('action', ''))} Docs: {tip}"
                ).strip(),
            }
        return {"steps": steps, "provider": self.name}


class OpenAIReasoningProvider(ReasoningProvider):
    """Optional OpenAI provider behind the ReasoningProvider interface."""

    def __init__(self, *, api_key: str, model: str = "gpt-4o-mini") -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for LLM_PROVIDER=openai")
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return f"openai:{self._model}"

    async def generate_root_cause(self, request: RootCauseRequest) -> dict[str, Any]:
        prompt = build_root_cause_prompt(
            {
                "classification_category": request.classification_category,
                "classification_confidence": request.classification_confidence,
                "root_cause_summary": request.root_cause_summary,
                "technical_explanation": request.technical_explanation,
                "evidence": request.evidence,
                "retrieved_docs": request.retrieved_docs,
                "signals": request.signals,
                "safety_rules": SAFETY_RULES,
            }
        )
        raw = await self._chat(prompt)
        return parse_json_response(raw)

    async def generate_recommendations(
        self,
        request: RecommendationRequest,
    ) -> dict[str, Any]:
        prompt = build_recommendation_prompt(
            {
                "root_cause": request.root_cause,
                "evidence": request.evidence,
                "retrieved_docs": request.retrieved_docs,
                "template_steps": request.template_steps,
                "safety_rules": SAFETY_RULES,
            }
        )
        raw = await self._chat(prompt)
        return parse_json_response(raw)

    async def _chat(self, prompt: str) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("openai package is required for LLM_PROVIDER=openai") from exc

        client = AsyncOpenAI(api_key=self._api_key)
        response = await client.chat.completions.create(
            model=self._model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are DevGuard AI. Return grounded JSON only. "
                        "Never invent evidence or documentation IDs."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty OpenAI response.")
        return content


def build_reasoning_provider(
    provider: str,
    *,
    api_key: str = "",
    model: str = "gpt-4o-mini",
) -> ReasoningProvider:
    if provider == "openai":
        return OpenAIReasoningProvider(api_key=api_key, model=model)
    return LocalGroundedReasoningProvider()


def dump_prompt_for_debug(request: RootCauseRequest) -> str:
    """Helper for evaluation / debugging (never log secrets)."""
    return build_root_cause_prompt(
        {
            "classification_category": request.classification_category,
            "evidence_count": len(request.evidence),
            "doc_count": len(request.retrieved_docs),
        }
    )
