"""Previous-success property-level restoration generator."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.ai.counterfactual_remediation.generation._helpers import (
    as_dict,
    first_str,
    get_current_values,
    get_source_fragment,
    safe_replace_once,
    sha256_text,
)
from app.ai.counterfactual_remediation.safety import contains_secret_material
from app.domain.counterfactual_remediation.enums import (
    CounterfactualCandidateStatus,
    CounterfactualChangeType,
    ExpectedFailureConditionStatus,
)
from app.domain.counterfactual_remediation.generation_enums import (
    RemediationGenerationStatus,
    RemediationGeneratorType,
)
from app.domain.counterfactual_remediation.generation_models import (
    RemediationGenerationContext,
    RemediationGenerationResult,
)
from app.domain.counterfactual_remediation.generation_versions import (
    RULE_REMEDIATION_GENERATOR_VERSION,
)
from app.domain.counterfactual_remediation.models import (
    CounterfactualChange,
    CounterfactualRemediationCandidate,
    RemediationCounterfactualState,
)

logger = logging.getLogger(__name__)


class PreviousSuccessRemediationGenerator:
    """Restore a single known property from previous successful version only."""

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self.version = RULE_REMEDIATION_GENERATOR_VERSION

    def generate(self, context: RemediationGenerationContext) -> RemediationGenerationResult:
        started = datetime.now(UTC)
        if not self._enabled:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.PREVIOUS_SUCCESS_RESTORATION,
                status=RemediationGenerationStatus.DISABLED,
                duration_ms=0,
            )

        diffs = list(context.previous_success_differences)
        previous = context.previous_successful_version
        if not previous and not diffs:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.PREVIOUS_SUCCESS_RESTORATION,
                status=RemediationGenerationStatus.NO_APPLICABLE_TEMPLATE,
                warnings=["no_previous_success_version"],
                duration_ms=self._ms(started),
            )

        state = as_dict(context.current_state)
        values = get_current_values(state)
        fragment = get_source_fragment(state, context.source_fragment)
        if not fragment:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.PREVIOUS_SUCCESS_RESTORATION,
                status=RemediationGenerationStatus.PARTIAL,
                warnings=["missing_source_fragment"],
                duration_ms=self._ms(started),
            )

        # Prefer explicit property-level diff entries.
        prop = None
        current_value = None
        previous_value = None
        commit = None
        for item in diffs:
            data = as_dict(item)
            prop = first_str(data.get("property"), data.get("target_property"))
            current_value = first_str(data.get("current_value"), data.get("after"))
            previous_value = first_str(data.get("previous_value"), data.get("before"))
            commit = first_str(data.get("commit_sha"), data.get("commit"), previous)
            if prop and current_value and previous_value and current_value != previous_value:
                break
            prop = current_value = previous_value = None

        if not prop:
            prop = first_str(values.get("changed_property"))
            current_value = first_str(values.get("current_value"), values.get(prop or ""))
            previous_value = first_str(
                values.get("previous_value"),
                values.get("previous_successful_value"),
            )
            commit = first_str(state.get("commit_sha"), previous)

        if not prop or not current_value or not previous_value:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.PREVIOUS_SUCCESS_RESTORATION,
                status=RemediationGenerationStatus.NO_APPLICABLE_TEMPLATE,
                warnings=["property_level_diff_unavailable"],
                duration_ms=self._ms(started),
            )
        if contains_secret_material(str(previous_value)):
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.PREVIOUS_SUCCESS_RESTORATION,
                status=RemediationGenerationStatus.BLOCKED,
                errors=["previous_value_looks_like_secret"],
                duration_ms=self._ms(started),
            )

        # Do not restore entire file — property substring only when present.
        if str(current_value) not in fragment:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.PREVIOUS_SUCCESS_RESTORATION,
                status=RemediationGenerationStatus.PARTIAL,
                warnings=["current_property_value_not_in_fragment"],
                duration_ms=self._ms(started),
            )
        proposed = safe_replace_once(fragment, str(current_value), str(previous_value))
        if proposed is None:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.PREVIOUS_SUCCESS_RESTORATION,
                status=RemediationGenerationStatus.FAILED,
                errors=["property_replace_failed"],
                duration_ms=self._ms(started),
            )

        candidate_id = str(uuid4())
        artifact_id = first_str(state.get("artifact_id"))
        change = CounterfactualChange(
            id=str(uuid4()),
            candidate_id=candidate_id,
            artifact_id=artifact_id,
            artifact_type=state.get("artifact_type"),
            source_path=first_str(state.get("source_path")),
            change_type=CounterfactualChangeType.UPDATE_VALUE,
            target_property=prop,
            original_fragment=fragment,
            proposed_fragment=proposed,
            expected_effect=f"EXPECTED: restore previous successful value for {prop}",
            rationale="Property-level previous-success restoration",
            content_hash_before=sha256_text(fragment),
            content_hash_after_candidate=sha256_text(proposed),
            assumptions=[
                f"previous_value={previous_value}",
                f"current_value={current_value}",
                f"commit_provenance={commit or 'unknown'}",
            ],
            limitations=["candidates_are_not_verified", "not_full_file_restore"],
        )
        candidate = CounterfactualRemediationCandidate(
            id=candidate_id,
            remediation_run_id=context.remediation_run_id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            incident_id=context.incident_id,
            analysis_id=context.analysis_id,
            hypothesis_id=context.hypothesis_id,
            candidate_key=f"{context.hypothesis_id}:previous_success:{prop}",
            title=f"Restore previous success: {prop}",
            summary=(
                f"Restore property '{prop}' from previous successful version. "
                "Not verified. Not applied."
            ),
            artifact_type=state.get("artifact_type"),
            affected_artifact_ids=[a for a in [artifact_id] if a],
            primary_artifact_id=artifact_id,
            target_paths=[p for p in [state.get("source_path")] if p],
            change_types=[CounterfactualChangeType.UPDATE_VALUE],
            changes=[change],
            current_state_snapshot=context.current_state,
            counterfactual_state_snapshot=RemediationCounterfactualState(
                candidate_id=candidate_id,
                artifact_id=artifact_id,
                proposed_values={prop: previous_value},
                expected_failure_condition_status=ExpectedFailureConditionStatus.EXPECTED_REMOVED,
                assumptions=["previous_success_property_restore"],
                unknown_effects=["differences_that_remain_unknown"],
            ),
            expected_effects=[f"EXPECTED: restore {prop}"],
            assumptions=[
                "previous_success_restoration",
                f"changed_property={prop}",
                f"commit_provenance={commit or 'unknown'}",
            ],
            limitations=["candidates_are_not_verified", "candidates_are_not_applied"],
            generator_type=RemediationGeneratorType.PREVIOUS_SUCCESS_RESTORATION.value,
            generator_name="previous_success",
            generator_version=self.version,
            status=CounterfactualCandidateStatus.STRUCTURED,
        )
        logger.debug("previous_success_candidate property=%s", prop)
        return RemediationGenerationResult(
            generator=RemediationGeneratorType.PREVIOUS_SUCCESS_RESTORATION,
            status=RemediationGenerationStatus.COMPLETE,
            candidates=[candidate],
            duration_ms=self._ms(started),
            generator_version=self.version,
        )

    @staticmethod
    def _ms(started: datetime) -> int:
        return int((datetime.now(UTC) - started).total_seconds() * 1000)
