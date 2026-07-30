"""Domain enumerations with lowercase stable identifiers."""

from enum import StrEnum


class PlatformRole(StrEnum):
    """Platform-level role on users (not organization membership)."""

    PLATFORM_ADMIN = "platform_admin"
    NONE = "none"


class OrganizationRole(StrEnum):
    """Authoritative organization membership roles."""

    ORGANIZATION_OWNER = "organization_owner"
    ORGANIZATION_ADMIN = "organization_admin"
    ENGINEER = "engineer"
    VIEWER = "viewer"


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class CiProvider(StrEnum):
    GITHUB_ACTIONS = "github_actions"
    GITLAB = "gitlab"
    JENKINS = "jenkins"
    OTHER = "other"


class IntegrationStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class FileType(StrEnum):
    LOG = "log"
    WORKFLOW_YAML = "workflow_yaml"
    TERRAFORM = "terraform"
    JSON = "json"
    ZIP = "zip"
    OTHER = "other"


class FileValidationStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    FAILED = "failed"


class SecretMaskingStatus(StrEnum):
    PENDING = "pending"
    MASKED = "masked"
    FAILED = "failed"
    NOT_REQUIRED = "not_required"


class FileProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IncidentStatus(StrEnum):
    DETECTED = "detected"
    ANALYSING = "analysing"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ANALYSIS_FAILED = "analysis_failed"
    IGNORED = "ignored"
    FALSE_POSITIVE = "false_positive"
    REOPENED = "reopened"


class IncidentSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentPriority(StrEnum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class AnalysisRunStatus(StrEnum):
    QUEUED = "queued"
    PREPROCESSING = "preprocessing"
    CLASSIFYING = "classifying"
    RETRIEVING = "retrieving"
    REASONING = "reasoning"
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


class RecommendationStepType(StrEnum):
    REMEDIATION = "remediation"
    VERIFICATION = "verification"
    PREVENTION = "prevention"


class NotificationType(StrEnum):
    INCIDENT_CREATED = "incident_created"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"
    ASSIGNMENT = "assignment"
    SYSTEM = "system"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class KnowledgeDocumentStatus(StrEnum):
    ACTIVE = "active"
    OUTDATED = "outdated"
    ARCHIVED = "archived"


class GenerationStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class WebhookProcessingStatus(StrEnum):
    """Durable processing state of an inbound webhook delivery (ADR-005).

    Persisted as VARCHAR rather than a PostgreSQL enum so the ingestion state
    machine can evolve without a migration.
    """

    RECEIVED = "received"
    VALIDATED = "validated"
    QUEUED = "queued"
    FETCHING_METADATA = "fetching_metadata"
    DOWNLOADING_LOGS = "downloading_logs"
    EXTRACTING_LOGS = "extracting_logs"
    CREATING_INCIDENT = "creating_incident"
    STARTING_ANALYSIS = "starting_analysis"
    COMPLETED = "completed"
    IGNORED = "ignored"
    RETRYING = "retrying"
    FAILED = "failed"


class GitHubInstallationStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class ModelVersionStatus(StrEnum):
    TRAINING = "training"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    FAILED = "failed"
