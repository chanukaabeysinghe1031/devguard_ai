"""Deterministic temporal evidence adapter (no embeddings)."""

from __future__ import annotations

import time
from typing import Any

from app.ai.hypothesis_retrieval.dedupe import normalized_content_hash
from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalSourceType,
    RetrievalFailureType,
    RetrievalItemRelation,
)
from app.domain.hypothesis_retrieval.models import (
    HypothesisRetrievalAdapterResult,
    HypothesisRetrievalContext,
    HypothesisRetrievalQuerySpec,
    HypothesisRetrievedItem,
)
from app.domain.services.secret_masker import mask_secrets

ADAPTER_NAME = "temporal_evidence"
ADAPTER_VERSION = "v1"


class TemporalEvidenceRetrievalAdapter:
    adapter_name = ADAPTER_NAME
    adapter_version = ADAPTER_VERSION
    supported_source_types = [HypothesisRetrievalSourceType.TEMPORAL]

    def __init__(self, *, enabled: bool = True, max_items: int = 40) -> None:
        self._enabled = enabled
        self._max_items = max(1, max_items)

    def is_available(self) -> bool:
        return self._enabled

    def health_status(self) -> dict[str, Any]:
        return {"available": self.is_available(), "enabled": self._enabled}

    def configuration_summary(self) -> dict[str, Any]:
        return {
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "max_items": self._max_items,
        }

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
                source_type=HypothesisRetrievalSourceType.TEMPORAL,
                query_id=query_spec.query_id,
                status="SOURCE_UNAVAILABLE",
                failure_type=RetrievalFailureType.SOURCE_UNAVAILABLE,
                errors=["temporal_adapter_disabled"],
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

        needle = (query_spec.normalized_query or "").lower()
        items: list[HypothesisRetrievedItem] = []
        rank = 0

        if context.temporal_primary_summary:
            text = context.temporal_primary_summary
            rank += 1
            items.append(
                self._item(
                    context,
                    query_spec,
                    text=text,
                    event_id=context.temporal_primary_event_id,
                    title="primary_failure",
                    score=0.9,
                    rank=rank,
                )
            )

        for summary in context.upstream_event_summaries[: self._max_items]:
            if needle and needle not in summary.lower() and not _tokens_overlap(needle, summary):
                continue
            rank += 1
            items.append(
                self._item(
                    context,
                    query_spec,
                    text=summary,
                    title="upstream_context",
                    score=0.65,
                    rank=rank,
                )
            )

        for summary in context.downstream_symptom_summaries[: self._max_items]:
            if needle and needle not in summary.lower() and not _tokens_overlap(needle, summary):
                continue
            rank += 1
            items.append(
                self._item(
                    context,
                    query_spec,
                    text=summary,
                    title="downstream_symptom",
                    score=0.55,
                    rank=rank,
                )
            )

        for warning in sorted(context.temporal_warnings)[:5]:
            rank += 1
            items.append(
                self._item(
                    context,
                    query_spec,
                    text=f"temporal_warning={warning}",
                    title="temporal_warning",
                    score=0.25,
                    rank=rank,
                    relation=RetrievalItemRelation.CONTEXT,
                )
            )

        limited = items[: query_spec.top_k]
        return HypothesisRetrievalAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            source_type=HypothesisRetrievalSourceType.TEMPORAL,
            query_id=query_spec.query_id,
            status="COMPLETE" if limited else "NO_EVIDENCE",
            raw_result_count=len(items),
            items=limited,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    def _item(
        self,
        context: HypothesisRetrievalContext,
        query_spec: HypothesisRetrievalQuerySpec,
        *,
        text: str,
        score: float,
        rank: int,
        event_id: str | None = None,
        title: str | None = None,
        relation: RetrievalItemRelation | None = None,
    ) -> HypothesisRetrievedItem:
        masked, _ = mask_secrets(text)
        return HypothesisRetrievedItem(
            source_type=HypothesisRetrievalSourceType.TEMPORAL,
            source_system="temporal_localisation",
            text_excerpt=masked[:1500],
            query_id=query_spec.query_id,
            hypothesis_id=context.hypothesis_id,
            source_id=event_id or title,
            temporal_event_id=event_id,
            title=title,
            normalized_text_hash=normalized_content_hash(masked[:400]),
            retrieval_score=score,
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            relation_candidate=relation
            or query_spec.expected_relation
            or RetrievalItemRelation.CONTEXT,
            rank_within_query=rank,
            associated_query_ids=[query_spec.query_id],
            contributing_adapters=[self.adapter_name],
            redaction_status="masked",
        )


def _tokens_overlap(needle: str, haystack: str) -> bool:
    tokens = [t for t in needle.split() if len(t) > 2]
    if not tokens:
        return False
    lower = haystack.lower()
    return any(t in lower for t in tokens[:8])
