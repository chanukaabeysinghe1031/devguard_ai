"""Phase 6A.6 Part 2 — generation config bound tests."""

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


def test_part2_flags_default_off() -> None:
    assert Settings.model_fields["rule_remediation_generation_enabled"].default is False
    assert Settings.model_fields["llm_remediation_generation_enabled"].default is False
    assert Settings.model_fields["remediation_deduplication_enabled"].default is False
    assert Settings.model_fields["remediation_diversity_enabled"].default is False
    assert Settings.model_fields["remediation_patch_rendering_enabled"].default is False
    assert Settings.model_fields["remediation_rollback_generation_enabled"].default is False
    assert Settings.model_fields["remediation_reference_validation_enabled"].default is False
    assert Settings.model_fields["remediation_constraint_validation_enabled"].default is False
    assert Settings.model_fields["remediation_risk_analysis_enabled"].default is False
    assert Settings.model_fields["remediation_ranking_enabled"].default is False


def test_part2_bound_defaults() -> None:
    assert Settings.model_fields["max_rule_candidates_per_hypothesis"].default == 3
    assert Settings.model_fields["max_llm_candidates_per_hypothesis"].default == 2
    assert Settings.model_fields["max_final_candidates_per_hypothesis"].default == 3
    assert Settings.model_fields["max_total_final_candidates"].default == 8
    assert Settings.model_fields["max_candidate_files"].default == 5
    assert Settings.model_fields["max_candidate_changed_lines"].default == 200
    assert Settings.model_fields["remediation_high_risk_threshold"].default == 0.70
    assert Settings.model_fields["remediation_reject_risk_threshold"].default == 0.90


def test_part2_zero_bounds_raise() -> None:
    with pytest.raises(ValidationError):
        _base_settings(MAX_TOTAL_FINAL_CANDIDATES=0)
    with pytest.raises(ValidationError):
        _base_settings(MAX_RULE_CANDIDATES_PER_HYPOTHESIS=0)


def test_part2_total_lt_final_runtime_problem() -> None:
    settings = _base_settings(
        MAX_FINAL_CANDIDATES_PER_HYPOTHESIS=4,
        MAX_TOTAL_FINAL_CANDIDATES=1,
    )
    problems = settings.validate_for_runtime()
    assert any("MAX_TOTAL_FINAL_CANDIDATES must be >=" in p for p in problems)


def test_part2_reject_lt_high_risk_runtime_problem() -> None:
    settings = _base_settings(
        REMEDIATION_HIGH_RISK_THRESHOLD=0.9,
        REMEDIATION_REJECT_RISK_THRESHOLD=0.5,
    )
    problems = settings.validate_for_runtime()
    assert any("REMEDIATION_REJECT_RISK_THRESHOLD must be >=" in p for p in problems)


def test_part2_constructed_settings_respect_defaults() -> None:
    settings = _base_settings()
    assert settings.rule_remediation_generation_enabled is False
    assert settings.max_rule_candidates_per_hypothesis == 3
    assert settings.remediation_tie_epsilon == 0.02
