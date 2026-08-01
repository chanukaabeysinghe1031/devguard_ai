"""Phase 6A.6 Part 1 — counterfactual remediation AI package."""

from __future__ import annotations

from app.ai.counterfactual_remediation.conflict_detector import (
    RemediationConstraintConflictDetector,
)
from app.ai.counterfactual_remediation.constraint_orchestrator import (
    RemediationConstraintOrchestrator,
)
from app.ai.counterfactual_remediation.context_builder import (
    CounterfactualRemediationContextBuilder,
)
from app.ai.counterfactual_remediation.current_state import (
    RemediationCurrentStateBuilder,
    build_remediation_current_state,
)
from app.ai.counterfactual_remediation.extractors import (
    AwsIamRemediationConstraintExtractor,
    OperationalRemediationConstraintExtractor,
    RemediationConstraintExtractor,
    RepositoryProjectConstraintExtractor,
    SecurityRemediationConstraintExtractor,
    TerraformRemediationConstraintExtractor,
    WorkflowRemediationConstraintExtractor,
)
from app.ai.counterfactual_remediation.failure_condition import (
    build_counterfactual_failure_condition,
)
from app.ai.counterfactual_remediation.foundation_service import (
    CounterfactualRemediationFoundationService,
)
from app.ai.counterfactual_remediation.generation import (
    CounterfactualRemediationGenerationService,
    RuleBasedRemediationGenerator,
    implemented_builder_template_ids,
)
from app.ai.counterfactual_remediation.minimal_planner import (
    LOCALITY_RULES,
    DeterministicMinimalChangePlanner,
    MinimalChangePlanner,
    build_minimal_change_objective,
)
from app.ai.counterfactual_remediation.persist import (
    CounterfactualRemediationPersistService,
    CounterfactualRemediationRepository,
)
from app.ai.counterfactual_remediation.preconditions import (
    build_counterfactual_preconditions,
)
from app.ai.counterfactual_remediation.safety import (
    contains_secret_material,
    mask_for_context,
    sanitize_untrusted_instructions,
)
from app.ai.counterfactual_remediation.structural_validator import (
    CounterfactualCandidateStructuralValidator,
)
from app.ai.counterfactual_remediation.template_registry import RemediationTemplateRegistry
from app.ai.counterfactual_remediation.templates import build_initial_template_skeletons

__all__ = [
    "AwsIamRemediationConstraintExtractor",
    "CounterfactualCandidateStructuralValidator",
    "CounterfactualRemediationContextBuilder",
    "CounterfactualRemediationFoundationService",
    "CounterfactualRemediationGenerationService",
    "CounterfactualRemediationPersistService",
    "CounterfactualRemediationRepository",
    "DeterministicMinimalChangePlanner",
    "LOCALITY_RULES",
    "MinimalChangePlanner",
    "OperationalRemediationConstraintExtractor",
    "RemediationConstraintConflictDetector",
    "RemediationConstraintExtractor",
    "RemediationConstraintOrchestrator",
    "RemediationCurrentStateBuilder",
    "RemediationTemplateRegistry",
    "RepositoryProjectConstraintExtractor",
    "RuleBasedRemediationGenerator",
    "SecurityRemediationConstraintExtractor",
    "TerraformRemediationConstraintExtractor",
    "WorkflowRemediationConstraintExtractor",
    "build_counterfactual_failure_condition",
    "build_counterfactual_preconditions",
    "build_initial_template_skeletons",
    "build_minimal_change_objective",
    "build_remediation_current_state",
    "contains_secret_material",
    "implemented_builder_template_ids",
    "mask_for_context",
    "sanitize_untrusted_instructions",
]
