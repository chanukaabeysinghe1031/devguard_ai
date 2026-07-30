"""GitHub App API client (ADR-005).

Authenticates as the App with a short-lived RS256 JWT, exchanges it for an
installation access token, and performs read-only Actions/metadata calls.
Installation tokens are cached in memory only and never persisted or logged.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
import structlog

from app.core.config import Settings
from app.domain.exceptions.integration import GitHubProviderError, IntegrationDisabledError
from app.domain.interfaces.github_provider import (
    GitHubInstallationInfo,
    GitHubRepositoryInfo,
    GitHubWorkflowInfo,
    GitHubWorkflowRunInfo,
)

logger = structlog.get_logger(__name__)

_APP_JWT_TTL_SECONDS = 540  # GitHub rejects App JWTs older than 10 minutes.
_RETRIABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
# Actions log downloads redirect to object storage; only these hosts are followed.
_ALLOWED_REDIRECT_HOSTS = (
    "githubusercontent.com",
    "objects.githubusercontent.com",
    "productionresultssa0.blob.core.windows.net",
)


@dataclass(slots=True)
class _CachedToken:
    token: str
    expires_at: float


def _host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    return any(
        host == allowed or host.endswith(f".{allowed}") for allowed in _ALLOWED_REDIRECT_HOSTS
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class GitHubAppProvider:
    """Read-only GitHub App client."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token_cache: dict[int, _CachedToken] = {}

    @property
    def name(self) -> str:
        return "github_app"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def _private_key(self) -> str:
        pem = (self._settings.github_app_private_key_pem or "").strip()
        if pem:
            return pem.replace("\\n", "\n")
        path = (self._settings.github_app_private_key_path or "").strip()
        if not path:
            raise IntegrationDisabledError("GitHub App private key is not configured.")
        try:
            with open(path, encoding="utf-8") as handle:
                return handle.read()
        except OSError as exc:
            raise IntegrationDisabledError("GitHub App private key file is unreadable.") from exc

    def build_app_jwt(self) -> str:
        app_id = (self._settings.github_app_id or "").strip()
        if not app_id:
            raise IntegrationDisabledError("GITHUB_APP_ID is not configured.")
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + _APP_JWT_TTL_SECONDS, "iss": app_id}
        return jwt.encode(payload, self._private_key(), algorithm="RS256")

    async def _installation_token(self, installation_id: int) -> str:
        cached = self._token_cache.get(installation_id)
        buffer = self._settings.github_installation_token_buffer_seconds
        if cached is not None and cached.expires_at - buffer > time.time():
            return cached.token

        payload = await self._request(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            token=self.build_app_jwt(),
        )
        token = str(payload.get("token") or "")
        if not token:
            raise GitHubProviderError("GitHub did not return an installation token.")
        expires = _parse_timestamp(payload.get("expires_at"))
        expires_at = expires.timestamp() if expires else time.time() + 3600
        self._token_cache[installation_id] = _CachedToken(token=token, expires_at=expires_at)
        logger.info("github_installation_token_issued", installation_id=installation_id)
        return token

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._settings.github_api_base_url.rstrip('/')}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {token}",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.github_api_timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.request(method, url, headers=headers, params=params)
        except httpx.HTTPError as exc:
            raise GitHubProviderError(
                "GitHub API request failed.",
                error_code="GITHUB_API_UNREACHABLE",
                retriable=True,
            ) from exc

        if response.status_code >= 400:
            raise GitHubProviderError(
                f"GitHub API returned {response.status_code} for {method} {path}.",
                error_code="GITHUB_API_ERROR",
                retriable=response.status_code in _RETRIABLE_STATUS,
            )
        if not response.content:
            return {}
        body = response.json()
        return body if isinstance(body, dict) else {"items": body}

    # ------------------------------------------------------------------
    # Read-only operations
    # ------------------------------------------------------------------
    async def get_installation(self, installation_id: int) -> GitHubInstallationInfo:
        payload = await self._request(
            "GET",
            f"/app/installations/{installation_id}",
            token=self.build_app_jwt(),
        )
        account = payload.get("account") or {}
        permissions = payload.get("permissions") or {}
        return GitHubInstallationInfo(
            installation_id=int(payload.get("id") or installation_id),
            account_login=str(account.get("login") or ""),
            account_id=int(account["id"]) if account.get("id") is not None else None,
            account_type=account.get("type"),
            repository_selection=payload.get("repository_selection"),
            permissions={str(k): str(v) for k, v in permissions.items()},
            created_at=_parse_timestamp(payload.get("created_at")),
        )

    async def list_installation_repositories(
        self,
        installation_id: int,
    ) -> list[GitHubRepositoryInfo]:
        token = await self._installation_token(installation_id)
        payload = await self._request(
            "GET",
            "/installation/repositories",
            token=token,
            params={"per_page": 100},
        )
        repositories = payload.get("repositories") or []
        return [
            GitHubRepositoryInfo(
                repository_id=int(repo["id"]),
                full_name=str(repo.get("full_name") or ""),
                default_branch=repo.get("default_branch"),
                html_url=repo.get("html_url"),
                private=bool(repo.get("private", True)),
            )
            for repo in repositories
            if isinstance(repo, dict) and repo.get("id") is not None
        ]

    async def list_repository_workflows(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
    ) -> list[GitHubWorkflowInfo]:
        token = await self._installation_token(installation_id)
        payload = await self._request(
            "GET",
            f"/repos/{repository_full_name}/actions/workflows",
            token=token,
            params={"per_page": 100},
        )
        workflows = payload.get("workflows") or []
        return [
            GitHubWorkflowInfo(
                workflow_id=int(item["id"]),
                name=str(item.get("name") or ""),
                path=item.get("path"),
                state=item.get("state"),
            )
            for item in workflows
            if isinstance(item, dict) and item.get("id") is not None
        ]

    async def get_workflow_run(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
        run_id: int,
    ) -> GitHubWorkflowRunInfo:
        token = await self._installation_token(installation_id)
        payload = await self._request(
            "GET",
            f"/repos/{repository_full_name}/actions/runs/{run_id}",
            token=token,
        )
        actor = payload.get("actor") or {}
        return GitHubWorkflowRunInfo(
            run_id=int(payload.get("id") or run_id),
            repository_full_name=repository_full_name,
            name=payload.get("name"),
            workflow_id=payload.get("workflow_id"),
            run_number=payload.get("run_number"),
            run_attempt=payload.get("run_attempt"),
            event=payload.get("event"),
            status=payload.get("status"),
            conclusion=payload.get("conclusion"),
            head_branch=payload.get("head_branch"),
            head_sha=payload.get("head_sha"),
            html_url=payload.get("html_url"),
            actor_login=actor.get("login"),
            run_started_at=_parse_timestamp(payload.get("run_started_at")),
            updated_at=_parse_timestamp(payload.get("updated_at")),
        )

    async def download_workflow_run_logs(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
        run_id: int,
    ) -> bytes | None:
        """Download the run log archive, following only allow-listed redirects."""
        token = await self._installation_token(installation_id)
        url = (
            f"{self._settings.github_api_base_url.rstrip('/')}"
            f"/repos/{repository_full_name}/actions/runs/{run_id}/logs"
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {token}",
        }
        max_bytes = self._settings.github_max_log_archive_bytes
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.github_api_timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.get(url, headers=headers)
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location", "")
                    if not _host_allowed(location):
                        raise GitHubProviderError(
                            "Refusing to follow log download redirect to an untrusted host.",
                            error_code="GITHUB_REDIRECT_REJECTED",
                        )
                    # The signed storage URL must not carry the installation token.
                    response = await client.get(location, headers={"Accept": "*/*"})
                if response.status_code == 404:
                    logger.info(
                        "github_workflow_logs_unavailable",
                        repository=repository_full_name,
                        run_id=run_id,
                    )
                    return None
                if response.status_code >= 400:
                    raise GitHubProviderError(
                        f"GitHub log download returned {response.status_code}.",
                        retriable=response.status_code in _RETRIABLE_STATUS,
                    )
                content = response.content
        except httpx.HTTPError as exc:
            raise GitHubProviderError(
                "GitHub log download failed.",
                error_code="GITHUB_API_UNREACHABLE",
                retriable=True,
            ) from exc

        if len(content) > max_bytes:
            raise GitHubProviderError(
                "Workflow log archive exceeds the configured size limit.",
                error_code="GITHUB_LOG_ARCHIVE_TOO_LARGE",
            )
        return content
