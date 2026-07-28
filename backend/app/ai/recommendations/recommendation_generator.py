"""Deterministic remediation templates keyed by seeded failure category codes."""

from __future__ import annotations

from app.ai.orchestration.analysis_context import (
    AnalysisContext,
    RecommendationCandidate,
    RecommendationStepCandidate,
)
from app.domain.enums import RiskLevel

_TEMPLATES: dict[str, dict] = {
    "aws_permission_failure": {
        "explanation": "Update IAM permissions for the deployment role and re-run the workflow.",
        "steps": [
            {
                "type": "remediation",
                "title": "Inspect denied IAM action",
                "action": "Identify the denied action from the AccessDenied message.",
                "risk": "low",
                "difficulty": "easy",
            },
            {
                "type": "remediation",
                "title": "Grant least-privilege permission",
                "action": "Add only the required IAM action to the deployment role policy.",
                "risk": "medium",
                "difficulty": "moderate",
                "command": ("aws iam get-role-policy --role-name <role> --policy-name <policy>"),
            },
            {
                "type": "verification",
                "title": "Re-run the failed workflow",
                "action": "Trigger the same pipeline job and confirm the API call succeeds.",
                "risk": "low",
                "difficulty": "easy",
            },
            {
                "type": "prevention",
                "title": "Add IAM policy validation",
                "action": "Add a pre-deploy IAM simulation or policy lint step in CI.",
                "risk": "low",
                "difficulty": "moderate",
            },
        ],
    },
    "terraform_failure": {
        "explanation": "Resolve the Terraform error, unlock state if needed, then re-plan/apply.",
        "steps": [
            {
                "type": "remediation",
                "title": "Review Terraform error output",
                "action": "Locate the first Error block and fix the referenced resource/config.",
                "risk": "low",
                "difficulty": "moderate",
            },
            {
                "type": "remediation",
                "title": "Clear stale state lock if applicable",
                "action": "Confirm no other apply is running before releasing a stale lock.",
                "risk": "high",
                "difficulty": "advanced",
            },
            {
                "type": "verification",
                "title": "Run terraform plan",
                "action": "Execute terraform plan and confirm no unexpected destroys.",
                "risk": "medium",
                "difficulty": "moderate",
                "command": "terraform plan",
            },
            {
                "type": "prevention",
                "title": "Enforce plan review gates",
                "action": "Require plan artifacts and approval before apply in CI.",
                "risk": "low",
                "difficulty": "moderate",
            },
        ],
    },
    "docker_failure": {
        "explanation": "Fix Dockerfile/build context or registry access, then rebuild the image.",
        "steps": [
            {
                "type": "remediation",
                "title": "Inspect Docker build logs",
                "action": "Identify the failing Dockerfile instruction or registry error.",
                "risk": "low",
                "difficulty": "easy",
            },
            {
                "type": "verification",
                "title": "Rebuild locally or in CI",
                "action": "Rebuild the image with the same tags used by the pipeline.",
                "risk": "low",
                "difficulty": "easy",
                "command": "docker build -t <image>:<tag> .",
            },
            {
                "type": "prevention",
                "title": "Pin base images",
                "action": "Pin digest/versioned base images to reduce registry drift.",
                "risk": "low",
                "difficulty": "easy",
            },
        ],
    },
    "dependency_failure": {
        "explanation": "Resolve dependency conflicts and regenerate lockfiles.",
        "steps": [
            {
                "type": "remediation",
                "title": "Inspect dependency resolution errors",
                "action": "Identify conflicting packages and compatible versions.",
                "risk": "low",
                "difficulty": "moderate",
            },
            {
                "type": "verification",
                "title": "Reinstall dependencies",
                "action": "Re-run the package manager install with the updated lockfile.",
                "risk": "low",
                "difficulty": "easy",
            },
            {
                "type": "prevention",
                "title": "Commit lockfiles",
                "action": "Ensure lockfiles are committed and CI uses reproducible installs.",
                "risk": "low",
                "difficulty": "easy",
            },
        ],
    },
    "test_failure": {
        "explanation": "Fix failing assertions or flaky tests, then re-run the suite.",
        "steps": [
            {
                "type": "remediation",
                "title": "Reproduce the failing test",
                "action": "Run the failing test case locally with the same inputs.",
                "risk": "low",
                "difficulty": "easy",
            },
            {
                "type": "verification",
                "title": "Re-run CI tests",
                "action": "Confirm the suite is green after the fix.",
                "risk": "low",
                "difficulty": "easy",
            },
            {
                "type": "prevention",
                "title": "Add regression coverage",
                "action": "Add or tighten assertions covering the failure mode.",
                "risk": "low",
                "difficulty": "moderate",
            },
        ],
    },
    "build_failure": {
        "explanation": "Fix compilation or packaging errors and rebuild the artifact.",
        "steps": [
            {
                "type": "remediation",
                "title": "Resolve compile errors",
                "action": "Address the first compiler/build error reported by the toolchain.",
                "risk": "low",
                "difficulty": "moderate",
            },
            {
                "type": "verification",
                "title": "Rebuild the project",
                "action": "Re-run the build job and confirm a successful artifact.",
                "risk": "low",
                "difficulty": "easy",
            },
            {
                "type": "prevention",
                "title": "Enable local pre-commit build checks",
                "action": "Add a fast compile/typecheck step before push.",
                "risk": "low",
                "difficulty": "easy",
            },
        ],
    },
    "configuration_failure": {
        "explanation": "Correct missing or invalid configuration and re-validate.",
        "steps": [
            {
                "type": "remediation",
                "title": "Supply required configuration",
                "action": "Add missing env vars/keys and validate YAML/JSON syntax.",
                "risk": "low",
                "difficulty": "easy",
            },
            {
                "type": "verification",
                "title": "Validate config in CI",
                "action": "Re-run config validation and the failed job.",
                "risk": "low",
                "difficulty": "easy",
            },
            {
                "type": "prevention",
                "title": "Schema-validate configs",
                "action": "Add schema or required-key checks to the pipeline.",
                "risk": "low",
                "difficulty": "moderate",
            },
        ],
    },
    "deployment_failure": {
        "explanation": "Fix the deploy target/settings and retry the rollout safely.",
        "steps": [
            {
                "type": "remediation",
                "title": "Inspect deploy logs",
                "action": "Identify the failing deploy step and target service.",
                "risk": "medium",
                "difficulty": "moderate",
            },
            {
                "type": "verification",
                "title": "Retry controlled rollout",
                "action": "Redeploy to a non-production environment first if available.",
                "risk": "medium",
                "difficulty": "moderate",
            },
            {
                "type": "prevention",
                "title": "Add health-check gates",
                "action": "Fail deploys when post-deploy health checks do not pass.",
                "risk": "low",
                "difficulty": "moderate",
            },
        ],
    },
    "network_failure": {
        "explanation": "Restore connectivity/DNS and retry the dependent network call.",
        "steps": [
            {
                "type": "remediation",
                "title": "Verify DNS and endpoints",
                "action": "Confirm hostnames resolve and ports are reachable from the runner.",
                "risk": "low",
                "difficulty": "moderate",
            },
            {
                "type": "verification",
                "title": "Retry the network-dependent step",
                "action": "Re-run the job after connectivity is restored.",
                "risk": "low",
                "difficulty": "easy",
            },
            {
                "type": "prevention",
                "title": "Add retries with backoff",
                "action": "Configure bounded retries for transient network errors.",
                "risk": "low",
                "difficulty": "easy",
            },
        ],
    },
    "security_misconfiguration": {
        "explanation": "Correct TLS/secrets/policy misconfiguration before retrying.",
        "steps": [
            {
                "type": "remediation",
                "title": "Fix security configuration",
                "action": "Rotate expired certificates or correct insecure settings.",
                "risk": "high",
                "difficulty": "moderate",
            },
            {
                "type": "verification",
                "title": "Validate secure connectivity",
                "action": "Confirm TLS and policy checks succeed after the change.",
                "risk": "medium",
                "difficulty": "moderate",
            },
            {
                "type": "prevention",
                "title": "Automate certificate/policy checks",
                "action": "Add security linting to CI for TLS and secret hygiene.",
                "risk": "low",
                "difficulty": "moderate",
            },
        ],
    },
    "unknown_failure": {
        "explanation": "Gather additional context and escalate for manual investigation.",
        "steps": [
            {
                "type": "remediation",
                "title": "Collect richer diagnostics",
                "action": "Upload complete logs, workflow YAML, and related IaC for review.",
                "risk": "low",
                "difficulty": "easy",
            },
            {
                "type": "verification",
                "title": "Reproduce with verbose logging",
                "action": "Re-run with debug logging enabled where safe.",
                "risk": "low",
                "difficulty": "moderate",
            },
            {
                "type": "prevention",
                "title": "Improve telemetry",
                "action": "Ensure CI captures structured failure output for future runs.",
                "risk": "low",
                "difficulty": "moderate",
            },
        ],
    },
}


_DANGEROUS = (
    "rm -rf",
    "terraform destroy",
    "dd if=",
    "mkfs",
    ":(){",
    "shutdown",
    "drop database",
)


class RecommendationGenerator:
    def generate(self, context: AnalysisContext) -> RecommendationCandidate | None:
        if not context.generate_recommendations or not context.classifications:
            return None
        primary = context.classifications[0]
        template = _TEMPLATES.get(primary.category_code, _TEMPLATES["unknown_failure"])
        steps: list[RecommendationStepCandidate] = []
        for idx, raw in enumerate(template["steps"], start=1):
            command = raw.get("command")
            if command and any(bad in command.lower() for bad in _DANGEROUS):
                command = None
                context.warnings.append("Blocked dangerous command template.")
            steps.append(
                RecommendationStepCandidate(
                    step_number=idx,
                    step_type=str(raw["type"]),
                    title=str(raw["title"]),
                    action=str(raw["action"]),
                    explanation=str(raw.get("explanation") or raw["action"]),
                    expected_result="Pipeline step succeeds after applying the change.",
                    risk_level=str(raw.get("risk", RiskLevel.LOW.value)),
                    difficulty=str(raw.get("difficulty", "moderate")),
                    command_template=command,
                )
            )
        candidate = RecommendationCandidate(
            root_cause_summary=primary.root_cause_summary,
            explanation=str(template["explanation"]),
            confidence_score=primary.confidence,
            steps=steps,
            llm_model="template",
        )
        context.recommendation = candidate
        return candidate
