"""Structural validator for counterfactual candidates (brief §34)."""

from __future__ import annotations

import logging
from typing import Any

from app.ai.counterfactual_remediation.model_types import (
    CandidateStructuralValidationResult,
    CounterfactualRemediationCandidate,
    CounterfactualRemediationContext,
    RemediationConstraintSet,
    RemediationCurrentState,
    RemediationTemplate,
)
from app.ai.counterfactual_remediation.safety import contains_secret_material
from app.ai.counterfactual_remediation.versions import REMEDIATION_CANDIDATE_VALIDATOR_VERSION
from app.domain.counterfactual_remediation.enums import (
    CandidateStructuralValidationStatus,
    PreconditionStatus,
    RemediationArtifactType,
)

logger = logging.getLogger(__name__)


class CounterfactualCandidateStructuralValidator:
    """Structural checks only — not independent verification."""

    def __init__(
        self,
        *,
        max_patch_characters: int = 30_000,
        max_patch_files: int = 5,
        max_changed_lines: int = 200,
    ) -> None:
        self._max_patch_characters = max_patch_characters
        self._max_patch_files = max_patch_files
        self._max_changed_lines = max_changed_lines

    def validate(
        self,
        candidate: CounterfactualRemediationCandidate,
        *,
        context: CounterfactualRemediationContext | None = None,
        current_state: RemediationCurrentState | None = None,
        constraint_set: RemediationConstraintSet | None = None,
        template: RemediationTemplate | None = None,
        precondition_statuses: list[PreconditionStatus] | None = None,
    ) -> CandidateStructuralValidationResult:
        reasons: list[str] = []
        warnings: list[str] = []
        blocking: list[str] = []
        checks: dict[str, bool | str] = {}

        checks["hypothesis_present"] = bool(candidate.hypothesis_id)
        if not candidate.hypothesis_id:
            reasons.append("hypothesis_missing")
            blocking.append("hypothesis_missing")

        if context is not None:
            org_ok = not candidate.organization_id or candidate.organization_id == context.organization_id
            checks["organization_scope_match"] = org_ok
            if not org_ok:
                reasons.append("organization_scope_mismatch")
                blocking.append("org_scope")
            if context.project_id and candidate.project_id and candidate.project_id != context.project_id:
                reasons.append("project_scope_mismatch")
                blocking.append("project_scope")
                checks["project_scope_match"] = False
            else:
                checks["project_scope_match"] = True
            if candidate.analysis_id and candidate.analysis_id != context.analysis_id:
                reasons.append("analysis_scope_mismatch")
                blocking.append("analysis_scope")
            if candidate.hypothesis_id != context.hypothesis_id:
                reasons.append("hypothesis_mismatch")
                blocking.append("hypothesis_mismatch")

        if current_state is not None:
            checks["artifact_present"] = bool(
                current_state.artifact_id or current_state.structured_entities
            )
            if not checks["artifact_present"]:
                warnings.append("artifact_incomplete")
            if current_state.content_hash and candidate.changes:
                for change in candidate.changes:
                    if (
                        change.content_hash_before
                        and change.content_hash_before != current_state.content_hash
                    ):
                        reasons.append("original_fragment_hash_mismatch")
                        blocking.append("hash_mismatch")
                        break

        checks["within_file_bounds"] = len(candidate.target_paths) <= self._max_patch_files
        if not checks["within_file_bounds"]:
            reasons.append("max_patch_files_exceeded")
            blocking.append("bounds")

        total_chars = 0
        secret_found = False
        for change in candidate.changes:
            for frag in (change.original_fragment, change.proposed_fragment):
                if frag:
                    total_chars += len(frag)
                    if contains_secret_material(frag):
                        secret_found = True
        checks["no_secret_material"] = not secret_found
        checks["within_char_bounds"] = total_chars <= self._max_patch_characters
        if secret_found:
            reasons.append("secret_material_in_change")
            blocking.append("secret")
        if not checks["within_char_bounds"]:
            reasons.append("max_patch_characters_exceeded")
            blocking.append("bounds")

        snapshot = candidate.counterfactual_state_snapshot
        proposed: Any = {}
        if isinstance(snapshot, dict):
            proposed = snapshot.get("proposed_permissions") or snapshot.get("proposed_values") or {}
        elif snapshot is not None:
            proposed = getattr(snapshot, "proposed_permissions", None) or getattr(
                snapshot, "proposed_values", None
            ) or {}
        wildcard = _has_wildcard(proposed) or _has_wildcard(candidate.summary) or _has_wildcard(
            candidate.title
        )
        checks["no_wildcard_broadening"] = not wildcard
        if wildcard:
            reasons.append("wildcard_broadening_rejected")
            blocking.append("wildcard")

        artifact_type = candidate.artifact_type
        artifact_value = (
            artifact_type.value if hasattr(artifact_type, "value") else str(artifact_type or "")
        )
        if artifact_value == RemediationArtifactType.SOURCE_CODE.value and not candidate.changes:
            warnings.append("source_code_without_changes")
            if not (current_state and current_state.source_fragment):
                reasons.append("prohibited_or_unsupported_source_rewrite")
                blocking.append("prohibited_artifact")

        if template is not None and candidate.template_id and template.template_id != candidate.template_id:
            reasons.append("template_mismatch")
            blocking.append("template")
        checks["template_ok"] = "template" not in blocking

        if precondition_statuses and any(
            s in {PreconditionStatus.NOT_SATISFIED, PreconditionStatus.UNKNOWN}
            for s in precondition_statuses
        ):
            warnings.append("required_preconditions_unsatisfied")

        if constraint_set is not None:
            unsatisfied_keys = {
                c.constraint_key
                for c in (candidate.unsatisfied_constraints or [])
                if getattr(c, "constraint_key", None)
            }
            for constraint in constraint_set.blocking_constraints:
                if constraint.constraint_key in unsatisfied_keys:
                    # Presence of unsatisfied blocking list is expected for skeletons.
                    warnings.append(f"blocking_listed:{constraint.constraint_key}")

        if not candidate.expected_failure_condition:
            warnings.append("expected_failure_condition_missing")
        if not candidate.verification_requirements:
            warnings.append("verification_requirements_missing")
        if candidate.rollback_plan is None:
            warnings.append("rollback_plan_missing")

        status = self._status(reasons=reasons, warnings=warnings, blocking=blocking)
        result = CandidateStructuralValidationResult(
            status=status,
            candidate_id=candidate.id,
            hypothesis_id=candidate.hypothesis_id,
            reasons=reasons,
            warnings=warnings,
            blocking_issues=blocking,
            checks=checks,
            validator_version=REMEDIATION_CANDIDATE_VALIDATOR_VERSION,
        )
        logger.debug(
            "candidate_structurally_validated id=%s status=%s",
            candidate.id,
            status.value,
        )
        return result

    def _status(
        self,
        *,
        reasons: list[str],
        warnings: list[str],
        blocking: list[str],
    ) -> CandidateStructuralValidationStatus:
        if "secret" in blocking or "wildcard" in blocking:
            return CandidateStructuralValidationStatus.UNSAFE
        if "org_scope" in blocking or "project_scope" in blocking:
            return CandidateStructuralValidationStatus.BLOCKED
        if reasons or blocking:
            return CandidateStructuralValidationStatus.INVALID
        if any("incomplete" in w or "missing" in w for w in warnings):
            return CandidateStructuralValidationStatus.INCOMPLETE
        if warnings:
            return CandidateStructuralValidationStatus.VALID_WITH_WARNINGS
        return CandidateStructuralValidationStatus.VALID_STRUCTURE


def _has_wildcard(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return '"*"' in value or value.strip() == "*" or "Action: *" in value or "Resource: *" in value
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in {"action", "resource"} and (
                item == "*" or item == ["*"] or (isinstance(item, list) and "*" in item)
            ):
                return True
            if _has_wildcard(item):
                return True
    if isinstance(value, list):
        return any(_has_wildcard(v) for v in value)
    return False
