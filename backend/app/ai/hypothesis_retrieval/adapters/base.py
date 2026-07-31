"""Adapter protocol for hypothesis-directed retrieval sources."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.domain.hypothesis_retrieval.enums import HypothesisRetrievalSourceType
from app.domain.hypothesis_retrieval.models import (
    HypothesisRetrievalAdapterResult,
    HypothesisRetrievalContext,
    HypothesisRetrievalQuerySpec,
)


@runtime_checkable
class HypothesisRetrievalAdapter(Protocol):
    adapter_name: str
    adapter_version: str
    supported_source_types: list[HypothesisRetrievalSourceType]

    def is_available(self) -> bool: ...

    def retrieve(
        self,
        context: HypothesisRetrievalContext,
        query_spec: HypothesisRetrievalQuerySpec,
    ) -> HypothesisRetrievalAdapterResult: ...

    def health_status(self) -> dict[str, Any]: ...

    def configuration_summary(self) -> dict[str, Any]: ...
