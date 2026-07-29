"""Reasoning providers — local grounded (deterministic) and optional OpenAI."""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import structlog

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

logger = structlog.get_logger(__name__)

_CIRCUIT_STATE: dict[str, dict[str, float | int]] = {}


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

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_base_delay_ms: int = 500,
        retry_max_delay_ms: int = 8000,
        circuit_breaker_failures: int = 5,
        circuit_breaker_reset_seconds: int = 60,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for LLM_PROVIDER=openai")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = max(5.0, float(timeout_seconds))
        self._max_retries = max(0, int(max_retries))
        self._retry_base_delay_ms = max(100, int(retry_base_delay_ms))
        self._retry_max_delay_ms = max(self._retry_base_delay_ms, int(retry_max_delay_ms))
        self._circuit_breaker_failures = max(1, int(circuit_breaker_failures))
        self._circuit_breaker_reset_seconds = max(5, int(circuit_breaker_reset_seconds))
        self._last_usage: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return f"openai:{self._model}"

    @property
    def last_usage(self) -> dict[str, Any]:
        return dict(self._last_usage)

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

        if _is_circuit_open(self._model):
            raise RuntimeError("OpenAI circuit breaker is open; using fallback provider.")

        client = AsyncOpenAI(api_key=self._api_key)
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            started = time.perf_counter()
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=self._model,
                        temperature=0.2,
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
                    ),
                    timeout=self._timeout_seconds,
                )
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty OpenAI response.")
                usage = getattr(response, "usage", None)
                input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                total_tokens = int(
                    getattr(
                        usage,
                        "total_tokens",
                        input_tokens + output_tokens,
                    )
                    or 0
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                self._last_usage = {
                    "provider": "openai",
                    "model": self._model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "latency_ms": latency_ms,
                    "attempt": attempt + 1,
                }
                _record_circuit_success(self._model)
                logger.info(
                    "openai_reasoning_success",
                    model=self._model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    attempt=attempt + 1,
                )
                return content
            except Exception as exc:  # noqa: BLE001 - classify + retry
                last_error = exc
                latency_ms = int((time.perf_counter() - started) * 1000)
                _record_circuit_failure(
                    self._model,
                    failure_threshold=self._circuit_breaker_failures,
                    reset_seconds=self._circuit_breaker_reset_seconds,
                )
                logger.warning(
                    "openai_reasoning_attempt_failed",
                    model=self._model,
                    error_type=type(exc).__name__,
                    latency_ms=latency_ms,
                    attempt=attempt + 1,
                    max_attempts=self._max_retries + 1,
                )
                if attempt >= self._max_retries:
                    break
                delay = min(
                    self._retry_max_delay_ms,
                    int(self._retry_base_delay_ms * (2**attempt)),
                )
                jitter = random.randint(0, max(50, delay // 4))
                await asyncio.sleep((delay + jitter) / 1000)

        raise RuntimeError(f"OpenAI request failed after retries: {type(last_error).__name__}")


def build_reasoning_provider(
    provider: str,
    *,
    api_key: str = "",
    model: str = "gpt-4o-mini",
    timeout_seconds: float = 30.0,
    max_retries: int = 3,
    retry_base_delay_ms: int = 500,
    retry_max_delay_ms: int = 8000,
    circuit_breaker_failures: int = 5,
    circuit_breaker_reset_seconds: int = 60,
) -> ReasoningProvider:
    if provider == "openai":
        return OpenAIReasoningProvider(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_base_delay_ms=retry_base_delay_ms,
            retry_max_delay_ms=retry_max_delay_ms,
            circuit_breaker_failures=circuit_breaker_failures,
            circuit_breaker_reset_seconds=circuit_breaker_reset_seconds,
        )
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


def _is_circuit_open(model: str) -> bool:
    state = _CIRCUIT_STATE.get(model) or {}
    opened_until = float(state.get("opened_until", 0) or 0)
    return opened_until > time.time()


def _record_circuit_success(model: str) -> None:
    _CIRCUIT_STATE[model] = {"failures": 0, "opened_until": 0.0}


def _record_circuit_failure(model: str, *, failure_threshold: int, reset_seconds: int) -> None:
    state = _CIRCUIT_STATE.setdefault(model, {"failures": 0, "opened_until": 0.0})
    failures = int(state.get("failures", 0) or 0) + 1
    state["failures"] = failures
    if failures >= failure_threshold:
        state["opened_until"] = time.time() + float(reset_seconds)
