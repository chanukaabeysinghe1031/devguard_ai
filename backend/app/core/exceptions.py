"""Application-specific exceptions and HTTP error mapping."""

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class DevGuardError(Exception):
    """Base exception for domain and service errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(DevGuardError):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": identifier},
        )


class ValidationError(DevGuardError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class AuthenticationError(DevGuardError):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationError(DevGuardError):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class UploadError(DevGuardError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            error_code="UPLOAD_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


async def devguard_exception_handler(request: Request, exc: DevGuardError) -> JSONResponse:
    """Map DevGuardError to standard JSON error envelope."""
    from datetime import UTC, datetime

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "timestamp": datetime.now(UTC).isoformat(),
            "path": str(request.url.path),
            **({"details": exc.details} if exc.details else {}),
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Map FastAPI HTTPException to standard JSON error envelope."""
    from datetime import UTC, datetime

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": "HTTP_ERROR",
            "timestamp": datetime.now(UTC).isoformat(),
            "path": str(request.url.path),
        },
    )
