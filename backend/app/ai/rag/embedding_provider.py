"""Embedding providers — deterministic hash embedding plus optional sentence-transformers."""

from __future__ import annotations

import hashlib
import math
import re

from app.domain.interfaces.ai_providers import EmbeddingProvider

_WORD = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic bag-of-features embedding for tests and offline MVP retrieval."""

    def __init__(self, dimensions: int = 256) -> None:
        self._dimensions = dimensions

    @property
    def name(self) -> str:
        return "hashing-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        tokens = _WORD.findall(text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self._dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Optional SentenceTransformer embedding (architecture-approved)."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "sentence-transformers is required for EMBEDDING_PROVIDER=sentence_transformers"
            ) from exc
        self._model = SentenceTransformer(model_name)
        self._model_name = model_name

    @property
    def name(self) -> str:
        return f"sentence-transformers:{self._model_name}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, row)) for row in vectors]


def build_embedding_provider(provider: str) -> EmbeddingProvider:
    if provider == "sentence_transformers":
        return SentenceTransformerEmbeddingProvider()
    return HashingEmbeddingProvider()
