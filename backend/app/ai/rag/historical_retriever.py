"""Organisation-scoped historical incident retrieval."""

from __future__ import annotations

from datetime import UTC, datetime

from app.ai.orchestration.models import clamp01
from app.ai.rag.authority import authority_score
from app.ai.rag.models import (
    DiagnosticQuery,
    RetrievalCandidate,
    RetrievalSourceType,
)
from app.ai.rag.stack_trace import stack_trace_similarity
from app.ai.rag.weight_profiles import HybridWeightProfile
from app.domain.interfaces.ai_providers import EmbeddingProvider, VectorStore
from app.domain.services.secret_masker import mask_secrets


class HistoricalIncidentRetriever:
    """Retrieve only trusted resolved incidents for the query organisation."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        profile: HybridWeightProfile,
    ) -> None:
        self._embeddings = embedding_provider
        self._store = vector_store
        self._profile = profile

    def retrieve(self, query: DiagnosticQuery) -> list[RetrievalCandidate]:
        if not self._profile.enable_historical:
            return []
        if query.organisation_id is None:
            return []

        masked_query, _ = mask_secrets(query.sanitised_text)
        embedding = self._embeddings.embed_query(masked_query)
        # Organisation filter is applied in the store query itself — never retrieve
        # globally then filter in memory as the sole isolation mechanism.
        where = {
            "$and": [
                {"document_status": {"$eq": "active"}},
                {"source_type": {"$eq": "historical_incident"}},
                {"organisation_id": {"$eq": str(query.organisation_id)}},
            ]
        }
        hits = self._store.query(
            embedding=embedding,
            top_k=self._profile.max_candidates_before_rerank,
            where=where,
        )
        # Do NOT soften organisation filters.

        candidates: list[RetrievalCandidate] = []
        for hit in hits:
            meta = dict(hit.metadata or {})
            if str(meta.get("organisation_id")) != str(query.organisation_id):
                continue  # defence in depth
            quality = float(meta.get("history_quality_score") or 0.0)
            if quality < self._profile.min_history_quality_score:
                continue
            masked_text, _ = mask_secrets(hit.text)
            if not masked_text.strip():
                continue

            candidate = RetrievalCandidate(
                candidate_id=f"history:{hit.chunk_id}",
                source_type=RetrievalSourceType.HISTORICAL_INCIDENT,
                source_id=str(meta.get("incident_id") or hit.chunk_id),
                chunk_id=str(hit.chunk_id),
                title=str(meta.get("title") or "") or None,
                content_excerpt=masked_text[:500],
                metadata={**meta, "persist_citation": False},
                semantic_score=clamp01(float(hit.score)),
                history_quality_score=clamp01(quality),
                authority_score=authority_score(
                    source_type=RetrievalSourceType.HISTORICAL_INCIDENT,
                    metadata=meta,
                ),
                recency_score=_recency_score(meta.get("resolved_at")),
            )
            candidate.category_score = _list_overlap_score(
                query.failure_category,
                meta.get("failure_categories") or [],
            )
            candidate.technology_score = _set_overlap_score(
                query.technologies,
                meta.get("technologies") or [],
            )
            candidate.error_code_score = _set_overlap_score(
                query.error_codes,
                meta.get("error_codes") or [],
            )
            candidate.stage_score = _list_overlap_score(
                query.pipeline_stage,
                meta.get("pipeline_stages") or [],
            )
            if self._profile.enable_stack_trace and query.stack_trace_fingerprint:
                candidate.stack_trace_score = stack_trace_similarity(
                    query.stack_trace_fingerprint,
                    str(meta.get("stack_trace_fingerprint") or ""),
                )
            candidates.append(candidate)
        return candidates


def _list_overlap_score(value: str | None, values: list) -> float | None:
    if not value:
        return None
    lowered = {str(v).lower() for v in values}
    if not lowered:
        return None
    return 1.0 if value.lower() in lowered else 0.0


def _set_overlap_score(left: list[str], right: list) -> float | None:
    if not left:
        return None
    a = {x.lower() for x in left}
    b = {str(x).lower() for x in right}
    if not b:
        return None
    return clamp01(len(a & b) / max(1, len(a)))


def _recency_score(resolved_at: str | None) -> float | None:
    if not resolved_at:
        return None
    try:
        when = datetime.fromisoformat(str(resolved_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    now = datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    days = max(0.0, (now - when).total_seconds() / 86400.0)
    # Bounded decay: 1.0 at day 0 → ~0.2 after ~365 days.
    return clamp01(1.0 / (1.0 + days / 120.0))
