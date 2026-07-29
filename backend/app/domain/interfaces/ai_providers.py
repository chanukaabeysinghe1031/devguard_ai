"""AI provider interfaces (embeddings, vector store, reasoning)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EmbeddedChunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VectorHit:
    chunk_id: str
    score: float
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RootCauseRequest:
    classification_category: str
    classification_confidence: float
    root_cause_summary: str
    technical_explanation: str
    evidence: list[dict[str, Any]]
    retrieved_docs: list[dict[str, Any]]
    signals: dict[str, Any]
    safety_rules: list[str]


@dataclass
class RecommendationRequest:
    root_cause: dict[str, Any]
    evidence: list[dict[str, Any]]
    retrieved_docs: list[dict[str, Any]]
    template_steps: list[dict[str, Any]]


class EmbeddingProvider(ABC):
    """Embed text for vector retrieval. Implementations must not call external APIs with secrets."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single search query. Default: batch ``embed`` with one text."""
        vectors = self.embed([text])
        if not vectors:
            return []
        return vectors[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents for indexing. Default: ``embed``."""
        return self.embed(texts)


class VectorStore(ABC):
    """Vector index boundary. Durable chunk text lives in PostgreSQL."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def upsert(self, chunks: list[EmbeddedChunk], embeddings: list[list[float]]) -> None: ...

    @abstractmethod
    def query(
        self,
        *,
        embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[VectorHit]: ...


class ReasoningProvider(ABC):
    """LLM / local grounded reasoning provider."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def generate_root_cause(self, request: RootCauseRequest) -> dict[str, Any]: ...

    @abstractmethod
    async def generate_recommendations(
        self,
        request: RecommendationRequest,
    ) -> dict[str, Any]: ...
