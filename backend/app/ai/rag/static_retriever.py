"""Static knowledge retrieval: embedding_only and hybrid_static paths."""

from __future__ import annotations

from app.ai.orchestration.models import clamp01
from app.ai.rag.authority import authority_score
from app.ai.rag.lexical_index import LexicalRetriever
from app.ai.rag.models import (
    DiagnosticQuery,
    RetrievalCandidate,
    RetrievalMode,
    RetrievalSourceType,
)
from app.ai.rag.stack_trace import stack_trace_similarity
from app.ai.rag.weight_profiles import HybridWeightProfile
from app.domain.interfaces.ai_providers import EmbeddingProvider, VectorHit, VectorStore
from app.domain.services.secret_masker import mask_secrets


class StaticKnowledgeRetriever:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        lexical_retriever: LexicalRetriever | None = None,
        retrieve_k: int = 10,
    ) -> None:
        self._embeddings = embedding_provider
        self._store = vector_store
        self._lexical = lexical_retriever
        self._retrieve_k = retrieve_k

    def retrieve(
        self,
        query: DiagnosticQuery,
        *,
        mode: RetrievalMode,
        profile: HybridWeightProfile,
    ) -> list[RetrievalCandidate]:
        masked_query, _ = mask_secrets(query.sanitised_text)
        embedding = self._embeddings.embed([masked_query])[0]

        where = {"document_status": "active"}
        # Soft provider preference only for knowledge docs (not tenant boundary).
        if query.technologies:
            # Do not hard-filter; soft boost via scoring.
            pass

        hits = self._store.query(
            embedding=embedding,
            top_k=max(self._retrieve_k, profile.max_candidates_before_rerank),
            where=where,
        )
        # Exclude historical corpus from static path (history has its own retriever).
        hits = [
            h
            for h in hits
            if str((h.metadata or {}).get("source_type") or "knowledge_document")
            != "historical_incident"
        ]

        if mode == RetrievalMode.EMBEDDING_ONLY:
            return [self._from_hit(h, query, profile, lexical_score=None) for h in hits]

        by_id: dict[str, RetrievalCandidate] = {}
        for hit in hits:
            by_id[hit.chunk_id] = self._from_hit(hit, query, profile, lexical_score=None)

        if profile.enable_lexical and self._lexical is not None:
            for lexical_hit in self._lexical.search(
                query, top_k=profile.max_candidates_before_rerank
            ):
                existing = by_id.get(lexical_hit.chunk_id)
                if existing is None:
                    # Lexical-only candidate (may lack semantic score → null, not zero).
                    meta = dict(lexical_hit.metadata)
                    if str(meta.get("source_type") or "") == "historical_incident":
                        continue
                    candidate = RetrievalCandidate(
                        candidate_id=f"knowledge:{lexical_hit.chunk_id}",
                        source_type=_source_type(meta),
                        source_id=str(
                            meta.get("document_id") or meta.get("title") or lexical_hit.chunk_id
                        ),
                        chunk_id=lexical_hit.chunk_id,
                        title=str(meta.get("title") or "") or None,
                        content_excerpt=mask_secrets(lexical_hit.text)[0][:500],
                        metadata=meta,
                        semantic_score=None,
                        keyword_score=lexical_hit.score,
                        match_reasons=list(lexical_hit.match_reasons),
                    )
                    self._apply_structured_scores(candidate, query, profile, meta)
                    by_id[lexical_hit.chunk_id] = candidate
                else:
                    existing.keyword_score = lexical_hit.score
                    existing.match_reasons = list(
                        dict.fromkeys(existing.match_reasons + lexical_hit.match_reasons)
                    )

        return list(by_id.values())

    def _from_hit(
        self,
        hit: VectorHit,
        query: DiagnosticQuery,
        profile: HybridWeightProfile,
        *,
        lexical_score: float | None,
    ) -> RetrievalCandidate:
        meta = dict(hit.metadata or {})
        masked, _ = mask_secrets(hit.text)
        candidate = RetrievalCandidate(
            candidate_id=f"knowledge:{hit.chunk_id}",
            source_type=_source_type(meta),
            source_id=str(meta.get("document_id") or meta.get("title") or hit.chunk_id),
            chunk_id=str(hit.chunk_id),
            title=str(meta.get("title") or "") or None,
            content_excerpt=masked[:500],
            metadata={**meta, "persist_citation": True},
            semantic_score=clamp01(float(hit.score)),
            keyword_score=lexical_score,
        )
        if profile.name != "embedding_baseline_v1":
            self._apply_structured_scores(candidate, query, profile, meta)
        else:
            # Embedding-only: do not apply structured boosts.
            candidate.authority_score = None
            candidate.category_score = None
        return candidate

    def _apply_structured_scores(
        self,
        candidate: RetrievalCandidate,
        query: DiagnosticQuery,
        profile: HybridWeightProfile,
        meta: dict,
    ) -> None:
        candidate.category_score = _category_score(query, meta)
        candidate.stage_score = _stage_score(query, meta)
        candidate.technology_score = _set_score(query.technologies, meta.get("technologies"))
        candidate.error_code_score = _set_score(query.error_codes, meta.get("error_codes"))
        candidate.resource_score = _set_score(query.resource_types, meta.get("resource_types"))
        candidate.authority_score = authority_score(
            source_type=candidate.source_type,
            metadata=meta,
        )
        if profile.enable_stack_trace:
            candidate.stack_trace_score = stack_trace_similarity(
                query.stack_trace_fingerprint,
                str(meta.get("stack_trace_fingerprint") or "") or None,
            )


def _source_type(meta: dict) -> RetrievalSourceType:
    raw = str(meta.get("source_type") or "knowledge_document")
    try:
        return RetrievalSourceType(raw)
    except ValueError:
        return RetrievalSourceType.KNOWLEDGE_DOCUMENT


def _category_score(query: DiagnosticQuery, meta: dict) -> float | None:
    cats = meta.get("failure_categories") or []
    if not query.failure_category:
        return None
    if not cats:
        # Missing metadata is not zero evidence.
        text = " ".join(
            [
                str(meta.get("title") or ""),
                str(meta.get("provider") or ""),
                str(meta.get("product") or ""),
            ]
        ).lower()
        token = query.failure_category.replace("_", " ").lower()
        if token and token in text:
            return 0.6
        return None
    lowered = {str(c).lower() for c in cats}
    if query.failure_category.lower() in lowered:
        return 1.0
    if query.failure_category.replace("_", " ").lower() in " ".join(lowered):
        return 0.8
    return 0.0


def _stage_score(query: DiagnosticQuery, meta: dict) -> float | None:
    if not query.pipeline_stage:
        return None
    stages = meta.get("pipeline_stages") or []
    if not stages:
        return None
    return 1.0 if query.pipeline_stage.lower() in {str(s).lower() for s in stages} else 0.0


def _set_score(left: list[str], right: list | None) -> float | None:
    if not left:
        return None
    if not right:
        return None
    a = {x.lower() for x in left}
    b = {str(x).lower() for x in right}
    return clamp01(len(a & b) / max(1, len(a)))
