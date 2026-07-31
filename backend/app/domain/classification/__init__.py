"""Phase 6A.3 hierarchical classification domain package."""

from app.domain.classification.enums import (
    AgreementLevel,
    ClassificationConflictType,
    ClassificationRecommendedAction,
    ClassificationStatus,
    DisagreementRecommendedAction,
    OpenSetStatus,
)
from app.domain.classification.models import (
    ClassificationCandidateDetail,
    ClassificationConfidenceBreakdown,
    ClassificationConfidenceComponent,
    ClassificationDisagreementResult,
    HierarchicalClassificationResult,
    OpenSetAssessment,
    StageClassifierResult,
)
from app.domain.classification.taxonomy_registry import (
    MAPPING_VERSION,
    FailureTaxonomyPath,
    FailureTaxonomyRegistry,
    get_taxonomy_registry,
)

__all__ = [
    "AgreementLevel",
    "ClassificationCandidateDetail",
    "ClassificationConfidenceBreakdown",
    "ClassificationConfidenceComponent",
    "ClassificationConflictType",
    "ClassificationDisagreementResult",
    "ClassificationRecommendedAction",
    "ClassificationStatus",
    "DisagreementRecommendedAction",
    "FailureTaxonomyPath",
    "FailureTaxonomyRegistry",
    "HierarchicalClassificationResult",
    "MAPPING_VERSION",
    "OpenSetAssessment",
    "OpenSetStatus",
    "StageClassifierResult",
    "get_taxonomy_registry",
]
