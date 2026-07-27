"""Parsing interfaces for uploaded artifacts (no AI analysis)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.enums import FileType


class ArtifactParser(ABC):
    """Extract lightweight metadata from validated upload content."""

    @abstractmethod
    def supports(self, file_type: FileType) -> bool:
        """Return True when this parser handles the file type."""

    @abstractmethod
    def extract_metadata(self, *, content: str, original_filename: str) -> dict[str, Any]:
        """Return serialisable metadata. Must not execute content."""
