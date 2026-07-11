"""SQLAlchemy PostgreSQL-native enum types."""

from sqlalchemy import Enum

from app.domain.enums import (
    EvidenceType,
    FileType,
    PipelineRunStatus,
    RiskLevel,
    UserRole,
)

user_role_enum = Enum(
    UserRole,
    name="user_role",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum: [member.value for member in enum],
)

file_type_enum = Enum(
    FileType,
    name="file_type",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum: [member.value for member in enum],
)

pipeline_run_status_enum = Enum(
    PipelineRunStatus,
    name="pipeline_run_status",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum: [member.value for member in enum],
)

evidence_type_enum = Enum(
    EvidenceType,
    name="evidence_type",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum: [member.value for member in enum],
)

risk_level_enum = Enum(
    RiskLevel,
    name="risk_level",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum: [member.value for member in enum],
)
