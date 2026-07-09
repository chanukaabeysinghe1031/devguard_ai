"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (
    EvidenceType,
    FileType,
    HistoryAction,
    PipelineRunStatus,
    RiskLevel,
    UserRole,
)
from app.infrastructure.database.base import Base, TimestampMixin, UpdatedAtMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default=UserRole.ANALYST.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    uploaded_files: Mapped[list["UploadedFile"]] = relationship(back_populates="user")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(back_populates="user")
    feedback_items: Mapped[list["Feedback"]] = relationship(back_populates="user")
    history_entries: Mapped[list["AnalysisHistory"]] = relationship(back_populates="user")


class UploadedFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "uploaded_files"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_type: Mapped[str] = mapped_column(String(64), default=FileType.LOG.value, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="uploaded_files")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(
        back_populates="uploaded_file",
        foreign_keys="PipelineRun.uploaded_file_id",
    )


class FailureCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "failure_categories"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="category")


class PipelineRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pipeline_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False
    )
    workflow_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default=PipelineRunStatus.PENDING.value, nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    pipeline_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_log_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    user: Mapped["User"] = relationship(back_populates="pipeline_runs")
    uploaded_file: Mapped["UploadedFile"] = relationship(
        back_populates="pipeline_runs",
        foreign_keys=[uploaded_file_id],
    )
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="pipeline_run")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(back_populates="pipeline_run")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="pipeline_run")
    feedback_items: Mapped[list["Feedback"]] = relationship(back_populates="pipeline_run")
    history_entries: Mapped[list["AnalysisHistory"]] = relationship(back_populates="pipeline_run")


class ModelVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "model_versions"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    classifier_type: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    training_dataset_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="model_version")
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="model_version")

    __table_args__ = (UniqueConstraint("name", "version", name="uq_model_name_version"),)


class Prediction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "predictions"

    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("failure_categories.id"), nullable=False
    )
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    classifier_name: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_vector_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    probabilities: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="predictions")
    category: Mapped["FailureCategory"] = relationship(back_populates="predictions")
    model_version: Mapped["ModelVersion | None"] = relationship(back_populates="predictions")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(back_populates="prediction")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="prediction")


class EvidenceItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidence_items"

    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True
    )
    evidence_type: Mapped[str] = mapped_column(
        String(64), default=EvidenceType.LOG_LINE.value, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_location: Mapped[str | None] = mapped_column(String(512), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    highlight_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    highlight_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="evidence_items")
    prediction: Mapped["Prediction | None"] = relationship(back_populates="evidence_items")


class Recommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "recommendations"

    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True
    )
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    remediation_steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), default=RiskLevel.MEDIUM.value, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    preventive_actions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    future_improvements: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    llm_model: Mapped[str] = mapped_column(String(128), nullable=False)
    rag_sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="recommendations")
    prediction: Mapped["Prediction | None"] = relationship(back_populates="recommendations")
    feedback_items: Mapped[list["Feedback"]] = relationship(back_populates="recommendation")


class Evaluation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evaluations"

    model_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    model_version: Mapped["ModelVersion"] = relationship(back_populates="evaluations")


class Feedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "feedback"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False
    )
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_helpful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="feedback_items")
    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="feedback_items")
    recommendation: Mapped["Recommendation | None"] = relationship(back_populates="feedback_items")


class AnalysisHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analysis_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    user: Mapped["User"] = relationship(back_populates="history_entries")
    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="history_entries")
