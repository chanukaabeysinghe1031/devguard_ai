"""Detect conflicts between remediation constraints."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from app.ai.counterfactual_remediation.model_types import (
    ConstraintConflict,
    RemediationConstraintSet,
    RemediationCurrentState,
)
from app.domain.counterfactual_remediation.enums import ConstraintSeverity, ConstraintType

logger = logging.getLogger(__name__)


class RemediationConstraintConflictDetector:
    """Deterministic conflict detection (brief §23). No LLM resolution."""

    def detect(
        self,
        constraint_set: RemediationConstraintSet,
        *,
        current_state: RemediationCurrentState | None = None,
        proposed_values: dict[str, Any] | None = None,
        rollback_available: bool | None = None,
        artifact_available: bool | None = None,
    ) -> list[ConstraintConflict]:
        constraints = list(constraint_set.constraints)
        by_key = {c.constraint_key: c for c in constraints}
        conflicts: list[ConstraintConflict] = []
        proposed = proposed_values or {}

        def add(
            conflict_type: str,
            involved: list[str],
            explanation: str,
            *,
            must_stop: bool = True,
            missing: list[str] | None = None,
            severity: ConstraintSeverity = ConstraintSeverity.BLOCKING,
        ) -> None:
            conflicts.append(
                ConstraintConflict(
                    id=str(uuid4()),
                    involved_constraint_ids=sorted({i for i in involved if i}),
                    severity=severity,
                    explanation=f"[{conflict_type}] {explanation}",
                    must_stop_generation=must_stop,
                    missing_evidence=list(missing or []),
                    limitations=["conflict_not_auto_resolved_by_llm"],
                )
            )

        deny = [
            c
            for c in constraints
            if c.constraint_type == ConstraintType.EXPLICIT_DENY
            or (c.machine_readable_rule or {}).get("rule") == "explicit_deny_blocks_add_allow"
        ]
        if deny and proposed.get("add_allow_over_deny"):
            add(
                "explicit_deny_vs_add_allow",
                [c.id for c in deny],
                "Explicit deny cannot be satisfied by adding an allow",
            )

        region_constraints = [
            c
            for c in constraints
            if c.constraint_type == ConstraintType.REGION
            or (c.machine_readable_rule or {}).get("rule")
            == "preserve_provider_region_unless_hypothesis_region"
        ]
        proposed_region = proposed.get("region")
        if (
            proposed_region
            and region_constraints
            and any(
                not (c.machine_readable_rule or {}).get("region_change_allowed", False)
                for c in region_constraints
            )
        ):
            expected = [
                str(c.expected_value or (c.machine_readable_rule or {}).get("region"))
                for c in region_constraints
            ]
            if proposed_region not in expected:
                add(
                    "region_conflict",
                    [c.id for c in region_constraints],
                    "Proposed region conflicts with project/provider region constraints",
                )

        version_constraints = [
            c for c in constraints if c.constraint_type == ConstraintType.VERSION
        ]
        if len(version_constraints) >= 2 and any(
            (c.machine_readable_rule or {}).get("no_overlap") for c in version_constraints
        ):
            add(
                "version_no_overlap",
                [c.id for c in version_constraints],
                "Version constraints have no overlapping range",
                missing=["compatible_version_range"],
            )

        prevent = [
            c
            for c in constraints
            if c.constraint_type == ConstraintType.DELETION_PROTECTION
            or (c.machine_readable_rule or {}).get("rule") == "honor_prevent_destroy"
        ]
        if prevent and (
            proposed.get("destroy")
            or proposed.get("bypass_prevent_destroy")
            or proposed.get("force_replace")
        ):
            add(
                "prevent_destroy",
                [c.id for c in prevent],
                "Proposed change conflicts with prevent_destroy",
            )

        if by_key.get("ops.rollback_required") and rollback_available is False:
            add(
                "rollback_unavailable",
                [by_key["ops.rollback_required"].id],
                "Rollback requirement cannot be met",
                missing=["rollback_plan"],
            )

        if artifact_available is False or (
            current_state is not None
            and "source_fragment" in (current_state.missing_fields or [])
            and not current_state.structured_entities
        ):
            add(
                "missing_artifact",
                [],
                "Affected artifact unavailable for concrete remediation",
                missing=["affected_artifact"],
            )

        least = [c for c in constraints if c.constraint_type == ConstraintType.LEAST_PRIVILEGE]
        if least and (
            proposed.get("Action") == "*"
            or proposed.get("Resource") == "*"
            or proposed.get("wildcard")
        ):
            add(
                "least_privilege_vs_broad_permission",
                [c.id for c in least],
                "Least-privilege constraints conflict with broad-permission proposal",
            )

        logger.debug("constraint_conflicts_detected count=%s", len(conflicts))
        return conflicts
