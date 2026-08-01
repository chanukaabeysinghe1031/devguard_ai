"""Phase 6A.6 Part 2 — remediation generation package."""

from __future__ import annotations

from app.ai.counterfactual_remediation.generation.blast_radius import (
    RemediationBlastRadiusEstimator,
)
from app.ai.counterfactual_remediation.generation.constraint_validator import (
    RemediationConstraintValidator,
)
from app.ai.counterfactual_remediation.generation.deduplicator import (
    RemediationCandidateDeduplicator,
)
from app.ai.counterfactual_remediation.generation.diversity import (
    RemediationCandidateDiversitySelector,
)
from app.ai.counterfactual_remediation.generation.generation_service import (
    CounterfactualRemediationGenerationService,
    build_generation_context_from_foundation,
)
from app.ai.counterfactual_remediation.generation.historical_adapter import (
    HistoricalRemediationAdapter,
)
from app.ai.counterfactual_remediation.generation.llm_generator import (
    LLMCounterfactualRemediationGenerator,
)
from app.ai.counterfactual_remediation.generation.patch_renderer import RemediationPatchRenderer
from app.ai.counterfactual_remediation.generation.previous_success import (
    PreviousSuccessRemediationGenerator,
)
from app.ai.counterfactual_remediation.generation.prioritiser import (
    RemediationCandidatePrioritiser,
)
from app.ai.counterfactual_remediation.generation.prompt import (
    COUNTERFACTUAL_REMEDIATION_JSON_SCHEMA,
    build_remediation_prompt,
)
from app.ai.counterfactual_remediation.generation.reference_validator import (
    RemediationReferenceValidator,
)
from app.ai.counterfactual_remediation.generation.risk_analyzer import RemediationRiskAnalyzer
from app.ai.counterfactual_remediation.generation.rollback_generator import (
    RemediationRollbackGenerator,
)
from app.ai.counterfactual_remediation.generation.rule_generator import (
    RuleBasedRemediationGenerator,
    implemented_builder_template_ids,
)
from app.ai.counterfactual_remediation.generation.side_effects import (
    RemediationSideEffectAnalyzer,
)

__all__ = [
    "COUNTERFACTUAL_REMEDIATION_JSON_SCHEMA",
    "CounterfactualRemediationGenerationService",
    "HistoricalRemediationAdapter",
    "LLMCounterfactualRemediationGenerator",
    "PreviousSuccessRemediationGenerator",
    "RemediationBlastRadiusEstimator",
    "RemediationCandidateDeduplicator",
    "RemediationCandidateDiversitySelector",
    "RemediationCandidatePrioritiser",
    "RemediationConstraintValidator",
    "RemediationPatchRenderer",
    "RemediationReferenceValidator",
    "RemediationRiskAnalyzer",
    "RemediationRollbackGenerator",
    "RemediationSideEffectAnalyzer",
    "RuleBasedRemediationGenerator",
    "build_generation_context_from_foundation",
    "build_remediation_prompt",
    "implemented_builder_template_ids",
]
