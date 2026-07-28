"""Factory helpers for RAG / LLM / Module 8–9 stacks."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestration.policy import RoutingPolicyConfig
from app.ai.rag.embedding_provider import build_embedding_provider
from app.ai.rag.historical_retriever import HistoricalIncidentRetriever
from app.ai.rag.hybrid_pipeline import HybridRetrievalPipeline
from app.ai.rag.knowledge_ingestion import KnowledgeIngestionService
from app.ai.rag.lexical_index import LexicalRetriever
from app.ai.rag.retriever import KnowledgeRetriever
from app.ai.rag.vector_store import build_vector_store
from app.ai.rag.weight_profiles import HybridRetrievalSettings
from app.ai.reasoning.reasoning_provider import build_reasoning_provider
from app.ai.reasoning.root_cause_analyzer import RootCauseAnalyzer
from app.core.config import Settings


def resolve_knowledge_base_path(settings: Settings) -> Path:
    path = Path(settings.knowledge_base_path)
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    candidate = (backend_root / path).resolve()
    if candidate.exists():
        return candidate
    repo_root = backend_root.parent
    return (repo_root / path).resolve()


def build_hybrid_settings(settings: Settings) -> HybridRetrievalSettings:
    return HybridRetrievalSettings(
        default_mode=settings.default_retrieval_mode,
        enable_hybrid_retrieval=settings.enable_hybrid_retrieval,
        enable_historical_retrieval=settings.enable_historical_retrieval,
        enable_lexical_retrieval=settings.enable_lexical_retrieval,
        enable_stack_trace_similarity=settings.enable_stack_trace_similarity,
        enable_retrieval_diversity=settings.enable_retrieval_diversity,
        weight_profile_name=settings.hybrid_weight_profile,
    )


async def build_retriever(
    session: AsyncSession,
    settings: Settings,
) -> KnowledgeRetriever:
    embeddings = build_embedding_provider(settings.embedding_provider)
    store = build_vector_store(
        settings.rag_backend,
        persist_path=settings.chroma_persist_path,
    )
    lexical = LexicalRetriever() if settings.enable_lexical_retrieval else None
    ingestion = KnowledgeIngestionService(
        session,
        embedding_provider=embeddings,
        vector_store=store,
        knowledge_base_path=resolve_knowledge_base_path(settings),
        lexical_retriever=lexical,
    )
    await ingestion.ensure_indexed()
    return KnowledgeRetriever(
        embedding_provider=embeddings,
        vector_store=store,
        retrieve_k=settings.rag_top_k,
        context_k=settings.rag_context_k,
    )


async def build_hybrid_pipeline(
    session: AsyncSession,
    settings: Settings,
) -> tuple[KnowledgeRetriever, HybridRetrievalPipeline]:
    embeddings = build_embedding_provider(settings.embedding_provider)
    store = build_vector_store(
        settings.rag_backend,
        persist_path=settings.chroma_persist_path,
    )
    lexical = LexicalRetriever() if settings.enable_lexical_retrieval else None
    ingestion = KnowledgeIngestionService(
        session,
        embedding_provider=embeddings,
        vector_store=store,
        knowledge_base_path=resolve_knowledge_base_path(settings),
        lexical_retriever=lexical,
    )
    await ingestion.ensure_indexed()
    baseline = KnowledgeRetriever(
        embedding_provider=embeddings,
        vector_store=store,
        retrieve_k=settings.rag_top_k,
        context_k=settings.rag_context_k,
    )
    hybrid_settings = build_hybrid_settings(settings)
    profile = hybrid_settings.resolve_profile(
        "hybrid_with_history"
        if settings.enable_historical_retrieval
        else settings.default_retrieval_mode
    )
    historical = None
    if settings.enable_historical_retrieval:
        historical = HistoricalIncidentRetriever(
            embedding_provider=embeddings,
            vector_store=store,
            profile=profile,
        )
    pipeline = HybridRetrievalPipeline(
        embedding_provider=embeddings,
        vector_store=store,
        baseline_retriever=baseline,
        settings=hybrid_settings,
        lexical_retriever=lexical,
        historical_retriever=historical,
    )
    return baseline, pipeline


def build_analyzer(settings: Settings) -> RootCauseAnalyzer:
    provider = build_reasoning_provider(
        settings.llm_provider,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )
    return RootCauseAnalyzer(provider)


def build_routing_policy(settings: Settings) -> RoutingPolicyConfig:
    return RoutingPolicyConfig(
        policy_name=settings.routing_policy_name,
        policy_version=settings.routing_policy_version,
        confidence_high_threshold=settings.confidence_high_threshold,
        confidence_medium_threshold=settings.confidence_medium_threshold,
        uncertainty_high_threshold=settings.uncertainty_high_threshold,
        uncertainty_medium_threshold=settings.uncertainty_medium_threshold,
        min_evidence_quality_for_deterministic=settings.min_evidence_quality_for_deterministic,
        min_retrieval_quality_for_reasoning=settings.min_retrieval_quality_for_reasoning,
        high_risk_requires_validation=settings.high_risk_requires_validation,
        enable_confidence_routing=settings.enable_confidence_routing,
        enable_rag=settings.enable_rag,
        enable_llm=settings.enable_llm,
        enable_local_reasoner=settings.enable_local_reasoner,
        enable_external_llm=settings.enable_external_llm
        or (settings.llm_provider == "openai" and bool(settings.openai_api_key)),
        max_provider_calls=settings.max_provider_calls_per_analysis,
        max_retrieval_calls=settings.max_retrieval_calls_per_analysis,
        max_latency_ms=settings.max_latency_limit_ms,
        max_budget_usd=settings.max_budget_usd_per_analysis,
    )
