"""Authentication and authorization domain exceptions."""

from fastapi import status

from app.core.exceptions import DevGuardError


class AuthenticationError(DevGuardError):
    """Base authentication failure."""

    def __init__(
        self,
        message: str = "Authentication failed.",
        error_code: str = "AUTHENTICATION_FAILED",
        status_code: int = status.HTTP_401_UNAUTHORIZED,
    ) -> None:
        super().__init__(message=message, error_code=error_code, status_code=status_code)


class InvalidCredentialsError(AuthenticationError):
    """Generic login failure (do not reveal whether email exists)."""

    def __init__(self) -> None:
        super().__init__(
            message="Invalid email or password.",
            error_code="INVALID_CREDENTIALS",
        )


class UserDisabledError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__(
            message="User account is disabled.",
            error_code="USER_DISABLED",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class InvalidTokenError(AuthenticationError):
    def __init__(self, message: str = "Invalid or expired token.") -> None:
        super().__init__(
            message=message,
            error_code="INVALID_TOKEN",
        )


class EmailAlreadyExistsError(DevGuardError):
    def __init__(self) -> None:
        super().__init__(
            message="A user with this email already exists.",
            error_code="EMAIL_ALREADY_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
        )


class WeakPasswordError(DevGuardError):
    def __init__(self, message: str = "Password does not meet security requirements.") -> None:
        super().__init__(
            message=message,
            error_code="WEAK_PASSWORD",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class AuthorizationError(DevGuardError):
    def __init__(
        self,
        message: str = "You are not authorized to perform this action.",
        error_code: str = "FORBIDDEN",
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class MembershipInactiveError(AuthorizationError):
    def __init__(self) -> None:
        super().__init__(
            message="Organization membership is inactive.",
            error_code="MEMBERSHIP_INACTIVE",
        )
