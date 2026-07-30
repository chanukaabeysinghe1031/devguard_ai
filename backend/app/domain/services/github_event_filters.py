"""Deterministic ingestion filters for GitHub workflow run events (ADR-005).

Pure functions: no database, no I/O. A connection either accepts a workflow run
for ingestion or ignores it with a stable machine-readable reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any

DEFAULT_FAILURE_CONCLUSIONS: tuple[str, ...] = (
    "failure",
    "timed_out",
    "action_required",
    "startup_failure",
)

DEFAULT_SEVERITY_RULES: dict[str, str] = {
    "production": "critical",
    "staging": "high",
    "default": "medium",
}


@dataclass(frozen=True, slots=True)
class FilterDecision:
    should_ingest: bool
    reason: str

    @classmethod
    def accept(cls) -> FilterDecision:
        return cls(should_ingest=True, reason="accepted")

    @classmethod
    def ignore(cls, reason: str) -> FilterDecision:
        return cls(should_ingest=False, reason=reason)


def normalise_conclusions(configured: Any) -> tuple[str, ...]:
    if isinstance(configured, list) and configured:
        values = tuple(str(item).strip().lower() for item in configured if str(item).strip())
        if values:
            return values
    return DEFAULT_FAILURE_CONCLUSIONS


def is_failure_conclusion(conclusion: str | None, configured: Any = None) -> bool:
    """True when the run conclusion is in the connection's failure allow-list."""
    if not conclusion:
        return False
    return conclusion.strip().lower() in normalise_conclusions(configured)


def matches_workflow_filter(workflow_name: str | None, filters: Any = None) -> bool:
    """Workflow name allow-list. ``{"mode": "all"}`` (or unset) matches everything."""
    if not isinstance(filters, dict):
        return True
    mode = str(filters.get("mode") or "all").strip().lower()
    if mode != "selected":
        return True
    names = filters.get("names")
    if not isinstance(names, list) or not names:
        # "selected" with no selection would silently drop every run.
        return True
    if not workflow_name:
        return False
    target = workflow_name.strip().lower()
    return any(str(name).strip().lower() == target for name in names)


def matches_branch_filter(
    branch: str | None,
    *,
    default_branch: str | None = None,
    filters: Any = None,
) -> bool:
    """Branch allow-list supporting ``all``, ``default``, and glob ``patterns``."""
    if not isinstance(filters, dict):
        return True
    mode = str(filters.get("mode") or "all").strip().lower()
    if mode == "all":
        return True
    if not branch:
        return False
    if mode == "default":
        return bool(default_branch) and branch == default_branch
    if mode == "patterns":
        patterns = filters.get("patterns")
        if not isinstance(patterns, list) or not patterns:
            return True
        return any(fnmatch(branch, str(pattern)) for pattern in patterns)
    return True


def evaluate_workflow_run(
    *,
    conclusion: str | None,
    workflow_name: str | None,
    branch: str | None,
    default_branch: str | None = None,
    failure_conclusions: Any = None,
    workflow_filters: Any = None,
    branch_filters: Any = None,
) -> FilterDecision:
    """Apply conclusion, workflow, and branch filters in that order."""
    if not is_failure_conclusion(conclusion, failure_conclusions):
        return FilterDecision.ignore("conclusion_not_failure")
    if not matches_workflow_filter(workflow_name, workflow_filters):
        return FilterDecision.ignore("workflow_filtered")
    if not matches_branch_filter(branch, default_branch=default_branch, filters=branch_filters):
        return FilterDecision.ignore("branch_filtered")
    return FilterDecision.accept()


def resolve_environment(branch: str | None, mapping: Any = None) -> str | None:
    """Map a branch to a deployment environment using exact then glob matches."""
    if not isinstance(mapping, dict) or not mapping:
        return None
    if branch:
        exact = mapping.get(branch)
        if isinstance(exact, str) and exact.strip():
            return exact.strip()
        for pattern, environment in mapping.items():
            if pattern == "default" or not isinstance(environment, str):
                continue
            if fnmatch(branch, str(pattern)):
                return environment.strip()
    fallback = mapping.get("default")
    return fallback.strip() if isinstance(fallback, str) and fallback.strip() else None


def resolve_severity(environment: str | None, rules: Any = None) -> str:
    """Map an environment to an incident severity using the connection rules."""
    effective = rules if isinstance(rules, dict) and rules else DEFAULT_SEVERITY_RULES
    if environment:
        candidate = effective.get(environment)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().lower()
    fallback = effective.get("default")
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip().lower()
    return DEFAULT_SEVERITY_RULES["default"]
