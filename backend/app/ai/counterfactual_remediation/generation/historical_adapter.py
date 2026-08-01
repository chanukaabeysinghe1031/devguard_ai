"""Historical remediation pattern adapter (no org-specific value copy)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.ai.counterfactual_remediation.generation._helpers import (
    as_dict,
    first_str,
    get_source_fragment,
    safe_replace_once,
    sha256_text,
    strip_org_specific_identifiers,
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


class HistoricalRemediationAdapter:
    """Adapt trusted historical patterns; strip org-specific IDs/secrets/ARNs."""

    def __init__(self, *, enabled: bool = True, max_candidates: int = 1) -> None:
        self._enabled = enabled
        self._max = max(1, max_candidates)
        self.version = RULE_REMEDIATION_GENERATOR_VERSION

    def generate(self, context: RemediationGenerationContext) -> RemediationGenerationResult:
        started = datetime.now(UTC)
        if not self._enabled:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.HISTORICAL_ADAPTATION,
                status=RemediationGenerationStatus.DISABLED,
                duration_ms=0,
            )

        eligible = [
            as_dict(item)
            for item in context.historical_candidates
            if self._is_eligible(as_dict(item), context)
        ]
        if not eligible:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.HISTORICAL_ADAPTATION,
                status=RemediationGenerationStatus.NO_APPLICABLE_TEMPLATE,
                warnings=["no_eligible_historical_candidates"],
                duration_ms=self._ms(started),
            )

        state = as_dict(context.current_state)
        fragment = get_source_fragment(state, context.source_fragment)
        if not fragment:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.HISTORICAL_ADAPTATION,
                status=RemediationGenerationStatus.PARTIAL,
                warnings=["missing_source_fragment"],
                duration_ms=self._ms(started),
            )

        candidates: list[CounterfactualRemediationCandidate] = []
        warnings: list[str] = []
        for item in eligible[: self._max]:
            pattern = as_dict(item.get("remediation_pattern") or item.get("pattern") or item)
            current_token = first_str(
                pattern.get("current_token"),
                pattern.get("from_value"),
                pattern.get("match"),
            )
            adapted_token = first_str(
                pattern.get("adapted_token"),
                pattern.get("to_value"),
                pattern.get("replacement"),
            )
            if not current_token or not adapted_token:
                warnings.append("historical_pattern_incomplete")
                continue
            adapted_token = strip_org_specific_identifiers(adapted_token)
            current_token = strip_org_specific_identifiers(current_token)
            if contains_secret_material(adapted_token):
                warnings.append("historical_secret_blocked")
                continue
            # Map pattern onto current fragment only when current token exists locally.
            if current_token not in fragment:
                warnings.append("historical_token_not_in_current_fragment")
                continue
            proposed = safe_replace_once(fragment, current_token, adapted_token)
            if proposed is None:
                continue
            candidates.append(
                self._build_candidate(context, state, fragment, proposed, item, pattern)
            )

        if not candidates:
            status = RemediationGenerationStatus.NO_APPLICABLE_TEMPLATE
        elif warnings:
            status = RemediationGenerationStatus.PARTIAL
        else:
            status = RemediationGenerationStatus.COMPLETE
        return RemediationGenerationResult(
            generator=RemediationGeneratorType.HISTORICAL_ADAPTATION,
            status=status,
            candidates=candidates,
            warnings=warnings,
            duration_ms=self._ms(started),
            generator_version=self.version,
        )

    def _is_eligible(self, item: dict[str, Any], context: RemediationGenerationContext) -> bool:
        status = str(item.get("resolution_status") or item.get("status") or "").upper()
        if status and status not in {"RESOLVED", "SUCCESS", "SUCCESSFUL", "CLOSED"}:
            return False
        artifact_type = str(item.get("artifact_type") or "").upper()
        current_type = str(as_dict(context.current_state).get("artifact_type") or "").upper()
        if artifact_type and current_type and artifact_type != current_type:
            return False
        mechanism = str(item.get("failure_mechanism") or item.get("category") or "").lower()
        if mechanism and context.category and mechanism not in context.category.lower():
            # Soft: allow if causal claim mentions mechanism.
            if mechanism not in (context.causal_claim or "").lower():
                return False
        if item.get("trusted") is False:
            return False
        return True

    def _build_candidate(
        self,
        context: RemediationGenerationContext,
        state: dict[str, Any],
        original: str,
        proposed: str,
        historical: dict[str, Any],
        pattern: dict[str, Any],
    ) -> CounterfactualRemediationCandidate:
        candidate_id = str(uuid4())
        artifact_id = first_str(state.get("artifact_id"))
        change_type_raw = first_str(pattern.get("change_type"), "UPDATE_REFERENCE") or "UPDATE_REFERENCE"
        try:
            change_type = CounterfactualChangeType(change_type_raw)
        except ValueError:
            change_type = CounterfactualChangeType.UPDATE_REFERENCE
        change = CounterfactualChange(
            id=str(uuid4()),
            candidate_id=candidate_id,
            artifact_id=artifact_id,
            artifact_type=state.get("artifact_type"),
            source_path=first_str(state.get("source_path")),
            change_type=change_type,
            target_property=first_str(pattern.get("target_property"), "adapted_pattern"),
            original_fragment=original,
            proposed_fragment=proposed,
            expected_effect="EXPECTED: adapted historical remediation pattern applied",
            rationale="Historical pattern adaptation with org-specific values stripped",
            content_hash_before=sha256_text(original),
            content_hash_after_candidate=sha256_text(proposed),
            limitations=["candidates_are_not_verified", "historical_adaptation_not_copy"],
        )
        return CounterfactualRemediationCandidate(
            id=candidate_id,
            remediation_run_id=context.remediation_run_id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            incident_id=context.incident_id,
            analysis_id=context.analysis_id,
            hypothesis_id=context.hypothesis_id,
            candidate_key=f"{context.hypothesis_id}:historical:{historical.get('id') or 'pattern'}",
            title="Historical adaptation candidate",
            summary=(
                "Adapted remediation pattern from trusted historical incident. "
                "Org-specific identifiers stripped. Not verified."
            ),
            artifact_type=state.get("artifact_type"),
            affected_artifact_ids=[a for a in [artifact_id] if a],
            primary_artifact_id=artifact_id,
            target_paths=[p for p in [state.get("source_path")] if p],
            change_types=[change_type],
            changes=[change],
            current_state_snapshot=context.current_state,
            counterfactual_state_snapshot=RemediationCounterfactualState(
                candidate_id=candidate_id,
                artifact_id=artifact_id,
                expected_failure_condition_status=ExpectedFailureConditionStatus.EXPECTED_REMOVED,
                assumptions=["historical_pattern_adapted"],
            ),
            expected_effects=["EXPECTED: adapted historical pattern"],
            assumptions=[
                "historical_adaptation",
                f"source_incident={historical.get('incident_id') or historical.get('id')}",
            ],
            limitations=[
                "candidates_are_not_verified",
                "not_literal_cross_org_copy",
            ],
            generator_type=RemediationGeneratorType.HISTORICAL_ADAPTATION.value,
            generator_name="historical_adapter",
            generator_version=self.version,
            status=CounterfactualCandidateStatus.STRUCTURED,
        )

    @staticmethod
    def _ms(started: datetime) -> int:
        return int((datetime.now(UTC) - started).total_seconds() * 1000)
