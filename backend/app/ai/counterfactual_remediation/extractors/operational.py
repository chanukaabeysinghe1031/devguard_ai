"""Operational / blast-radius remediation constraint extractor."""

from __future__ import annotations

from app.ai.counterfactual_remediation.extractors._helpers import (
    base_constraint,
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

_OPERATIONAL_RULES: tuple[tuple[str, str, dict, bool], ...] = (
    (
        "ops.no_prod_apply",
        "No production Terraform/cloud apply from remediation candidates",
        {"rule": "no_production_apply", "prohibit_commands": ["terraform apply", "kubectl apply"]},
        True,
    ),
    (
        "ops.no_destructive_replace",
        "No destructive resource replacement without explicit evidence",
        {"rule": "no_destructive_replace", "requires_explicit_evidence": True},
        True,
    ),
    (
        "ops.rollback_required",
        "Rollback must be possible for generated candidates",
        {"rule": "rollback_required", "rollback_types_allowed": [
            "RESTORE_ORIGINAL_FRAGMENT",
            "RESTORE_ORIGINAL_FILE",
            "REVERT_REFERENCE",
            "RESTORE_VERSION",
        ]},
        True,
    ),
    (
        "ops.minimal_scope",
        "Change scope should remain minimal and target hypothesized failure",
        {"rule": "minimal_scope", "prefer_one_file": True},
        True,
    ),
    (
        "ops.no_schema_reset",
        "No schema reset or database data loss",
        {"rule": "no_schema_reset_or_data_loss"},
        True,
    ),
    (
        "ops.no_volume_deletion",
        "No Docker volume deletion",
        {"rule": "no_docker_volume_deletion"},
        True,
    ),
    (
        "ops.preserve_unrelated_stages",
        "Preserve unrelated pipeline stages",
        {"rule": "preserve_unrelated_pipeline_stages"},
        False,
    ),
)


class OperationalRemediationConstraintExtractor(BaseRemediationConstraintExtractor):
    extractor_name = "operational_remediation_constraint_extractor"
    extractor_version = CONSTRAINT_EXTRACTOR_VERSION
    supported_artifact_types = frozenset(set(RemediationArtifactType))

    def extract(
        self,
        context: CounterfactualRemediationContext,
        current_state: RemediationCurrentState,
    ) -> ConstraintExtractionResult:
        started = now_ms()
        constraints: list[RemediationConstraint] = []
        for key, description, rule, blocking in _OPERATIONAL_RULES:
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key=key,
                    constraint_type=ConstraintType.OPERATIONAL,
                    severity=(
                        ConstraintSeverity.BLOCKING if blocking else ConstraintSeverity.HIGH
                    ),
                    source_type=ConstraintSourceType.SYSTEM_POLICY,
                    description=description,
                    machine_readable_rule=dict(rule),
                    is_blocking=blocking,
                    extractor_name=self.extractor_name,
                    limitations=["planning_layer_not_verifier"],
                )
            )

        if current_state.current_plan_changes:
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key="ops.plan_replacement_risk",
                    constraint_type=ConstraintType.REPLACEMENT_RISK,
                    severity=ConstraintSeverity.HIGH,
                    source_type=ConstraintSourceType.TERRAFORM_PLAN,
                    description="Plan indicates changes; avoid unrelated replacements",
                    machine_readable_rule={
                        "rule": "respect_plan_replacement_signals",
                        "plan_change_count": len(current_state.current_plan_changes),
                    },
                    is_blocking=True,
                    extractor_name=self.extractor_name,
                )
            )

        return finalize_result(
            extractor_name=self.extractor_name,
            constraints=constraints,
            started_ms=started,
            artifact_ids=[a for a in [current_state.artifact_id] if a],
            limitations=self.limitations(),
        )

    def limitations(self) -> list[str]:
        return super().limitations() + [
            "planning_layer_not_verifier",
            "cost_avoidance_heuristic_only",
        ]
