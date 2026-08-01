"""Repository and project remediation constraint extractor."""

from __future__ import annotations

from app.ai.counterfactual_remediation.extractors._helpers import (
    base_constraint,
    finalize_result,
    now_ms,
)
from app.ai.counterfactual_remediation.extractors.base import BaseRemediationConstraintExtractor
from app.ai.counterfactual_remediation.model_types import (
    ConstraintExtractionResult,
    CounterfactualRemediationContext,
    RemediationConstraint,
    RemediationCurrentState,
)
from app.ai.counterfactual_remediation.versions import CONSTRAINT_EXTRACTOR_VERSION
from app.domain.counterfactual_remediation.enums import (
    ConstraintSeverity,
    ConstraintSourceType,
    ConstraintType,
    RemediationArtifactType,
)


class RepositoryProjectConstraintExtractor(BaseRemediationConstraintExtractor):
    extractor_name = "repository_project_constraint_extractor"
    extractor_version = CONSTRAINT_EXTRACTOR_VERSION
    supported_artifact_types = frozenset(set(RemediationArtifactType))

    def extract(
        self,
        context: CounterfactualRemediationContext,
        current_state: RemediationCurrentState,
    ) -> ConstraintExtractionResult:
        started = now_ms()
        constraints: list[RemediationConstraint] = []
        warnings: list[str] = []

        path = current_state.source_path or context.source_path
        if path:
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key=f"repo.path.boundary:{path}",
                    constraint_type=ConstraintType.RESOURCE_SCOPE,
                    severity=ConstraintSeverity.HIGH,
                    source_type=ConstraintSourceType.REPOSITORY,
                    description="Changes should remain within repository path boundaries",
                    machine_readable_rule={
                        "rule": "respect_repository_path_boundaries",
                        "source_path": path,
                    },
                    is_blocking=True,
                    extractor_name=self.extractor_name,
                    expected_value=path,
                )
            )

        changed = sorted(set(context.related_changed_files))
        if changed:
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key="repo.changed_file_scope",
                    constraint_type=ConstraintType.RESOURCE_SCOPE,
                    severity=ConstraintSeverity.MEDIUM,
                    source_type=ConstraintSourceType.REPOSITORY,
                    description="Prefer remediating within the observed changed-file scope",
                    machine_readable_rule={
                        "rule": "prefer_changed_file_scope",
                        "changed_files": changed,
                    },
                    extractor_name=self.extractor_name,
                    expected_value=changed,
                )
            )

        constraints.append(
            base_constraint(
                context=context,
                current_state=current_state,
                constraint_key="repo.max_candidate_files",
                constraint_type=ConstraintType.OPERATIONAL,
                severity=ConstraintSeverity.HIGH,
                source_type=ConstraintSourceType.PROJECT_CONFIGURATION,
                description="Maximum candidate file count must be respected",
                machine_readable_rule={
                    "rule": "max_candidate_files",
                    "max_files": 5,
                },
                is_blocking=True,
                extractor_name=self.extractor_name,
                expected_value=5,
            )
        )

        constraints.append(
            base_constraint(
                context=context,
                current_state=current_state,
                constraint_key="repo.org_isolation",
                constraint_type=ConstraintType.ORGANIZATION_POLICY,
                severity=ConstraintSeverity.BLOCKING,
                source_type=ConstraintSourceType.ORGANIZATION_POLICY,
                description="Candidate must remain within organization scope",
                machine_readable_rule={
                    "rule": "organization_scope_match",
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                },
                is_blocking=True,
                extractor_name=self.extractor_name,
                expected_value=context.organization_id,
            )
        )

        # Do not invent CODEOWNERS if absent.
        if not any("CODEOWNERS" in f.upper() for f in changed + ([path] if path else [])):
            warnings.append("codeowners_absent_not_invented")

        if context.previous_successful_version:
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key="repo.previous_successful_commit",
                    constraint_type=ConstraintType.VERSION,
                    severity=ConstraintSeverity.MEDIUM,
                    source_type=ConstraintSourceType.REPOSITORY,
                    description="Previous successful commit may guide restore templates",
                    machine_readable_rule={
                        "rule": "prefer_restore_previous_successful_when_supported",
                        "commit": context.previous_successful_version,
                    },
                    extractor_name=self.extractor_name,
                    expected_value=context.previous_successful_version,
                )
            )

        constraints.append(
            base_constraint(
                context=context,
                current_state=current_state,
                constraint_key="repo.no_source_rewrite_without_fragment",
                constraint_type=ConstraintType.EVIDENCE_LIMITATION,
                severity=ConstraintSeverity.HIGH,
                source_type=ConstraintSourceType.REPOSITORY,
                description="Source-code patches unsupported without exact causal fragment",
                machine_readable_rule={
                    "rule": "source_code_requires_exact_fragment",
                    "prohibited_artifact_type": RemediationArtifactType.SOURCE_CODE.value,
                },
                is_blocking=True,
                extractor_name=self.extractor_name,
            )
        )

        return finalize_result(
            extractor_name=self.extractor_name,
            constraints=constraints,
            started_ms=started,
            artifact_ids=[a for a in [current_state.artifact_id] if a],
            warnings=warnings,
            limitations=self.limitations(),
        )

    def limitations(self) -> list[str]:
        return super().limitations() + [
            "codeowners_not_invented_when_absent",
            "protected_files_require_explicit_config",
        ]
