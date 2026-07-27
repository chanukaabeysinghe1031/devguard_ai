"""Upload-specific domain exceptions."""

from fastapi import status

from app.core.exceptions import DevGuardError
from app.domain.exceptions.business import ConflictError, ValidationBusinessError


class FileTooLargeError(DevGuardError):
    def __init__(self, message: str = "Uploaded file exceeds the maximum allowed size.") -> None:
        super().__init__(
            message=message,
            error_code="FILE_TOO_LARGE",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )


class UnsupportedFileTypeError(DevGuardError):
    def __init__(self, message: str = "Unsupported file type.") -> None:
        super().__init__(
            message=message,
            error_code="UNSUPPORTED_FILE_TYPE",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )


class EmptyFileError(ValidationBusinessError):
    def __init__(self) -> None:
        super().__init__(message="Uploaded file is empty.", error_code="EMPTY_FILE")


class TooManyFilesError(ValidationBusinessError):
    def __init__(self) -> None:
        super().__init__(
            message="Too many files in a single upload request.",
            error_code="TOO_MANY_FILES",
        )


class DuplicateFileError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            message="A file with the same content already exists for this incident.",
            error_code="DUPLICATE_FILE",
        )


class InvalidArchiveError(ValidationBusinessError):
    def __init__(self) -> None:
        super().__init__(
            message="Archive uploads are not supported.",
            error_code="INVALID_ARCHIVE",
        )


class FileDeletionForbiddenError(ConflictError):
    def __init__(
        self,
        message: str = "File cannot be deleted after analysis has started.",
    ) -> None:
        super().__init__(message=message, error_code="FILE_DELETION_FORBIDDEN")


class StorageConfigurationError(RuntimeError):
    """Raised when file storage settings are missing or unsafe."""
