"""Repository-layer domain exceptions."""


class RepositoryError(Exception):
    """Base class for repository failures."""


class EntityNotFoundError(RepositoryError):
    """Raised when a requested entity does not exist."""


class DuplicateEntityError(RepositoryError):
    """Raised when a uniqueness constraint would be violated."""


class InvalidRepositoryOperationError(RepositoryError):
    """Raised when a repository operation is not permitted."""
