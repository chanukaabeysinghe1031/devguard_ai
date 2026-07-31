"""Versioned deterministic hypothesis templates (Phase 6A.4)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HypothesisTemplate:
    template_id: str
    template_version: str
    family: str
    category_code: str
    title: str
    causal_claim_template: str
    required_signal_tokens: tuple[str, ...]
    optional_signal_tokens: tuple[str, ...] = ()
    contradicting_signal_tokens: tuple[str, ...] = ()
    expected_observations: tuple[str, ...] = ()
    falsifying_observations: tuple[str, ...] = ()
    verification_steps: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    min_required_hits: int = 1
    base_confidence: float = 0.55
    diversity_bucket: str = "generic"
    notes: str = ""


def _iam(
    tid: str,
    title: str,
    claim: str,
    required: tuple[str, ...],
    *,
    contradicting: tuple[str, ...] = (),
    optional: tuple[str, ...] = (),
    bucket: str = "identity",
    confidence: float = 0.62,
) -> HypothesisTemplate:
    return HypothesisTemplate(
        template_id=tid,
        template_version="v1",
        family="iam",
        category_code="aws_permission_failure",
        title=title,
        causal_claim_template=claim,
        required_signal_tokens=required,
        optional_signal_tokens=optional,
        contradicting_signal_tokens=contradicting,
        expected_observations=(
            "CloudTrail or CI log shows AccessDenied for the claimed principal/action",
            "Identity or resource policy evaluation matches the claimed gap",
        ),
        falsifying_observations=(
            "The claimed principal successfully performs the action in the same context",
            "Policy simulation shows the required action is already allowed without deny",
        ),
        verification_steps=(
            "Identify the active principal (assumed role / user) from STS/CI logs",
            "Simulate or inspect identity and resource policies for the denied action",
            "Confirm account/region/ARN match the failing resource",
        ),
        limitations=("Template match is not proof of causality.",),
        min_required_hits=1,
        base_confidence=confidence,
        diversity_bucket=bucket,
    )


def _tf(
    tid: str,
    title: str,
    claim: str,
    required: tuple[str, ...],
    *,
    optional: tuple[str, ...] = (),
    bucket: str = "configuration",
) -> HypothesisTemplate:
    return HypothesisTemplate(
        template_id=tid,
        template_version="v1",
        family="terraform",
        category_code="terraform_failure",
        title=title,
        causal_claim_template=claim,
        required_signal_tokens=required,
        optional_signal_tokens=optional,
        expected_observations=(
            "Terraform diagnostic names a specific reference, variable, or backend issue",
            "Plan/apply fails before or at the referenced resource",
        ),
        falsifying_observations=(
            "The referenced resource/output/variable exists and resolves correctly",
        ),
        verification_steps=(
            "Inspect the named .tf file and reference",
            "Re-run terraform validate/plan with the same backend/workspace",
        ),
        limitations=("Plan-failed messages alone are treated as symptoms.",),
        base_confidence=0.6,
        diversity_bucket=bucket,
    )


def _wf(
    tid: str,
    title: str,
    claim: str,
    required: tuple[str, ...],
    *,
    category: str = "configuration_failure",
    bucket: str = "configuration",
) -> HypothesisTemplate:
    return HypothesisTemplate(
        template_id=tid,
        template_version="v1",
        family="workflow",
        category_code=category,
        title=title,
        causal_claim_template=claim,
        required_signal_tokens=required,
        expected_observations=(
            "Workflow YAML or runner log cites the invalid config/secret/dependency",
        ),
        falsifying_observations=(
            "The referenced workflow configuration is valid and present",
        ),
        verification_steps=(
            "Open the workflow file at the cited job/step",
            "Confirm secrets/vars/needs/matrix values against repository settings",
        ),
        limitations=("Workflow status failures are symptoms unless no stronger cause exists.",),
        base_confidence=0.58,
        diversity_bucket=bucket,
    )


def _dep(
    tid: str,
    title: str,
    claim: str,
    required: tuple[str, ...],
) -> HypothesisTemplate:
    return HypothesisTemplate(
        template_id=tid,
        template_version="v1",
        family="dependency",
        category_code="dependency_failure",
        title=title,
        causal_claim_template=claim,
        required_signal_tokens=required,
        expected_observations=(
            "Package manager output names a missing package or version conflict",
        ),
        falsifying_observations=(
            "Lockfile and registry resolution succeed for the same dependency set",
        ),
        verification_steps=(
            "Inspect package manifest and lockfile",
            "Reproduce install with the same runtime version",
        ),
        limitations=("Registry outages may look like local dependency conflicts.",),
        base_confidence=0.6,
        diversity_bucket="dependency",
    )


def _ctr(
    tid: str,
    title: str,
    claim: str,
    required: tuple[str, ...],
    *,
    category: str = "docker_failure",
    bucket: str = "environment",
) -> HypothesisTemplate:
    return HypothesisTemplate(
        template_id=tid,
        template_version="v1",
        family="container",
        category_code=category,
        title=title,
        causal_claim_template=claim,
        required_signal_tokens=required,
        expected_observations=(
            "Container/registry/deploy log cites image, tag, permission, or quota issue",
        ),
        falsifying_observations=(
            "The image is pullable and the deployment resource exists in the target env",
        ),
        verification_steps=(
            "Verify image reference and registry permissions",
            "Confirm deployment target environment and quotas",
        ),
        limitations=("Generic deploy-failed messages are symptoms.",),
        base_confidence=0.58,
        diversity_bucket=bucket,
    )


TEMPLATES_V1: tuple[HypothesisTemplate, ...] = (
    # IAM / authorization
    _iam(
        "iam.missing_identity_permission",
        "Missing identity-policy permission",
        "The active identity policy does not grant the denied action for the target resource.",
        ("accessdenied", "not authorized", "explicitly denied", "s3:putobject", "iam"),
        optional=("role", "policy", "permission"),
        contradicting=("explicit deny", "bucket policy deny"),
        bucket="identity",
        confidence=0.7,
    ),
    _iam(
        "iam.wrong_assumed_role",
        "Incorrect assumed role",
        "The workflow assumed an unexpected role; the expected deployment role was not used.",
        ("assumed-role", "assumerole", "sts", "role/"),
        optional=("oidc", "aws-actions/configure-aws-credentials"),
        bucket="identity",
        confidence=0.65,
    ),
    _iam(
        "iam.explicit_resource_deny",
        "Explicit resource-policy deny",
        "A resource policy explicitly denies the request even if identity policy allows it.",
        ("explicit deny", "bucket policy", "resource-based policy", "accessdenied"),
        optional=("condition", "principal"),
        bucket="resource_policy",
        confidence=0.68,
    ),
    _iam(
        "iam.permissions_boundary",
        "Permissions boundary restriction",
        "A permissions boundary prevents the identity from performing the denied action.",
        ("permissions boundary", "permissionsboundary"),
        bucket="identity",
        confidence=0.6,
    ),
    _iam(
        "iam.scp_restriction",
        "Service-control-policy restriction",
        "An organization SCP denies or omits the required action for this account.",
        ("service control policy", "scp", "organization"),
        bucket="resource_policy",
        confidence=0.55,
    ),
    _iam(
        "iam.wrong_account_or_environment",
        "Wrong account or environment",
        "The pipeline targeted a resource in a different account or environment than intended.",
        ("account", "wrong account", "environment", "arn:aws"),
        optional=("accessdenied",),
        bucket="environment",
        confidence=0.55,
    ),
    _iam(
        "iam.wrong_resource_arn",
        "Wrong resource ARN",
        "The request targeted an incorrect resource ARN relative to the intended artifact.",
        ("arn:aws", "nosuchbucket", "nosuchkey", "resource"),
        optional=("accessdenied",),
        bucket="environment",
        confidence=0.55,
    ),
    _iam(
        "iam.invalid_credentials",
        "Expired or invalid credentials",
        "Credentials used by the pipeline are expired, invalid, or not authorized.",
        ("invalidclienttokenid", "expiredtoken", "unable to locate credentials", "security token"),
        bucket="identity",
        confidence=0.66,
    ),
    # Terraform
    _tf(
        "tf.invalid_reference",
        "Invalid resource reference",
        "Terraform references a resource, attribute, or address that does not resolve.",
        (
            "a resource with the id",
            "reference to undeclared",
            "unsupported attribute",
            "invalid reference",
        ),
    ),
    _tf(
        "tf.missing_module_output",
        "Missing module output",
        "A module output required by a dependent resource is missing or renamed.",
        ("unsupported attribute", "module.", "output"),
        optional=("reference",),
    ),
    _tf(
        "tf.invalid_variable",
        "Invalid variable value",
        "A Terraform variable value is missing, mistyped, or fails validation.",
        ("no value for required variable", "invalid value for", "variable"),
    ),
    _tf(
        "tf.dependency_ordering",
        "Dependency ordering issue",
        "Terraform dependency ordering is incorrect for the failing resource graph.",
        ("cycle", "depends_on", "dependency"),
    ),
    _tf(
        "tf.provider_config",
        "Provider configuration error",
        "Provider configuration is incomplete or incorrect for the failing operation.",
        ("provider", "no valid credential", "failed to configure"),
    ),
    _tf(
        "tf.state_lock",
        "State lock or backend issue",
        "Terraform state is locked or the backend cannot be reached.",
        ("error acquiring the state lock", "state lock", "backend"),
        bucket="configuration",
    ),
    _tf(
        "tf.region_mismatch",
        "Region/provider mismatch",
        "The Terraform provider region does not match the target resource region.",
        ("region", "provider", "wrong region"),
        bucket="environment",
    ),
    _tf(
        "tf.undeclared_resource",
        "Undeclared resource",
        "Configuration references an undeclared resource address.",
        ("undeclared resource", "reference to undeclared resource"),
    ),
    _tf(
        "tf.incompatible_provider",
        "Incompatible provider version",
        "The required provider version is incompatible with the configuration.",
        ("incompatible provider", "provider version", "required_providers"),
    ),
    # Workflow
    _wf(
        "wf.invalid_yaml",
        "Invalid YAML configuration",
        "The workflow YAML is syntactically or structurally invalid.",
        ("yaml", "invalid workflow", "mapping values are not allowed", "did not find expected"),
    ),
    _wf(
        "wf.invalid_job_dependency",
        "Invalid job dependency",
        "A job `needs` dependency is missing, cyclic, or incorrectly named.",
        ("needs:", "job dependency", "unrecognized named-value: needs"),
    ),
    _wf(
        "wf.invalid_condition",
        "Incorrect condition expression",
        "A job/step `if` condition evaluates incorrectly for this run.",
        ("if:", "unrecognized named-value", "condition"),
    ),
    _wf(
        "wf.missing_env",
        "Missing environment variable",
        "A required environment variable is missing from the job/step context.",
        ("environment variable", "env.", "not set"),
    ),
    _wf(
        "wf.missing_secret",
        "Missing secret reference",
        "A required secret reference is missing or not available to the workflow.",
        ("secret", "secrets.", "not found"),
        category="security_misconfiguration",
        bucket="configuration",
    ),
    _wf(
        "wf.wrong_action_version",
        "Wrong action version",
        "The workflow pins an incorrect or incompatible GitHub Action version.",
        ("uses:", "action", "unable to resolve action"),
    ),
    _wf(
        "wf.reusable_input",
        "Incorrect reusable-workflow input",
        "A reusable workflow input is missing or mismatched.",
        ("reusable workflow", "workflow_call", "input"),
    ),
    _wf(
        "wf.matrix_value",
        "Incorrect matrix value",
        "A matrix combination produces an invalid configuration for this job.",
        ("matrix", "strategy", "include"),
    ),
    # Dependency
    _dep(
        "dep.missing_package",
        "Missing package",
        "A required package cannot be resolved from the configured registries.",
        ("could not find a version", "no matching distribution", "404 not found", "eresolve"),
    ),
    _dep(
        "dep.version_conflict",
        "Version conflict",
        "Dependency versions conflict and cannot be satisfied together.",
        ("eresolve", "conflict", "version conflict", "resolutionimpossible"),
    ),
    _dep(
        "dep.registry_auth",
        "Registry authentication failure",
        "Authentication to the package registry failed.",
        ("401", "403", "unauthorized", "registry", "npm login"),
    ),
    _dep(
        "dep.lockfile_mismatch",
        "Lock-file mismatch",
        "The lockfile does not match the package manifest.",
        ("lockfile", "package-lock", "out of sync", "yarn.lock"),
    ),
    _dep(
        "dep.runtime_version",
        "Incompatible runtime version",
        "The runtime version is incompatible with the dependency set.",
        ("engine", "requires node", "python version", "unsupported"),
    ),
    # Container / deployment
    _ctr(
        "ctr.image_unavailable",
        "Image unavailable",
        "The container image cannot be found or pulled.",
        ("pull access denied", "not found", "manifest unknown", "image"),
    ),
    _ctr(
        "ctr.incorrect_tag",
        "Incorrect tag",
        "The deployment references an incorrect image tag.",
        ("tag", "manifest unknown", "image"),
    ),
    _ctr(
        "ctr.registry_permission",
        "Registry permission failure",
        "Registry credentials or permissions prevent pulling/pushing the image.",
        ("denied", "unauthorized", "registry", "ecr"),
        category="aws_permission_failure",
        bucket="identity",
    ),
    _ctr(
        "ctr.missing_deploy_resource",
        "Missing deployment resource",
        "A required deployment resource is missing in the target environment.",
        ("not found", "deployment", "no such", "does not exist"),
        category="deployment_failure",
    ),
    _ctr(
        "ctr.environment_mismatch",
        "Environment mismatch",
        "Deployment targeted the wrong environment or cluster/context.",
        ("environment", "namespace", "cluster", "context"),
        category="deployment_failure",
        bucket="environment",
    ),
    _ctr(
        "ctr.resource_quota",
        "Resource quota failure",
        "Quota or capacity limits prevent the deployment from proceeding.",
        ("quota", "insufficient", "out of memory", "cannot schedule"),
        category="ci_runner_failure",
        bucket="environment",
    ),
)

TEMPLATE_BY_ID: dict[str, HypothesisTemplate] = {t.template_id: t for t in TEMPLATES_V1}

# Downstream symptom phrases that should rarely be root causes.
DOWNSTREAM_SYMPTOM_TOKENS: tuple[str, ...] = (
    "workflow failed",
    "job failed",
    "process completed with exit code",
    "exited with code",
    "deployment failed",
    "terraform plan failed",
    "##[error]process completed",
)
