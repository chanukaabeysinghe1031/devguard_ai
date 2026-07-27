"""Business-domain exceptions for Module 4 APIs."""

from fastapi import status

from app.core.exceptions import DevGuardError


class ResourceNotFoundError(DevGuardError):
    def __init__(self, message: str = "The requested resource could not be found.") -> None:
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(DevGuardError):
    def __init__(
        self,
        message: str,
        error_code: str = "CONFLICT",
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_409_CONFLICT,
        )


class InvalidTransitionError(ConflictError):
    def __init__(self, message: str = "Invalid incident status transition.") -> None:
        super().__init__(message=message, error_code="INVALID_STATUS_TRANSITION")


class LastOwnerProtectionError(ConflictError):
    def __init__(
        self,
        message: str = "Cannot remove or demote the last active organization owner.",
    ) -> None:
        super().__init__(message=message, error_code="LAST_OWNER_PROTECTED")


class ValidationBusinessError(DevGuardError):
    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR") -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
