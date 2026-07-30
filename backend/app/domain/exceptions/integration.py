"""Integration (Phase 5B GitHub ingestion) domain exceptions."""

from fastapi import status

from app.core.exceptions import DevGuardError


class IntegrationDisabledError(DevGuardError):
    def __init__(self, message: str = "GitHub integration is not enabled on this server.") -> None:
        super().__init__(
            message=message,
            error_code="INTEGRATION_DISABLED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class WebhookConfigurationError(DevGuardError):
    def __init__(self, message: str = "Webhook receiver is not configured.") -> None:
        super().__init__(
            message=message,
            error_code="WEBHOOK_NOT_CONFIGURED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class WebhookSignatureError(DevGuardError):
    """Raised when the HMAC signature of an inbound webhook cannot be verified."""

    def __init__(self, message: str = "Webhook signature verification failed.") -> None:
        super().__init__(
            message=message,
            error_code="WEBHOOK_SIGNATURE_INVALID",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class GitHubProviderError(DevGuardError):
    """Upstream GitHub API failure. ``retriable`` drives delivery retry policy."""

    def __init__(
        self,
        message: str = "GitHub API request failed.",
        *,
        error_code: str = "GITHUB_API_ERROR",
        retriable: bool = False,
    ) -> None:
        self.retriable = retriable
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class LogArchiveError(DevGuardError):
    """Raised when a workflow log archive violates the safe-extraction policy."""

    def __init__(self, message: str, error_code: str = "LOG_ARCHIVE_REJECTED") -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
