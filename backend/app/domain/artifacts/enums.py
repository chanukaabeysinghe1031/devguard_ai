"""Phase 6A artifact acquisition and parse status enumerations."""

from enum import StrEnum


class ArtifactKind(StrEnum):
    EXECUTION_LOG = "execution_log"
    PREVIOUS_SUCCESS_LOG = "previous_success_log"
    WORKFLOW_YAML = "workflow_yaml"
    REUSABLE_WORKFLOW_YAML = "reusable_workflow_yaml"
    TERRAFORM_FILE = "terraform_file"
    TERRAFORM_PLAN_JSON = "terraform_plan_json"
    TERRAFORM_LOCK = "terraform_lock"
    IAM_POLICY_JSON = "iam_policy_json"
    AWS_ERROR_METADATA = "aws_error_metadata"
    COMMIT_METADATA = "commit_metadata"
    CHANGED_FILES_METADATA = "changed_files_metadata"
    VARIABLE_FILE = "variable_file"
    OTHER = "other"


class ArtifactSource(StrEnum):
    GITHUB = "github"
    UPLOAD = "upload"
    DERIVED = "derived"
    SYSTEM = "system"


class AcquisitionStatus(StrEnum):
    COLLECTED = "collected"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    SKIPPED = "skipped"


class RedactionStatus(StrEnum):
    PENDING = "pending"
    MASKED = "masked"
    NOT_REQUIRED = "not_required"
    FAILED = "failed"


class ParseStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
