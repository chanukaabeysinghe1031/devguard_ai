"""Build CounterfactualFailureCondition with expected language only."""

from __future__ import annotations

import logging
from uuid import uuid4

from app.ai.counterfactual_remediation.extractors._helpers import context_category
from app.ai.counterfactual_remediation.model_types import (
    CounterfactualFailureCondition,
    CounterfactualRemediationContext,
    RemediationCurrentState,
)
from app.domain.counterfactual_remediation.enums import VerifierType

logger = logging.getLogger(__name__)


def build_counterfactual_failure_condition(
    context: CounterfactualRemediationContext,
    current_state: RemediationCurrentState,
) -> CounterfactualFailureCondition:
    """Construct expected failure-condition contract (brief §25)."""
    category = context_category(context)
    observed = (
        context.failure_condition_summary
        or context.causal_claim
        or current_state.current_failure_condition
        or "observed failure condition"
    )
    denied = current_state.current_values.get("denied_action") or context.error_code
    principal = current_state.current_values.get("principal") or current_state.current_values.get(
        "role"
    )
    resource = context.affected_resource or current_state.current_values.get("resource")

    if any(k in category for k in ("iam", "permission", "access")):
        condition_type = "iam_access_denied"
        expected = (
            "EXPECTED: IAM evaluation no longer denies the known action "
            "for the known principal/resource (not a runtime guarantee)"
        )
        verifiers: list[VerifierType | str] = [
            VerifierType.IAM_POLICY_STRUCTURE,
            VerifierType.IAM_LEAST_PRIVILEGE,
            VerifierType.COUNTERFACTUAL_FAILURE_CONDITION,
        ]
        indicator = f"policy_allows:{denied}" if denied else "policy_allows_denied_action"
    elif any(k in category for k in ("terraform", "reference", "module")):
        condition_type = "terraform_reference_error"
        expected = (
            "EXPECTED: Terraform reference resolves to an existing resource/output "
            "(static check only; not verified)"
        )
        verifiers = [
            VerifierType.TERRAFORM_VALIDATE,
            VerifierType.TERRAFORM_DEPENDENCY,
            VerifierType.COUNTERFACTUAL_FAILURE_CONDITION,
        ]
        indicator = "reference_resolves"
    elif any(k in category for k in ("workflow", "needs", "github", "job")):
        condition_type = "workflow_dependency_error"
        expected = (
            "EXPECTED: Workflow job dependency points to an existing job "
            "and expressions resolve (parse-level expectation only)"
        )
        verifiers = [
            VerifierType.WORKFLOW_YAML_PARSE,
            VerifierType.ACTIONLINT,
            VerifierType.COUNTERFACTUAL_FAILURE_CONDITION,
        ]
        indicator = "needs_target_exists"
    elif any(k in category for k in ("depend", "version", "package", "lock")):
        condition_type = "dependency_version_conflict"
        expected = (
            "EXPECTED: Required package version constraints become compatible "
            "(not installed or executed in Part 1)"
        )
        verifiers = [VerifierType.COUNTERFACTUAL_FAILURE_CONDITION]
        indicator = "version_constraints_compatible"
    else:
        condition_type = "generic_failure_condition"
        expected = (
            "EXPECTED_REMOVED or EXPECTED_REDUCED for the hypothesized failure "
            "condition after a minimal configuration change (unverified)"
        )
        verifiers = [VerifierType.COUNTERFACTUAL_FAILURE_CONDITION]
        indicator = "failure_signature_absent_in_static_check"

    condition = CounterfactualFailureCondition(
        condition_id=str(uuid4()),
        hypothesis_id=context.hypothesis_id,
        observed_condition=str(observed),
        condition_type=condition_type,
        triggering_action=str(denied) if denied else context.affected_command,
        affected_resource=str(resource) if resource else None,
        active_principal=str(principal) if principal else None,
        affected_artifact=current_state.source_path or context.source_path,
        expected_condition_after_change=expected,
        measurable_static_indicator=indicator,
        required_verifier_types=verifiers,
        confidence=0.0,
        limitations=[
            "expected_language_only_not_runtime_guarantee",
            "does_not_claim_failure_will_definitely_disappear",
            "verifiers_not_executed_in_part_1",
        ],
    )
    logger.debug(
        "failure_condition_built hypothesis_id=%s type=%s",
        context.hypothesis_id,
        condition_type,
    )
    return condition
