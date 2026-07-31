"""Hybrid pipeline adapter for hypothesis-directed knowledge retrieval."""

from __future__ import annotations

import copy
import time
from typing import Any

from app.ai.hypothesis_retrieval.cache import InMemoryRetrievalCache, build_retrieval_cache_key
from app.ai.hypothesis_retrieval.dedupe import normalized_content_hash
from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.rag.hybrid_pipeline import HybridRetrievalPipeline
from app.ai.rag.models import RetrievalCandidate, RetrievalSourceType
from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalSourceType,
    RetrievalFailureType,
    RetrievalItemRelation,
)
from app.domain.hypothesis_retrieval.models import (
    PLAN_VERSION,
    HypothesisRetrievalAdapterResult,
    HypothesisRetrievalContext,
    HypothesisRetrievalQuerySpec,
    HypothesisRetrievedItem,
)
from app.domain.services.secret_masker import mask_secrets

ADAPTER_NAME = "hybrid_pipeline"
ADAPTER_VERSION = "v1"


def _map_source_type(candidate: RetrievalCandidate) -> HypothesisRetrievalSourceType:
    raw = candidate.source_type
    if raw == RetrievalSourceType.HISTORICAL_INCIDENT:
        return HypothesisRetrievalSourceType.HISTORICAL_INCIDENT
    reasons = " ".join(candidate.match_reasons or []).lower()
    meta = candidate.metadata or {}
    meta_source = str(meta.get("source_type") or "").lower()
    if "lexical" in reasons or meta.get("lexical_match") or "lexical" in meta_source:
        return HypothesisRetrievalSourceType.LEXICAL_KNOWLEDGE
    keyword = candidate.keyword_score or 0
    semantic_leads = candidate.semantic_score is not None and (
        candidate.keyword_score is None or candidate.semantic_score >= keyword
    )
    semantic_reasons = "embedding" in reasons or "vector" in reasons or "semantic" in reasons
    if semantic_leads and semantic_reasons:
        return HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE
    if "vector" in meta_source or "embedding" in meta_source:
        return HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE
    return HypothesisRetrievalSourceType.STATIC_KNOWLEDGE


def _candidate_to_item(
    candidate: RetrievalCandidate,
    *,
    context: HypothesisRetrievalContext,
    query_spec: HypothesisRetrievalQuerySpec,
    rank: int,
    embedding_model_version: str | None,
) -> HypothesisRetrievedItem:
    masked, _ = mask_secrets(candidate.content_excerpt or "")
    meta = dict(candidate.metadata or {})
    source_type = _map_source_type(candidate)
    historical_id = None
    if source_type == HypothesisRetrievalSourceType.HISTORICAL_INCIDENT:
        hist_raw = (
            meta.get("incident_id")
            or meta.get("historical_incident_id")
            or candidate.source_id
            or ""
        )
        historical_id = str(hist_raw) or None
    document_id = None
    if source_type != HypothesisRetrievalSourceType.HISTORICAL_INCIDENT:
        document_id = str(meta.get("document_id") or candidate.source_id or "") or None
    return HypothesisRetrievedItem(
        source_type=source_type,
        source_system="hybrid_retrieval_pipeline",
        text_excerpt=masked[:2000],
        query_id=query_spec.query_id,
        hypothesis_id=context.hypothesis_id,
        source_id=str(candidate.source_id) if candidate.source_id else None,
        document_id=document_id,
        chunk_id=str(candidate.chunk_id) if candidate.chunk_id else None,
        historical_incident_id=historical_id,
        title=(candidate.title or None),
        normalized_text_hash=normalized_content_hash(masked[:400]),
        source_path=str(meta.get("source_path") or meta.get("path") or "") or None,
        repository=str(meta.get("repository") or "") or None,
        commit_sha=str(meta.get("commit_sha") or "") or None,
        retrieval_score=float(
            candidate.hybrid_score
            if candidate.hybrid_score is not None
            else candidate.semantic_score or 0.0
        ),
        lexical_score=float(candidate.keyword_score)
        if candidate.keyword_score is not None
        else None,
        vector_score=float(candidate.semantic_score)
        if candidate.semantic_score is not None
        else None,
        historical_score=float(candidate.history_quality_score)
        if candidate.history_quality_score is not None
        else None,
        adapter_name=ADAPTER_NAME,
        adapter_version=ADAPTER_VERSION,
        embedding_model_version=embedding_model_version,
        relation_candidate=query_spec.expected_relation or RetrievalItemRelation.UNKNOWN,
        rank_within_query=rank,
        metadata={
            "candidate_id": candidate.candidate_id,
            "match_reasons": list(candidate.match_reasons or []),
            "pipeline_source_type": candidate.source_type.value,
        },
        associated_query_ids=[query_spec.query_id],
        contributing_adapters=[ADAPTER_NAME],
        redaction_status="masked",
    )


class HybridPipelineHypothesisAdapter:
    """Wraps HybridRetrievalPipeline without mutating the caller's AnalysisContext."""

    adapter_name = ADAPTER_NAME
    adapter_version = ADAPTER_VERSION
    supported_source_types = [
        HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
        HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE,
        HypothesisRetrievalSourceType.LEXICAL_KNOWLEDGE,
        HypothesisRetrievalSourceType.HISTORICAL_INCIDENT,
    ]

    def __init__(
        self,
        pipeline: HybridRetrievalPipeline | None,
        *,
        analysis_context: AnalysisContext | None = None,
        cache: InMemoryRetrievalCache | None = None,
        cache_enabled: bool = True,
        knowledge_base_version: str = "kb_v1",
        embedding_model_version: str | None = None,
        historical_enabled: bool = True,
        static_kb_enabled: bool = True,
        metadata_filtering_enabled: bool = False,
        exact_identifier_boost_enabled: bool = False,
    ) -> None:
        self._pipeline = pipeline
        self._analysis_context = analysis_context
        self._cache = cache
        self._cache_enabled = cache_enabled and cache is not None
        self._kb_version = knowledge_base_version
        self._embedding_version = embedding_model_version
        self._historical_enabled = historical_enabled
        self._static_kb_enabled = static_kb_enabled
        self._metadata_filtering_enabled = metadata_filtering_enabled
        self._exact_identifier_boost_enabled = exact_identifier_boost_enabled

    def is_available(self) -> bool:
        return self._pipeline is not None and self._analysis_context is not None and (
            self._static_kb_enabled or self._historical_enabled
        )

    def health_status(self) -> dict[str, Any]:
        return {
            "available": self.is_available(),
            "pipeline_present": self._pipeline is not None,
            "analysis_context_present": self._analysis_context is not None,
            "static_kb_enabled": self._static_kb_enabled,
            "historical_enabled": self._historical_enabled,
        }

    def configuration_summary(self) -> dict[str, Any]:
        return {
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "supported_source_types": [s.value for s in self.supported_source_types],
            "cache_enabled": self._cache_enabled,
            "knowledge_base_version": self._kb_version,
            "embedding_model_version": self._embedding_version,
        }

    def bind_analysis_context(self, analysis_context: AnalysisContext) -> None:
        self._analysis_context = analysis_context

    def retrieve(
        self,
        context: HypothesisRetrievalContext,
        query_spec: HypothesisRetrievalQuerySpec,
    ) -> HypothesisRetrievalAdapterResult:
        started = time.perf_counter()
        if not self.is_available():
            return HypothesisRetrievalAdapterResult(
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
                source_type=HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
                query_id=query_spec.query_id,
                status="SOURCE_UNAVAILABLE",
                failure_type=RetrievalFailureType.SOURCE_UNAVAILABLE,
                errors=["hybrid_pipeline_unavailable"],
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

        assert self._pipeline is not None
        assert self._analysis_context is not None

        cache_key = None
        if self._cache_enabled and self._cache is not None:
            meta = query_spec.metadata or {}
            intent_fp = str(meta.get("intent_id") or meta.get("intent_type") or "")
            routing_raw = meta.get("routing")
            routing: dict[str, Any] = (
                routing_raw if isinstance(routing_raw, dict) else {}
            )
            routing_fp = ",".join(
                sorted(str(x) for x in (routing.get("selected_sources") or []))
            )
            filter_fp = ""
            if self._metadata_filtering_enabled:
                filter_fp = str(meta.get("identifiers") or meta.get("identifiers_used") or "")
            cache_key = build_retrieval_cache_key(
                organization_id=context.organization_id,
                project_id=context.project_id,
                knowledge_base_version=self._kb_version,
                embedding_model_version=self._embedding_version or "",
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
                normalized_query=query_spec.normalized_query,
                source_filters=[s.value for s in query_spec.source_types],
                repository_commit=context.commit_sha,
                artifact_constraints={"affected_artifact_id": context.affected_artifact_id},
                top_k=query_spec.top_k,
                plan_version=PLAN_VERSION,
                intent_fingerprint=intent_fp,
                routing_fingerprint=routing_fp,
                filter_fingerprint=filter_fp,
            )
            cached = self._cache.get(cache_key)
            if isinstance(cached, list):
                items = [
                    _clone_cached_item(item, context=context, query_spec=query_spec)
                    for item in cached
                    if isinstance(item, HypothesisRetrievedItem)
                ]
                return HypothesisRetrievalAdapterResult(
                    adapter_name=self.adapter_name,
                    adapter_version=self.adapter_version,
                    source_type=HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
                    query_id=query_spec.query_id,
                    status="COMPLETE",
                    raw_result_count=len(items),
                    items=items,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    cache_hit=True,
                )

        try:
            ctx_copy = copy.copy(self._analysis_context)
            ctx_copy.options = dict(self._analysis_context.options or {})
            ctx_copy.options["hypothesis_directed_query"] = query_spec.query_text
            ctx_copy.options["top_k_predictions"] = query_spec.top_k
            # Isolate mutable retrieval state — never mutate caller's chunks.
            ctx_copy.retrieved_chunks = []
            ctx_copy.warnings = list(self._analysis_context.warnings or [])

            if self._metadata_filtering_enabled or self._exact_identifier_boost_enabled:
                structured = _build_structured_options(context, query_spec)
                ctx_copy.options["hypothesis_directed_structured"] = structured
                if self._exact_identifier_boost_enabled:
                    ctx_copy.options["hypothesis_exact_identifier_boost"] = True
                    ctx_copy.options["hypothesis_exact_identifiers"] = list(
                        structured.get("keywords") or []
                    )[:16]
                if self._metadata_filtering_enabled:
                    # Soft filters only — never remove org scope.
                    ctx_copy.options["hypothesis_soft_metadata_filters"] = {
                        "category": context.category_code,
                        "resource_types": list(query_spec.target_resource_identifiers[:8]),
                        "actions": list(query_spec.target_actions[:8]),
                    }

            result = self._pipeline.retrieve(ctx_copy)
            selected = list(result.candidates_selected or [])[: query_spec.top_k]
            items = [
                _candidate_to_item(
                    candidate,
                    context=context,
                    query_spec=query_spec,
                    rank=idx,
                    embedding_model_version=self._embedding_version
                    or ctx_copy.embedding_provider_name,
                )
                for idx, candidate in enumerate(selected, start=1)
            ]
            if cache_key and self._cache is not None:
                self._cache.set(cache_key, items)

            # Ensure caller context untouched.
            if self._analysis_context.retrieved_chunks is ctx_copy.retrieved_chunks:
                # Defensive: should never share identity after fresh list assignment.
                self._analysis_context.retrieved_chunks = list(
                    self._analysis_context.retrieved_chunks
                )

            return HypothesisRetrievalAdapterResult(
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
                source_type=HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
                query_id=query_spec.query_id,
                status="COMPLETE" if items else "NO_EVIDENCE",
                raw_result_count=len(selected),
                items=items,
                duration_ms=int((time.perf_counter() - started) * 1000),
                warnings=[result.fallback_reason] if result.fallback_reason else [],
            )
        except Exception as exc:  # noqa: BLE001 — soft-fail adapter
            return HypothesisRetrievalAdapterResult(
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
                source_type=HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
                query_id=query_spec.query_id,
                status="FAILED",
                failure_type=RetrievalFailureType.INTERNAL_ERROR,
                errors=[f"{type(exc).__name__}"],
                duration_ms=int((time.perf_counter() - started) * 1000),
            )


def _clone_cached_item(
    item: HypothesisRetrievedItem,
    *,
    context: HypothesisRetrievalContext,
    query_spec: HypothesisRetrievalQuerySpec,
) -> HypothesisRetrievedItem:
    cloned = HypothesisRetrievedItem(
        source_type=item.source_type,
        source_system=item.source_system,
        text_excerpt=item.text_excerpt,
        query_id=query_spec.query_id,
        hypothesis_id=context.hypothesis_id,
        source_id=item.source_id,
        document_id=item.document_id,
        chunk_id=item.chunk_id,
        artifact_id=item.artifact_id,
        graph_node_id=item.graph_node_id,
        graph_edge_id=item.graph_edge_id,
        temporal_event_id=item.temporal_event_id,
        historical_incident_id=item.historical_incident_id,
        title=item.title,
        normalized_text_hash=item.normalized_text_hash,
        source_path=item.source_path,
        line_start=item.line_start,
        line_end=item.line_end,
        repository=item.repository,
        commit_sha=item.commit_sha,
        source_timestamp=item.source_timestamp,
        retrieval_score=item.retrieval_score,
        lexical_score=item.lexical_score,
        vector_score=item.vector_score,
        historical_score=item.historical_score,
        graph_distance=item.graph_distance,
        adapter_name=item.adapter_name,
        adapter_version=item.adapter_version,
        embedding_model_version=item.embedding_model_version,
        relation_candidate=query_spec.expected_relation,
        rank_within_query=item.rank_within_query,
        metadata=dict(item.metadata),
        redaction_status=item.redaction_status,
        associated_query_ids=[query_spec.query_id],
        contributing_adapters=list(item.contributing_adapters) or [ADAPTER_NAME],
    )
    return cloned


def _build_structured_options(
    context: HypothesisRetrievalContext,
    query_spec: HypothesisRetrievalQuerySpec,
) -> dict[str, Any]:
    meta = query_spec.metadata or {}
    identifiers = meta.get("identifiers") if isinstance(meta.get("identifiers"), dict) else {}
    keywords: list[str] = []
    for key in (
        "aws_actions",
        "aws_error_codes",
        "terraform_resources",
        "exception_names",
        "all_identifiers",
    ):
        values = identifiers.get(key) if isinstance(identifiers, dict) else None
        if isinstance(values, list):
            keywords.extend(str(v) for v in values if v)
    keywords.extend(str(x) for x in (query_spec.target_resource_identifiers or []) if x)
    keywords.extend(str(x) for x in (query_spec.target_actions or []) if x)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            ordered.append(kw)
    return {
        "failure_category": context.category_code,
        "error_codes": list(identifiers.get("aws_error_codes") or [])[:8]
        if isinstance(identifiers, dict)
        else [],
        "exception_names": list(identifiers.get("exception_names") or [])[:8]
        if isinstance(identifiers, dict)
        else [],
        "keywords": ordered[:20],
        "aws_services": list(identifiers.get("aws_services") or [])[:8]
        if isinstance(identifiers, dict)
        else [],
        "resource_types": list(identifiers.get("terraform_resource_types") or [])[:8]
        if isinstance(identifiers, dict)
        else [],
        "technologies": [],
    }
