"""Domain entities used across repository boundaries."""

from app.domain.entities.failure_category import FailureCategoryEntity
from app.domain.entities.pipeline_run import PipelineRunEntity
from app.domain.entities.user import UserEntity

__all__ = [
    "FailureCategoryEntity",
    "PipelineRunEntity",
    "UserEntity",
]
