"""Rule definitions and pattern matching for deterministic classification."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RulePattern:
    name: str
    category_code: str
    pattern: re.Pattern[str]
    weight: float
    root_cause: str
    technical: str
    impact: str


def _p(expr: str, flags: int = re.IGNORECASE | re.MULTILINE) -> re.Pattern[str]:
    return re.compile(expr, flags)


RULES: tuple[RulePattern, ...] = (
    RulePattern(
        name="aws_access_denied",
        category_code="aws_permission_failure",
        pattern=_p(
            r"AccessDenied|not authorized to perform|UnauthorizedOperation"
            r"|is not authorized"
        ),
        weight=0.95,
        root_cause="The AWS principal lacks permission for the requested API action.",
        technical="IAM authorization rejected the call (AccessDenied / not authorized).",
        impact="The deployment or infrastructure update could not complete.",
    ),
    RulePattern(
        name="aws_invalid_credentials",
        category_code="aws_permission_failure",
        pattern=_p(
            r"UnrecognizedClientException|InvalidClientTokenId|ExpiredToken"
            r"|Unable to locate credentials"
        ),
        weight=0.90,
        root_cause="AWS credentials are missing, invalid, or expired.",
        technical="The AWS SDK/CLI could not authenticate the request.",
        impact="Cloud API calls failed before authorization checks completed.",
    ),
    RulePattern(
        name="terraform_error",
        category_code="terraform_failure",
        pattern=_p(
            r"Error: |Terraform has no|Failed to .*terraform|terraform apply"
            r"|terraform plan"
        ),
        weight=0.88,
        root_cause="Terraform planning or apply failed.",
        technical="A Terraform operation returned an error while managing infrastructure.",
        impact="Infrastructure changes were not applied as intended.",
    ),
    RulePattern(
        name="terraform_state_lock",
        category_code="terraform_failure",
        pattern=_p(r"Error acquiring the state lock|state locked|ConditionalCheckFailedException"),
        weight=0.92,
        root_cause="Terraform state is locked by another operation.",
        technical="Backend state locking prevented a concurrent Terraform run.",
        impact="Infrastructure changes are blocked until the lock is released.",
    ),
    RulePattern(
        name="docker_build_fail",
        category_code="docker_failure",
        pattern=_p(
            r"docker(?:\.exe)? (?:build|pull|push).*failed|failed to solve"
            r"|Cannot connect to the Docker daemon|error building image"
        ),
        weight=0.88,
        root_cause="A Docker image build or registry operation failed.",
        technical="Docker reported an error during build, pull, or push.",
        impact="The container image was not produced or published.",
    ),
    RulePattern(
        name="docker_not_found",
        category_code="docker_failure",
        pattern=_p(r"manifest unknown|pull access denied|repository does not exist"),
        weight=0.86,
        root_cause="The container image or repository could not be accessed.",
        technical="Registry authentication or image reference resolution failed.",
        impact="Workload packaging or deployment cannot proceed.",
    ),
    RulePattern(
        name="npm_dependency",
        category_code="dependency_failure",
        pattern=_p(r"npm ERR!|ERESOLVE|Could not resolve dependency|yarn error|pnpm ERR"),
        weight=0.90,
        root_cause="A package dependency could not be resolved or installed.",
        technical="The package manager failed while resolving or fetching dependencies.",
        impact="The build cannot install required libraries.",
    ),
    RulePattern(
        name="pip_dependency",
        category_code="dependency_failure",
        pattern=_p(
            r"ERROR: Could not find a version|No matching distribution"
            r"|pip install.*failed|ResolutionImpossible"
        ),
        weight=0.88,
        root_cause="A Python dependency could not be resolved or installed.",
        technical="pip/poetry dependency resolution failed.",
        impact="The Python environment cannot be prepared for the build.",
    ),
    RulePattern(
        name="test_assertion",
        category_code="test_failure",
        pattern=_p(r"AssertionError|FAILED .*::|tests? failed|expected .* but (got|was)|FAIL: "),
        weight=0.87,
        root_cause="One or more automated tests failed.",
        technical="The test runner reported assertion or case failures.",
        impact="Quality gates blocked the pipeline.",
    ),
    RulePattern(
        name="pytest_fail",
        category_code="test_failure",
        pattern=_p(r"=+ .* failed in |FAILED tests/|pytest.*exitstatus"),
        weight=0.89,
        root_cause="Pytest reported failing test cases.",
        technical="Pytest exited with failing tests.",
        impact="The CI quality check did not pass.",
    ),
    RulePattern(
        name="compile_error",
        category_code="build_failure",
        pattern=_p(
            r"compilation failed|error TS\d+|BUILD FAILURE|Gradle build failed"
            r"|mvn .* FAILURE|Cannot find module"
        ),
        weight=0.86,
        root_cause="The project failed to compile or build.",
        technical="The build toolchain reported a compilation or packaging error.",
        impact="No deployable artifact was produced.",
    ),
    RulePattern(
        name="config_invalid",
        category_code="configuration_failure",
        pattern=_p(
            r"invalid configuration|config(?:uration)? error|missing required (?:env"
            r"|environment|property|key)|YAMLException|while parsing a"
        ),
        weight=0.84,
        root_cause="Configuration is invalid or incomplete.",
        technical="Required configuration keys or structured config files failed validation.",
        impact="The workflow cannot run with the current settings.",
    ),
    RulePattern(
        name="deploy_fail",
        category_code="deployment_failure",
        pattern=_p(
            r"deployment failed|deploy .* failed|rollout .* failed"
            r"|UpdateService.*failed|Helm.*ERROR"
        ),
        weight=0.85,
        root_cause="The deployment step failed while updating the target environment.",
        technical="A deploy/rollout command exited with an error.",
        impact="The new version was not released to the environment.",
    ),
    RulePattern(
        name="network_timeout",
        category_code="network_failure",
        pattern=_p(
            r"connection timed out|Connection refused|Could not resolve host"
            r"|Name or service not known|ETIMEDOUT|ECONNREFUSED"
        ),
        weight=0.88,
        root_cause="A network connection timed out or was refused.",
        technical="Outbound connectivity or DNS resolution failed during the job.",
        impact="Dependent services or registries could not be reached.",
    ),
    RulePattern(
        name="security_misconfig",
        category_code="security_misconfiguration",
        pattern=_p(
            r"insecure|TLS handshake|certificate (?:verify failed|has expired)|CORS"
            r"|CSP|secret exposed|permissions-policy"
        ),
        weight=0.80,
        root_cause="A security-related configuration issue was detected.",
        technical="TLS, secrets, or policy configuration blocked or failed the operation.",
        impact="Secure communication or policy compliance was compromised.",
    ),
)


def score_text(text: str) -> dict[str, list[tuple[RulePattern, float]]]:
    """Return category_code -> list of (rule, score) matches."""
    scores: dict[str, list[tuple[RulePattern, float]]] = {}
    for rule in RULES:
        if rule.pattern.search(text):
            scores.setdefault(rule.category_code, []).append((rule, rule.weight))
    return scores
