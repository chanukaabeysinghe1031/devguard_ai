"""Centralized incident status transition rules."""

from __future__ import annotations

from app.domain.enums import IncidentStatus
from app.domain.exceptions.business import InvalidTransitionError

# Allowed manual transitions (API POST /incidents/{id}/status).
_ALLOWED_TRANSITIONS: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    IncidentStatus.DETECTED: frozenset(
        {
            IncidentStatus.ANALYSING,
            IncidentStatus.OPEN,
            IncidentStatus.IGNORED,
            IncidentStatus.FALSE_POSITIVE,
        }
    ),
    IncidentStatus.ANALYSING: frozenset(
        {
            IncidentStatus.OPEN,
            IncidentStatus.ANALYSIS_FAILED,
        }
    ),
    IncidentStatus.ANALYSIS_FAILED: frozenset(
        {
            IncidentStatus.ANALYSING,
            IncidentStatus.OPEN,
            IncidentStatus.IGNORED,
        }
    ),
    IncidentStatus.OPEN: frozenset(
        {
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.ANALYSING,
            IncidentStatus.IGNORED,
            IncidentStatus.FALSE_POSITIVE,
            IncidentStatus.RESOLVED,
        }
    ),
    IncidentStatus.IN_PROGRESS: frozenset(
        {
            IncidentStatus.OPEN,
            IncidentStatus.RESOLVED,
            IncidentStatus.ANALYSING,
        }
    ),
    IncidentStatus.RESOLVED: frozenset({IncidentStatus.CLOSED, IncidentStatus.REOPENED}),
    IncidentStatus.CLOSED: frozenset({IncidentStatus.REOPENED}),
    IncidentStatus.REOPENED: frozenset(
        {
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.OPEN,
            IncidentStatus.ANALYSING,
        }
    ),
    IncidentStatus.IGNORED: frozenset({IncidentStatus.OPEN, IncidentStatus.REOPENED}),
    IncidentStatus.FALSE_POSITIVE: frozenset({IncidentStatus.OPEN, IncidentStatus.REOPENED}),
}

_TERMINAL_FOR_EDIT = frozenset({IncidentStatus.CLOSED, IncidentStatus.RESOLVED})


def validate_status_transition(
    current: IncidentStatus,
    target: IncidentStatus,
) -> None:
    """Raise InvalidTransitionError when the transition is not permitted."""
    if current == target:
        return
    allowed = _ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition incident from '{current.value}' to '{target.value}'."
        )


def assert_incident_mutable(status: IncidentStatus) -> None:
    """Closed or resolved incidents require reopen before field edits."""
    if status in _TERMINAL_FOR_EDIT:
        raise InvalidTransitionError(
            "Incident must be reopened before it can be modified."
        )


def format_incident_number(incident_number: int) -> str:
    return f"INC-{incident_number:06d}"
