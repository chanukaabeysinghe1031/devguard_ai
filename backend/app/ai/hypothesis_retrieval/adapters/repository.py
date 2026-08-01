"""Deterministic repository-change adapter (context paths/commit only)."""

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

ADAPTER_NAME = "repository_change"
ADAPTER_VERSION = "v1"


class RepositoryChangeRetrievalAdapter:
    """Retrieve changed files / commit metadata from hypothesis context only."""

    adapter_name = ADAPTER_NAME
    adapter_version = ADAPTER_VERSION
    supported_source_types = [HypothesisRetrievalSourceType.REPOSITORY_CHANGE]

    def __init__(self, *, enabled: bool = True, max_items: int = 20) -> None:
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
                source_type=HypothesisRetrievalSourceType.REPOSITORY_CHANGE,
                query_id=query_spec.query_id,
                status="SOURCE_UNAVAILABLE",
                failure_type=RetrievalFailureType.SOURCE_UNAVAILABLE,
                errors=["repository_adapter_disabled"],
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

        needle = (query_spec.normalized_query or "").lower()
        target_paths = {p.lower() for p in (query_spec.target_paths or []) if p}
        target_paths.update(p.lower() for p in context.changed_files if p)
        if context.affected_path:
            target_paths.add(context.affected_path.lower())
        if context.workflow_path:
            target_paths.add(context.workflow_path.lower())

        items: list[HypothesisRetrievedItem] = []
        paths = list(context.changed_files)
        if context.affected_path and context.affected_path not in paths:
            paths.append(context.affected_path)
        if context.workflow_path and context.workflow_path not in paths:
            paths.append(context.workflow_path)

        for idx, path in enumerate(paths[: self._max_items], start=1):
            path_l = path.lower()
            if target_paths and path_l not in target_paths and needle and needle not in path_l:
                continue
            if (
                needle
                and needle not in path_l
                and path_l not in target_paths
                and path not in context.changed_files
                and path != context.affected_path
            ):
                continue
            text = f"repository_change path={path} commit={context.commit_sha or ''}"
            masked, _ = mask_secrets(text)
            items.append(
                HypothesisRetrievedItem(
                    source_type=HypothesisRetrievalSourceType.REPOSITORY_CHANGE,
                    source_system="hypothesis_context",
                    text_excerpt=masked[:2000],
                    query_id=query_spec.query_id,
                    hypothesis_id=context.hypothesis_id,
                    source_id=path,
                    source_path=path,
                    commit_sha=context.commit_sha,
                    normalized_text_hash=normalized_content_hash(masked[:400]),
                    retrieval_score=1.0 if path in context.changed_files else 0.7,
                    adapter_name=self.adapter_name,
                    adapter_version=self.adapter_version,
                    relation_candidate=query_spec.expected_relation
                    or RetrievalItemRelation.CONTEXT,
                    rank_within_query=idx,
                    metadata={
                        "changed": path in context.changed_files,
                        "constraints": (query_spec.metadata or {}).get("artifact_constraints"),
                    },
                    associated_query_ids=[query_spec.query_id],
                    contributing_adapters=[self.adapter_name],
                )
            )

        if context.commit_sha and not items:
            text = f"repository_commit sha={context.commit_sha}"
            masked, _ = mask_secrets(text)
            items.append(
                HypothesisRetrievedItem(
                    source_type=HypothesisRetrievalSourceType.REPOSITORY_CHANGE,
                    source_system="hypothesis_context",
                    text_excerpt=masked,
                    query_id=query_spec.query_id,
                    hypothesis_id=context.hypothesis_id,
                    commit_sha=context.commit_sha,
                    normalized_text_hash=normalized_content_hash(masked),
                    retrieval_score=0.5,
                    adapter_name=self.adapter_name,
                    adapter_version=self.adapter_version,
                    relation_candidate=RetrievalItemRelation.CONTEXT,
                    rank_within_query=1,
                    associated_query_ids=[query_spec.query_id],
                    contributing_adapters=[self.adapter_name],
                )
            )

        return HypothesisRetrievalAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            source_type=HypothesisRetrievalSourceType.REPOSITORY_CHANGE,
            query_id=query_spec.query_id,
            status="COMPLETE" if items else "NO_EVIDENCE",
            raw_result_count=len(items),
            items=items,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
