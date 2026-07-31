"""Deterministic artifact evidence adapter (no embeddings)."""

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

ADAPTER_NAME = "artifact_evidence"
ADAPTER_VERSION = "v1"


class ArtifactEvidenceRetrievalAdapter:
    adapter_name = ADAPTER_NAME
    adapter_version = ADAPTER_VERSION
    supported_source_types = [HypothesisRetrievalSourceType.ARTIFACT]

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
                source_type=HypothesisRetrievalSourceType.ARTIFACT,
                query_id=query_spec.query_id,
                status="SOURCE_UNAVAILABLE",
                failure_type=RetrievalFailureType.SOURCE_UNAVAILABLE,
                errors=["artifact_adapter_disabled"],
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

        needle = (query_spec.normalized_query or "").lower()
        candidates: list[HypothesisRetrievedItem] = []

        # Affected artifact / path — always include when present (structured evidence).
        if context.affected_artifact_id or context.affected_path:
            text = " | ".join(
                part
                for part in [
                    (
                        f"artifact_id={context.affected_artifact_id}"
                        if context.affected_artifact_id
                        else ""
                    ),
                    f"path={context.affected_path}" if context.affected_path else "",
                ]
                if part
            )
            candidates.append(
                self._item(
                    context,
                    query_spec,
                    text=text,
                    artifact_id=context.affected_artifact_id,
                    source_path=context.affected_path,
                    title="affected_artifact",
                    score=0.85,
                    rank=1,
                )
            )

        for idx, path in enumerate(sorted(context.changed_files)[: self._max_items], start=1):
            if needle and needle not in path.lower() and not _tokens_overlap(needle, path):
                continue
            candidates.append(
                self._item(
                    context,
                    query_spec,
                    text=f"changed_file={path}",
                    artifact_id=context.affected_artifact_id,
                    source_path=path,
                    title="changed_file",
                    score=0.55,
                    rank=idx + 10,
                )
            )

        related_artifacts = sorted(context.related_artifacts)[: self._max_items]
        for idx, related in enumerate(related_artifacts, start=1):
            if needle and needle not in related.lower() and not _tokens_overlap(needle, related):
                continue
            candidates.append(
                self._item(
                    context,
                    query_spec,
                    text=f"related_artifact={related}",
                    artifact_id=related,
                    title="related_artifact",
                    score=0.5,
                    rank=idx + 20,
                )
            )

        for idx, evidence in enumerate(context.parser_evidence[: self._max_items], start=1):
            if not isinstance(evidence, dict):
                continue
            excerpt = str(
                evidence.get("excerpt")
                or evidence.get("summary")
                or evidence.get("diagnostic")
                or evidence.get("message")
                or ""
            )
            if not excerpt:
                continue
            needle_miss = (
                needle
                and needle not in excerpt.lower()
                and not _tokens_overlap(needle, excerpt)
            )
            if needle_miss and evidence.get("artifact_id") != context.affected_artifact_id:
                continue
            artifact_id = (
                str(evidence.get("artifact_id") or "") or context.affected_artifact_id
            )
            title = str(
                evidence.get("title") or evidence.get("parser_name") or "parser_evidence"
            )
            candidates.append(
                self._item(
                    context,
                    query_spec,
                    text=excerpt,
                    artifact_id=artifact_id,
                    source_path=str(evidence.get("source_path") or "") or None,
                    line_start=_as_int(evidence.get("line_start")),
                    line_end=_as_int(evidence.get("line_end")),
                    title=title,
                    score=float(evidence.get("confidence") or 0.6),
                    rank=idx + 30,
                    metadata={"parser_evidence": True},
                )
            )

        for marker in sorted(context.artifact_availability)[:10]:
            candidates.append(
                self._item(
                    context,
                    query_spec,
                    text=f"artifact_available={marker}",
                    title="artifact_availability",
                    score=0.3,
                    rank=100,
                )
            )

        limited = candidates[: query_spec.top_k]
        return HypothesisRetrievalAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            source_type=HypothesisRetrievalSourceType.ARTIFACT,
            query_id=query_spec.query_id,
            status="COMPLETE" if limited else "NO_EVIDENCE",
            raw_result_count=len(candidates),
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
        artifact_id: str | None = None,
        source_path: str | None = None,
        line_start: int | None = None,
        line_end: int | None = None,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> HypothesisRetrievedItem:
        masked, _ = mask_secrets(text)
        return HypothesisRetrievedItem(
            source_type=HypothesisRetrievalSourceType.ARTIFACT,
            source_system="artifact_bundle",
            text_excerpt=masked[:1500],
            query_id=query_spec.query_id,
            hypothesis_id=context.hypothesis_id,
            source_id=artifact_id or source_path or title,
            artifact_id=artifact_id,
            title=title,
            normalized_text_hash=normalized_content_hash(masked[:400]),
            source_path=source_path,
            line_start=line_start,
            line_end=line_end,
            commit_sha=context.commit_sha,
            retrieval_score=score,
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            relation_candidate=query_spec.expected_relation or RetrievalItemRelation.CONTEXT,
            rank_within_query=rank,
            metadata=metadata or {},
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


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
