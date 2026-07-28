"""In-memory lexical / exact-match retrieval (no external search service)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.ai.orchestration.models import clamp01
from app.ai.rag.models import DiagnosticQuery
from app.domain.interfaces.ai_providers import EmbeddedChunk


@dataclass
class LexicalHit:
    chunk_id: str
    score: float
    text: str
    metadata: dict
    match_reasons: list[str] = field(default_factory=list)


class LexicalRetriever:
    """Token inverted index for exact diagnostic matches."""

    def __init__(self) -> None:
        self._by_token: dict[str, set[str]] = defaultdict(set)
        self._chunks: dict[str, EmbeddedChunk] = {}

    def clear(self) -> None:
        self._by_token.clear()
        self._chunks.clear()

    def index(self, chunks: list[EmbeddedChunk]) -> None:
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk
            tokens = _index_tokens(chunk.text, chunk.metadata)
            for token in tokens:
                self._by_token[token].add(chunk.chunk_id)

    def search(self, query: DiagnosticQuery, *, top_k: int = 20) -> list[LexicalHit]:
        scored: dict[str, float] = defaultdict(float)
        reasons: dict[str, list[str]] = defaultdict(list)

        def boost(ids: set[str], weight: float, reason: str) -> None:
            for chunk_id in ids:
                scored[chunk_id] += weight
                reasons[chunk_id].append(reason)

        for code in query.error_codes:
            boost(self._by_token.get(code.lower(), set()), 1.0, f"exact error code {code}")
        for exc in query.exception_names:
            boost(self._by_token.get(exc.lower(), set()), 0.9, f"exception {exc}")
        for cmd in query.commands:
            for token in cmd.lower().split():
                boost(self._by_token.get(token, set()), 0.7, f"command token {token}")
        for resource in query.resource_types:
            boost(
                self._by_token.get(resource.lower(), set()),
                0.75,
                f"resource {resource}",
            )
        for service in query.aws_services:
            boost(self._by_token.get(service.lower(), set()), 0.7, f"aws service {service}")
        if query.pipeline_stage:
            boost(
                self._by_token.get(query.pipeline_stage.lower(), set()),
                0.55,
                f"pipeline stage {query.pipeline_stage}",
            )
        for tech in query.technologies:
            boost(self._by_token.get(tech.lower(), set()), 0.5, f"technology {tech}")
        for keyword in query.keywords[:8]:
            boost(
                self._by_token.get(keyword.lower(), set()),
                0.25,
                f"keyword {keyword}",
            )

        if not scored:
            return []
        max_score = max(scored.values()) or 1.0
        hits = [
            LexicalHit(
                chunk_id=chunk_id,
                score=clamp01(score / max_score),
                text=self._chunks[chunk_id].text if chunk_id in self._chunks else "",
                metadata=dict(self._chunks[chunk_id].metadata) if chunk_id in self._chunks else {},
                match_reasons=reasons[chunk_id][:6],
            )
            for chunk_id, score in scored.items()
            if chunk_id in self._chunks
        ]
        hits.sort(key=lambda h: (-h.score, h.chunk_id))
        return hits[:top_k]


def _index_tokens(text: str, metadata: dict) -> set[str]:
    tokens: set[str] = set()
    for part in (text or "").lower().replace("/", " ").replace(":", " ").split():
        cleaned = part.strip(".,;()[]{}\"'")
        if len(cleaned) >= 3:
            tokens.add(cleaned)
    for key in (
        "failure_categories",
        "technologies",
        "error_codes",
        "exception_names",
        "commands",
        "resource_types",
        "aws_services",
        "pipeline_stages",
        "file_types",
    ):
        values = metadata.get(key) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            tokens.add(str(value).lower())
    if metadata.get("provider"):
        tokens.add(str(metadata["provider"]).lower())
    return tokens
