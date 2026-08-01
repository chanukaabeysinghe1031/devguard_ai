"""Phase 6A.6 Part 2 — blast-radius estimator (static heuristic)."""

from __future__ import annotations

from app.domain.counterfactual_remediation.generation_enums import BlastRadiusLevel
from app.domain.counterfactual_remediation.generation_models import BlastRadiusAssessment
from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate


class RemediationBlastRadiusEstimator:
    def estimate(self, candidate: CounterfactualRemediationCandidate) -> BlastRadiusAssessment:
        files = {c.source_path for c in (candidate.changes or []) if c.source_path}
        file_count = max(candidate.changed_file_count, len(files), 0)
        change_types = {str(t).upper() for t in (candidate.change_types or [])}
        cross = bool(change_types & {"UPDATE_ENVIRONMENT_REFERENCE", "UPDATE_REGION"})

        reasoning: list[str] = []
        if file_count <= 1 and not cross:
            level = BlastRadiusLevel.LOCAL
            reasoning.append("single_file_local_property")
        elif file_count <= 2:
            level = BlastRadiusLevel.LIMITED
            reasoning.append("limited_file_set")
        elif file_count <= 5:
            level = BlastRadiusLevel.MODERATE
            reasoning.append("multi_file_moderate")
        else:
            level = BlastRadiusLevel.BROAD
            reasoning.append("broad_file_set")

        if cross:
            if level == BlastRadiusLevel.LOCAL:
                level = BlastRadiusLevel.LIMITED
            reasoning.append("cross_environment_or_region_signal")

        return BlastRadiusAssessment(
            level=level,
            artifacts_changed=max(file_count, len(candidate.affected_artifact_ids or [])),
            environments_affected=2 if cross else 1,
            cross_account_or_region=cross,
            affected_entities=list(candidate.affected_artifact_ids or []),
            reasoning=reasoning,
        )
