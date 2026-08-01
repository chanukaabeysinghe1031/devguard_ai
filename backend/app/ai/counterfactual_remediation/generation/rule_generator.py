"""Deterministic rule-based remediation candidate builders."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.ai.counterfactual_remediation.generation._helpers import (
    as_dict,
    contains_wildcard,
    first_str,
    get_current_values,
    get_source_fragment,
    safe_replace_once,
    sha256_text,
)
from app.ai.counterfactual_remediation.safety import contains_secret_material
from app.ai.counterfactual_remediation.templates import IMPLEMENTED_TEMPLATE_BUILDERS
from app.domain.counterfactual_remediation.enums import (
    CounterfactualCandidateStatus,
    CounterfactualChangeType,
    ExpectedFailureConditionStatus,
)
from app.domain.counterfactual_remediation.generation_enums import (
    RemediationGenerationStatus,
    RemediationGeneratorType,
)
from app.domain.counterfactual_remediation.generation_models import (
    RemediationGenerationContext,
    RemediationGenerationResult,
)
from app.domain.counterfactual_remediation.generation_versions import (
    RULE_REMEDIATION_GENERATOR_VERSION,
)
from app.domain.counterfactual_remediation.models import (
    CounterfactualChange,
    CounterfactualRemediationCandidate,
    MinimalChangePlan,
    RemediationCounterfactualState,
    RemediationTemplate,
)

logger = logging.getLogger(__name__)

BuilderFn = Callable[
    [RemediationGenerationContext, RemediationTemplate, dict[str, Any]],
    CounterfactualRemediationCandidate | None,
]


class RuleBasedRemediationGenerator:
    """Build structured candidates from current-state values only (no invention)."""

    def __init__(self, *, enabled: bool = True, max_candidates: int = 3) -> None:
        self._enabled = enabled
        self._max = max(1, max_candidates)
        self.version = RULE_REMEDIATION_GENERATOR_VERSION
        self._builders: dict[str, BuilderFn] = {
            "iam.add_scoped_missing_action": self._build_iam_add_action,
            "iam.correct_assumed_role_reference": self._build_iam_correct_role,
            "iam.correct_region": self._build_iam_correct_region,
            "iam.address_resource_policy_deny": self._build_iam_resource_policy_deny,
            "terraform.correct_invalid_resource_reference": self._build_tf_resource_ref,
            "terraform.correct_missing_module_output": self._build_tf_module_output,
            "terraform.correct_invalid_variable_value": self._build_tf_variable,
            "terraform.align_provider_alias_region": self._build_tf_provider_region,
            "terraform.correct_dependency_relationship": self._build_tf_dependency,
            "terraform.align_provider_version": self._build_tf_provider_version,
            "gha.correct_job_dependency": self._build_gha_job_dependency,
            "gha.correct_expression": self._build_gha_expression,
            "gha.correct_secret_reference_name": self._build_gha_secret_name,
            "gha.correct_reusable_workflow_input": self._build_gha_reusable_input,
            "gha.correct_action_version": self._build_gha_action_version,
            "gha.correct_environment_or_role_reference": self._build_gha_env_or_role,
            "deps.align_package_version": self._build_deps_align_version,
            "deps.restore_lockfile_consistency": self._build_deps_lockfile,
            "deps.use_supported_runtime_version": self._build_deps_runtime,
            "container.correct_image_tag": self._build_container_image_tag,
            "container.correct_registry_reference": self._build_container_registry,
            "container.correct_deployment_resource_name": self._build_container_resource_name,
            "container.correct_environment_configuration": self._build_container_environment,
        }

    def generate(
        self,
        context: RemediationGenerationContext,
        *,
        plan: MinimalChangePlan | None = None,
        templates: list[RemediationTemplate] | None = None,
    ) -> RemediationGenerationResult:
        started = datetime.now(UTC)
        if not self._enabled:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.RULE_TEMPLATE,
                status=RemediationGenerationStatus.DISABLED,
                duration_ms=0,
            )

        if context.unresolved_conflicts and any(
            as_dict(c).get("must_stop_generation") for c in context.unresolved_conflicts
        ):
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.RULE_TEMPLATE,
                status=RemediationGenerationStatus.BLOCKED,
                warnings=["blocked_by_unresolved_conflicts"],
                duration_ms=self._duration_ms(started),
            )

        templates = templates or list(context.eligible_templates)
        plan = plan or (context.plan if isinstance(context.plan, MinimalChangePlan) else None)
        state = as_dict(context.current_state)
        candidates: list[CounterfactualRemediationCandidate] = []
        rejected: list[str] = []
        warnings: list[str] = []

        for template in templates:
            if template.template_id in context.prohibited_template_ids:
                rejected.append(template.template_id)
                continue
            builder = self._builders.get(template.template_id)
            if builder is None:
                rejected.append(template.template_id)
                warnings.append(f"no_builder:{template.template_id}")
                continue
            try:
                candidate = builder(context, template, state)
            except Exception as exc:  # noqa: BLE001 — soft-fail per template
                warnings.append(f"builder_failed:{template.template_id}:{type(exc).__name__}")
                rejected.append(template.template_id)
                continue
            if candidate is None:
                rejected.append(template.template_id)
                warnings.append(f"incomplete_requirements:{template.template_id}")
                continue
            if plan is not None:
                candidate.change_types = list(
                    dict.fromkeys(list(candidate.change_types) + list(plan.proposed_change_types))
                )
            candidates.append(candidate)
            if len(candidates) >= self._max:
                break

        if not candidates and not templates or not candidates:
            status = RemediationGenerationStatus.NO_APPLICABLE_TEMPLATE
        elif warnings or rejected:
            status = RemediationGenerationStatus.PARTIAL
        else:
            status = RemediationGenerationStatus.COMPLETE

        return RemediationGenerationResult(
            generator=RemediationGeneratorType.RULE_TEMPLATE,
            status=status,
            candidates=candidates,
            rejected_template_ids=rejected,
            warnings=warnings,
            duration_ms=self._duration_ms(started),
            generator_version=self.version,
        )

    # --- IAM builders -----------------------------------------------------

    def _build_iam_add_action(
        self,
        context: RemediationGenerationContext,
        template: RemediationTemplate,
        state: dict[str, Any],
    ) -> CounterfactualRemediationCandidate | None:
        values = get_current_values(state)
        action = first_str(
            values.get("missing_action"),
            values.get("denied_action"),
            values.get("action"),
        )
        resource = first_str(values.get("resource"), values.get("denied_resource"))
        principal = first_str(values.get("principal"), values.get("role"), values.get("role_arn"))
        fragment = get_source_fragment(state, context.source_fragment)
        if not action or not resource or not principal or not fragment:
            return None
        if contains_wildcard(action) or contains_wildcard(resource):
            return self._rejected_candidate(
                context,
                template,
                state,
                reason="wildcard_action_or_resource_prohibited",
            )
        if values.get("explicit_denies") or values.get("explicit_deny"):
            return self._rejected_candidate(
                context,
                template,
                state,
                reason="explicit_deny_blocks_identity_policy_add",
            )
        # Build a narrowly scoped statement fragment addition.
        statement = {
            "Sid": "DevGuardScopedAllow",
            "Effect": "Allow",
            "Action": action,
            "Resource": resource,
        }
        original = fragment
        proposed = self._insert_iam_statement(fragment, statement)
        if proposed is None or proposed == original:
            return None
        return self._candidate_from_change(
            context,
            template,
            state,
            change_type=CounterfactualChangeType.UPDATE_PERMISSION,
            target_property="Statement",
            original=original,
            proposed=proposed,
            expected_effect=f"EXPECTED: allow {action} on {resource}",
            rationale="Add narrowly scoped missing action from current-state denial signals",
        )

    def _build_iam_correct_role(
        self,
        context: RemediationGenerationContext,
        template: RemediationTemplate,
        state: dict[str, Any],
    ) -> CounterfactualRemediationCandidate | None:
        values = get_current_values(state)
        current_role = first_str(
            values.get("role_arn"), values.get("role"), values.get("current_role")
        )
        expected_role = first_str(
            values.get("expected_role"),
            values.get("intended_role"),
            values.get("correct_role_arn"),
        )
        fragment = get_source_fragment(state, context.source_fragment)
        if not current_role or not expected_role or not fragment:
            return None
        if contains_wildcard(expected_role) or contains_secret_material(expected_role):
            return None
        proposed = safe_replace_once(fragment, current_role, expected_role)
        if proposed is None:
            return None
        return self._candidate_from_change(
            context,
            template,
            state,
            change_type=CounterfactualChangeType.UPDATE_ROLE,
            target_property="role",
            original=fragment,
            proposed=proposed,
            expected_effect="EXPECTED: workflow uses intended role ARN",
            rationale="Replace assumed role reference with known intended role",
        )

    def _build_iam_correct_region(
        self,
        context: RemediationGenerationContext,
        template: RemediationTemplate,
        state: dict[str, Any],
    ) -> CounterfactualRemediationCandidate | None:
        values = get_current_values(state)
        current = first_str(
            state.get("current_region"), values.get("region"), values.get("provider_region")
        )
        intended = first_str(
            values.get("intended_region"),
            values.get("expected_region"),
            values.get("target_region"),
        )
        fragment = get_source_fragment(state, context.source_fragment)
        if not current or not intended or not fragment or current == intended:
            return None
        proposed = safe_replace_once(fragment, current, intended)
        if proposed is None:
            return None
        return self._candidate_from_change(
            context,
            template,
            state,
            change_type=CounterfactualChangeType.UPDATE_REGION,
            target_property="region",
            original=fragment,
            proposed=proposed,
            expected_effect="EXPECTED: region reference matches target resource region",
            rationale="Update exact region property from known intended region",
        )

    def _build_iam_resource_policy_deny(
        self,
        context: RemediationGenerationContext,
        template: RemediationTemplate,
        state: dict[str, Any],
    ) -> CounterfactualRemediationCandidate | None:
        values = get_current_values(state)
        deny_id = first_str(
            values.get("deny_statement_id"),
            (values.get("explicit_denies") or [None])[0]
            if isinstance(values.get("explicit_denies"), list)
            else None,
        )
        intended_condition = first_str(
            values.get("intended_condition"),
            values.get("allowed_condition"),
        )
        fragment = get_source_fragment(state, context.source_fragment)
        if not deny_id or not intended_condition or not fragment:
            # Incomplete — do not invent a bypass allow.
            return self._incomplete_candidate(
                context,
                template,
                state,
                reason="resource_policy_deny_requires_known_intended_condition",
            )
        # Only adjust a known condition fragment when present.
        current_condition = first_str(values.get("current_condition"), values.get("deny_condition"))
        if not current_condition or current_condition not in fragment:
            return self._incomplete_candidate(
                context,
                template,
                state,
                reason="deny_condition_fragment_not_found",
            )
        proposed = safe_replace_once(fragment, current_condition, intended_condition)
        if proposed is None:
            return None
        return self._candidate_from_change(
            context,
            template,
            state,
            change_type=CounterfactualChangeType.UPDATE_CONDITION,
            target_property="Condition",
            original=fragment,
            proposed=proposed,
            expected_effect="EXPECTED: resource-policy deny addressed without add-allow bypass",
            rationale="Adjust known deny condition using supported intended condition",
        )

    # --- Terraform builders -----------------------------------------------

    def _build_tf_resource_ref(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("invalid_reference", "current_reference"),
            intended_keys=("valid_reference", "expected_reference", "corrected_reference"),
            change_type=CounterfactualChangeType.UPDATE_REFERENCE,
            target_property="resource_reference",
            expected_effect="EXPECTED: reference resolves to existing resource",
        )

    def _build_tf_module_output(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("missing_output_reference", "current_output_reference"),
            intended_keys=("expected_output_reference", "corrected_output_reference"),
            change_type=CounterfactualChangeType.UPDATE_REFERENCE,
            target_property="module_output",
            expected_effect="EXPECTED: module output reference corrected",
        )

    def _build_tf_variable(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("invalid_variable_value", "current_variable_value"),
            intended_keys=("expected_variable_value", "valid_variable_value"),
            change_type=CounterfactualChangeType.UPDATE_VALUE,
            target_property="variable",
            expected_effect="EXPECTED: variable value satisfies type/validation",
        )

    def _build_tf_provider_region(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("provider_region", "region", "current_region"),
            intended_keys=("intended_region", "expected_provider_region"),
            change_type=CounterfactualChangeType.UPDATE_REGION,
            target_property="provider.region",
            expected_effect="EXPECTED: provider alias/region aligned",
            also_check_state_region=True,
        )

    def _build_tf_dependency(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("invalid_depends_on", "current_dependency"),
            intended_keys=("expected_depends_on", "corrected_dependency"),
            change_type=CounterfactualChangeType.UPDATE_DEPENDENCY,
            target_property="depends_on",
            expected_effect="EXPECTED: dependency relationship corrected",
        )

    def _build_tf_provider_version(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("provider_version", "current_provider_version"),
            intended_keys=("compatible_provider_version", "expected_provider_version"),
            change_type=CounterfactualChangeType.UPDATE_VERSION,
            target_property="required_providers",
            expected_effect="EXPECTED: provider version constraints compatible",
        )

    # --- GitHub Actions builders ------------------------------------------

    def _build_gha_job_dependency(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("invalid_needs", "current_needs"),
            intended_keys=("expected_needs", "valid_job"),
            change_type=CounterfactualChangeType.UPDATE_JOB_DEPENDENCY,
            target_property="needs",
            expected_effect="EXPECTED: job dependency points to existing job",
        )

    def _build_gha_expression(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("invalid_expression", "current_expression"),
            intended_keys=("expected_expression", "corrected_expression"),
            change_type=CounterfactualChangeType.UPDATE_WORKFLOW_EXPRESSION,
            target_property="expression",
            expected_effect="EXPECTED: workflow expression corrected",
        )

    def _build_gha_secret_name(self, ctx, template, state):  # type: ignore[no-untyped-def]
        values = get_current_values(state)
        current = first_str(values.get("secret_reference"), values.get("current_secret_name"))
        intended = first_str(
            values.get("expected_secret_name"), values.get("corrected_secret_name")
        )
        fragment = get_source_fragment(state, ctx.source_fragment)
        if not current or not intended or not fragment:
            return None
        # Never embed secret values — names only.
        if contains_secret_material(intended) and "secrets." not in intended.lower():
            return None
        if not intended.startswith("secrets.") and "secrets." in (current or ""):
            # Keep secrets. prefix shape when correcting the name token.
            name = intended.split(".")[-1]
            intended = f"secrets.{name}"
        proposed = safe_replace_once(fragment, current, intended)
        if proposed is None:
            return None
        return self._candidate_from_change(
            ctx,
            template,
            state,
            change_type=CounterfactualChangeType.UPDATE_REFERENCE,
            target_property="secrets",
            original=fragment,
            proposed=proposed,
            expected_effect="EXPECTED: secret-reference name corrected (value never embedded)",
            rationale="Correct secret reference name only",
        )

    def _build_gha_reusable_input(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("invalid_workflow_input", "current_input"),
            intended_keys=("expected_workflow_input", "corrected_input"),
            change_type=CounterfactualChangeType.UPDATE_VALUE,
            target_property="with",
            expected_effect="EXPECTED: reusable-workflow input corrected",
        )

    def _build_gha_action_version(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("action_version", "current_action_ref"),
            intended_keys=("expected_action_version", "compatible_action_ref"),
            change_type=CounterfactualChangeType.UPDATE_VERSION,
            target_property="uses",
            expected_effect="EXPECTED: action version corrected",
        )

    def _build_gha_env_or_role(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("environment", "role_arn", "current_environment"),
            intended_keys=("expected_environment", "intended_role", "expected_role_arn"),
            change_type=CounterfactualChangeType.UPDATE_ENVIRONMENT_REFERENCE,
            target_property="environment",
            expected_effect="EXPECTED: environment/role reference corrected",
        )

    # --- Dependency builders ----------------------------------------------

    def _build_deps_align_version(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("package_version", "current_version"),
            intended_keys=("compatible_version", "expected_version"),
            change_type=CounterfactualChangeType.UPDATE_VERSION,
            target_property="version",
            expected_effect="EXPECTED: package version constraints compatible",
        )

    def _build_deps_lockfile(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("lockfile_entry", "current_lock_hash"),
            intended_keys=("expected_lockfile_entry", "previous_lock_hash"),
            change_type=CounterfactualChangeType.UPDATE_DEPENDENCY,
            target_property="lockfile",
            expected_effect="EXPECTED: lock-file consistency restored",
        )

    def _build_deps_runtime(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("runtime_version", "python_version", "node_version"),
            intended_keys=("supported_runtime_version", "expected_runtime_version"),
            change_type=CounterfactualChangeType.UPDATE_VERSION,
            target_property="runtime",
            expected_effect="EXPECTED: supported runtime version used",
        )

    # --- Container builders -----------------------------------------------

    def _build_container_image_tag(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("image_tag", "current_image"),
            intended_keys=("expected_image_tag", "corrected_image"),
            change_type=CounterfactualChangeType.UPDATE_VERSION,
            target_property="image",
            expected_effect="EXPECTED: image tag corrected",
        )

    def _build_container_registry(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("registry", "current_registry"),
            intended_keys=("expected_registry", "corrected_registry"),
            change_type=CounterfactualChangeType.UPDATE_REFERENCE,
            target_property="registry",
            expected_effect="EXPECTED: registry reference corrected",
        )

    def _build_container_resource_name(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("deployment_name", "resource_name"),
            intended_keys=("expected_deployment_name", "corrected_resource_name"),
            change_type=CounterfactualChangeType.UPDATE_RESOURCE_TARGET,
            target_property="metadata.name",
            expected_effect="EXPECTED: deployment resource name corrected",
        )

    def _build_container_environment(self, ctx, template, state):  # type: ignore[no-untyped-def]
        return self._replace_known_pair(
            ctx,
            template,
            state,
            current_keys=("env_value", "current_environment_config"),
            intended_keys=("expected_env_value", "corrected_environment_config"),
            change_type=CounterfactualChangeType.UPDATE_ENVIRONMENT_REFERENCE,
            target_property="env",
            expected_effect="EXPECTED: environment configuration corrected",
        )

    # --- Shared helpers ---------------------------------------------------

    def _replace_known_pair(
        self,
        context: RemediationGenerationContext,
        template: RemediationTemplate,
        state: dict[str, Any],
        *,
        current_keys: tuple[str, ...],
        intended_keys: tuple[str, ...],
        change_type: CounterfactualChangeType,
        target_property: str,
        expected_effect: str,
        also_check_state_region: bool = False,
    ) -> CounterfactualRemediationCandidate | None:
        values = get_current_values(state)
        current_args: list[Any] = [values.get(k) for k in current_keys]
        if also_check_state_region:
            current_args.append(state.get("current_region"))
        current = first_str(*current_args)
        intended = first_str(*(values.get(k) for k in intended_keys))
        fragment = get_source_fragment(state, context.source_fragment)
        if not current or not intended or not fragment or current == intended:
            return None
        if contains_wildcard(intended) or contains_secret_material(intended):
            return None
        proposed = safe_replace_once(fragment, str(current), str(intended))
        if proposed is None:
            return None
        return self._candidate_from_change(
            context,
            template,
            state,
            change_type=change_type,
            target_property=target_property,
            original=fragment,
            proposed=proposed,
            expected_effect=expected_effect,
            rationale=f"Deterministic transform for {template.template_id}",
        )

    def _insert_iam_statement(self, fragment: str, statement: dict[str, Any]) -> str | None:
        try:
            data = json.loads(fragment)
        except json.JSONDecodeError:
            # Textual insertion before closing Statement array if present.
            stmt_json = json.dumps(statement)
            match = re.search(r'("Statement"\s*:\s*\[)', fragment)
            if not match:
                return None
            insert_at = match.end()
            return fragment[:insert_at] + stmt_json + "," + fragment[insert_at:]
        if not isinstance(data, dict):
            return None
        statements = data.get("Statement")
        if statements is None:
            data["Statement"] = [statement]
        elif isinstance(statements, list):
            data["Statement"] = list(statements) + [statement]
        elif isinstance(statements, dict):
            data["Statement"] = [statements, statement]
        else:
            return None
        return json.dumps(data, indent=2) + "\n"

    def _candidate_from_change(
        self,
        context: RemediationGenerationContext,
        template: RemediationTemplate,
        state: dict[str, Any],
        *,
        change_type: CounterfactualChangeType,
        target_property: str,
        original: str,
        proposed: str,
        expected_effect: str,
        rationale: str,
        status: CounterfactualCandidateStatus = CounterfactualCandidateStatus.STRUCTURED,
    ) -> CounterfactualRemediationCandidate:
        candidate_id = str(uuid4())
        artifact_id = first_str(state.get("artifact_id"), *(context.valid_artifact_ids or [None]))
        change = CounterfactualChange(
            id=str(uuid4()),
            candidate_id=candidate_id,
            artifact_id=artifact_id,
            artifact_type=state.get("artifact_type"),
            source_path=first_str(state.get("source_path")),
            change_type=change_type,
            target_property=target_property,
            original_fragment=original,
            proposed_fragment=proposed,
            expected_effect=expected_effect,
            expected_failure_condition_removed=True,
            rationale=rationale,
            content_hash_before=sha256_text(original),
            content_hash_after_candidate=sha256_text(proposed),
            limitations=[
                "change_is_not_verified",
                "candidates_are_not_verified",
            ],
        )
        cf_state = RemediationCounterfactualState(
            candidate_id=candidate_id,
            artifact_id=artifact_id,
            artifact_type=state.get("artifact_type"),
            proposed_values={target_property: "updated"},
            expected_failure_condition_status=ExpectedFailureConditionStatus.EXPECTED_REMOVED,
            expected_changed_behaviors=[expected_effect],
            assumptions=["deterministic_rule_transform"],
            unknown_effects=["runtime_effects_unknown"],
            limitations=[
                "expected_effects_are_not_verified",
                "candidates_are_not_verified",
            ],
        )
        return CounterfactualRemediationCandidate(
            id=candidate_id,
            remediation_run_id=context.remediation_run_id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            incident_id=context.incident_id,
            analysis_id=context.analysis_id,
            hypothesis_id=context.hypothesis_id,
            candidate_key=f"{context.hypothesis_id}:{template.template_id}:rule",
            title=f"Rule candidate: {template.template_id}",
            summary=(
                f"Deterministic remediation candidate for hypothesis {context.hypothesis_id} "
                f"using template {template.template_id}. Not verified. Not applied."
            ),
            artifact_type=state.get("artifact_type"),
            affected_artifact_ids=[a for a in [artifact_id] if a],
            primary_artifact_id=artifact_id,
            target_paths=[p for p in [state.get("source_path")] if p],
            change_types=[change_type],
            changes=[change],
            current_state_snapshot=context.current_state,
            counterfactual_state_snapshot=cf_state,
            expected_effects=[expected_effect],
            expected_preserved_behaviors=list(template.expected_preserved_behaviors),
            assumptions=["rule_template_generation", "values_from_current_state_only"],
            limitations=[
                "candidates_are_not_verified",
                "candidates_are_not_applied",
                "no_runtime_verification_in_part2_generation",
            ],
            generator_type=RemediationGeneratorType.RULE_TEMPLATE.value,
            generator_name="rule_based_remediation_generator",
            generator_version=self.version,
            template_id=template.template_id,
            template_version=template.template_version,
            status=status,
        )

    def _incomplete_candidate(
        self,
        context: RemediationGenerationContext,
        template: RemediationTemplate,
        state: dict[str, Any],
        *,
        reason: str,
    ) -> CounterfactualRemediationCandidate:
        candidate_id = str(uuid4())
        artifact_id = first_str(state.get("artifact_id"))
        return CounterfactualRemediationCandidate(
            id=candidate_id,
            remediation_run_id=context.remediation_run_id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            incident_id=context.incident_id,
            analysis_id=context.analysis_id,
            hypothesis_id=context.hypothesis_id,
            candidate_key=f"{context.hypothesis_id}:{template.template_id}:incomplete",
            title=f"Incomplete: {template.template_id}",
            summary=f"Incomplete rule candidate ({reason}). Not verified.",
            artifact_type=state.get("artifact_type"),
            affected_artifact_ids=[a for a in [artifact_id] if a],
            primary_artifact_id=artifact_id,
            assumptions=["incomplete_requirements", reason],
            limitations=[
                "candidates_are_not_verified",
                "incomplete_current_state_requirements",
            ],
            generator_type=RemediationGeneratorType.RULE_TEMPLATE.value,
            generator_name="rule_based_remediation_generator",
            generator_version=self.version,
            template_id=template.template_id,
            template_version=template.template_version,
            status=CounterfactualCandidateStatus.INCOMPLETE,
        )

    def _rejected_candidate(
        self,
        context: RemediationGenerationContext,
        template: RemediationTemplate,
        state: dict[str, Any],
        *,
        reason: str,
    ) -> CounterfactualRemediationCandidate:
        candidate_id = str(uuid4())
        artifact_id = first_str(state.get("artifact_id"))
        return CounterfactualRemediationCandidate(
            id=candidate_id,
            remediation_run_id=context.remediation_run_id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            incident_id=context.incident_id,
            analysis_id=context.analysis_id,
            hypothesis_id=context.hypothesis_id,
            candidate_key=f"{context.hypothesis_id}:{template.template_id}:rejected",
            title=f"Rejected: {template.template_id}",
            summary=f"Rejected rule candidate ({reason}). Not verified.",
            artifact_type=state.get("artifact_type"),
            affected_artifact_ids=[a for a in [artifact_id] if a],
            primary_artifact_id=artifact_id,
            assumptions=[reason],
            limitations=["candidates_are_not_verified", "unsafe_or_prohibited_transform"],
            generator_type=RemediationGeneratorType.RULE_TEMPLATE.value,
            generator_name="rule_based_remediation_generator",
            generator_version=self.version,
            template_id=template.template_id,
            template_version=template.template_version,
            status=CounterfactualCandidateStatus.REJECTED,
        )

    @staticmethod
    def _duration_ms(started: datetime) -> int:
        return int((datetime.now(UTC) - started).total_seconds() * 1000)


def implemented_builder_template_ids() -> frozenset[str]:
    return IMPLEMENTED_TEMPLATE_BUILDERS
