"""AWS / IAM remediation constraint extractor."""

from __future__ import annotations

from typing import Any

from app.ai.counterfactual_remediation.extractors._helpers import (
    base_constraint,
    entity_meta,
    entity_type,
    finalize_result,
    now_ms,
)
from app.ai.counterfactual_remediation.extractors.base import BaseRemediationConstraintExtractor
from app.ai.counterfactual_remediation.model_types import (
    ConstraintExtractionResult,
    CounterfactualRemediationContext,
    RemediationConstraint,
    RemediationCurrentState,
)
from app.ai.counterfactual_remediation.versions import CONSTRAINT_EXTRACTOR_VERSION
from app.domain.counterfactual_remediation.enums import (
    ConstraintSeverity,
    ConstraintSourceType,
    ConstraintType,
    RemediationArtifactType,
)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


class AwsIamRemediationConstraintExtractor(BaseRemediationConstraintExtractor):
    extractor_name = "aws_iam_remediation_constraint_extractor"
    extractor_version = CONSTRAINT_EXTRACTOR_VERSION
    supported_artifact_types = frozenset(
        {
            RemediationArtifactType.IAM_POLICY,
            RemediationArtifactType.RESOURCE_POLICY,
            RemediationArtifactType.TERRAFORM_POLICY,
        }
    )

    def extract(
        self,
        context: CounterfactualRemediationContext,
        current_state: RemediationCurrentState,
    ) -> ConstraintExtractionResult:
        started = now_ms()
        constraints: list[RemediationConstraint] = []
        warnings: list[str] = []
        entities = list(current_state.structured_entities) or list(context.parser_entities)

        denied_action = current_state.current_values.get("denied_action") or context.error_code
        if not denied_action and context.affected_command:
            denied_action = context.affected_command
        principal = current_state.current_values.get(
            "principal"
        ) or current_state.current_values.get("role")
        resource = context.affected_resource or current_state.current_values.get("resource")

        if denied_action:
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key=f"iam.denied_action:{denied_action}",
                    constraint_type=ConstraintType.PERMISSION,
                    severity=ConstraintSeverity.HIGH,
                    source_type=ConstraintSourceType.AWS_ERROR,
                    description="Missing permission should be scoped to known denied action",
                    machine_readable_rule={
                        "rule": "scope_allow_to_denied_action",
                        "action": denied_action,
                        "resource": resource,
                        "principal": principal,
                    },
                    is_blocking=False,
                    extractor_name=self.extractor_name,
                    expected_value=denied_action,
                )
            )

        explicit_denies: list[str] = []
        for entity in entities:
            et = entity_type(entity)
            meta = entity_meta(entity)
            if et in {"POLICY_STATEMENT", "IAM_POLICY"}:
                effect = str(meta.get("Effect") or meta.get("effect") or "").lower()
                actions = [str(a) for a in _as_list(meta.get("Action") or meta.get("actions"))]
                resources = [
                    str(r) for r in _as_list(meta.get("Resource") or meta.get("resources"))
                ]
                sid = str(entity.get("label") or entity.get("id") or "")
                if effect == "deny":
                    explicit_denies.append(sid)
                    constraints.append(
                        base_constraint(
                            context=context,
                            current_state=current_state,
                            constraint_key=f"iam.explicit_deny:{sid}",
                            constraint_type=ConstraintType.EXPLICIT_DENY,
                            severity=ConstraintSeverity.BLOCKING,
                            source_type=ConstraintSourceType.IAM_POLICY,
                            description="Explicit deny cannot be fixed by adding another allow",
                            machine_readable_rule={
                                "rule": "explicit_deny_blocks_add_allow",
                                "sid": sid,
                                "Action": actions,
                                "Resource": resources,
                            },
                            is_blocking=True,
                            extractor_name=self.extractor_name,
                            prohibited_value={"add_allow_over_deny": True},
                        )
                    )
                if "*" in actions or any(a == "*" for a in actions):
                    constraints.append(
                        base_constraint(
                            context=context,
                            current_state=current_state,
                            constraint_key=f"iam.wildcard.action:{sid}",
                            constraint_type=ConstraintType.LEAST_PRIVILEGE,
                            severity=ConstraintSeverity.BLOCKING,
                            source_type=ConstraintSourceType.IAM_POLICY,
                            description="Candidate must not silently introduce Action: '*'",
                            machine_readable_rule={
                                "rule": "no_action_wildcard",
                                "sid": sid,
                            },
                            is_blocking=True,
                            extractor_name=self.extractor_name,
                            prohibited_value="*",
                        )
                    )
                if "*" in resources or any(r == "*" for r in resources):
                    constraints.append(
                        base_constraint(
                            context=context,
                            current_state=current_state,
                            constraint_key=f"iam.wildcard.resource:{sid}",
                            constraint_type=ConstraintType.LEAST_PRIVILEGE,
                            severity=ConstraintSeverity.BLOCKING,
                            source_type=ConstraintSourceType.IAM_POLICY,
                            description="Candidate must not silently introduce Resource: '*'",
                            machine_readable_rule={
                                "rule": "no_resource_wildcard",
                                "sid": sid,
                            },
                            is_blocking=True,
                            extractor_name=self.extractor_name,
                            prohibited_value="*",
                        )
                    )

        if principal:
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key=f"iam.principal:{principal}",
                    constraint_type=ConstraintType.PERMISSION,
                    severity=ConstraintSeverity.HIGH,
                    source_type=ConstraintSourceType.AWS_ERROR,
                    description="Wrong role must not be fixed by broadening an unrelated role",
                    machine_readable_rule={
                        "rule": "correct_intended_principal_not_broaden_unrelated",
                        "principal": principal,
                    },
                    is_blocking=True,
                    extractor_name=self.extractor_name,
                    expected_value=principal,
                )
            )

        constraints.append(
            base_constraint(
                context=context,
                current_state=current_state,
                constraint_key="iam.least_privilege",
                constraint_type=ConstraintType.LEAST_PRIVILEGE,
                severity=ConstraintSeverity.BLOCKING,
                source_type=ConstraintSourceType.SYSTEM_POLICY,
                description="Allow statements must remain least-privilege scoped",
                machine_readable_rule={
                    "rule": "least_privilege_required",
                    "forbid_action_star": True,
                    "forbid_resource_star": True,
                },
                is_blocking=True,
                extractor_name=self.extractor_name,
            )
        )

        # Missing SCP / permissions boundary as evidence limitation — not invented.
        constraints.append(
            base_constraint(
                context=context,
                current_state=current_state,
                constraint_key="iam.scp_unknown",
                constraint_type=ConstraintType.EVIDENCE_LIMITATION,
                severity=ConstraintSeverity.INFORMATIONAL,
                source_type=ConstraintSourceType.AWS_ERROR,
                description="SCP / permissions-boundary state unknown; do not invent",
                machine_readable_rule={
                    "rule": "missing_scp_is_evidence_limitation",
                    "scp_available": False,
                    "permissions_boundary_available": False,
                },
                is_blocking=False,
                extractor_name=self.extractor_name,
                limitations=["scp_not_observed", "permissions_boundary_not_observed"],
            )
        )
        warnings.append("scp_and_permissions_boundary_unknown")

        if not entities:
            warnings.append("iam_policy_entities_unavailable")

        return finalize_result(
            extractor_name=self.extractor_name,
            constraints=constraints,
            started_ms=started,
            artifact_ids=[a for a in [current_state.artifact_id] if a],
            warnings=warnings,
            limitations=self.limitations(),
        )

    def limitations(self) -> list[str]:
        return super().limitations() + [
            "no_aws_api_calls",
            "scp_unknown_unless_artifact_present",
            "explicit_deny_detection_from_parser_only",
        ]
