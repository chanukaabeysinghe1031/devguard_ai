"""Minimal-change planner contract and deterministic skeleton (brief §27–§28)."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from app.ai.counterfactual_remediation.extractors._helpers import context_category
from app.ai.counterfactual_remediation.model_types import (
    OPTIMIZATION_PRIORITIES,
    ConstraintConflict,
    CounterfactualFailureCondition,
    CounterfactualPrecondition,
    CounterfactualRemediationContext,
    MinimalChangeObjective,
    MinimalChangePlan,
    RemediationConstraintSet,
    RemediationCurrentState,
    RemediationTemplate,
)
from app.ai.counterfactual_remediation.versions import MINIMAL_CHANGE_PLANNER_VERSION
from app.domain.counterfactual_remediation.enums import (
    MinimalChangePlanStatus,
    PreconditionStatus,
    RemediationArtifactType,
)

logger = logging.getLogger(__name__)

LOCALITY_RULES: tuple[str, ...] = (
    "prefer_artifact_connected_to_hypothesized_cause",
    "prefer_one_file_over_multi_file",
    "prefer_exact_property_replacement_over_rewrite",
    "prefer_update_wrong_reference_over_adding_permissions",
    "prefer_correct_intended_role_over_broadening_wrong_role",
    "prefer_explicit_dependency_correction_over_sleep_retry",
    "prefer_scoped_iam_over_wildcard",
    "prefer_version_alignment_over_disabling_checks",
    "prefer_correct_region_account_env_over_duplicating_resources",
    "prefer_restore_previous_successful_when_supported",
    "never_fix_test_by_deleting_or_bypassing_test",
    "never_fix_policy_failure_by_disabling_scanner",
)


@runtime_checkable
class MinimalChangePlanner(Protocol):
    """Planner contract — Part 1 returns skeletons only, no final patches."""

    def plan(
        self,
        context: CounterfactualRemediationContext,
        current_state: RemediationCurrentState,
        constraint_set: RemediationConstraintSet,
        preconditions: list[CounterfactualPrecondition],
        failure_condition: CounterfactualFailureCondition,
        objective: MinimalChangeObjective,
        templates: list[RemediationTemplate],
        *,
        conflicts: list[ConstraintConflict] | None = None,
        enabled: bool = True,
    ) -> MinimalChangePlan: ...


class DeterministicMinimalChangePlanner:
    """Heuristic skeleton planner applying locality rules. No patch bodies."""

    planner_version = MINIMAL_CHANGE_PLANNER_VERSION

    def plan(
        self,
        context: CounterfactualRemediationContext,
        current_state: RemediationCurrentState,
        constraint_set: RemediationConstraintSet,
        preconditions: list[CounterfactualPrecondition],
        failure_condition: CounterfactualFailureCondition,
        objective: MinimalChangeObjective,
        templates: list[RemediationTemplate],
        *,
        conflicts: list[ConstraintConflict] | None = None,
        enabled: bool = True,
    ) -> MinimalChangePlan:
        if not enabled:
            return MinimalChangePlan(
                hypothesis_id=context.hypothesis_id,
                candidate_plan_key=f"{context.hypothesis_id}:disabled",
                status=MinimalChangePlanStatus.DISABLED,
                planner_version=self.planner_version,
            )

        conflicts = conflicts or []
        blocking_keys = [
            c.constraint_key for c in constraint_set.blocking_constraints if c.constraint_key
        ]
        incomplete = list(context.missing_information) + list(context.missing_artifacts)
        for pre in preconditions:
            if pre.is_required and pre.status in {
                PreconditionStatus.NOT_SATISFIED,
                PreconditionStatus.UNKNOWN,
            }:
                incomplete.append(f"precondition:{pre.condition_type}")

        artifact_type = current_state.artifact_type
        if hasattr(artifact_type, "value"):
            artifact_value = str(artifact_type.value)  # type: ignore[union-attr]
        else:
            artifact_value = str(artifact_type or "")

        if artifact_value == RemediationArtifactType.SOURCE_CODE.value and not (
            current_state.source_fragment
        ):
            return MinimalChangePlan(
                hypothesis_id=context.hypothesis_id,
                candidate_plan_key=f"{context.hypothesis_id}:unsupported_source",
                status=MinimalChangePlanStatus.UNSUPPORTED_ARTIFACT,
                incomplete_information=incomplete + ["source_code_without_fragment"],
                blocking_constraints=blocking_keys,
                assumptions=list(LOCALITY_RULES),
                planner_version=self.planner_version,
                limitations=["plan_skeleton_only_no_final_patch", "candidates_are_not_verified"],
            )

        if any(c.must_stop_generation for c in conflicts):
            return MinimalChangePlan(
                hypothesis_id=context.hypothesis_id,
                candidate_plan_key=f"{context.hypothesis_id}:blocked_conflict",
                status=MinimalChangePlanStatus.BLOCKED_BY_CONSTRAINTS,
                blocking_constraints=blocking_keys
                + [i for c in conflicts for i in c.involved_constraint_ids],
                incomplete_information=incomplete,
                assumptions=["conflict_resolution_deferred", *LOCALITY_RULES[:3]],
                planner_version=self.planner_version,
                limitations=["plan_skeleton_only_no_final_patch", "candidates_are_not_verified"],
            )

        if not templates and artifact_value == RemediationArtifactType.UNKNOWN.value:
            return MinimalChangePlan(
                hypothesis_id=context.hypothesis_id,
                candidate_plan_key=f"{context.hypothesis_id}:unsupported",
                status=MinimalChangePlanStatus.UNSUPPORTED_ARTIFACT,
                incomplete_information=incomplete + ["no_applicable_template"],
                planner_version=self.planner_version,
                assumptions=list(LOCALITY_RULES),
                limitations=["plan_skeleton_only_no_final_patch", "candidates_are_not_verified"],
            )

        target = (
            current_state.artifact_id
            or context.source_path
            or objective.primary_target
            or "unknown_target"
        )
        change_types = sorted(
            {
                (t.change_type.value if hasattr(t.change_type, "value") else str(t.change_type))
                for t in templates
            }
        )
        category = context_category(context)
        properties = [
            p
            for p in [
                objective.primary_property,
                "reference" if "reference" in (context.causal_claim or "").lower() else None,
                "permission" if "permission" in category else None,
            ]
            if p
        ]

        if (
            incomplete
            and not current_state.source_fragment
            and not current_state.structured_entities
        ):
            status = MinimalChangePlanStatus.INCOMPLETE
        elif blocking_keys and not templates:
            status = MinimalChangePlanStatus.NO_SAFE_CHANGE
        elif incomplete:
            status = MinimalChangePlanStatus.INCOMPLETE
        else:
            status = MinimalChangePlanStatus.READY_FOR_GENERATION

        plan = MinimalChangePlan(
            hypothesis_id=context.hypothesis_id,
            candidate_plan_key=(
                f"{context.hypothesis_id}:skeleton:"
                f"{templates[0].template_id if templates else 'none'}"
            ),
            target_artifacts=[str(target)],
            proposed_change_types=change_types,
            proposed_properties=properties,
            change_sequence=[
                {
                    "order": 1,
                    "action": "apply_locality_rules",
                    "rules": list(LOCALITY_RULES[:5]),
                    "template_id": templates[0].template_id if templates else None,
                    "template_ids": [t.template_id for t in templates],
                }
            ],
            constraints_considered=[c.constraint_key for c in constraint_set.constraints],
            blocking_constraints=blocking_keys,
            assumptions=[
                "part_1_skeleton_only",
                "no_final_patch",
                "optimization_order="
                f"{list(objective.optimization_priorities or OPTIMIZATION_PRIORITIES)[:3]}",
                *LOCALITY_RULES,
            ],
            expected_effects=[
                effect
                for effect in [
                    failure_condition.expected_condition_after_change,
                    *[e for t in templates for e in t.expected_effects],
                ]
                if effect
            ][:20],
            expected_preserved_behaviors=[
                b for t in templates for b in t.expected_preserved_behaviors
            ][:20],
            rollback_requirements=["RESTORE_ORIGINAL_FRAGMENT"],
            incomplete_information=sorted(set(incomplete)),
            planner_version=self.planner_version,
            status=status,
            warnings=[],
            limitations=["plan_skeleton_only_no_final_patch", "candidates_are_not_verified"],
        )
        logger.debug(
            "minimal_plan_built hypothesis_id=%s status=%s",
            context.hypothesis_id,
            status.value,
        )
        return plan


def build_minimal_change_objective(
    context: CounterfactualRemediationContext,
    current_state: RemediationCurrentState,
    *,
    maximum_files: int = 5,
    maximum_changed_lines: int = 200,
) -> MinimalChangeObjective:
    return MinimalChangeObjective(
        hypothesis_id=context.hypothesis_id,
        primary_target=current_state.artifact_id or context.source_path,
        primary_property=None,
        desired_state="remove_or_reduce_predicted_failure_condition",
        maximum_files=maximum_files,
        maximum_changed_lines=maximum_changed_lines,
        allowed_artifact_types=[
            (
                str(current_state.artifact_type.value)  # type: ignore[union-attr]
                if hasattr(current_state.artifact_type, "value")
                else str(current_state.artifact_type or RemediationArtifactType.UNKNOWN.value)
            )
        ],
        preserve_behaviors=[
            "security_controls",
            "approval_gates",
            "encryption",
            "unrelated_pipeline_stages",
        ],
        avoid_side_effects=[
            "permission_expansion",
            "resource_replacement",
            "public_exposure",
            "test_bypass",
        ],
        optimization_priorities=list(OPTIMIZATION_PRIORITIES),
    )
