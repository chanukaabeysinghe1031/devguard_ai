"""SQLAlchemy PostgreSQL-native enum types."""

from sqlalchemy import Enum

from app.domain.enums import (
    AnalysisRunStatus,
    CiProvider,
    DeliveryStatus,
    EvidenceType,
    FileProcessingStatus,
    FileType,
    FileValidationStatus,
    GenerationStatus,
    IncidentPriority,
    IncidentSeverity,
    IncidentStatus,
    IntegrationStatus,
    InvitationStatus,
    KnowledgeDocumentStatus,
    ModelVersionStatus,
    NotificationType,
    OrganizationRole,
    OrganizationStatus,
    PipelineRunStatus,
    PlatformRole,
    ProjectStatus,
    RecommendationStepType,
    RiskLevel,
    SecretMaskingStatus,
)


def _enum(enum_cls: type, name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        create_constraint=True,
        native_enum=True,
        values_callable=lambda e: [member.value for member in e],
    )


platform_role_enum = _enum(PlatformRole, "platform_role")
organization_role_enum = _enum(OrganizationRole, "organization_role")
organization_status_enum = _enum(OrganizationStatus, "organization_status")
project_status_enum = _enum(ProjectStatus, "project_status")
ci_provider_enum = _enum(CiProvider, "ci_provider")
integration_status_enum = _enum(IntegrationStatus, "integration_status")
file_type_enum = _enum(FileType, "file_type")
file_validation_status_enum = _enum(FileValidationStatus, "file_validation_status")
secret_masking_status_enum = _enum(SecretMaskingStatus, "secret_masking_status")
file_processing_status_enum = _enum(FileProcessingStatus, "file_processing_status")
pipeline_run_status_enum = _enum(PipelineRunStatus, "pipeline_run_status")
incident_status_enum = _enum(IncidentStatus, "incident_status")
incident_severity_enum = _enum(IncidentSeverity, "incident_severity")
incident_priority_enum = _enum(IncidentPriority, "incident_priority")
analysis_run_status_enum = _enum(AnalysisRunStatus, "analysis_run_status")
evidence_type_enum = _enum(EvidenceType, "evidence_type")
risk_level_enum = _enum(RiskLevel, "risk_level")
recommendation_step_type_enum = _enum(RecommendationStepType, "recommendation_step_type")
notification_type_enum = _enum(NotificationType, "notification_type")
delivery_status_enum = _enum(DeliveryStatus, "delivery_status")
knowledge_document_status_enum = _enum(KnowledgeDocumentStatus, "knowledge_document_status")
generation_status_enum = _enum(GenerationStatus, "generation_status")
model_version_status_enum = _enum(ModelVersionStatus, "model_version_status")
invitation_status_enum = _enum(InvitationStatus, "invitation_status")
