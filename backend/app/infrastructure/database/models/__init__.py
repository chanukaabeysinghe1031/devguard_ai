"""Register all ORM models with SQLAlchemy metadata (Alembic autogenerate)."""

from app.infrastructure.database.base import Base
from app.infrastructure.database.models.analysis_artifact_bundle import (
    AnalysisArtifact,
    AnalysisArtifactBundle,
    ArtifactParseResult,
)
from app.infrastructure.database.models.analysis_run import AnalysisRun
from app.infrastructure.database.models.audit_log import AuditLog
from app.infrastructure.database.models.evaluation import Evaluation
from app.infrastructure.database.models.evidence_item import EvidenceItem
from app.infrastructure.database.models.failure_category import FailureCategory
from app.infrastructure.database.models.feedback import Feedback
from app.infrastructure.database.models.github_installation import GitHubInstallation
from app.infrastructure.database.models.github_repository_connection import (
    GitHubRepositoryConnection,
)
from app.infrastructure.database.models.hierarchical_classification import (
    ClassificationCandidateRow,
    ClassificationConfidenceComponentRow,
    ClassificationDisagreementResultRow,
    HierarchicalClassificationResultRow,
    OpenSetAssessmentRow,
    TaxonomyMappingRow,
)
from app.infrastructure.database.models.causal_hypotheses import (
    CausalHypothesisRow,
    CausalHypothesisRunRow,
    HypothesisCriticResultRow,
    HypothesisEvidenceLinkRow,
)
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_assignment import IncidentAssignment
from app.infrastructure.database.models.incident_event import IncidentEvent
from app.infrastructure.database.models.incident_note import IncidentNote
from app.infrastructure.database.models.incident_report import IncidentReport
from app.infrastructure.database.models.incident_resolution import IncidentResolution
from app.infrastructure.database.models.knowledge_chunk import KnowledgeChunk
from app.infrastructure.database.models.knowledge_document import KnowledgeDocument
from app.infrastructure.database.models.model_version import ModelVersion
from app.infrastructure.database.models.notification import Notification
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.organization_invitation import OrganizationInvitation
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.database.models.prediction import Prediction
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.project_integration import ProjectIntegration
from app.infrastructure.database.models.recommendation import Recommendation
from app.infrastructure.database.models.recommendation_step import RecommendationStep
from app.infrastructure.database.models.refresh_token import RefreshToken
from app.infrastructure.database.models.retrieved_document import RetrievedDocument
from app.infrastructure.database.models.temporal_evidence_graph import (
    EvidenceGraphEdgeRow,
    EvidenceGraphNodeRow,
    EvidenceGraphRow,
    GraphConsistencyReportRow,
    TemporalEventLinkRow,
    TemporalEventRow,
    TemporalLocalisationResultRow,
)
from app.infrastructure.database.models.uploaded_file import UploadedFile
from app.infrastructure.database.models.user import User
from app.infrastructure.database.models.webhook_delivery import WebhookDelivery

__all__ = [
    "Base",
    "AnalysisArtifact",
    "AnalysisArtifactBundle",
    "AnalysisRun",
    "ArtifactParseResult",
    "AuditLog",
    "Evaluation",
    "EvidenceGraphEdgeRow",
    "EvidenceGraphNodeRow",
    "EvidenceGraphRow",
    "EvidenceItem",
    "FailureCategory",
    "Feedback",
    "GitHubInstallation",
    "GitHubRepositoryConnection",
    "GraphConsistencyReportRow",
    "ClassificationCandidateRow",
    "ClassificationConfidenceComponentRow",
    "ClassificationDisagreementResultRow",
    "HierarchicalClassificationResultRow",
    "OpenSetAssessmentRow",
    "TaxonomyMappingRow",
    "CausalHypothesisRow",
    "CausalHypothesisRunRow",
    "HypothesisCriticResultRow",
    "HypothesisEvidenceLinkRow",
    "Incident",
    "IncidentAssignment",
    "IncidentEvent",
    "IncidentNote",
    "IncidentReport",
    "IncidentResolution",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "ModelVersion",
    "Notification",
    "Organization",
    "OrganizationInvitation",
    "OrganizationMember",
    "PipelineRun",
    "Prediction",
    "Project",
    "ProjectIntegration",
    "Recommendation",
    "RecommendationStep",
    "RefreshToken",
    "RetrievedDocument",
    "TemporalEventLinkRow",
    "TemporalEventRow",
    "TemporalLocalisationResultRow",
    "UploadedFile",
    "User",
    "WebhookDelivery",
]
