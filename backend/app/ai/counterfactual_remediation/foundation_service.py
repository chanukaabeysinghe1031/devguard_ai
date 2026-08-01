"""Phase 6A.6 Part 1 foundation service — flag-gated, soft-fail, no LLM/verifiers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.ai.counterfactual_remediation.conflict_detector import (
    RemediationConstraintConflictDetector,
)
from app.ai.counterfactual_remediation.constraint_orchestrator import (
    RemediationConstraintOrchestrator,
)
from app.ai.counterfactual_remediation.context_builder import (
    CounterfactualRemediationContextBuilder,
)
from app.ai.counterfactual_remediation.current_state import RemediationCurrentStateBuilder
from app.ai.counterfactual_remediation.failure_condition import (
    build_counterfactual_failure_condition,
)
from app.ai.counterfactual_remediation.generation.generation_service import (
    CounterfactualRemediationGenerationService,
    build_generation_context_from_foundation,
)
from app.ai.counterfactual_remediation.minimal_planner import (
    DeterministicMinimalChangePlanner,
    build_minimal_change_objective,
)
from app.ai.counterfactual_remediation.model_types import (
    CounterfactualRemediationCandidate,
    CounterfactualRemediationRun,
    HypothesisEligibilityResult,
    RemediationRollbackPlan,
    RemediationVerificationRequirement,
)
from app.ai.counterfactual_remediation.persist import CounterfactualRemediationPersistService
from app.ai.counterfactual_remediation.preconditions import build_counterfactual_preconditions
from app.ai.counterfactual_remediation.structural_validator import (
    CounterfactualCandidateStructuralValidator,
)
from app.ai.counterfactual_remediation.template_registry import RemediationTemplateRegistry
from app.ai.counterfactual_remediation.versions import (
    COUNTERFACTUAL_CONTEXT_VERSION,
    MINIMAL_CHANGE_PLANNER_VERSION,
    REMEDIATION_CONSTRAINTS_VERSION,
    REMEDIATION_TEMPLATES_VERSION,
)
from app.domain.counterfactual_remediation.generation_models import RemediationGenerationContext
from app.domain.counterfactual_remediation.enums import (
    CounterfactualCandidateStatus,
    CounterfactualRemediationRunStatus,
    HypothesisEligibilityStatus,
    MinimalChangePlanStatus,
    RollbackType,
    VerifierType,
)

logger = logging.getLogger(__name__)


def _coerce_verifier(value: Any) -> VerifierType:
    if isinstance(value, VerifierType):
        return value
    try:
        return VerifierType(str(value))
    except ValueError:
        return VerifierType.COUNTERFACTUAL_FAILURE_CONDITION


def _flag(settings: Any, name: str, default: bool = False) -> bool:
    if settings is None:
        return default
    if isinstance(settings, dict):
        return bool(settings.get(name, default))
    return bool(getattr(settings, name, default))


def _bound(settings: Any, name: str, default: int) -> int:
    if settings is None:
        return default
    if isinstance(settings, dict):
        value = settings.get(name, default)
    else:
        value = getattr(settings, name, default)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        payload = value.to_dict()
        return dict(payload) if isinstance(payload, dict) else {}
    return {}


class CounterfactualRemediationFoundationService:
    """Orchestrate Part 1 foundation stage. Soft-fail friendly. No LLM. No verifiers."""

    def __init__(
        self,
        settings: Any = None,
        *,
        persist_service: CounterfactualRemediationPersistService | None = None,
        template_registry: RemediationTemplateRegistry | None = None,
        **bounds: Any,
    ) -> None:
        self._settings = settings
        self._bounds = bounds
        self._last_persist_payload: dict[str, Any] = {}
        self._persist = persist_service or CounterfactualRemediationPersistService(
            enabled=_flag(settings, "counterfactual_persistence_enabled", False)
            or bool(bounds.get("persistence_enabled", False))
        )
        max_constraints = _bound(
            settings, "max_constraints_per_hypothesis", bounds.get("max_constraints", 100)
        )
        self._context_builder = CounterfactualRemediationContextBuilder(
            max_context_chars=_bound(
                settings,
                "max_counterfactual_context_chars",
                bounds.get("max_context_chars", 80_000),
            ),
            max_graph_nodes=_bound(
                settings,
                "max_counterfactual_graph_nodes",
                bounds.get("max_graph_nodes", 100),
            ),
            max_graph_edges=_bound(
                settings,
                "max_counterfactual_graph_edges",
                bounds.get("max_graph_edges", 200),
            ),
        )
        self._current_state_builder = RemediationCurrentStateBuilder()
        self._constraint_orchestrator = RemediationConstraintOrchestrator(
            max_constraints=max_constraints
        )
        self._conflict_detector = RemediationConstraintConflictDetector()
        self._planner = DeterministicMinimalChangePlanner()
        self._registry = template_registry or RemediationTemplateRegistry()
        self._validator = CounterfactualCandidateStructuralValidator(
            max_patch_characters=_bound(
                settings, "max_patch_characters", bounds.get("max_patch_characters", 30_000)
            ),
            max_patch_files=_bound(
                settings,
                "max_patch_files_per_candidate",
                bounds.get("max_patch_files", 5),
            ),
            max_changed_lines=_bound(
                settings,
                "max_changed_lines_per_candidate",
                bounds.get("max_changed_lines", 200),
            ),
        )
        self._generation = CounterfactualRemediationGenerationService(settings)

    def run(
        self,
        *,
        organization_id: str,
        analysis_id: str,
        options: dict[str, Any] | None = None,
        project_id: str | None = None,
        incident_id: str | None = None,
        eligibility_results: list[HypothesisEligibilityResult] | dict[str, Any] | None = None,
    ) -> CounterfactualRemediationRun:
        started = datetime.now(UTC)
        options = options or {}
        project_id = project_id or ""
        incident_id = incident_id or ""

        if not self._master_enabled():
            disabled = CounterfactualRemediationRun(
                id=str(uuid4()),
                organization_id=organization_id,
                project_id=project_id,
                incident_id=incident_id,
                analysis_id=analysis_id,
                status=CounterfactualRemediationRunStatus.DISABLED,
                configuration_snapshot=self._config_snapshot(),
                context_version=COUNTERFACTUAL_CONTEXT_VERSION,
                constraint_version=REMEDIATION_CONSTRAINTS_VERSION,
                planner_version=MINIMAL_CHANGE_PLANNER_VERSION,
                template_registry_version=REMEDIATION_TEMPLATES_VERSION,
            )
            self._last_persist_payload = {
                "run": disabled,
                "candidates": [],
                "constraints": [],
                "preconditions": [],
            }
            return disabled

        run = CounterfactualRemediationRun(
            id=str(uuid4()),
            organization_id=organization_id,
            project_id=project_id,
            incident_id=incident_id,
            analysis_id=analysis_id,
            status=CounterfactualRemediationRunStatus.RUNNING,
            started_at=started,
            configuration_snapshot=self._config_snapshot(),
            context_version=COUNTERFACTUAL_CONTEXT_VERSION,
            constraint_version=REMEDIATION_CONSTRAINTS_VERSION,
            planner_version=MINIMAL_CHANGE_PLANNER_VERSION,
            template_registry_version=REMEDIATION_TEMPLATES_VERSION,
        )

        try:
            hypotheses = self._load_hypotheses(options)
            eligible = self._filter_eligible(hypotheses, eligibility_results, options)
            max_hyps = _bound(
                self._settings,
                "max_hypotheses_for_remediation",
                self._bounds.get("max_hypotheses", 3),
            )
            eligible = eligible[:max_hyps]
            run.selected_hypothesis_ids = [h["id"] for h in eligible]
            run.selected_hypothesis_count = len(eligible)

            if not eligible:
                run.status = CounterfactualRemediationRunStatus.NO_ELIGIBLE_HYPOTHESES
                run.warnings.append("no_eligible_hypotheses")
                self._last_persist_payload = {
                    "run": run,
                    "candidates": [],
                    "constraints": [],
                    "preconditions": [],
                }
                return self._finalize(run, started)

            candidates: list[CounterfactualRemediationCandidate] = []
            all_constraints: list[Any] = []
            all_preconditions: list[Any] = []
            generation_contexts: list[RemediationGenerationContext] = []

            for hypothesis in eligible:
                hyp_result = self._process_hypothesis(
                    run=run,
                    hypothesis=hypothesis,
                    options=options,
                    organization_id=organization_id,
                    analysis_id=analysis_id,
                    project_id=project_id,
                    incident_id=incident_id,
                )
                candidates.extend(hyp_result.get("candidates") or [])
                all_constraints.extend(hyp_result.get("constraints") or [])
                all_preconditions.extend(hyp_result.get("preconditions") or [])
                run.warnings.extend(hyp_result.get("warnings") or [])
                gen_ctx = hyp_result.get("generation_context")
                if gen_ctx is not None:
                    generation_contexts.append(gen_ctx)

            # Part 2 generation — only when at least one generation flag is ON.
            # When ALL generation flags are OFF, behavior is identical to Part 1.
            if self._generation.any_generation_enabled():
                try:
                    candidates, _gen_meta = self._generation.run(
                        run=run,
                        options=options,
                        skeleton_candidates=candidates,
                        generation_contexts=generation_contexts,
                        return_meta=True,
                    )
                except Exception as exc:  # noqa: BLE001 — soft-fail generation
                    logger.warning(
                        "counterfactual_generation_failed analysis_id=%s error=%s",
                        analysis_id,
                        type(exc).__name__,
                    )
                    run.warnings.append(f"generation_failed:{type(exc).__name__}")

            run.candidate_count = len(candidates)
            run.safe_candidate_count = sum(
                1
                for c in candidates
                if c.status
                in {
                    CounterfactualCandidateStatus.READY_FOR_GENERATION,
                    CounterfactualCandidateStatus.READY_FOR_VERIFICATION,
                    CounterfactualCandidateStatus.STRUCTURED,
                }
            )
            run.incomplete_candidate_count = sum(
                1 for c in candidates if c.status == CounterfactualCandidateStatus.INCOMPLETE
            )
            run.rejected_candidate_count = sum(
                1
                for c in candidates
                if c.status
                in {
                    CounterfactualCandidateStatus.REJECTED,
                    CounterfactualCandidateStatus.UNSAFE,
                    CounterfactualCandidateStatus.INVALID,
                }
            )

            if not candidates:
                run.status = CounterfactualRemediationRunStatus.NO_SAFE_CANDIDATES
            elif run.warnings or run.incomplete_candidate_count:
                run.status = CounterfactualRemediationRunStatus.PARTIAL
            else:
                run.status = CounterfactualRemediationRunStatus.COMPLETE

            run.configuration_snapshot["candidate_summaries"] = [c.to_dict() for c in candidates]
            run.configuration_snapshot["constraint_count"] = len(all_constraints)
            run.configuration_snapshot["persist_pending"] = self._persist.enabled
            # Transient payload for run_async persistence (not serialised to options).
            self._last_persist_payload = {
                "run": run,
                "candidates": candidates,
                "constraints": all_constraints,
                "preconditions": all_preconditions,
            }
            return self._finalize(run, started)
        except Exception as exc:  # noqa: BLE001 — soft-fail stage
            logger.warning(
                "counterfactual_foundation_failed analysis_id=%s error=%s",
                analysis_id,
                type(exc).__name__,
            )
            run.status = CounterfactualRemediationRunStatus.FAILED
            run.errors.append(f"foundation_failed:{type(exc).__name__}")
            self._last_persist_payload = {
                "run": run,
                "candidates": [],
                "constraints": [],
                "preconditions": [],
            }
            return self._finalize(run, started)

    async def run_async(
        self,
        *,
        organization_id: str,
        analysis_id: str,
        options: dict[str, Any] | None = None,
        project_id: str | None = None,
        incident_id: str | None = None,
        eligibility_results: list[HypothesisEligibilityResult] | dict[str, Any] | None = None,
    ) -> CounterfactualRemediationRun:
        self._last_persist_payload = {}
        run = self.run(
            organization_id=organization_id,
            analysis_id=analysis_id,
            options=options,
            project_id=project_id,
            incident_id=incident_id,
            eligibility_results=eligibility_results,
        )
        try:
            payload = dict(self._last_persist_payload or {})
            payload.setdefault("run", run)
            await self._persist.persist_foundation_result(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("counterfactual_persist_failed error=%s", type(exc).__name__)
            run.warnings.append("persist_failed")
        return run

    def _master_enabled(self) -> bool:
        return _flag(
            self._settings,
            "counterfactual_remediation_enabled",
            bool(self._bounds.get("enabled", False)),
        )

    def _config_snapshot(self) -> dict[str, Any]:
        return {
            "counterfactual_remediation_enabled": self._master_enabled(),
            "constraint_extraction_enabled": _flag(
                self._settings,
                "counterfactual_constraint_extraction_enabled",
                self._bounds.get("constraint_extraction_enabled", True),
            ),
            "minimal_change_planning_enabled": _flag(
                self._settings,
                "minimal_change_planning_enabled",
                self._bounds.get("planning_enabled", True),
            ),
            "template_registry_enabled": _flag(
                self._settings,
                "counterfactual_template_registry_enabled",
                self._bounds.get("template_registry_enabled", True),
            ),
            "persistence_enabled": self._persist.enabled,
            "llm_remediation_generation_enabled": _flag(
                self._settings, "llm_remediation_generation_enabled", False
            ),
            "rule_remediation_generation_enabled": _flag(
                self._settings, "rule_remediation_generation_enabled", False
            ),
            "remediation_risk_analysis_enabled": _flag(
                self._settings, "remediation_risk_analysis_enabled", False
            ),
            "remediation_side_effect_analysis_enabled": _flag(
                self._settings, "remediation_side_effect_analysis_enabled", False
            ),
            "remediation_ranking_enabled": _flag(
                self._settings, "remediation_ranking_enabled", False
            ),
            "remediation_deduplication_enabled": _flag(
                self._settings, "remediation_deduplication_enabled", False
            ),
            "remediation_diversity_enabled": _flag(
                self._settings, "remediation_diversity_enabled", False
            ),
            "remediation_patch_rendering_enabled": _flag(
                self._settings, "remediation_patch_rendering_enabled", False
            ),
            "remediation_rollback_generation_enabled": _flag(
                self._settings, "remediation_rollback_generation_enabled", False
            ),
            "remediation_reference_validation_enabled": _flag(
                self._settings, "remediation_reference_validation_enabled", False
            ),
            "remediation_constraint_validation_enabled": _flag(
                self._settings, "remediation_constraint_validation_enabled", False
            ),
        }

    def _load_hypotheses(self, options: dict[str, Any]) -> list[dict[str, Any]]:
        raw = options.get("causal_hypotheses") or options.get("hypotheses") or []
        hypotheses: list[dict[str, Any]] = []
        for item in _as_list(raw):
            data = _as_dict(item)
            if not data:
                continue
            hyp_id = str(data.get("id") or data.get("hypothesis_id") or "")
            if not hyp_id:
                continue
            data["id"] = hyp_id
            hypotheses.append(data)
        hypotheses.sort(key=lambda h: (str(h.get("rank") or 999), h["id"]))
        return hypotheses

    def _filter_eligible(
        self,
        hypotheses: list[dict[str, Any]],
        eligibility_results: list[HypothesisEligibilityResult] | dict[str, Any] | None,
        options: dict[str, Any],
    ) -> list[dict[str, Any]]:
        by_id: dict[str, HypothesisEligibilityStatus] = {}
        if isinstance(eligibility_results, list):
            for result in eligibility_results:
                status = result.status
                hid = result.hypothesis_id or ""
                by_id[hid] = (
                    status
                    if isinstance(status, HypothesisEligibilityStatus)
                    else HypothesisEligibilityStatus(str(status))
                )
        elif isinstance(eligibility_results, dict):
            for key, value in eligibility_results.items():
                if isinstance(value, HypothesisEligibilityResult):
                    by_id[key] = value.status
                elif isinstance(value, dict) and "status" in value:
                    by_id[key] = HypothesisEligibilityStatus(str(value["status"]))
                else:
                    by_id[key] = HypothesisEligibilityStatus(str(value))

        assessment = _as_dict(options.get("hypothesis_evidence_assessment"))
        selection = _as_dict(assessment.get("candidate_selection"))
        selected_ids = {
            str(x)
            for x in _as_list(
                selection.get("selected_hypothesis_ids")
                or selection.get("top_hypothesis_ids")
                or []
            )
        }

        eligible: list[dict[str, Any]] = []
        for hyp in hypotheses:
            hyp_id = hyp["id"]
            if hyp_id in by_id:
                status = by_id[hyp_id]
                if status in {
                    HypothesisEligibilityStatus.ELIGIBLE,
                    HypothesisEligibilityStatus.ELIGIBLE_WITH_WARNINGS,
                    HypothesisEligibilityStatus.INCOMPLETE,
                }:
                    eligible.append(hyp)
                continue
            status_text = str(hyp.get("selection_status") or "").upper()
            if (
                selected_ids
                and hyp_id in selected_ids
                or status_text in {"SELECTED", "TOP", "TIE", "ELIGIBLE"}
            ):
                eligible.append(hyp)
            elif not selected_ids and not by_id:
                continue
        return eligible

    def _process_hypothesis(
        self,
        *,
        run: CounterfactualRemediationRun,
        hypothesis: dict[str, Any],
        options: dict[str, Any],
        organization_id: str,
        analysis_id: str,
        project_id: str,
        incident_id: str,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        context = self._context_builder.build_from_analysis_options(
            organization_id=organization_id,
            analysis_id=analysis_id,
            hypothesis=hypothesis,
            options=options,
            project_id=project_id,
            incident_id=incident_id,
        )
        entities = list(context.parser_entities)
        artifact_meta: dict[str, Any] = {}
        if context.affected_artifact:
            artifact_meta["artifact_id"] = context.affected_artifact
        if context.source_path:
            artifact_meta["source_path"] = context.source_path
        # Recover type hints from hypothesis affected artifact dict when present.
        affected_raw = hypothesis.get("affected_artifact")
        if isinstance(affected_raw, dict):
            artifact_meta.update(
                {
                    k: v
                    for k, v in affected_raw.items()
                    if k
                    in {
                        "artifact_id",
                        "artifact_type",
                        "kind",
                        "type",
                        "source_path",
                        "path",
                        "commit_sha",
                    }
                }
            )

        current_state = self._current_state_builder.build(
            entities=entities,
            artifact_metadata=artifact_meta,
            source_fragment=context.current_configuration_fragment,
            failure_condition=context.failure_condition_summary,
            organization_id=organization_id,
        )

        constraint_enabled = _flag(
            self._settings,
            "counterfactual_constraint_extraction_enabled",
            self._bounds.get("constraint_extraction_enabled", True),
        )
        constraint_set = self._constraint_orchestrator.run(
            context,
            current_state,
            enabled=constraint_enabled,
        )
        conflicts = self._conflict_detector.detect(
            constraint_set,
            current_state=current_state,
            artifact_available=bool(
                current_state.artifact_id
                or current_state.structured_entities
                or current_state.source_fragment
            ),
            rollback_available=True,
        )
        preconditions = build_counterfactual_preconditions(context, current_state)
        failure_condition = build_counterfactual_failure_condition(context, current_state)
        objective = build_minimal_change_objective(
            context,
            current_state,
            maximum_files=_bound(
                self._settings,
                "max_patch_files_per_candidate",
                self._bounds.get("max_patch_files", 5),
            ),
            maximum_changed_lines=_bound(
                self._settings,
                "max_changed_lines_per_candidate",
                self._bounds.get("max_changed_lines", 200),
            ),
        )

        templates: list[Any] = []
        if _flag(
            self._settings,
            "counterfactual_template_registry_enabled",
            self._bounds.get("template_registry_enabled", True),
        ):
            artifact_type = current_state.artifact_type
            artifact_type = (
                str(artifact_type.value)  # type: ignore[union-attr]
                if hasattr(artifact_type, "value")
                else str(artifact_type or "")
            )
            templates = self._registry.resolve(
                category=context.category,
                artifact_type=artifact_type,
                hypothesis_text=context.causal_claim,
            )

        planning_enabled = _flag(
            self._settings,
            "minimal_change_planning_enabled",
            self._bounds.get("planning_enabled", True),
        )
        plan = self._planner.plan(
            context,
            current_state,
            constraint_set,
            preconditions,
            failure_condition,
            objective,
            templates,
            conflicts=conflicts,
            enabled=planning_enabled,
        )

        candidates: list[CounterfactualRemediationCandidate] = []
        max_candidates = _bound(
            self._settings,
            "max_remediation_candidates_per_hypothesis",
            self._bounds.get("max_candidates_per_hypothesis", 3),
        )
        if plan.status in {
            MinimalChangePlanStatus.READY_FOR_GENERATION,
            MinimalChangePlanStatus.INCOMPLETE,
        }:
            for template in templates[:max_candidates]:
                candidate = self._build_candidate_skeleton(
                    run=run,
                    context=context,
                    current_state=current_state,
                    failure_condition=failure_condition,
                    plan=plan,
                    template=template,
                    constraint_set=constraint_set,
                )
                validation = self._validator.validate(
                    candidate,
                    context=context,
                    current_state=current_state,
                    constraint_set=constraint_set,
                    template=template,
                    precondition_statuses=[p.status for p in preconditions],
                )
                if validation.status.value in {"INVALID", "UNSAFE", "BLOCKED"}:
                    candidate.status = CounterfactualCandidateStatus.REJECTED
                    warnings.append(
                        f"candidate_rejected:{candidate.candidate_key}:{validation.status.value}"
                    )
                elif plan.status == MinimalChangePlanStatus.INCOMPLETE:
                    candidate.status = CounterfactualCandidateStatus.INCOMPLETE
                else:
                    candidate.status = CounterfactualCandidateStatus.READY_FOR_GENERATION
                candidates.append(candidate)
        elif plan.status == MinimalChangePlanStatus.BLOCKED_BY_CONSTRAINTS:
            warnings.append(f"hypothesis_blocked:{context.hypothesis_id}")
        elif plan.status == MinimalChangePlanStatus.NO_SAFE_CHANGE:
            warnings.append(f"no_safe_change:{context.hypothesis_id}")

        if any(c.must_stop_generation for c in conflicts):
            warnings.append(f"conflicts_stop_generation:{context.hypothesis_id}")

        generation_context = build_generation_context_from_foundation(
            run=run,
            context=context,
            current_state=current_state,
            constraint_set=constraint_set,
            plan=plan,
            objective=objective,
            templates=templates,
            conflicts=conflicts,
        )

        return {
            "candidates": candidates,
            "constraints": list(constraint_set.constraints),
            "preconditions": list(preconditions),
            "warnings": warnings,
            "plan_status": plan.status.value,
            "generation_context": generation_context,
        }

    def _build_candidate_skeleton(
        self,
        *,
        run: CounterfactualRemediationRun,
        context: Any,
        current_state: Any,
        failure_condition: Any,
        plan: Any,
        template: Any,
        constraint_set: Any,
    ) -> CounterfactualRemediationCandidate:
        candidate_id = str(uuid4())
        verifiers = [
            RemediationVerificationRequirement(
                requirement_id=str(uuid4()),
                candidate_id=candidate_id,
                verifier_type=_coerce_verifier(v),
                required=True,
                reason="part_1_reserved_verifier",
                expected_check="structural_or_static_check",
                expected_success_condition="not_executed_in_part_1",
            )
            for v in (template.default_verification_requirements or [])
        ]
        if not verifiers:
            verifiers = [
                RemediationVerificationRequirement(
                    requirement_id=str(uuid4()),
                    candidate_id=candidate_id,
                    verifier_type=VerifierType.COUNTERFACTUAL_FAILURE_CONDITION,
                    required=True,
                    reason="default_failure_condition_check",
                )
            ]
        rollback = RemediationRollbackPlan(
            candidate_id=candidate_id,
            rollback_type=(
                template.default_rollback_strategy
                if isinstance(template.default_rollback_strategy, RollbackType)
                else RollbackType.RESTORE_ORIGINAL_FRAGMENT
            ),
            original_content_hashes=[h for h in [current_state.content_hash] if h],
            affected_artifacts=[a for a in [current_state.artifact_id] if a],
            rollback_steps=[
                {
                    "step": 1,
                    "action": "restore_original_fragment",
                    "content_hash": current_state.content_hash,
                }
            ],
            can_restore_exactly=bool(current_state.content_hash),
            rollback_limitations=["no_shell_commands", "structured_steps_only"],
        )
        return CounterfactualRemediationCandidate(
            id=candidate_id,
            remediation_run_id=run.id,
            organization_id=context.organization_id,
            project_id=context.project_id or "",
            incident_id=context.incident_id or "",
            analysis_id=context.analysis_id,
            hypothesis_id=context.hypothesis_id,
            candidate_key=f"{context.hypothesis_id}:{template.template_id}",
            title=f"Skeleton: {template.template_id}",
            summary=(
                f"Part 1 candidate skeleton for hypothesis {context.hypothesis_id} "
                f"using template {template.template_id}. Not verified. No final patch."
            ),
            artifact_type=current_state.artifact_type,
            affected_artifact_ids=[a for a in [current_state.artifact_id] if a],
            primary_artifact_id=current_state.artifact_id,
            target_paths=[p for p in [current_state.source_path or context.source_path] if p],
            change_types=list(plan.proposed_change_types),
            current_state_snapshot=current_state,
            counterfactual_state_snapshot={
                "expected_failure_condition_status": "EXPECTED_REMOVED",
                "proposed_values": {},
                "assumptions": ["skeleton_only"],
                "unknown_effects": ["runtime_effects_unknown"],
            },
            expected_effects=list(plan.expected_effects)[:20],
            expected_preserved_behaviors=list(plan.expected_preserved_behaviors)[:20],
            expected_failure_condition=failure_condition,
            assumptions=["part_1_skeleton_only", "builder_unimplemented"],
            limitations=[
                "candidate_is_not_verified",
                "candidate_is_not_applied",
                "part_1_skeleton_only",
            ],
            constraints=list(constraint_set.constraints[:50]),
            unsatisfied_constraints=list(constraint_set.blocking_constraints[:50]),
            verification_requirements=verifiers,
            rollback_plan=rollback,
            generator_type="deterministic_skeleton",
            generator_name="minimal_change_planner",
            generator_version=MINIMAL_CHANGE_PLANNER_VERSION,
            template_id=template.template_id,
            template_version=template.template_version,
            status=CounterfactualCandidateStatus.DRAFT,
        )

    def _finalize(
        self,
        run: CounterfactualRemediationRun,
        started: datetime,
    ) -> CounterfactualRemediationRun:
        now = datetime.now(UTC)
        run.updated_at = now
        run.completed_at = now
        run.duration_ms = int((now - started).total_seconds() * 1000)
        logger.debug(
            "counterfactual_foundation_complete analysis_id=%s status=%s duration_ms=%s",
            run.analysis_id,
            run.status.value,
            run.duration_ms,
        )
        return run
