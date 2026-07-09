"""Domain enumerations."""

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class FileType(StrEnum):
    LOG = "log"
    WORKFLOW_YAML = "workflow_yaml"
    TERRAFORM = "terraform"
    OTHER = "other"


class Platform(StrEnum):
    GITHUB_ACTIONS = "github_actions"
    TERRAFORM = "terraform"
    AWS = "aws"
    # Extensible — future: GITLAB_CI, AZURE_DEVOPS, JENKINS, DOCKER, K8S, AZURE, GCP


class PipelineRunStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FailureCategorySlug(StrEnum):
    BUILD_FAILURE = "build_failure"
    TEST_FAILURE = "test_failure"
    DEPENDENCY_FAILURE = "dependency_failure"
    CONFIGURATION_FAILURE = "configuration_failure"
    TERRAFORM_FAILURE = "terraform_failure"
    DOCKER_FAILURE = "docker_failure"
    DEPLOYMENT_FAILURE = "deployment_failure"
    AWS_PERMISSION_FAILURE = "aws_permission_failure"
    NETWORK_FAILURE = "network_failure"
    SECURITY_MISCONFIGURATION = "security_misconfiguration"
    UNKNOWN_FAILURE = "unknown_failure"


class EvidenceType(StrEnum):
    LOG_LINE = "log_line"
    CONFIG_SNIPPET = "config_snippet"
    STACK_TRACE = "stack_trace"
    METRIC = "metric"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ClassifierType(StrEnum):
    LOGISTIC_REGRESSION = "logistic_regression"
    RANDOM_FOREST = "random_forest"


class HistoryAction(StrEnum):
    UPLOADED = "uploaded"
    ANALYZED = "analyzed"
    VIEWED = "viewed"
    EXPORTED = "exported"
