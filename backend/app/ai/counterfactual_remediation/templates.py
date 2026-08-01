"""Remediation template skeletons for core failure families (brief §30)."""

from __future__ import annotations

from app.ai.counterfactual_remediation.model_types import RemediationTemplate
from app.ai.counterfactual_remediation.versions import REMEDIATION_TEMPLATES_VERSION
from app.domain.counterfactual_remediation.enums import (
    CounterfactualChangeType,
    RemediationArtifactType,
    RollbackType,
    VerifierType,
)

# Template IDs with Part 2 deterministic builders (see generation/rule_generator.py).
IMPLEMENTED_TEMPLATE_BUILDERS: frozenset[str] = frozenset(
    {
        "iam.add_scoped_missing_action",
        "iam.correct_assumed_role_reference",
        "iam.correct_region",
        "iam.address_resource_policy_deny",
        "terraform.correct_invalid_resource_reference",
        "terraform.correct_missing_module_output",
        "terraform.correct_invalid_variable_value",
        "terraform.align_provider_alias_region",
        "terraform.correct_dependency_relationship",
        "terraform.align_provider_version",
        "gha.correct_job_dependency",
        "gha.correct_expression",
        "gha.correct_secret_reference_name",
        "gha.correct_reusable_workflow_input",
        "gha.correct_action_version",
        "gha.correct_environment_or_role_reference",
        "deps.align_package_version",
        "deps.restore_lockfile_consistency",
        "deps.use_supported_runtime_version",
        "container.correct_image_tag",
        "container.correct_registry_reference",
        "container.correct_deployment_resource_name",
        "container.correct_environment_configuration",
    }
)


def _skel(
    *,
    template_id: str,
    family: str,
    category_codes: list[str],
    patterns: list[str],
    artifact_types: list[str],
    change_type: CounterfactualChangeType,
    effects: list[str],
    verifiers: list[str],
    prohibited: list[str] | None = None,
) -> RemediationTemplate:
    implemented = template_id in IMPLEMENTED_TEMPLATE_BUILDERS
    limitations = (
        [
            "candidate_builder_implemented=true",
            "candidates_are_not_verified",
            "builder_does_not_execute_verifiers",
        ]
        if implemented
        else [
            "candidate_builder_implemented=false",
            "candidate_builder_not_implemented",
            "no_final_patch_generation",
        ]
    )
    risk_notes = (
        ["part_2_deterministic_builder", f"family:{family}"]
        if implemented
        else ["part_1_skeleton_unimplemented_builder", f"family:{family}"]
    )
    return RemediationTemplate(
        template_id=template_id,
        template_version=REMEDIATION_TEMPLATES_VERSION,
        category_codes=category_codes,
        hierarchy_paths=[f"family/{family}"],
        supported_hypothesis_patterns=patterns,
        supported_artifact_types=artifact_types,
        prohibited_conditions=list(
            prohibited
            or [
                "plaintext_secret",
                "action_wildcard",
                "resource_wildcard",
                "disable_scanner",
                "delete_test",
            ]
        ),
        change_type=change_type,
        expected_effects=effects,
        expected_preserved_behaviors=[
            "least_privilege",
            "security_controls",
            "rollback_possibility",
        ],
        default_verification_requirements=verifiers,
        default_rollback_strategy=RollbackType.RESTORE_ORIGINAL_FRAGMENT,
        risk_notes=risk_notes,
        limitations=limitations,
    )


def build_initial_template_skeletons() -> list[RemediationTemplate]:
    """Template registry entries — Part 2 builders marked where implemented."""
    iam = RemediationArtifactType.IAM_POLICY.value
    resource_policy = RemediationArtifactType.RESOURCE_POLICY.value
    tf = RemediationArtifactType.TERRAFORM_CONFIGURATION.value
    gha = RemediationArtifactType.GITHUB_WORKFLOW.value
    dep = RemediationArtifactType.DEPENDENCY_MANIFEST.value
    lock = RemediationArtifactType.LOCK_FILE.value
    docker = RemediationArtifactType.DOCKERFILE.value
    k8s = RemediationArtifactType.KUBERNETES_MANIFEST.value

    templates: list[RemediationTemplate] = [
        # AWS/IAM
        _skel(
            template_id="iam.add_scoped_missing_action",
            family="aws_iam",
            category_codes=["aws_iam", "permission_denied", "access_denied"],
            patterns=["missing_permission", "access_denied", "s3:PutObject"],
            artifact_types=[iam, tf],
            change_type=CounterfactualChangeType.UPDATE_PERMISSION,
            effects=["EXPECTED: narrowly scoped allow for denied action"],
            verifiers=[
                VerifierType.IAM_POLICY_STRUCTURE.value,
                VerifierType.IAM_LEAST_PRIVILEGE.value,
            ],
        ),
        _skel(
            template_id="iam.correct_assumed_role_reference",
            family="aws_iam",
            category_codes=["aws_iam", "wrong_role", "oidc"],
            patterns=["wrong_role", "assume_role", "role_arn"],
            artifact_types=[gha, iam],
            change_type=CounterfactualChangeType.UPDATE_ROLE,
            effects=["EXPECTED: workflow uses intended role ARN"],
            verifiers=[VerifierType.WORKFLOW_YAML_PARSE.value],
        ),
        _skel(
            template_id="iam.address_resource_policy_deny",
            family="aws_iam",
            category_codes=["aws_iam", "resource_policy"],
            patterns=["resource_policy_deny", "explicit_deny"],
            artifact_types=[resource_policy, iam, tf],
            change_type=CounterfactualChangeType.UPDATE_CONDITION,
            effects=["EXPECTED: resource-policy deny addressed without add-allow bypass"],
            verifiers=[VerifierType.IAM_POLICY_STRUCTURE.value],
            prohibited=["add_allow_over_deny", "action_wildcard"],
        ),
        _skel(
            template_id="iam.correct_account_or_environment_reference",
            family="aws_iam",
            category_codes=["aws_iam", "wrong_account", "environment"],
            patterns=["wrong_account", "wrong_environment"],
            artifact_types=[iam, tf, gha],
            change_type=CounterfactualChangeType.UPDATE_ENVIRONMENT_REFERENCE,
            effects=["EXPECTED: account/environment reference corrected"],
            verifiers=[VerifierType.COUNTERFACTUAL_FAILURE_CONDITION.value],
        ),
        _skel(
            template_id="iam.correct_region",
            family="aws_iam",
            category_codes=["aws_iam", "wrong_region", "region"],
            patterns=["wrong_region", "region_mismatch"],
            artifact_types=[iam, tf, gha],
            change_type=CounterfactualChangeType.UPDATE_REGION,
            effects=["EXPECTED: region reference matches target resource region"],
            verifiers=[VerifierType.COUNTERFACTUAL_FAILURE_CONDITION.value],
        ),
        _skel(
            template_id="iam.update_trust_relationship",
            family="aws_iam",
            category_codes=["aws_iam", "trust_policy"],
            patterns=["trust_relationship", "trust_policy"],
            artifact_types=[iam, tf],
            change_type=CounterfactualChangeType.UPDATE_CONDITION,
            effects=["EXPECTED: trust relationship updated when supported"],
            verifiers=[VerifierType.IAM_POLICY_STRUCTURE.value],
        ),
        # Terraform
        _skel(
            template_id="terraform.correct_invalid_resource_reference",
            family="terraform",
            category_codes=["terraform", "invalid_reference"],
            patterns=["invalid_resource_reference", "unknown_resource"],
            artifact_types=[tf],
            change_type=CounterfactualChangeType.UPDATE_REFERENCE,
            effects=["EXPECTED: reference resolves to existing resource"],
            verifiers=[
                VerifierType.TERRAFORM_VALIDATE.value,
                VerifierType.TERRAFORM_DEPENDENCY.value,
            ],
        ),
        _skel(
            template_id="terraform.correct_missing_module_output",
            family="terraform",
            category_codes=["terraform", "module_output"],
            patterns=["missing_module_output", "output_reference"],
            artifact_types=[tf],
            change_type=CounterfactualChangeType.UPDATE_REFERENCE,
            effects=["EXPECTED: module output reference corrected"],
            verifiers=[VerifierType.TERRAFORM_VALIDATE.value],
        ),
        _skel(
            template_id="terraform.correct_invalid_variable_value",
            family="terraform",
            category_codes=["terraform", "variable"],
            patterns=["invalid_variable", "variable_validation"],
            artifact_types=[tf, RemediationArtifactType.TERRAFORM_VARIABLES.value],
            change_type=CounterfactualChangeType.UPDATE_VALUE,
            effects=["EXPECTED: variable value satisfies type/validation"],
            verifiers=[VerifierType.TERRAFORM_VALIDATE.value],
        ),
        _skel(
            template_id="terraform.align_provider_alias_region",
            family="terraform",
            category_codes=["terraform", "provider", "region"],
            patterns=["provider_alias", "provider_region"],
            artifact_types=[tf],
            change_type=CounterfactualChangeType.UPDATE_REGION,
            effects=["EXPECTED: provider alias/region aligned"],
            verifiers=[VerifierType.TERRAFORM_VALIDATE.value],
        ),
        _skel(
            template_id="terraform.correct_dependency_relationship",
            family="terraform",
            category_codes=["terraform", "dependency"],
            patterns=["depends_on", "implicit_dependency"],
            artifact_types=[tf],
            change_type=CounterfactualChangeType.UPDATE_DEPENDENCY,
            effects=["EXPECTED: dependency relationship corrected"],
            verifiers=[VerifierType.TERRAFORM_DEPENDENCY.value],
        ),
        _skel(
            template_id="terraform.align_provider_version",
            family="terraform",
            category_codes=["terraform", "provider_version"],
            patterns=["provider_version", "required_providers"],
            artifact_types=[tf],
            change_type=CounterfactualChangeType.UPDATE_VERSION,
            effects=["EXPECTED: provider version constraints compatible"],
            verifiers=[VerifierType.TERRAFORM_VALIDATE.value],
        ),
        # GitHub Actions
        _skel(
            template_id="gha.correct_job_dependency",
            family="github_actions",
            category_codes=["github_actions", "workflow", "needs"],
            patterns=["missing_needs", "invalid_job_dependency"],
            artifact_types=[gha, RemediationArtifactType.REUSABLE_WORKFLOW.value],
            change_type=CounterfactualChangeType.UPDATE_JOB_DEPENDENCY,
            effects=["EXPECTED: job dependency points to existing job"],
            verifiers=[
                VerifierType.WORKFLOW_YAML_PARSE.value,
                VerifierType.ACTIONLINT.value,
            ],
        ),
        _skel(
            template_id="gha.correct_expression",
            family="github_actions",
            category_codes=["github_actions", "expression"],
            patterns=["invalid_expression", "context_access"],
            artifact_types=[gha],
            change_type=CounterfactualChangeType.UPDATE_WORKFLOW_EXPRESSION,
            effects=["EXPECTED: workflow expression corrected"],
            verifiers=[VerifierType.WORKFLOW_YAML_PARSE.value],
        ),
        _skel(
            template_id="gha.correct_secret_reference_name",
            family="github_actions",
            category_codes=["github_actions", "secret"],
            patterns=["secret_reference", "secrets."],
            artifact_types=[gha],
            change_type=CounterfactualChangeType.UPDATE_REFERENCE,
            effects=["EXPECTED: secret-reference name corrected (value never embedded)"],
            verifiers=[VerifierType.WORKFLOW_YAML_PARSE.value],
            prohibited=["plaintext_secret", "embed_secret_value"],
        ),
        _skel(
            template_id="gha.correct_reusable_workflow_input",
            family="github_actions",
            category_codes=["github_actions", "reusable_workflow"],
            patterns=["reusable_workflow_input", "workflow_call"],
            artifact_types=[gha, RemediationArtifactType.REUSABLE_WORKFLOW.value],
            change_type=CounterfactualChangeType.UPDATE_VALUE,
            effects=["EXPECTED: reusable-workflow input corrected"],
            verifiers=[VerifierType.WORKFLOW_YAML_PARSE.value],
        ),
        _skel(
            template_id="gha.correct_action_version",
            family="github_actions",
            category_codes=["github_actions", "action_version"],
            patterns=["action_version", "uses:"],
            artifact_types=[gha],
            change_type=CounterfactualChangeType.UPDATE_VERSION,
            effects=["EXPECTED: action version corrected"],
            verifiers=[VerifierType.ACTIONLINT.value],
        ),
        _skel(
            template_id="gha.correct_environment_or_role_reference",
            family="github_actions",
            category_codes=["github_actions", "environment", "role"],
            patterns=["environment_reference", "role_reference"],
            artifact_types=[gha],
            change_type=CounterfactualChangeType.UPDATE_ENVIRONMENT_REFERENCE,
            effects=["EXPECTED: environment/role reference corrected"],
            verifiers=[VerifierType.WORKFLOW_YAML_PARSE.value],
        ),
        # Dependencies
        _skel(
            template_id="deps.align_package_version",
            family="dependencies",
            category_codes=["dependency", "package_version"],
            patterns=["version_conflict", "package_version"],
            artifact_types=[dep, lock],
            change_type=CounterfactualChangeType.UPDATE_VERSION,
            effects=["EXPECTED: package version constraints compatible"],
            verifiers=[VerifierType.COUNTERFACTUAL_FAILURE_CONDITION.value],
        ),
        _skel(
            template_id="deps.restore_lockfile_consistency",
            family="dependencies",
            category_codes=["dependency", "lockfile"],
            patterns=["lockfile_mismatch", "lock_file"],
            artifact_types=[lock, dep],
            change_type=CounterfactualChangeType.UPDATE_DEPENDENCY,
            effects=["EXPECTED: lock-file consistency restored"],
            verifiers=[VerifierType.COUNTERFACTUAL_FAILURE_CONDITION.value],
        ),
        _skel(
            template_id="deps.use_supported_runtime_version",
            family="dependencies",
            category_codes=["dependency", "runtime"],
            patterns=["runtime_version", "python_version", "node_version"],
            artifact_types=[dep, gha],
            change_type=CounterfactualChangeType.UPDATE_VERSION,
            effects=["EXPECTED: supported runtime version used"],
            verifiers=[VerifierType.COUNTERFACTUAL_FAILURE_CONDITION.value],
        ),
        _skel(
            template_id="deps.correct_package_registry_reference",
            family="dependencies",
            category_codes=["dependency", "registry"],
            patterns=["registry_reference", "package_registry"],
            artifact_types=[dep],
            change_type=CounterfactualChangeType.UPDATE_REFERENCE,
            effects=["EXPECTED: package-registry reference corrected"],
            verifiers=[VerifierType.COUNTERFACTUAL_FAILURE_CONDITION.value],
        ),
        # Container / deployment
        _skel(
            template_id="container.correct_image_tag",
            family="container",
            category_codes=["container", "docker", "image"],
            patterns=["image_tag", "image_not_found"],
            artifact_types=[docker, k8s, RemediationArtifactType.DOCKER_COMPOSE.value],
            change_type=CounterfactualChangeType.UPDATE_VERSION,
            effects=["EXPECTED: image tag corrected"],
            verifiers=[VerifierType.COUNTERFACTUAL_FAILURE_CONDITION.value],
        ),
        _skel(
            template_id="container.correct_registry_reference",
            family="container",
            category_codes=["container", "registry"],
            patterns=["registry_reference", "image_pull"],
            artifact_types=[docker, k8s],
            change_type=CounterfactualChangeType.UPDATE_REFERENCE,
            effects=["EXPECTED: registry reference corrected"],
            verifiers=[VerifierType.COUNTERFACTUAL_FAILURE_CONDITION.value],
        ),
        _skel(
            template_id="container.correct_deployment_resource_name",
            family="container",
            category_codes=["kubernetes", "deployment"],
            patterns=["deployment_name", "resource_name"],
            artifact_types=[k8s],
            change_type=CounterfactualChangeType.UPDATE_RESOURCE_TARGET,
            effects=["EXPECTED: deployment resource name corrected"],
            verifiers=[VerifierType.COUNTERFACTUAL_FAILURE_CONDITION.value],
        ),
        _skel(
            template_id="container.correct_environment_configuration",
            family="container",
            category_codes=["container", "environment"],
            patterns=["environment_configuration", "env_config"],
            artifact_types=[
                docker,
                k8s,
                RemediationArtifactType.ENVIRONMENT_CONFIGURATION.value,
            ],
            change_type=CounterfactualChangeType.UPDATE_ENVIRONMENT_REFERENCE,
            effects=["EXPECTED: environment configuration corrected"],
            verifiers=[VerifierType.COUNTERFACTUAL_FAILURE_CONDITION.value],
        ),
    ]
    return templates
