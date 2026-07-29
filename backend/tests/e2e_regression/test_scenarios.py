"""Phase 4B E2E regression: classification + failure-state + technology signals."""

from __future__ import annotations

import uuid

import pytest

from app.ai.classification.hybrid_classifier import HybridClassifier
from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.rag.signals import DiagnosticSignalExtractor
from tests.e2e_regression.scenarios import SCENARIOS, Scenario


def _ctx(text: str) -> AnalysisContext:
    return AnalysisContext(
        analysis_run_id=uuid.uuid4(),
        incident_id=uuid.uuid4(),
        combined_text=text,
        options={"top_k_predictions": 3},
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_scenario_classification(scenario: Scenario) -> None:
    ctx = _ctx(scenario.log)
    candidates = HybridClassifier().classify(ctx)
    assert candidates, f"{scenario.id}: no candidates"
    primary = candidates[0].category_code
    assert primary == scenario.expected_primary_category, (
        f"{scenario.id}: expected {scenario.expected_primary_category}, got {primary}"
    )


@pytest.mark.parametrize(
    "scenario",
    [s for s in SCENARIOS if not s.expected_failure_state],
    ids=[s.id for s in SCENARIOS if not s.expected_failure_state],
)
def test_successful_pipelines_not_hard_failures(scenario: Scenario) -> None:
    ctx = _ctx(scenario.log)
    primary = HybridClassifier().classify(ctx)[0].category_code
    assert primary == "unknown_failure", (
        f"{scenario.id}: successful pipeline must not be labelled a hard failure"
    )


@pytest.mark.parametrize(
    "scenario",
    [s for s in SCENARIOS if s.expected_technology_signal],
    ids=[s.id for s in SCENARIOS if s.expected_technology_signal],
)
def test_technology_signals(scenario: Scenario) -> None:
    ctx = _ctx(scenario.log)
    HybridClassifier().classify(ctx)
    signals = DiagnosticSignalExtractor().extract(ctx)
    expected = scenario.expected_technology_signal
    assert expected is not None
    assert any(expected.lower() in t.lower() for t in signals.technologies), (
        f"{scenario.id}: expected technology {expected!r} in {signals.technologies}"
    )


def test_scenario_count_at_least_30() -> None:
    assert len(SCENARIOS) >= 30
