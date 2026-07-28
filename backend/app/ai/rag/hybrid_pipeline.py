"""Module 9 hybrid retrieval pipeline coordinating modes, scoring, and budgets."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.orchestration.budget_manager import AIExecutionBudgetManager
from app.ai.rag.historical_retriever import HistoricalIncidentRetriever
from app.ai.rag.hybrid_query_builder import HybridDiagnosticQueryBuilder
from app.ai.rag.hybrid_reranker import HybridReranker
from app.ai.rag.lexical_index import LexicalRetriever
from app.ai.rag.models import (
    RetrievalMode,
    RetrievalResult,
    parse_retrieval_mode,
)
from app.ai.rag.retriever import KnowledgeRetriever, RetrievedChunkCandidate
from app.ai.rag.static_retriever import StaticKnowledgeRetriever
from app.ai.rag.weight_profiles import HybridRetrievalSettings, HybridWeightProfile
from app.domain.interfaces.ai_providers import EmbeddingProvider, VectorStore
from app.domain.services.secret_masker import mask_secrets


class HybridRetrievalPipeline:
    """Selects retrieval mode, retrieves, scores, dedupes, diversifies, and adapts to budget."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        baseline_retriever: KnowledgeRetriever,
        settings: HybridRetrievalSettings,
        lexical_retriever: LexicalRetriever | None = None,
        historical_retriever: HistoricalIncidentRetriever | None = None,
    ) -> None:
        self._embeddings = embedding_provider
        self._store = vector_store
        self._baseline = baseline_retriever
        self._settings = settings
        self._lexical = lexical_retriever
        self._historical = historical_retriever
        self._query_builder = HybridDiagnosticQueryBuilder()
        self._static = StaticKnowledgeRetriever(
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            lexical_retriever=lexical_retriever,
            retrieve_k=getattr(baseline_retriever, "_retrieve_k", 10),
        )

    def retrieve(
        self,
        context: AnalysisContext,
        *,
        budget_manager: AIExecutionBudgetManager | None = None,
        elapsed_ms: int = 0,
    ) -> RetrievalResult:
        started = time.perf_counter()
        requested_mode = self._resolve_mode(context)
        mode = requested_mode
        fallback_used = False
        fallback_reason: str | None = None

        # Budget / latency downgrades before expensive stages.
        if budget_manager is not None:
            if not budget_manager.can_retrieve():
                mode = RetrievalMode.EMBEDDING_ONLY
                fallback_used = True
                fallback_reason = "Retrieval call budget exhausted; downgraded."
            elif not budget_manager.latency_remaining(elapsed_ms):
                mode = RetrievalMode.EMBEDDING_ONLY
                fallback_used = True
                fallback_reason = "Latency budget exhausted; skipped hybrid retrieval."
            elif mode == RetrievalMode.HYBRID_WITH_HISTORY and not budget_manager.latency_remaining(
                elapsed_ms + 50
            ):
                mode = RetrievalMode.HYBRID_STATIC
                fallback_used = True
                fallback_reason = "Latency budget low; skipped historical retrieval."

        if (
            mode == RetrievalMode.HYBRID_WITH_HISTORY
            and not self._settings.enable_historical_retrieval
        ):
            mode = RetrievalMode.HYBRID_STATIC
            fallback_used = True
            fallback_reason = "Historical retrieval disabled by server configuration."

        if mode != RetrievalMode.EMBEDDING_ONLY and not self._settings.enable_hybrid_retrieval:
            mode = RetrievalMode.EMBEDDING_ONLY
            fallback_used = True
            fallback_reason = "Hybrid retrieval disabled; using embedding_only baseline."

        profile = self._settings.resolve_profile(mode.value)
        query = self._query_builder.build(context)

        # embedding_only preserves Module 7 baseline behaviour.
        if mode == RetrievalMode.EMBEDDING_ONLY:
            self._baseline.retrieve(context)
            latency = int((time.perf_counter() - started) * 1000)
            selected = [
                _chunk_to_candidate(chunk, rank=i)
                for i, chunk in enumerate(context.retrieved_chunks, start=1)
            ]
            result = RetrievalResult(
                query=query,
                retrieval_mode=mode,
                candidates_considered=len(selected),
                candidates_selected=selected,
                duplicate_count=0,
                filtered_count=0,
                retrieval_latency_ms=latency,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                configuration_hash=profile.configuration_hash(),
                weight_profile=profile.name,
            )
            self._store_result(context, result, profile)
            return result

        candidates = self._static.retrieve(query, mode=mode, profile=profile)
        historical_considered = 0
        if mode == RetrievalMode.HYBRID_WITH_HISTORY and self._historical is not None:
            historical = self._historical.retrieve(query)
            historical_considered = len(historical)
            candidates.extend(historical)

        reranker = HybridReranker(profile)
        selected, duplicate_count, filtered_count = reranker.rerank(query, candidates)
        historical_selected = sum(
            1 for c in selected if c.source_type.value == "historical_incident"
        )

        # Map selected candidates onto AnalysisContext.retrieved_chunks for Module 7/8.
        context.retrieved_chunks = [
            _candidate_to_chunk(candidate, rank=idx)
            for idx, candidate in enumerate(selected, start=1)
        ]
        context.retrieval_backend = self._store.name
        context.embedding_provider_name = self._embeddings.name
        if not context.retrieved_chunks:
            context.warnings.append("RAG retrieved no knowledge chunks.")
            context.partial = True

        latency = int((time.perf_counter() - started) * 1000)
        result = RetrievalResult(
            query=query,
            retrieval_mode=mode,
            candidates_considered=len(candidates),
            candidates_selected=selected,
            duplicate_count=duplicate_count,
            filtered_count=filtered_count,
            retrieval_latency_ms=latency,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            configuration_hash=profile.configuration_hash(),
            weight_profile=profile.name,
            historical_candidates_considered=historical_considered,
            historical_candidates_selected=historical_selected,
        )
        self._store_result(context, result, profile)
        return result

    def _resolve_mode(self, context: AnalysisContext) -> RetrievalMode:
        options = context.options or {}
        raw = options.get("retrieval_mode")
        if raw is not None:
            mode = parse_retrieval_mode(str(raw), default=RetrievalMode.HYBRID_STATIC)
            return mode

        execution_mode = str(options.get("execution_mode") or context.execution_mode)
        default = parse_retrieval_mode(
            self._settings.default_mode,
            default=RetrievalMode.HYBRID_STATIC,
        )
        if not self._settings.enable_hybrid_retrieval:
            return RetrievalMode.EMBEDDING_ONLY

        if execution_mode == "confidence_routed":
            # Adaptive: lower-cost validation vs ambiguous cases.
            calibrated = None
            if context.confidence_assessment is not None:
                calibrated = context.confidence_assessment.calibrated_confidence
            unc = None
            if context.uncertainty_assessment is not None:
                unc = context.uncertainty_assessment.uncertainty_score
            if calibrated is not None and calibrated >= 0.85 and (unc or 0) < 0.4:
                return RetrievalMode.EMBEDDING_ONLY
            if (
                self._settings.enable_historical_retrieval
                and calibrated is not None
                and calibrated < 0.6
            ):
                return RetrievalMode.HYBRID_WITH_HISTORY
            return RetrievalMode.HYBRID_STATIC

        if execution_mode in {"rules_rag", "rag_llm"}:
            return default
        return RetrievalMode.EMBEDDING_ONLY

    def _store_result(
        self,
        context: AnalysisContext,
        result: RetrievalResult,
        profile: HybridWeightProfile,
    ) -> None:
        context.options["retrieval_result"] = result.evaluation_metadata()
        context.options["retrieval_mode"] = result.retrieval_mode.value
        context.options["retrieval_configuration_hash"] = result.configuration_hash
        context.options["retrieval_weight_profile"] = profile.name
        eval_meta = dict(context.evaluation_metadata or {})
        eval_meta["retrieval"] = result.evaluation_metadata()
        context.evaluation_metadata = eval_meta


def _chunk_to_candidate(chunk: Any, *, rank: int) -> Any:
    from app.ai.rag.models import RetrievalCandidate, RetrievalSourceType

    meta = dict(getattr(chunk, "metadata", None) or {})
    return RetrievalCandidate(
        candidate_id=f"knowledge:{chunk.chunk_id}",
        source_type=RetrievalSourceType.KNOWLEDGE_DOCUMENT,
        source_id=str(meta.get("document_id") or meta.get("title") or chunk.chunk_id),
        chunk_id=str(chunk.chunk_id),
        title=getattr(chunk, "title", None),
        content_excerpt=str(getattr(chunk, "content", ""))[:500],
        metadata=meta,
        semantic_score=float(getattr(chunk, "similarity_score", 0.0)),
        hybrid_score=float(getattr(chunk, "similarity_score", 0.0)),
        match_reasons=["embedding_only baseline"],
    )


def _candidate_to_chunk(candidate: Any, *, rank: int) -> RetrievedChunkCandidate:
    chunk_id_raw = candidate.chunk_id or candidate.candidate_id
    try:
        chunk_uuid = UUID(str(chunk_id_raw))
    except ValueError:
        # Should not happen for knowledge/history uuid5 ids.
        chunk_uuid = UUID(int=0)
    masked, _ = mask_secrets(candidate.content_excerpt)
    meta = dict(candidate.metadata or {})
    meta["match_reasons"] = list(candidate.match_reasons)
    if candidate.score_breakdown is not None:
        meta["score_breakdown"] = candidate.score_breakdown.to_dict()
    meta["source_type"] = candidate.source_type.value
    meta["hybrid_score"] = candidate.hybrid_score
    return RetrievedChunkCandidate(
        chunk_id=chunk_uuid,
        rank=rank,
        similarity_score=round(
            float(
                candidate.hybrid_score
                if candidate.hybrid_score is not None
                else candidate.semantic_score or 0.0
            ),
            6,
        ),
        content=masked,
        title=candidate.title,
        source_url=str(meta.get("source_url") or "") or None,
        provider=str(meta.get("provider") or "") or None,
        used_in_reasoning=True,
        metadata=meta,
    )
