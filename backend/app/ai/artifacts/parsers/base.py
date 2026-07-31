"""Abstract base for Phase 6A structured artifact parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.artifacts.enums import ArtifactKind
from app.domain.artifacts.models import StructuredParseResult


class StructuredArtifactParser(ABC):
    """Pure structured extractor — no DB, network, or side effects."""

    name: str
    version: str

    @abstractmethod
    def supports(self, kind: ArtifactKind) -> bool:
        """Return True when this parser handles the artifact kind."""

    @abstractmethod
    def parse(
        self,
        content: str,
        *,
        filename: str,
        kind: ArtifactKind,
    ) -> StructuredParseResult:
        """Parse artifact content into entities, relationships, and evidence."""
