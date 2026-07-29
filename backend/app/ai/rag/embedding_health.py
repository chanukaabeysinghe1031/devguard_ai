"""Safe embedding provider health summary for internal use."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.rag.embedding_provider import (
    EmbeddingHealthResult,
    build_embedding_provider_from_settings,
)
from app.core.config import Settings


@dataclass(frozen=True)
class EmbeddingProviderHealthView:
    configured: bool
    provider: str | None
    model: str | None
    device: str | None
    dimension: int | None
    healthy: bool
    normalised: bool | None
    safe_error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "provider": self.provider,
            "model": self.model,
            "device": self.device,
            "dimension": self.dimension,
            "healthy": self.healthy,
            "normalised": self.normalised,
            "safe_error": self.safe_error,
        }


def check_embedding_provider_health(settings: Settings) -> EmbeddingProviderHealthView:
    """Non-destructive embedding health. Does not write to Chroma."""
    try:
        provider = build_embedding_provider_from_settings(settings, use_cache=True)
        health: EmbeddingHealthResult = provider.health_check()  # type: ignore[attr-defined]
        return EmbeddingProviderHealthView(
            configured=True,
            provider=health.provider,
            model=health.model,
            device=health.device,
            dimension=health.dimension,
            healthy=health.status == "healthy",
            normalised=health.normalised,
            safe_error=health.safe_error,
        )
    except Exception as exc:  # noqa: BLE001 - never leak stack traces
        return EmbeddingProviderHealthView(
            configured=False,
            provider=getattr(settings, "embedding_provider", None),
            model=getattr(settings, "embedding_model", None),
            device=None,
            dimension=None,
            healthy=False,
            normalised=None,
            safe_error=f"{type(exc).__name__}: {exc}"[:240],
        )
