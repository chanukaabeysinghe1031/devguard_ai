"""GitHub provider construction (Phase 5B)."""

from __future__ import annotations

from app.core.config import Settings
from app.domain.interfaces.github_provider import GitHubProvider


def get_github_provider(settings: Settings) -> GitHubProvider:
    """Return the configured GitHub provider.

    The deterministic fake is used when ``GITHUB_PROVIDER=fake`` or when the
    GitHub App is disabled, so local development and tests never require real
    App credentials. Production configuration rejects the fake provider.
    """
    if settings.github_provider == "fake" or not settings.github_app_enabled:
        from app.infrastructure.integrations.fake_github_provider import FakeGitHubProvider

        return FakeGitHubProvider()

    from app.infrastructure.integrations.github_app_provider import GitHubAppProvider

    return GitHubAppProvider(settings)
