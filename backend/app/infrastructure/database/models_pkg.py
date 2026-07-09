"""Register ORM models for Alembic autogenerate."""

from app.infrastructure.database.models import (  # noqa: F401
    AnalysisHistory,
    Evaluation,
    EvidenceItem,
    FailureCategory,
    Feedback,
    ModelVersion,
    PipelineRun,
    Prediction,
    Recommendation,
    UploadedFile,
    User,
)
