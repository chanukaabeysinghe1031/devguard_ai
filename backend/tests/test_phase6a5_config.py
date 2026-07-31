"""Phase 6A.5 Part 1B — configuration flag and bound tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "PROJECT_NAME": "DevGuard AI Test",
        "APP_VERSION": "1.0.0",
        "ENVIRONMENT": "development",
        "DEBUG": False,
        "DATABASE_URL": "postgresql+asyncpg://devguard:change_me@localhost:5432/devguard_test",
        "JWT_SECRET_KEY": "x" * 32,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_phase6a5_experimental_flags_default_off() -> None:
    assert Settings.model_fields["hypothesis_directed_rag_enabled"].default is False
    assert Settings.model_fields["multi_query_retrieval_enabled"].default is False
    assert Settings.model_fields["hypothesis_graph_context_enabled"].default is False
    assert Settings.model_fields["causal_ranking_enabled"].default is False


def test_phase6a5_supporting_toggles_default_on() -> None:
    assert Settings.model_fields["hypothesis_historical_retrieval_enabled"].default is True
    assert Settings.model_fields["hypothesis_static_kb_retrieval_enabled"].default is True
    assert Settings.model_fields["hypothesis_artifact_retrieval_enabled"].default is True
    assert Settings.model_fields["hypothesis_retrieval_persistence_enabled"].default is True
    assert Settings.model_fields["retrieval_cache_enabled"].default is True


def test_phase6a5_constructed_settings_respect_defaults() -> None:
    settings = _base_settings(
        HYPOTHESIS_DIRECTED_RAG_ENABLED=False,
        MULTI_QUERY_RETRIEVAL_ENABLED=False,
        HYPOTHESIS_GRAPH_CONTEXT_ENABLED=False,
        CAUSAL_RANKING_ENABLED=False,
        HYPOTHESIS_HISTORICAL_RETRIEVAL_ENABLED=True,
        HYPOTHESIS_STATIC_KB_RETRIEVAL_ENABLED=True,
        HYPOTHESIS_ARTIFACT_RETRIEVAL_ENABLED=True,
        HYPOTHESIS_RETRIEVAL_PERSISTENCE_ENABLED=True,
        RETRIEVAL_CACHE_ENABLED=True,
    )
    assert settings.hypothesis_directed_rag_enabled is False
    assert settings.multi_query_retrieval_enabled is False
    assert settings.hypothesis_graph_context_enabled is False
    assert settings.causal_ranking_enabled is False
    assert settings.hypothesis_historical_retrieval_enabled is True
    assert settings.hypothesis_static_kb_retrieval_enabled is True
    assert settings.hypothesis_artifact_retrieval_enabled is True
    assert settings.hypothesis_retrieval_persistence_enabled is True
    assert settings.retrieval_cache_enabled is True


def test_max_queries_zero_raises() -> None:
    with pytest.raises(ValidationError):
        _base_settings(MAX_QUERIES_PER_HYPOTHESIS=0)


def test_retrieval_timeout_non_positive_raises() -> None:
    with pytest.raises(ValidationError):
        _base_settings(HYPOTHESIS_RETRIEVAL_TIMEOUT_SECONDS=0)
    with pytest.raises(ValidationError):
        _base_settings(HYPOTHESIS_RETRIEVAL_TIMEOUT_SECONDS=-1.0)


def test_concurrent_sessions_cannot_exceed_max_hypotheses() -> None:
    settings = _base_settings(
        MAX_HYPOTHESES_FOR_RETRIEVAL=3,
        MAX_CONCURRENT_HYPOTHESIS_RETRIEVAL_SESSIONS=5,
    )
    problems = settings.validate_for_runtime()
    assert any(
        "MAX_CONCURRENT_HYPOTHESIS_RETRIEVAL_SESSIONS cannot exceed" in p for p in problems
    )


def test_concurrent_sessions_within_max_hypotheses_ok() -> None:
    settings = _base_settings(
        MAX_HYPOTHESES_FOR_RETRIEVAL=5,
        MAX_CONCURRENT_HYPOTHESIS_RETRIEVAL_SESSIONS=2,
    )
    problems = settings.validate_for_runtime()
    assert not any("MAX_CONCURRENT_HYPOTHESIS_RETRIEVAL_SESSIONS" in p for p in problems)
