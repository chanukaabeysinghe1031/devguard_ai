"""Shared helpers for deterministic constraint extractors."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from app.ai.counterfactual_remediation.model_types import (
    ConstraintExtractionResult,
    CounterfactualRemediationContext,
    RemediationConstraint,
    RemediationCurrentState,
)
from app.ai.counterfactual_remediation.versions import CONSTRAINT_EXTRACTOR_VERSION
from app.domain.counterfactual_remediation.enums import (
    ConstraintExtractionStatus,
    ConstraintSeverity,
    ConstraintSourceType,
    ConstraintType,
)


def now_ms() -> int:
    return int(time.perf_counter() * 1000)


def _scope_str(value: str | None) -> str:
    return value or ""


def base_constraint(
    *,
    context: CounterfactualRemediationContext,
    current_state: RemediationCurrentState,
    constraint_key: str,
    constraint_type: ConstraintType,
    severity: ConstraintSeverity,
    source_type: ConstraintSourceType,
    description: str,
    machine_readable_rule: dict[str, Any],
    is_blocking: bool = False,
    extractor_name: str,
    expected_value: Any = None,
    prohibited_value: Any = None,
    limitations: list[str] | None = None,
) -> RemediationConstraint:
    del extractor_name  # provenance via extraction_method / version
    return RemediationConstraint(
        id=str(uuid4()),
        organization_id=_scope_str(context.organization_id),
        project_id=_scope_str(context.project_id),
        incident_id=_scope_str(context.incident_id),
        analysis_id=_scope_str(context.analysis_id),
        hypothesis_id=_scope_str(context.hypothesis_id),
        constraint_key=constraint_key,
        constraint_type=constraint_type,
        severity=severity,
        source_type=source_type,
        source_artifact_id=current_state.artifact_id,
        source_path=current_state.source_path or context.source_path,
        description=description,
        machine_readable_rule=dict(machine_readable_rule),
        expected_value=expected_value,
        prohibited_value=prohibited_value,
        confidence=1.0,
        extraction_method="deterministic",
        extractor_version=CONSTRAINT_EXTRACTOR_VERSION,
        is_blocking=is_blocking,
        limitations=list(limitations or []),
    )


def finalize_result(
    *,
    extractor_name: str,
    constraints: list[RemediationConstraint],
    started_ms: int,
    artifact_ids: list[str],
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    status: ConstraintExtractionStatus | None = None,
    limitations: list[str] | None = None,
) -> ConstraintExtractionResult:
    blocking = [c for c in constraints if c.is_blocking]
    if status is None:
        if errors:
            status = ConstraintExtractionStatus.FAILED
        elif not constraints:
            status = ConstraintExtractionStatus.NO_CONSTRAINTS
        elif warnings:
            status = ConstraintExtractionStatus.PARTIAL
        else:
            status = ConstraintExtractionStatus.COMPLETE
    return ConstraintExtractionResult(
        extractor_name=extractor_name,
        status=status,
        constraints=constraints,
        artifact_ids_processed=sorted({a for a in artifact_ids if a}),
        extracted_count=len(constraints),
        blocking_count=len(blocking),
        warnings=list(warnings or []),
        errors=list(errors or []),
        duration_ms=max(0, now_ms() - started_ms),
        extractor_version=CONSTRAINT_EXTRACTOR_VERSION,
        limitations=list(limitations or []),
    )


def entity_type(entity: dict[str, Any]) -> str:
    return str(entity.get("type") or "").upper()


def entity_meta(entity: dict[str, Any]) -> dict[str, Any]:
    meta = entity.get("metadata")
    return dict(meta) if isinstance(meta, dict) else {}


def context_category(context: CounterfactualRemediationContext) -> str:
    return str(getattr(context, "category", None) or "").lower()
