"""Warm up the configured local embedding model without touching Chroma."""

from __future__ import annotations

import argparse
import sys
import time

from app.ai.rag.embedding_provider import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    build_embedding_provider,
)
from app.core.config import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Warm up DevGuard embedding provider")
    parser.add_argument("--provider", default=None, help="Override EMBEDDING_PROVIDER")
    parser.add_argument("--model", default=None, help="Override EMBEDDING_MODEL")
    parser.add_argument("--device", default=None, help="Override EMBEDDING_DEVICE")
    args = parser.parse_args(argv)

    settings = get_settings()
    provider_name = args.provider or settings.embedding_provider
    model = args.model or settings.embedding_model
    device = args.device or settings.embedding_device

    started = time.perf_counter()
    try:
        provider = build_embedding_provider(
            provider_name,
            model=model,
            device=device,  # type: ignore[arg-type]
            batch_size=settings.embedding_batch_size,
            normalize=settings.embedding_normalize,
            max_input_characters=settings.embedding_max_input_characters,
            lazy_load=True,
        )
        health = provider.health_check()  # type: ignore[attr-defined]
    except (EmbeddingConfigurationError, EmbeddingProviderError) as exc:
        print("Status: unavailable")
        print(f"Error: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print("Status: unavailable")
        print(f"Error: {type(exc).__name__}")
        return 1

    elapsed = time.perf_counter() - started
    print(f"Provider: {health.provider}")
    print(f"Model: {health.model}")
    print(f"Device: {health.device}")
    print(f"Dimension: {health.dimension}")
    print(f"Normalised: {health.normalised}")
    print(f"Status: {health.status}")
    print(f"Elapsed seconds: {elapsed:.2f}")
    if health.safe_error:
        print(f"Error: {health.safe_error}")
        return 1
    return 0 if health.status == "healthy" else 1


if __name__ == "__main__":
    sys.exit(main())
