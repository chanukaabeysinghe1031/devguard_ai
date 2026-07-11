"""Domain enumerations with lowercase stable identifiers."""

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


class PipelineRunStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


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
