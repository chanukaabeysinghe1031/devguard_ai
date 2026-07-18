"""Domain exceptions."""

from app.domain.exceptions.repository import (
    DuplicateEntityError,
    EntityNotFoundError,
    InvalidRepositoryOperationError,
    RepositoryError,
)

__all__ = [
    "DuplicateEntityError",
    "EntityNotFoundError",
    "InvalidRepositoryOperationError",
    "RepositoryError",
]
