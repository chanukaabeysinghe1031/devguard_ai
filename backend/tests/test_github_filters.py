"""Deterministic ingestion filters for GitHub workflow runs (Phase 5B)."""

from __future__ import annotations

import pytest

from app.domain.services.github_event_filters import (
    DEFAULT_FAILURE_CONCLUSIONS,
    evaluate_workflow_run,
    is_failure_conclusion,
    matches_branch_filter,
    matches_workflow_filter,
    resolve_environment,
    resolve_severity,
)


@pytest.mark.parametrize("conclusion", DEFAULT_FAILURE_CONCLUSIONS)
def test_default_failure_conclusions_accepted(conclusion: str) -> None:
    assert is_failure_conclusion(conclusion) is True


@pytest.mark.parametrize("conclusion", ["success", "skipped", "cancelled", "neutral", None, ""])
def test_non_failure_conclusions_rejected(conclusion: str | None) -> None:
    assert is_failure_conclusion(conclusion) is False


def test_configured_conclusion_allow_list_overrides_defaults() -> None:
    allowed = ["timed_out"]
    assert is_failure_conclusion("timed_out", allowed) is True
    assert is_failure_conclusion("failure", allowed) is False


def test_conclusion_matching_is_case_insensitive() -> None:
    assert is_failure_conclusion("FAILURE") is True


def test_workflow_filter_all_mode_matches_everything() -> None:
    assert matches_workflow_filter("CI", {"mode": "all"}) is True
    assert matches_workflow_filter(None, None) is True


def test_workflow_filter_selected_mode() -> None:
    filters = {"mode": "selected", "names": ["CI", "Deploy"]}
    assert matches_workflow_filter("CI", filters) is True
    assert matches_workflow_filter("deploy", filters) is True
    assert matches_workflow_filter("Nightly", filters) is False
    assert matches_workflow_filter(None, filters) is False


def test_workflow_filter_selected_with_empty_selection_does_not_drop_everything() -> None:
    assert matches_workflow_filter("CI", {"mode": "selected", "names": []}) is True


def test_branch_filter_all_mode() -> None:
    assert matches_branch_filter("feature/x", filters={"mode": "all"}) is True
    assert matches_branch_filter("feature/x", filters=None) is True


def test_branch_filter_default_mode() -> None:
    filters = {"mode": "default"}
    assert matches_branch_filter("main", default_branch="main", filters=filters) is True
    assert matches_branch_filter("feature/x", default_branch="main", filters=filters) is False
    assert matches_branch_filter("main", default_branch=None, filters=filters) is False


def test_branch_filter_pattern_mode_uses_globs() -> None:
    filters = {"mode": "patterns", "patterns": ["main", "release/*"]}
    assert matches_branch_filter("main", filters=filters) is True
    assert matches_branch_filter("release/1.2", filters=filters) is True
    assert matches_branch_filter("feature/login", filters=filters) is False


def test_evaluate_accepts_failure_on_allowed_workflow_and_branch() -> None:
    decision = evaluate_workflow_run(
        conclusion="failure",
        workflow_name="CI",
        branch="main",
        default_branch="main",
        workflow_filters={"mode": "selected", "names": ["CI"]},
        branch_filters={"mode": "default"},
    )
    assert decision.should_ingest is True
    assert decision.reason == "accepted"


@pytest.mark.parametrize(
    ("conclusion", "workflow", "branch", "expected_reason"),
    [
        ("success", "CI", "main", "conclusion_not_failure"),
        ("failure", "Nightly", "main", "workflow_filtered"),
        ("failure", "CI", "feature/x", "branch_filtered"),
    ],
)
def test_evaluate_ignore_reasons(
    conclusion: str,
    workflow: str,
    branch: str,
    expected_reason: str,
) -> None:
    decision = evaluate_workflow_run(
        conclusion=conclusion,
        workflow_name=workflow,
        branch=branch,
        default_branch="main",
        workflow_filters={"mode": "selected", "names": ["CI"]},
        branch_filters={"mode": "default"},
    )
    assert decision.should_ingest is False
    assert decision.reason == expected_reason


def test_resolve_environment_exact_then_glob_then_default() -> None:
    mapping = {"main": "production", "release/*": "staging", "default": "development"}
    assert resolve_environment("main", mapping) == "production"
    assert resolve_environment("release/2.0", mapping) == "staging"
    assert resolve_environment("feature/x", mapping) == "development"
    assert resolve_environment("main", None) is None


def test_resolve_severity_uses_rules_then_default() -> None:
    rules = {"production": "critical", "staging": "high", "default": "medium"}
    assert resolve_severity("production", rules) == "critical"
    assert resolve_severity("staging", rules) == "high"
    assert resolve_severity("sandbox", rules) == "medium"
    assert resolve_severity(None, rules) == "medium"
    assert resolve_severity("production", None) == "critical"
