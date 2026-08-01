"""Diversity selection across remediation mechanism buckets."""

from __future__ import annotations

import logging

from app.domain.counterfactual_remediation.enums import CounterfactualChangeType
from app.domain.counterfactual_remediation.generation_versions import (
    REMEDIATION_DIVERSITY_VERSION,
)
from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate

logger = logging.getLogger(__name__)

_BUCKET_BY_CHANGE: dict[str, str] = {
    CounterfactualChangeType.UPDATE_PERMISSION.value: "permission_correction",
    CounterfactualChangeType.UPDATE_CONDITION.value: "resource_policy_correction",
    CounterfactualChangeType.UPDATE_REFERENCE.value: "configuration_reference_correction",
    CounterfactualChangeType.UPDATE_DEPENDENCY.value: "dependency_correction",
    CounterfactualChangeType.UPDATE_VERSION.value: "version_restoration",
    CounterfactualChangeType.UPDATE_ENVIRONMENT_REFERENCE.value: "environment_correction",
    CounterfactualChangeType.UPDATE_ROLE.value: "configuration_reference_correction",
    CounterfactualChangeType.UPDATE_REGION.value: "configuration_reference_correction",
    CounterfactualChangeType.UPDATE_JOB_DEPENDENCY.value: "configuration_reference_correction",
    CounterfactualChangeType.UPDATE_WORKFLOW_EXPRESSION.value: "configuration_reference_correction",
    CounterfactualChangeType.UPDATE_RESOURCE_TARGET.value: "configuration_reference_correction",
    CounterfactualChangeType.UPDATE_VALUE.value: "configuration_reference_correction",
}


class RemediationCandidateDiversitySelector:
    """Preserve different causal mechanisms; avoid near-duplicate wording."""

    def __init__(self, *, max_per_bucket: int = 2, max_total: int = 8) -> None:
        self._max_per_bucket = max_per_bucket
        self._max_total = max_total
        self.version = REMEDIATION_DIVERSITY_VERSION

    def select(
        self,
        candidates: list[CounterfactualRemediationCandidate],
    ) -> list[CounterfactualRemediationCandidate]:
        buckets: dict[str, int] = {}
        selected: list[CounterfactualRemediationCandidate] = []
        for candidate in candidates:
            bucket = self.bucket_for(candidate)
            count = buckets.get(bucket, 0)
            if count >= self._max_per_bucket and len(selected) >= 2:
                continue
            selected.append(candidate)
            buckets[bucket] = count + 1
            if len(selected) >= self._max_total:
                break
        logger.debug(
            "diversity_selected in=%s out=%s buckets=%s",
            len(candidates),
            len(selected),
            sorted(buckets),
        )
        return selected

    def bucket_for(self, candidate: CounterfactualRemediationCandidate) -> str:
        gen = (candidate.generator_type or "").upper()
        if "PREVIOUS_SUCCESS" in gen or candidate.generator_name == "previous_success":
            return "previous_success_restoration"
        if "HISTORICAL" in gen or candidate.generator_name == "historical_adapter":
            return "historical_adaptation"
        for change in candidate.changes:
            ctype = (
                change.change_type.value
                if hasattr(change.change_type, "value")
                else str(change.change_type or "")
            )
            if ctype in _BUCKET_BY_CHANGE:
                return _BUCKET_BY_CHANGE[ctype]
        if candidate.template_id:
            family = candidate.template_id.split(".", 1)[0]
            return f"family_{family}"
        return "unknown"
