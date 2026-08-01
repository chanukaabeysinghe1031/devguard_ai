"""Build CounterfactualPrecondition list from hypothesis category + current state."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from app.ai.counterfactual_remediation.extractors._helpers import context_category
from app.ai.counterfactual_remediation.model_types import (
    CounterfactualPrecondition,
    CounterfactualRemediationContext,
    RemediationCurrentState,
)
from app.domain.counterfactual_remediation.enums import PreconditionStatus

logger = logging.getLogger(__name__)


def _status(present: bool | None) -> PreconditionStatus:
    if present is True:
        return PreconditionStatus.SATISFIED
    if present is False:
        return PreconditionStatus.NOT_SATISFIED
    return PreconditionStatus.UNKNOWN


def build_counterfactual_preconditions(
    context: CounterfactualRemediationContext,
    current_state: RemediationCurrentState,
    *,
    category: str | None = None,
) -> list[CounterfactualPrecondition]:
    """Deterministic preconditions (brief §24)."""
    category_text = (category or context_category(context) or context.causal_claim or "").lower()
    values = current_state.current_values or {}
    preconditions: list[CounterfactualPrecondition] = []

    def add(
        condition_type: str,
        description: str,
        *,
        expected: str | None,
        actual: Any,
        required: bool = True,
    ) -> None:
        if actual is None or actual == "" or actual == []:
            present: bool | None = False if expected else None
        else:
            present = True
        preconditions.append(
            CounterfactualPrecondition(
                id=str(uuid4()),
                hypothesis_id=context.hypothesis_id,
                condition_type=condition_type,
                description=description,
                expected_current_state=expected,
                actual_current_state=None if actual is None else str(actual),
                status=_status(present),
                artifact_ids=[a for a in [current_state.artifact_id] if a],
                is_required=required,
                limitations=["precondition_not_runtime_verified"],
            )
        )

    add(
        "affected_artifact_available",
        "Affected artifact / parser entities available",
        expected="artifact_present",
        actual=current_state.artifact_id or current_state.structured_entities or None,
        required=True,
    )

    if any(k in category_text for k in ("iam", "permission", "accessdenied", "access_denied", "policy")):
        denied = values.get("denied_action") or context.error_code or context.affected_command
        add(
            "iam_denied_action_known",
            "Denied IAM action is known",
            expected="denied_action",
            actual=denied,
        )
        principal = values.get("principal") or values.get("role") or values.get("role_arn")
        add(
            "iam_principal_known",
            "Active principal / role is known",
            expected="principal",
            actual=principal,
        )
        resource = context.affected_resource or values.get("resource")
        add(
            "iam_target_resource_known",
            "Target resource is known",
            expected="resource",
            actual=resource,
            required=False,
        )
        denies = values.get("explicit_denies")
        add(
            "iam_explicit_deny_state",
            "Explicit deny state known or explicitly unknown",
            expected="deny_state",
            actual="unknown" if denies is None else denies,
            required=False,
        )
        add(
            "iam_policy_artifact_available",
            "Policy artifact is available",
            expected="policy_artifact",
            actual=current_state.artifact_id
            if str(current_state.artifact_type).upper().find("POLICY") >= 0
            or current_state.current_permissions
            else None,
        )

    if any(k in category_text for k in ("role", "assume", "oidc", "credentials")):
        role_ref = values.get("role") or values.get("role_arn")
        add(
            "workflow_role_reference_known",
            "Workflow role reference is known",
            expected="role_arn",
            actual=role_ref,
        )

    if any(k in category_text for k in ("terraform", "reference", "module", "provider")):
        add(
            "terraform_addresses_known",
            "Terraform declared addresses available",
            expected="addresses",
            actual=values.get("addresses") or current_state.structured_entities or None,
        )

    if any(k in category_text for k in ("workflow", "needs", "job", "github")):
        add(
            "workflow_jobs_known",
            "Workflow jobs / needs graph available",
            expected="jobs",
            actual=current_state.current_dependencies or current_state.structured_entities or None,
        )

    logger.debug(
        "preconditions_built hypothesis_id=%s count=%s",
        context.hypothesis_id,
        len(preconditions),
    )
    return preconditions
