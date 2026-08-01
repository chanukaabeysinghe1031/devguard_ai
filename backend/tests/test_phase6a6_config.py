"""Phase 6A.6 Part 1 — configuration flag and bound tests."""

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


def test_phase6a6_flags_default_off() -> None:
    assert Settings.model_fields["counterfactual_remediation_enabled"].default is False
    assert Settings.model_fields["counterfactual_constraint_extraction_enabled"].default is False
    assert Settings.model_fields["minimal_change_planning_enabled"].default is False
    assert Settings.model_fields["counterfactual_template_registry_enabled"].default is False
    assert Settings.model_fields["counterfactual_persistence_enabled"].default is False
    assert Settings.model_fields["counterfactual_debug_api_enabled"].default is False
    assert Settings.model_fields["rule_remediation_generation_enabled"].default is False
    assert Settings.model_fields["llm_remediation_generation_enabled"].default is False
    assert Settings.model_fields["remediation_risk_analysis_enabled"].default is False
    assert Settings.model_fields["remediation_side_effect_analysis_enabled"].default is False
    assert Settings.model_fields["remediation_ranking_enabled"].default is False


def test_phase6a6_bound_defaults() -> None:
    assert Settings.model_fields["max_hypotheses_for_remediation"].default == 3
    assert Settings.model_fields["max_remediation_candidates_per_hypothesis"].default == 3
    assert Settings.model_fields["max_total_remediation_candidates"].default == 8
    assert Settings.model_fields["max_constraints_per_hypothesis"].default == 100
    assert Settings.model_fields["max_counterfactual_context_chars"].default == 80_000
    assert Settings.model_fields["max_patch_characters"].default == 30_000
    assert Settings.model_fields["max_patch_files_per_candidate"].default == 5
    assert Settings.model_fields["max_changed_lines_per_candidate"].default == 200
    assert Settings.model_fields["counterfactual_stage_timeout_seconds"].default == 60.0


def test_phase6a6_zero_bounds_raise() -> None:
    with pytest.raises(ValidationError):
        _base_settings(MAX_TOTAL_REMEDIATION_CANDIDATES=0)
    with pytest.raises(ValidationError):
        _base_settings(MAX_CONSTRAINTS_PER_HYPOTHESIS=0)
    with pytest.raises(ValidationError):
        _base_settings(MAX_COUNTERFACTUAL_GRAPH_NODES=0)


def test_phase6a6_total_lt_per_hypothesis_runtime_problem() -> None:
    settings = _base_settings(
        MAX_REMEDIATION_CANDIDATES_PER_HYPOTHESIS=4,
        MAX_TOTAL_REMEDIATION_CANDIDATES=1,
    )
    problems = settings.validate_for_runtime()
    assert any("MAX_TOTAL_REMEDIATION_CANDIDATES must be >=" in p for p in problems)


def test_phase6a6_constructed_settings_respect_defaults() -> None:
    settings = _base_settings()
    assert settings.counterfactual_remediation_enabled is False
    assert settings.counterfactual_debug_api_enabled is False
    assert settings.max_hypotheses_for_remediation == 3
