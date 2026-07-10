"""Application exceptions and global error handlers."""

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def build_error_response(
    request: Request,
    *,
    detail: str,
    error_code: str,
    status_code: int,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build the standard error envelope."""
    content: dict[str, Any] = {
        "detail": detail,
        "error_code": error_code,
        "timestamp": datetime.now(UTC).isoformat(),
        "path": str(request.url.path),
        "request_id": _get_request_id(request),
    }
    if extra:
        content.update(extra)
    return JSONResponse(status_code=status_code, content=content)


class DevGuardError(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


class ServiceUnavailableError(DevGuardError):
    """Raised when a dependency (e.g. database) is unavailable."""

    def __init__(self, message: str = "Service temporarily unavailable") -> None:
        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


async def devguard_exception_handler(request: Request, exc: DevGuardError) -> JSONResponse:
    return build_error_response(
        request,
        detail=exc.message,
        error_code=exc.error_code,
        status_code=exc.status_code,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return build_error_response(
        request,
        detail=str(exc.detail),
        error_code="HTTP_ERROR",
        status_code=exc.status_code,
    )


async def starlette_http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    return build_error_response(
        request,
        detail=str(exc.detail),
        error_code="HTTP_ERROR",
        status_code=exc.status_code,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return build_error_response(
        request,
        detail="Request validation failed",
        error_code="VALIDATION_ERROR",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        extra={"errors": exc.errors()},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return build_error_response(
        request,
        detail="An unexpected error occurred",
        error_code="INTERNAL_ERROR",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
