"""Debug/read APIs for Phase 6A.6 Part 1 counterfactual remediation foundation."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import UUID

from app.application.services.analysis_run_service import AnalysisRunService
from app.core.config import Settings
from app.domain.exceptions.business import ResourceNotFoundError
from app.infrastructure.database.models.counterfactual_remediation import (
    CounterfactualRemediationCandidateRow,
)
from app.infrastructure.repositories.counterfactual_remediation_repository import (
    CounterfactualRemediationRepositoryImpl,
)
from app.schemas.phase6a6 import (
    CounterfactualChangeItem,
    CounterfactualChangeListResponse,
    CounterfactualConstraintValidationResponse,
    CounterfactualPatchResponse,
    CounterfactualPrioritisationResponse,
    CounterfactualRemediationCandidateDetailResponse,
    CounterfactualRemediationCandidateListItem,
    CounterfactualRemediationCandidateListResponse,
    CounterfactualRemediationRunResponse,
    CounterfactualRiskResponse,
    CounterfactualRollbackResponse,
    CounterfactualSideEffectsResponse,
    CounterfactualStateSnapshotResponse,
    RemediationConstraintItem,
    RemediationConstraintListResponse,
    RemediationPreconditionItem,
    RemediationPreconditionListResponse,
    RemediationVerificationRequirementItem,
    RemediationVerificationRequirementListResponse,
)

_SECRETISH = re.compile(
    r"(?i)(password|secret|token|api[_-]?key|private[_-]?key|bearer\s+|akia[0-9a-z]{16})"
)


def _hash_preview(value: str | None) -> str | None:
    if not value:
        return None
    digest = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"sha256:{digest}"


def _redact_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Prefer hashes/paths; drop secret-looking fragment bodies."""
    if not snapshot:
        return {}
    out: dict[str, Any] = {}
    for key, value in dict(snapshot).items():
        key_l = str(key).lower()
        if key_l in {
            "source_fragment",
            "original_fragment",
            "proposed_fragment",
            "raw_content",
            "secret_value",
            "credentials",
        }:
            if isinstance(value, str) and value:
                out[f"{key}_hash"] = _hash_preview(value)
                out[f"{key}_redacted"] = True
            continue
        if isinstance(value, str) and _SECRETISH.search(value):
            out[key] = "[REDACTED]"
            out[f"{key}_hash"] = _hash_preview(value)
            continue
        if isinstance(value, dict):
            out[key] = _redact_snapshot(value)
        elif isinstance(value, list):
            out[key] = [
                _redact_snapshot(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            out[key] = value
    # Prefer path/hash fields when present.
    if "content_hash" in snapshot and "content_hash" not in out:
        out["content_hash"] = snapshot.get("content_hash")
    if "source_path" in snapshot:
        out["source_path"] = snapshot.get("source_path")
    return out


class Phase6A6CounterfactualService:
    def __init__(self, run_service: AnalysisRunService, settings: Settings) -> None:
        self._runs = run_service
        self._session = run_service._session  # noqa: SLF001
        self._settings = settings
        self._repo = CounterfactualRemediationRepositoryImpl(self._session)

    def _ensure_debug_enabled(self) -> None:
        if not self._settings.counterfactual_debug_api_enabled:
            raise ResourceNotFoundError("Counterfactual remediation debug API not found.")

    async def get_run(
        self, *, organization_id: UUID, analysis_run_id: UUID
    ) -> CounterfactualRemediationRunResponse:
        self._ensure_debug_enabled()
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._repo.get_run_by_analysis(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
        )
        if row is None:
            raise ResourceNotFoundError("Counterfactual remediation run not found.")
        snapshot = dict(row.configuration_snapshot or {})
        # Drop bulky candidate bodies from run response if present.
        summaries = snapshot.get("candidate_summaries")
        if isinstance(summaries, list):
            snapshot["candidate_summaries"] = [
                {
                    "id": item.get("id") if isinstance(item, dict) else None,
                    "candidate_key": item.get("candidate_key") if isinstance(item, dict) else None,
                    "status": item.get("status") if isinstance(item, dict) else None,
                    "template_id": item.get("template_id") if isinstance(item, dict) else None,
                }
                for item in summaries
            ]
        return CounterfactualRemediationRunResponse(
            id=row.id,
            analysis_run_id=row.analysis_run_id,
            project_id=row.project_id,
            incident_id=row.incident_id,
            status=row.status,
            selected_hypothesis_ids=[str(x) for x in (row.selected_hypothesis_ids or [])],
            selected_hypothesis_count=row.selected_hypothesis_count,
            candidate_count=row.candidate_count,
            safe_candidate_count=row.safe_candidate_count,
            incomplete_candidate_count=row.incomplete_candidate_count,
            rejected_candidate_count=row.rejected_candidate_count,
            duration_ms=row.duration_ms,
            context_version=row.context_version,
            constraint_version=row.constraint_version,
            planner_version=row.planner_version,
            template_registry_version=row.template_registry_version,
            snapshot_version=row.snapshot_version,
            configuration_snapshot=snapshot,
            warnings=[str(x) for x in (row.warnings or [])],
            errors=[str(x) for x in (row.errors or [])],
            limitations=[str(x) for x in (row.limitations or [])],
            created_at=row.created_at,
        )

    async def list_candidates(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        page: int = 1,
        page_size: int = 50,
        hypothesis_id: UUID | None = None,
        status: str | None = None,
        generator_type: str | None = None,
        artifact_type: str | None = None,
        risk_level: str | None = None,
        blast_radius: str | None = None,
        priority_status: str | None = None,
        template_id: str | None = None,
    ) -> CounterfactualRemediationCandidateListResponse:
        self._ensure_debug_enabled()
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size
        rows = await self._repo.list_candidates_by_analysis(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            hypothesis_id=hypothesis_id,
            status=status,
            artifact_type=artifact_type,
            template_id=template_id,
            generator_type=generator_type,
            risk_level=risk_level,
            blast_radius=blast_radius,
            priority_status=priority_status,
            limit=page_size,
            offset=offset,
        )
        # Approximate total with a second unbounded count via filters (same filters, high limit).
        all_filtered = await self._repo.list_candidates_by_analysis(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            hypothesis_id=hypothesis_id,
            status=status,
            artifact_type=artifact_type,
            template_id=template_id,
            generator_type=generator_type,
            risk_level=risk_level,
            blast_radius=blast_radius,
            priority_status=priority_status,
            limit=500,
            offset=0,
        )
        items = [self._list_item(r) for r in rows]
        return CounterfactualRemediationCandidateListResponse(
            items=items,
            total_items=len(all_filtered),
            page=page,
            page_size=page_size,
        )

    def _list_item(
        self, r: CounterfactualRemediationCandidateRow
    ) -> CounterfactualRemediationCandidateListItem:
        return CounterfactualRemediationCandidateListItem(
            id=r.id,
            candidate_key=r.candidate_key,
            hypothesis_id=r.hypothesis_id,
            title=r.title,
            summary=r.summary,
            artifact_type=r.artifact_type,
            status=r.status,
            template_id=r.template_id,
            change_types=[str(x) for x in (r.change_types or [])],
            target_paths=[str(x) for x in (r.target_paths or [])],
            generator_type=r.generator_type,
            risk_level=getattr(r, "risk_level", None),
            blast_radius=getattr(r, "blast_radius", None),
            priority_status=getattr(r, "priority_status", None),
            priority_score=getattr(r, "priority_score", None),
            risk_score=getattr(r, "risk_score", None),
            changed_file_count=int(getattr(r, "changed_file_count", 0) or 0),
            changed_line_count=int(getattr(r, "changed_line_count", 0) or 0),
            validation_status=getattr(r, "validation_status", None),
            constraint_status=getattr(r, "constraint_status", None),
        )

    async def get_candidate(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> CounterfactualRemediationCandidateDetailResponse:
        row = await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        return CounterfactualRemediationCandidateDetailResponse(
            id=row.id,
            remediation_run_id=row.remediation_run_id,
            analysis_run_id=row.analysis_run_id,
            hypothesis_id=row.hypothesis_id,
            candidate_key=row.candidate_key,
            title=row.title,
            summary=row.summary,
            artifact_type=row.artifact_type,
            category_code=row.category_code,
            affected_artifact_ids=[str(x) for x in (row.affected_artifact_ids or [])],
            primary_artifact_id=row.primary_artifact_id,
            target_paths=[str(x) for x in (row.target_paths or [])],
            change_types=[str(x) for x in (row.change_types or [])],
            expected_effects=list(row.expected_effects or []),
            expected_preserved_behaviors=list(row.expected_preserved_behaviors or []),
            assumptions=[str(x) for x in (row.assumptions or [])],
            limitations=[str(x) for x in (row.limitations or [])],
            rollback_plan=_redact_snapshot(dict(row.rollback_plan or {})),
            risk_summary=list(row.risk_summary or []),
            blast_radius_summary=dict(row.blast_radius_summary or {}),
            generator_type=row.generator_type,
            generator_name=row.generator_name,
            generator_version=row.generator_version,
            template_id=row.template_id,
            template_version=row.template_version,
            status=row.status,
            patch_format=getattr(row, "patch_format", None),
            patch_hash=getattr(row, "patch_hash", None),
            has_rendered_patch=bool(getattr(row, "rendered_patch", None)),
            changed_file_count=int(getattr(row, "changed_file_count", 0) or 0),
            changed_line_count=int(getattr(row, "changed_line_count", 0) or 0),
            risk_score=getattr(row, "risk_score", None),
            risk_level=getattr(row, "risk_level", None),
            blast_radius=getattr(row, "blast_radius", None),
            priority_score=getattr(row, "priority_score", None),
            priority_status=getattr(row, "priority_status", None),
            deduplication_fingerprint=getattr(row, "deduplication_fingerprint", None),
            validation_status=getattr(row, "validation_status", None),
            constraint_status=getattr(row, "constraint_status", None),
            prompt_version=getattr(row, "prompt_version", None),
            side_effects_json=list(getattr(row, "side_effects_json", None) or []),
            quality_components_json=dict(getattr(row, "quality_components_json", None) or {}),
            risk_components_json=dict(getattr(row, "risk_components_json", None) or {}),
            generation_provenance=dict(getattr(row, "generation_provenance", None) or {}),
        )

    async def list_changes(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> CounterfactualChangeListResponse:
        await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        rows = await self._repo.list_changes_by_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        items = [
            CounterfactualChangeItem(
                id=r.id,
                artifact_id=r.artifact_id,
                artifact_type=r.artifact_type,
                source_path=r.source_path,
                change_type=r.change_type,
                target_property=r.target_property,
                original_fragment_hash=_hash_preview(r.original_fragment),
                proposed_fragment_hash=_hash_preview(r.proposed_fragment),
                has_normalized_diff=bool(r.normalized_diff),
                expected_effect=r.expected_effect,
                rationale=r.rationale or "",
                change_order=r.change_order,
                content_hash_before=r.content_hash_before,
                content_hash_after_candidate=r.content_hash_after_candidate,
            )
            for r in rows
        ]
        return CounterfactualChangeListResponse(
            candidate_id=candidate_id,
            analysis_run_id=analysis_run_id,
            items=items,
            total_items=len(items),
        )

    async def get_patch(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> CounterfactualPatchResponse:
        row = await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        patch = getattr(row, "rendered_patch", None)
        if isinstance(patch, str) and _SECRETISH.search(patch):
            patch = "[REDACTED]"
        return CounterfactualPatchResponse(
            candidate_id=row.id,
            analysis_run_id=row.analysis_run_id,
            patch_format=getattr(row, "patch_format", None),
            patch_hash=getattr(row, "patch_hash", None),
            rendered_patch=patch,
            changed_file_count=int(getattr(row, "changed_file_count", 0) or 0),
            changed_line_count=int(getattr(row, "changed_line_count", 0) or 0),
        )

    async def get_risk(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> CounterfactualRiskResponse:
        row = await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        return CounterfactualRiskResponse(
            candidate_id=row.id,
            analysis_run_id=row.analysis_run_id,
            risk_score=getattr(row, "risk_score", None),
            risk_level=getattr(row, "risk_level", None),
            risk_components_json=dict(getattr(row, "risk_components_json", None) or {}),
            risk_summary=list(row.risk_summary or []),
        )

    async def get_side_effects(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> CounterfactualSideEffectsResponse:
        row = await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        return CounterfactualSideEffectsResponse(
            candidate_id=row.id,
            analysis_run_id=row.analysis_run_id,
            side_effects_json=list(getattr(row, "side_effects_json", None) or []),
        )

    async def get_rollback(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> CounterfactualRollbackResponse:
        row = await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        return CounterfactualRollbackResponse(
            candidate_id=row.id,
            analysis_run_id=row.analysis_run_id,
            rollback_plan=_redact_snapshot(dict(row.rollback_plan or {})),
        )

    async def get_constraint_validation(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> CounterfactualConstraintValidationResponse:
        row = await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        return CounterfactualConstraintValidationResponse(
            candidate_id=row.id,
            analysis_run_id=row.analysis_run_id,
            validation_status=getattr(row, "validation_status", None),
            constraint_status=getattr(row, "constraint_status", None),
        )

    async def get_prioritisation(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> CounterfactualPrioritisationResponse:
        self._ensure_debug_enabled()
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        run_row = await self._repo.get_run_by_analysis(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
        )
        snapshot = dict(run_row.configuration_snapshot or {}) if run_row else {}
        prioritisation = dict(snapshot.get("prioritisation") or {})
        rows = await self._repo.list_candidates_by_analysis(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            limit=100,
            offset=0,
        )
        # Order by priority_score desc when present.
        rows_sorted = sorted(
            rows,
            key=lambda r: (
                -(float(getattr(r, "priority_score", None) or 0.0)),
                r.candidate_key,
            ),
        )
        return CounterfactualPrioritisationResponse(
            analysis_run_id=analysis_run_id,
            prioritisation=prioritisation,
            candidates=[self._list_item(r) for r in rows_sorted],
        )

    async def get_current_state(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> CounterfactualStateSnapshotResponse:
        row = await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        return CounterfactualStateSnapshotResponse(
            candidate_id=row.id,
            analysis_run_id=row.analysis_run_id,
            snapshot_kind="current_state",
            snapshot=_redact_snapshot(dict(row.current_state_snapshot or {})),
        )

    async def get_counterfactual_state(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> CounterfactualStateSnapshotResponse:
        row = await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        return CounterfactualStateSnapshotResponse(
            candidate_id=row.id,
            analysis_run_id=row.analysis_run_id,
            snapshot_kind="counterfactual_state",
            snapshot=_redact_snapshot(dict(row.counterfactual_state_snapshot or {})),
        )

    async def list_constraints(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> RemediationConstraintListResponse:
        await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        rows = await self._repo.list_constraints_by_analysis(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        # Also include analysis-scoped constraints without candidate_id when none linked.
        if not rows:
            rows = await self._repo.list_constraints_by_analysis(
                organization_id=organization_id,
                analysis_run_id=analysis_run_id,
                candidate_id=None,
            )
            # Filter to hypothesis-linked if we can; otherwise return analysis-level.
        items = [
            RemediationConstraintItem(
                id=r.id,
                constraint_key=r.constraint_key,
                constraint_type=r.constraint_type,
                severity=r.severity,
                source_type=r.source_type,
                description=r.description or "",
                source_path=r.source_path,
                is_blocking=bool(r.is_blocking),
                satisfaction_status=r.satisfaction_status,
                machine_readable_rule=dict(r.machine_readable_rule or {}),
                limitations=[str(x) for x in (r.limitations or [])],
            )
            for r in rows
        ]
        return RemediationConstraintListResponse(
            candidate_id=candidate_id,
            analysis_run_id=analysis_run_id,
            items=items,
            total_items=len(items),
        )

    async def list_preconditions(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> RemediationPreconditionListResponse:
        await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        rows = await self._repo.list_preconditions_by_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        items = [
            RemediationPreconditionItem(
                id=r.id,
                condition_type=r.condition_type,
                description=r.description or "",
                status=r.status,
                is_required=bool(r.is_required),
                evidence_ids=[str(x) for x in (r.evidence_ids or [])],
                artifact_ids=[str(x) for x in (r.artifact_ids or [])],
                limitations=[str(x) for x in (r.limitations or [])],
            )
            for r in rows
        ]
        return RemediationPreconditionListResponse(
            candidate_id=candidate_id,
            analysis_run_id=analysis_run_id,
            items=items,
            total_items=len(items),
        )

    async def list_verification_requirements(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> RemediationVerificationRequirementListResponse:
        await self._load_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        rows = await self._repo.list_verification_requirements_by_candidate(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            candidate_id=candidate_id,
        )
        items = [
            RemediationVerificationRequirementItem(
                id=r.id,
                requirement_key=r.requirement_key,
                verifier_type=r.verifier_type,
                required=bool(r.required),
                reason=r.reason or "",
                expected_check=r.expected_check,
                expected_success_condition=r.expected_success_condition,
                blocking_on_failure=bool(r.blocking_on_failure),
                limitations=[str(x) for x in (r.limitations or [])],
            )
            for r in rows
        ]
        return RemediationVerificationRequirementListResponse(
            candidate_id=candidate_id,
            analysis_run_id=analysis_run_id,
            items=items,
            total_items=len(items),
        )

    async def _load_candidate(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        candidate_id: UUID,
    ) -> CounterfactualRemediationCandidateRow:
        self._ensure_debug_enabled()
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._repo.get_candidate_by_id(
            organization_id=organization_id,
            candidate_id=candidate_id,
        )
        if row is None or row.analysis_run_id != analysis_run_id:
            raise ResourceNotFoundError("Counterfactual remediation candidate not found.")
        return row
