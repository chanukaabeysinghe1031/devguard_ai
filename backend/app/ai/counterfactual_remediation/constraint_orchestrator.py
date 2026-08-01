"""Master constraint orchestrator — select, run, merge, dedupe, classify."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from app.ai.counterfactual_remediation.extractors import (
    AwsIamRemediationConstraintExtractor,
    OperationalRemediationConstraintExtractor,
    RemediationConstraintExtractor,
    RepositoryProjectConstraintExtractor,
    SecurityRemediationConstraintExtractor,
    TerraformRemediationConstraintExtractor,
    WorkflowRemediationConstraintExtractor,
)
from app.ai.counterfactual_remediation.model_types import (
    ConstraintExtractionResult,
    CounterfactualRemediationContext,
    RemediationConstraint,
    RemediationConstraintSet,
    RemediationCurrentState,
)
from app.ai.counterfactual_remediation.versions import REMEDIATION_CONSTRAINTS_VERSION
from app.domain.counterfactual_remediation.enums import (
    ConstraintSetCompleteness,
    ConstraintSeverity,
    ConstraintSourceType,
    ConstraintType,
    RemediationArtifactType,
)

logger = logging.getLogger(__name__)


def _artifact_type(value: RemediationArtifactType | str | None) -> RemediationArtifactType:
    if value is None:
        return RemediationArtifactType.UNKNOWN
    if isinstance(value, RemediationArtifactType):
        return value
    try:
        return RemediationArtifactType(str(value))
    except ValueError:
        return RemediationArtifactType.UNKNOWN


def _constraint_type_value(value: ConstraintType | str | None) -> str:
    if value is None:
        return ""
    return value.value if isinstance(value, ConstraintType) else str(value)


class RemediationConstraintOrchestrator:
    """Run deterministic extractors and produce a stable constraint set."""

    def __init__(
        self,
        *,
        max_constraints: int = 100,
        extractors: Iterable[RemediationConstraintExtractor] | None = None,
    ) -> None:
        self._max_constraints = max(1, max_constraints)
        self._extractors: list[RemediationConstraintExtractor] = list(
            extractors
            or [
                WorkflowRemediationConstraintExtractor(),
                TerraformRemediationConstraintExtractor(),
                AwsIamRemediationConstraintExtractor(),
                SecurityRemediationConstraintExtractor(),
                RepositoryProjectConstraintExtractor(),
                OperationalRemediationConstraintExtractor(),
            ]
        )

    def run(
        self,
        context: CounterfactualRemediationContext,
        current_state: RemediationCurrentState,
        *,
        enabled: bool = True,
    ) -> RemediationConstraintSet:
        if not enabled:
            return RemediationConstraintSet(
                hypothesis_id=context.hypothesis_id,
                extraction_version=REMEDIATION_CONSTRAINTS_VERSION,
                completeness=ConstraintSetCompleteness.INSUFFICIENT,
                extraction_warnings=["constraint_extraction_disabled"],
            )

        selected = self._select_extractors(current_state)
        missing_sources: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []
        merged: list[RemediationConstraint] = []
        results: list[ConstraintExtractionResult] = []

        available_names = {e.extractor_name for e in selected}
        for extractor in self._extractors:
            if extractor.extractor_name not in available_names:
                if not extractor.is_available():
                    missing_sources.append(extractor.extractor_name)
                continue
            if not extractor.is_available():
                missing_sources.append(extractor.extractor_name)
                warnings.append(f"extractor_unavailable:{extractor.extractor_name}")
                continue
            try:
                result = extractor.extract(context, current_state)
                validation_errors = extractor.validate_output(result)
                if validation_errors:
                    errors.extend(f"{extractor.extractor_name}:{err}" for err in validation_errors)
                # Drop LLM-only blocking constraints (defence in depth).
                safe_constraints = [
                    c
                    for c in result.constraints
                    if not (
                        c.is_blocking and str(c.extraction_method).lower() in {"llm", "llm_only"}
                    )
                ]
                if len(safe_constraints) != len(result.constraints):
                    warnings.append(f"dropped_llm_only_blocking:{extractor.extractor_name}")
                result.constraints = safe_constraints
                result.extracted_count = len(safe_constraints)
                result.blocking_count = sum(1 for c in safe_constraints if c.is_blocking)
                results.append(result)
                merged.extend(safe_constraints)
                warnings.extend(result.warnings)
                errors.extend(result.errors)
            except Exception as exc:  # noqa: BLE001 — soft-fail extractor
                logger.warning(
                    "constraint_extractor_failed name=%s error=%s",
                    extractor.extractor_name,
                    type(exc).__name__,
                )
                errors.append(f"{extractor.extractor_name}:failed")
                missing_sources.append(extractor.extractor_name)

        deduped = self._dedupe(merged)
        if len(deduped) > self._max_constraints:
            warnings.append(f"constraints_truncated_to_{self._max_constraints}")
            # Prefer keeping blocking constraints.
            blocking = [c for c in deduped if c.is_blocking]
            non_blocking = [c for c in deduped if not c.is_blocking]
            keep = blocking[: self._max_constraints]
            remaining = self._max_constraints - len(keep)
            if remaining > 0:
                keep.extend(non_blocking[:remaining])
            deduped = keep

        classified = self._classify(deduped)
        completeness = self._completeness(
            results=results,
            missing_sources=missing_sources,
            context=context,
        )
        constraint_set = RemediationConstraintSet(
            hypothesis_id=context.hypothesis_id,
            constraints=deduped,
            blocking_constraints=classified["blocking"],
            security_constraints=classified["security"],
            workflow_constraints=classified["workflow"],
            terraform_constraints=classified["terraform"],
            cloud_constraints=classified["cloud"],
            repository_constraints=classified["repository"],
            operational_constraints=classified["operational"],
            missing_constraint_sources=sorted(set(missing_sources)),
            extraction_warnings=warnings,
            extraction_errors=errors,
            extraction_version=REMEDIATION_CONSTRAINTS_VERSION,
            completeness=completeness,
        )
        logger.debug(
            "constraints_orchestrated hypothesis_id=%s count=%s blocking=%s completeness=%s",
            context.hypothesis_id,
            len(deduped),
            len(classified["blocking"]),
            completeness.value,
        )
        return constraint_set

    def _select_extractors(
        self,
        current_state: RemediationCurrentState,
    ) -> list[RemediationConstraintExtractor]:
        artifact = _artifact_type(current_state.artifact_type)
        selected: list[RemediationConstraintExtractor] = []
        for extractor in self._extractors:
            supported: frozenset[Any] | set[Any] = getattr(
                extractor, "supported_artifact_types", frozenset()
            )
            # Security / repo / operational always run; typed extractors when matching.
            name = extractor.extractor_name
            always = name.startswith(("security_", "repository_", "operational_"))
            if always or artifact in supported or artifact == RemediationArtifactType.UNKNOWN:
                # For UNKNOWN, still run typed extractors if entities hint at type.
                if always or artifact in supported:
                    selected.append(extractor)
                    continue
                entities = current_state.structured_entities
                types = {str(e.get("type") or "").upper() for e in entities}
                if (
                    name.startswith("workflow_")
                    and ("JOB" in types or "WORKFLOW" in types)
                    or name.startswith("terraform_")
                    and types
                    & {
                        "RESOURCE",
                        "MODULE",
                        "VARIABLE",
                        "PROVIDER",
                        "OUTPUT",
                        "DATA",
                    }
                    or name.startswith("aws_iam_")
                    and types
                    & {
                        "IAM_POLICY",
                        "POLICY_STATEMENT",
                    }
                    or artifact == RemediationArtifactType.UNKNOWN
                    and always
                ):
                    selected.append(extractor)
        # Ensure universal extractors always present.
        names = {e.extractor_name for e in selected}
        for extractor in self._extractors:
            if (
                extractor.extractor_name.startswith(("security_", "repository_", "operational_"))
                and extractor.extractor_name not in names
            ):
                selected.append(extractor)
        return selected

    def _dedupe(self, constraints: list[RemediationConstraint]) -> list[RemediationConstraint]:
        by_key: dict[str, RemediationConstraint] = {}
        for constraint in sorted(
            constraints,
            key=lambda c: (
                0 if c.is_blocking else 1,
                c.severity.value if isinstance(c.severity, ConstraintSeverity) else str(c.severity),
                c.constraint_key,
            ),
        ):
            key = constraint.constraint_key or constraint.id
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = constraint
                continue
            # Prefer blocking / higher severity.
            if constraint.is_blocking and not existing.is_blocking:
                by_key[key] = constraint
        return [by_key[k] for k in sorted(by_key)]

    def _classify(
        self,
        constraints: list[RemediationConstraint],
    ) -> dict[str, list[RemediationConstraint]]:
        buckets: dict[str, list[RemediationConstraint]] = {
            "blocking": [],
            "security": [],
            "workflow": [],
            "terraform": [],
            "cloud": [],
            "repository": [],
            "operational": [],
        }
        for constraint in constraints:
            if constraint.is_blocking or constraint.severity == ConstraintSeverity.BLOCKING:
                constraint.is_blocking = True
                buckets["blocking"].append(constraint)
            source = constraint.source_type
            if source in {
                ConstraintSourceType.SECURITY_POLICY,
                ConstraintSourceType.SYSTEM_POLICY,
            } or _constraint_type_value(constraint.constraint_type) in {
                "SECURITY",
                "ENCRYPTION",
                "PUBLIC_ACCESS",
            }:
                buckets["security"].append(constraint)
            if source == ConstraintSourceType.WORKFLOW:
                buckets["workflow"].append(constraint)
            if source in {
                ConstraintSourceType.TERRAFORM,
                ConstraintSourceType.TERRAFORM_PLAN,
            }:
                buckets["terraform"].append(constraint)
            if source in {
                ConstraintSourceType.AWS_ERROR,
                ConstraintSourceType.IAM_POLICY,
                ConstraintSourceType.RESOURCE_POLICY,
            }:
                buckets["cloud"].append(constraint)
            if source in {
                ConstraintSourceType.REPOSITORY,
                ConstraintSourceType.PROJECT_CONFIGURATION,
            }:
                buckets["repository"].append(constraint)
            if (
                source == ConstraintSourceType.SYSTEM_POLICY
                and constraint.constraint_key.startswith("ops.")
                or _constraint_type_value(constraint.constraint_type)
                in {"OPERATIONAL", "ROLLBACK", "COST"}
            ):
                buckets["operational"].append(constraint)
        return buckets

    def _completeness(
        self,
        *,
        results: list[ConstraintExtractionResult],
        missing_sources: list[str],
        context: CounterfactualRemediationContext,
    ) -> ConstraintSetCompleteness:
        if not results and missing_sources:
            return ConstraintSetCompleteness.INSUFFICIENT
        if getattr(context, "missing_artifacts", None) or missing_sources:
            return ConstraintSetCompleteness.PARTIAL
        if any(r.warnings or r.errors for r in results):
            return ConstraintSetCompleteness.PARTIAL
        if not any(r.constraints for r in results):
            return ConstraintSetCompleteness.LOW
        return ConstraintSetCompleteness.COMPLETE
