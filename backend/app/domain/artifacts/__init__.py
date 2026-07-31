"""Phase 6A artifact domain models and taxonomy helpers."""

from app.domain.artifacts.enums import (
    AcquisitionStatus,
    ArtifactKind,
    ArtifactSource,
    ParseStatus,
    RedactionStatus,
)
from app.domain.artifacts.models import (
    AcquisitionError,
    ArtifactRecord,
    DiagnosticMessage,
    EvidenceCandidate,
    GraphEntityPreview,
    GraphRelationshipPreview,
    IncidentArtifactBundle,
    SourceLocation,
    StructuredParseResult,
    content_sha256,
)
from app.domain.artifacts.taxonomy_hierarchy import map_failure_category

__all__ = [
    "AcquisitionError",
    "AcquisitionStatus",
    "ArtifactKind",
    "ArtifactRecord",
    "ArtifactSource",
    "DiagnosticMessage",
    "EvidenceCandidate",
    "GraphEntityPreview",
    "GraphRelationshipPreview",
    "IncidentArtifactBundle",
    "ParseStatus",
    "RedactionStatus",
    "SourceLocation",
    "StructuredParseResult",
    "content_sha256",
    "map_failure_category",
]
