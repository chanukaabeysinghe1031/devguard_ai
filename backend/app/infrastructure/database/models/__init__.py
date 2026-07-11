"""Register all ORM models with SQLAlchemy metadata (Alembic autogenerate)."""

from app.infrastructure.database.base import Base
from app.infrastructure.database.models.analysis_history import AnalysisHistory
from app.infrastructure.database.models.evaluation import Evaluation
from app.infrastructure.database.models.evidence_item import EvidenceItem
from app.infrastructure.database.models.failure_category import FailureCategory
from app.infrastructure.database.models.feedback import Feedback
from app.infrastructure.database.models.model_version import ModelVersion
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.database.models.prediction import Prediction
from app.infrastructure.database.models.recommendation import Recommendation
from app.infrastructure.database.models.uploaded_file import UploadedFile
from app.infrastructure.database.models.user import User

__all__ = [
    "Base",
    "AnalysisHistory",
    "Evaluation",
    "EvidenceItem",
    "FailureCategory",
    "Feedback",
    "ModelVersion",
    "PipelineRun",
    "Prediction",
    "Recommendation",
    "UploadedFile",
    "User",
]
