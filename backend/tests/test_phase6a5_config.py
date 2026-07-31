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
    assert Settings.model_fields["adaptive_hypothesis_retrieval_enabled"].default is False
    assert Settings.model_fields["hypothesis_query_expansion_enabled"].default is False
    assert Settings.model_fields["hypothesis_source_routing_enabled"].default is False
    assert Settings.model_fields["retrieval_result_validation_enabled"].default is False
    assert Settings.model_fields["retrieval_follow_up_enabled"].default is False
    assert Settings.model_fields["hypothesis_exact_identifier_boost_enabled"].default is False
    assert Settings.model_fields["hypothesis_metadata_filtering_enabled"].default is False


def test_phase6a5_part2_bounds_defaults() -> None:
    assert Settings.model_fields["max_query_expansions_per_hypothesis"].default == 4
    assert Settings.model_fields["max_follow_up_rounds"].default == 1
    assert Settings.model_fields["max_total_queries_per_hypothesis"].default == 10
    assert Settings.model_fields["max_source_types_per_query"].default == 5
    assert Settings.model_fields["min_results_before_follow_up"].default == 2
    assert Settings.model_fields["min_retrieval_score_for_acceptance"].default == 0.35
    assert Settings.model_fields["max_exact_identifiers_per_query"].default == 8
    assert Settings.model_fields["max_retrieval_validation_items"].default == 50
    assert Settings.model_fields["max_graph_retrieval_depth"].default == 4
    assert Settings.model_fields["max_graph_retrieval_nodes"].default == 80
    assert Settings.model_fields["max_graph_retrieval_edges"].default == 150
    assert Settings.model_fields["max_artifact_results_per_query"].default == 15
    assert Settings.model_fields["max_temporal_results_per_query"].default == 15
    assert Settings.model_fields["max_historical_results_per_query"].default == 10
    assert Settings.model_fields["max_official_document_results_per_query"].default == 10
    assert Settings.model_fields["max_retrieval_total_duration_seconds"].default == 60.0


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


def test_follow_up_rounds_cannot_exceed_two() -> None:
    settings = _base_settings(MAX_FOLLOW_UP_ROUNDS=3)
    problems = settings.validate_for_runtime()
    assert any("MAX_FOLLOW_UP_ROUNDS cannot exceed 2" in p for p in problems)


def test_total_queries_must_be_gte_max_queries() -> None:
    settings = _base_settings(
        MAX_QUERIES_PER_HYPOTHESIS=6,
        MAX_TOTAL_QUERIES_PER_HYPOTHESIS=3,
    )
    problems = settings.validate_for_runtime()
    assert any("MAX_TOTAL_QUERIES_PER_HYPOTHESIS must be >=" in p for p in problems)


def test_acceptance_score_out_of_range_raises() -> None:
    with pytest.raises(ValidationError):
        _base_settings(MIN_RETRIEVAL_SCORE_FOR_ACCEPTANCE=1.5)
    with pytest.raises(ValidationError):
        _base_settings(MIN_RETRIEVAL_SCORE_FOR_ACCEPTANCE=-0.1)


def test_part2_zero_bound_raises() -> None:
    with pytest.raises(ValidationError):
        _base_settings(MAX_QUERY_EXPANSIONS_PER_HYPOTHESIS=0)
    with pytest.raises(ValidationError):
        _base_settings(MAX_RETRIEVAL_TOTAL_DURATION_SECONDS=0)
