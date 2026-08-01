"""Orchestrate Phase 6A.6 Part 2 remediation generation (no verify/apply)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.ai.counterfactual_remediation.generation._helpers import (
    as_dict,
    as_list,
    bound_float,
    bound_int,
    flag,
    first_str,
)
from app.ai.counterfactual_remediation.generation.blast_radius import (
    RemediationBlastRadiusEstimator,
)
from app.ai.counterfactual_remediation.generation.constraint_validator import (
    RemediationConstraintValidator,
)
from app.ai.counterfactual_remediation.generation.deduplicator import (
    RemediationCandidateDeduplicator,
)
from app.ai.counterfactual_remediation.generation.diversity import (
    RemediationCandidateDiversitySelector,
)
from app.ai.counterfactual_remediation.generation.historical_adapter import (
    HistoricalRemediationAdapter,
)
from app.ai.counterfactual_remediation.generation.llm_generator import (
    LLMCounterfactualRemediationGenerator,
    LlmCall,
)
from app.ai.counterfactual_remediation.generation.patch_renderer import RemediationPatchRenderer
from app.ai.counterfactual_remediation.generation.previous_success import (
    PreviousSuccessRemediationGenerator,
)
from app.ai.counterfactual_remediation.generation.prioritiser import (
    RemediationCandidatePrioritiser,
)
from app.ai.counterfactual_remediation.generation.reference_validator import (
    RemediationReferenceValidator,
)
from app.ai.counterfactual_remediation.generation.risk_analyzer import RemediationRiskAnalyzer
from app.ai.counterfactual_remediation.generation.rollback_generator import (
    RemediationRollbackGenerator,
)
from app.ai.counterfactual_remediation.generation.rule_generator import (
    RuleBasedRemediationGenerator,
)
from app.ai.counterfactual_remediation.generation.side_effects import (
    RemediationSideEffectAnalyzer,
)
from app.domain.counterfactual_remediation.enums import (
    CounterfactualCandidateStatus,
    CounterfactualRemediationRunStatus,
)
from app.domain.counterfactual_remediation.generation_enums import (
    ConstraintValidationStatus,
    RemediationGenerationStatus,
    RiskLevel,
)
from app.domain.counterfactual_remediation.generation_models import (
    PrioritisationResult,
    RemediationGenerationContext,
)
from app.domain.counterfactual_remediation.models import (
    CounterfactualRemediationCandidate,
    CounterfactualRemediationRun,
)

logger = logging.getLogger(__name__)


class CounterfactualRemediationGenerationService:
    """Flag-gated Part 2 generation orchestrator. Soft-fail per candidate."""

    def __init__(
        self,
        settings: Any = None,
        *,
        llm_call: LlmCall | None = None,
        persist_service: Any = None,
    ) -> None:
        self._settings = settings
        self._llm_call = llm_call
        self._persist = persist_service
        self._rule = RuleBasedRemediationGenerator(
            enabled=flag(settings, "rule_remediation_generation_enabled", False),
            max_candidates=bound_int(settings, "max_rule_candidates_per_hypothesis", 3),
        )
        self._previous = PreviousSuccessRemediationGenerator(
            enabled=flag(settings, "rule_remediation_generation_enabled", False),
        )
        self._historical = HistoricalRemediationAdapter(
            enabled=flag(settings, "rule_remediation_generation_enabled", False),
        )
        self._llm = LLMCounterfactualRemediationGenerator(
            enabled=flag(settings, "llm_remediation_generation_enabled", False),
            llm_call=llm_call,
            max_candidates=bound_int(settings, "max_llm_candidates_per_hypothesis", 2),
            max_calls=bound_int(settings, "max_remediation_llm_calls_per_analysis", 3),
        )
        self._refs = RemediationReferenceValidator()
        self._patch = RemediationPatchRenderer(
            max_patch_characters=bound_int(settings, "max_candidate_patch_characters", 30_000),
            max_changed_lines=bound_int(settings, "max_candidate_changed_lines", 200),
        )
        self._constraints = RemediationConstraintValidator()
        self._risk = RemediationRiskAnalyzer()
        self._blast = RemediationBlastRadiusEstimator()
        self._side = RemediationSideEffectAnalyzer()
        self._rollback = RemediationRollbackGenerator(
            max_steps=bound_int(settings, "max_rollback_steps_per_candidate", 20),
        )
        self._dedupe = RemediationCandidateDeduplicator(
            similarity_threshold=bound_float(
                settings, "remediation_duplicate_similarity_threshold", 0.88
            ),
        )
        self._diversity = RemediationCandidateDiversitySelector(
            max_total=bound_int(settings, "max_total_final_candidates", 8),
        )
        self._prioritiser = RemediationCandidatePrioritiser()
        self._high_risk = bound_float(settings, "remediation_high_risk_threshold", 0.70)
        self._reject_risk = bound_float(settings, "remediation_reject_risk_threshold", 0.90)
        self._tie_epsilon = bound_float(settings, "remediation_tie_epsilon", 0.02)

    def any_generation_enabled(self) -> bool:
        return flag(self._settings, "rule_remediation_generation_enabled", False) or flag(
            self._settings, "llm_remediation_generation_enabled", False
        )

    def run(
        self,
        run: CounterfactualRemediationRun | None = None,
        options: dict[str, Any] | None = None,
        *,
        foundation_candidates: list[CounterfactualRemediationCandidate] | None = None,
        skeleton_candidates: list[CounterfactualRemediationCandidate] | None = None,
        generation_contexts: list[RemediationGenerationContext] | None = None,
        return_meta: bool | None = None,
    ) -> Any:
        """Generate candidates.

        Return styles:
        - `(candidates, meta)` when `return_meta=True` or skeleton/generation_contexts kwargs used
        - `(run, candidates)` otherwise (analysis-execution / run_async path)
        """
        del options  # clients cannot enable generation by request options alone
        skeletons = list(foundation_candidates or skeleton_candidates or [])
        contexts = list(generation_contexts or [])
        if return_meta is None:
            return_meta = False

        if run is None:
            raise ValueError("run_required")

        if not self.any_generation_enabled():
            meta = {
                "generation_enabled": False,
                "status": RemediationGenerationStatus.DISABLED.value,
                "warnings": ["remediation_generation_disabled"],
                "errors": [],
            }
            if "remediation_generation_disabled" not in run.warnings:
                run.warnings.append("remediation_generation_disabled")
            if return_meta:
                return [], meta
            return run, []

        started = datetime.now(UTC)
        meta: dict[str, Any] = {
            "generation_enabled": True,
            "generator_results": [],
            "prioritisation": None,
            "warnings": [],
            "errors": [],
        }
        generated: list[CounterfactualRemediationCandidate] = []
        contexts_by_hyp = {c.hypothesis_id: c for c in contexts}

        if not contexts and skeletons:
            for cand in skeletons:
                if cand.hypothesis_id in contexts_by_hyp:
                    continue
                thin = RemediationGenerationContext(
                    organization_id=cand.organization_id,
                    project_id=cand.project_id,
                    incident_id=cand.incident_id,
                    analysis_id=cand.analysis_id,
                    hypothesis_id=cand.hypothesis_id,
                    remediation_run_id=run.id,
                    current_state=cand.current_state_snapshot,
                    valid_artifact_ids=list(cand.affected_artifact_ids),
                    valid_template_ids=[t for t in [cand.template_id] if t],
                )
                contexts.append(thin)
                contexts_by_hyp[cand.hypothesis_id] = thin

        for context in contexts:
            try:
                generated.extend(self._generate_for_context(context, meta))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "generation_hypothesis_failed hypothesis_id=%s error=%s",
                    context.hypothesis_id,
                    type(exc).__name__,
                )
                meta["errors"].append(
                    f"hypothesis_generation_failed:{context.hypothesis_id}:{type(exc).__name__}"
                )

        enriched: list[CounterfactualRemediationCandidate] = []
        for candidate in generated:
            try:
                ctx = contexts_by_hyp.get(candidate.hypothesis_id)
                if ctx is None:
                    meta["warnings"].append(f"missing_context:{candidate.id}")
                    continue
                processed = self._enrich_candidate(candidate, ctx)
                if processed is not None:
                    enriched.append(processed)
            except Exception as exc:  # noqa: BLE001
                meta["warnings"].append(
                    f"candidate_enrichment_failed:{candidate.id}:{type(exc).__name__}"
                )

        if flag(self._settings, "remediation_deduplication_enabled", False):
            enriched = self._dedupe.deduplicate(enriched)
        if flag(self._settings, "remediation_diversity_enabled", False):
            enriched = self._diversity.select(enriched)

        prioritisation: PrioritisationResult | None = None
        if flag(self._settings, "remediation_ranking_enabled", False):
            prioritisation = self._prioritiser.prioritise(
                enriched,
                high_risk_threshold=self._high_risk,
                reject_risk_threshold=self._reject_risk,
                tie_epsilon=self._tie_epsilon,
            )
            meta["prioritisation"] = prioritisation.to_dict()
            max_final = bound_int(self._settings, "max_final_candidates_per_hypothesis", 3)
            if prioritisation.selected_for_verification:
                selected_ids = set(prioritisation.selected_for_verification[:max_final])
                for candidate in enriched:
                    if candidate.id in selected_ids:
                        candidate.status = CounterfactualCandidateStatus.READY_FOR_VERIFICATION
        else:
            for candidate in enriched:
                if candidate.status == CounterfactualCandidateStatus.STRUCTURED and candidate.changes:
                    candidate.status = CounterfactualCandidateStatus.READY_FOR_VERIFICATION

        final = self._merge_with_skeletons(skeletons, enriched)
        max_total = bound_int(self._settings, "max_total_final_candidates", 8)
        final = final[:max_total]

        run.warnings.extend(meta.get("warnings") or [])
        run.errors.extend(meta.get("errors") or [])
        self._update_run_counts(run, final, prioritisation)
        meta["status"] = self._overall_status(final, meta).value
        meta["duration_ms"] = int((datetime.now(UTC) - started).total_seconds() * 1000)
        snap = dict(run.configuration_snapshot or {})
        snap["part2_generation_meta"] = {
            k: v for k, v in meta.items() if k != "generator_results"
        }
        snap["part2_generator_result_count"] = len(meta.get("generator_results") or [])
        run.configuration_snapshot = snap
        if return_meta:
            return final, meta
        return run, final

    async def run_async(
        self,
        run: CounterfactualRemediationRun,
        options: dict[str, Any] | None = None,
        *,
        foundation_candidates: list[CounterfactualRemediationCandidate] | None = None,
        generation_contexts: list[RemediationGenerationContext] | None = None,
    ) -> tuple[CounterfactualRemediationRun, list[CounterfactualRemediationCandidate]]:
        result_run, candidates = self.run(
            run,
            options,
            foundation_candidates=foundation_candidates,
            generation_contexts=generation_contexts,
            return_meta=False,
        )
        if self._persist is not None and flag(
            self._settings, "counterfactual_persistence_enabled", False
        ):
            try:
                await self._persist.persist_foundation_result(
                    {
                        "run": result_run,
                        "candidates": candidates,
                        "constraints": [],
                        "preconditions": [],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("generation_persist_failed error=%s", type(exc).__name__)
                result_run.warnings.append("generation_persist_failed")
        return result_run, candidates

    def _generate_for_context(
        self,
        context: RemediationGenerationContext,
        meta: dict[str, Any],
    ) -> list[CounterfactualRemediationCandidate]:
        out: list[CounterfactualRemediationCandidate] = []
        if flag(self._settings, "rule_remediation_generation_enabled", False):
            rule_result = self._rule.generate(context)
            meta["generator_results"].append(rule_result.to_dict())
            out.extend(rule_result.candidates)
            prev = self._previous.generate(context)
            meta["generator_results"].append(prev.to_dict())
            out.extend(prev.candidates)
            hist = self._historical.generate(context)
            meta["generator_results"].append(hist.to_dict())
            out.extend(hist.candidates)
        if flag(self._settings, "llm_remediation_generation_enabled", False):
            llm_result = self._llm.generate(context)
            meta["generator_results"].append(llm_result.to_dict())
            out.extend(llm_result.candidates)
        return out

    def _enrich_candidate(
        self,
        candidate: CounterfactualRemediationCandidate,
        context: RemediationGenerationContext,
    ) -> CounterfactualRemediationCandidate | None:
        if flag(self._settings, "remediation_reference_validation_enabled", False):
            ref_result = self._refs.validate(candidate, context=context)
            if ref_result.get("status") == "REJECTED":
                candidate.status = CounterfactualCandidateStatus.REJECTED
                errors = [str(e) for e in (ref_result.get("errors") or [])][:10]
                candidate.limitations = list(candidate.limitations) + errors
                candidate.validation_status = "REJECTED"
                return candidate
            candidate.validation_status = "VALID"

        if flag(self._settings, "remediation_patch_rendering_enabled", False):
            patched_any = False
            for change in candidate.changes:
                rendered = self._patch.render(
                    original_fragment=change.original_fragment,
                    proposed_fragment=change.proposed_fragment,
                    artifact_type=change.artifact_type or candidate.artifact_type,
                    source_path=change.source_path,
                )
                change.normalized_diff = rendered.normalized_diff
                change.content_hash_before = (
                    rendered.content_hash_before or change.content_hash_before
                )
                change.content_hash_after_candidate = (
                    rendered.content_hash_after or change.content_hash_after_candidate
                )
                if rendered.normalized_diff and not patched_any:
                    candidate.rendered_patch = rendered.normalized_diff
                    candidate.patch_format = (
                        rendered.patch_format.value
                        if hasattr(rendered.patch_format, "value")
                        else str(rendered.patch_format)
                    )
                    candidate.patch_hash = rendered.content_hash_after
                    patched_any = True
                candidate.changed_line_count += int(rendered.changed_line_count or 0)
                if rendered.incomplete:
                    candidate.status = CounterfactualCandidateStatus.INCOMPLETE
                    candidate.limitations = list(candidate.limitations) + rendered.warnings
            paths = {c.source_path for c in candidate.changes if c.source_path}
            candidate.changed_file_count = max(len(paths), len(candidate.target_paths), 1)

        if flag(self._settings, "remediation_constraint_validation_enabled", False):
            validation = self._constraints.validate(
                candidate,
                constraint_set=context.constraint_set,
            )
            candidate.constraint_status = (
                validation.status.value
                if hasattr(validation.status, "value")
                else str(validation.status)
            )
            if validation.status in {
                ConstraintValidationStatus.BLOCKED,
                ConstraintValidationStatus.UNSAFE,
                ConstraintValidationStatus.INVALID,
            }:
                candidate.status = (
                    CounterfactualCandidateStatus.UNSAFE
                    if validation.status == ConstraintValidationStatus.UNSAFE
                    else CounterfactualCandidateStatus.REJECTED
                )
                candidate.limitations = list(candidate.limitations) + validation.blocking_violations
            elif validation.status == ConstraintValidationStatus.INCOMPLETE:
                candidate.status = CounterfactualCandidateStatus.INCOMPLETE

        if flag(self._settings, "remediation_risk_analysis_enabled", False):
            risk = self._risk.analyse(
                candidate,
                high_risk_threshold=self._high_risk,
                reject_risk_threshold=self._reject_risk,
            )
            candidate.risk_summary = list(risk.risk_signals)
            candidate.risk_score = risk.overall_risk_score
            candidate.risk_level = (
                risk.risk_level.value
                if hasattr(risk.risk_level, "value")
                else str(risk.risk_level)
            )
            candidate.risk_components_json = dict(risk.component_scores)
            if risk.risk_level == RiskLevel.CRITICAL or risk.blocking_risks:
                candidate.status = CounterfactualCandidateStatus.REJECTED
                candidate.limitations = list(candidate.limitations) + risk.blocking_risks

            blast = self._blast.estimate(candidate)
            candidate.blast_radius_summary = blast.to_dict()
            candidate.blast_radius = (
                blast.level.value if hasattr(blast.level, "value") else str(blast.level)
            )

        if flag(self._settings, "remediation_side_effect_analysis_enabled", False):
            side = self._side.analyse(candidate)
            candidate.side_effects_json = list(side.potential_side_effects)
            candidate.assumptions = list(candidate.assumptions) + [
                f"side_effect:{s}" for s in side.potential_side_effects[:5]
            ]

        if flag(self._settings, "remediation_rollback_generation_enabled", False):
            candidate.rollback_plan = self._rollback.generate(candidate)

        return candidate

    def _merge_with_skeletons(
        self,
        skeletons: list[CounterfactualRemediationCandidate],
        generated: list[CounterfactualRemediationCandidate],
    ) -> list[CounterfactualRemediationCandidate]:
        if not generated:
            return list(skeletons)
        covered: set[tuple[str, str | None]] = {
            (c.hypothesis_id, c.template_id) for c in generated
        }
        retained = [
            s
            for s in skeletons
            if (s.hypothesis_id, s.template_id) not in covered
            and s.generator_type == "deterministic_skeleton"
        ]
        # Prefer generated; keep uncovered skeletons as incomplete fallbacks.
        return list(generated) + retained

    def _update_run_counts(
        self,
        run: CounterfactualRemediationRun,
        candidates: list[CounterfactualRemediationCandidate],
        prioritisation: PrioritisationResult | None,
    ) -> None:
        run.candidate_count = len(candidates)
        run.safe_candidate_count = sum(
            1
            for c in candidates
            if c.status
            in {
                CounterfactualCandidateStatus.READY_FOR_VERIFICATION,
                CounterfactualCandidateStatus.STRUCTURED,
                CounterfactualCandidateStatus.READY_FOR_GENERATION,
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
        if prioritisation and prioritisation.no_safe_candidate and not candidates:
            run.status = CounterfactualRemediationRunStatus.NO_SAFE_CANDIDATES
        elif run.errors:
            run.status = CounterfactualRemediationRunStatus.FAILED
        elif run.warnings or run.incomplete_candidate_count or run.rejected_candidate_count:
            run.status = CounterfactualRemediationRunStatus.PARTIAL
        elif candidates:
            run.status = CounterfactualRemediationRunStatus.COMPLETE
        else:
            run.status = CounterfactualRemediationRunStatus.NO_SAFE_CANDIDATES

        snap = dict(run.configuration_snapshot or {})
        snap["part2_generation"] = True
        snap["candidate_summaries"] = [c.to_dict() for c in candidates]
        if prioritisation is not None:
            snap["prioritisation"] = prioritisation.to_dict()
        run.configuration_snapshot = snap

    def _overall_status(
        self,
        candidates: list[CounterfactualRemediationCandidate],
        meta: dict[str, Any],
    ) -> RemediationGenerationStatus:
        if meta.get("errors") and not candidates:
            return RemediationGenerationStatus.FAILED
        if not candidates:
            return RemediationGenerationStatus.NO_APPLICABLE_TEMPLATE
        if meta.get("warnings") or any(
            c.status == CounterfactualCandidateStatus.INCOMPLETE for c in candidates
        ):
            return RemediationGenerationStatus.PARTIAL
        return RemediationGenerationStatus.COMPLETE


def build_generation_context_from_foundation(
    *,
    run: CounterfactualRemediationRun,
    context: Any,
    current_state: Any,
    constraint_set: Any,
    plan: Any,
    objective: Any,
    templates: list[Any],
    conflicts: list[Any] | None = None,
) -> RemediationGenerationContext:
    """Helper used by foundation_service to assemble Part 2 context."""
    state = as_dict(current_state)
    hyp_nodes = list(getattr(context, "causal_path_nodes", None) or [])
    evidence_ids: list[str] = []
    for item in as_list(getattr(context, "top_validated_evidence_candidates", None)):
        data = as_dict(item)
        eid = first_str(data.get("id"), data.get("evidence_id"))
        if eid:
            evidence_ids.append(eid)
    artifact_ids = [a for a in [state.get("artifact_id"), getattr(context, "affected_artifact", None)] if a]
    template_ids = [t.template_id for t in templates if getattr(t, "template_id", None)]
    allowed_changes: list[str] = []
    for t in templates:
        ctype = getattr(t, "change_type", None)
        if ctype is not None:
            allowed_changes.append(ctype.value if hasattr(ctype, "value") else str(ctype))
    if plan is not None:
        for ctype in getattr(plan, "proposed_change_types", None) or []:
            allowed_changes.append(ctype.value if hasattr(ctype, "value") else str(ctype))

    blocking = list(getattr(constraint_set, "blocking_constraints", None) or [])
    return RemediationGenerationContext(
        organization_id=run.organization_id,
        project_id=run.project_id,
        incident_id=run.incident_id,
        analysis_id=run.analysis_id,
        hypothesis_id=getattr(context, "hypothesis_id", ""),
        remediation_run_id=run.id,
        hypothesis_key=getattr(context, "hypothesis_key", "") or "",
        causal_claim=getattr(context, "causal_claim", "") or "",
        category=getattr(context, "category", None),
        hierarchy=list(getattr(context, "hierarchy", None) or []),
        ranking_score=getattr(context, "ranking_score", None),
        support_assessment=dict(getattr(context, "support_assessment", None) or {}),
        contradiction_assessment=dict(getattr(context, "contradiction_assessment", None) or {}),
        evidence_sufficiency=getattr(context, "evidence_sufficiency", None),
        critic_decision=dict(getattr(context, "critic_result", None) or {}),
        hypothesis_limitations=list(getattr(context, "hypothesis_limitations", None) or []),
        current_state=current_state,
        source_fragment=getattr(context, "current_configuration_fragment", None)
        or state.get("source_fragment"),
        content_hash=state.get("content_hash"),
        failure_condition_summary=getattr(context, "failure_condition_summary", None),
        parser_entities=list(getattr(context, "parser_entities", None) or []),
        graph_node_ids=list(hyp_nodes),
        graph_edge_ids=list(getattr(context, "causal_path_edges", None) or []),
        constraint_set=constraint_set,
        blocking_constraints=blocking,
        unresolved_conflicts=[as_dict(c) for c in (conflicts or [])],
        objective=objective,
        plan=plan,
        eligible_templates=list(templates),
        verification_requirements=list(getattr(plan, "rollback_requirements", None) or []),
        rollback_requirements=list(getattr(plan, "rollback_requirements", None) or []),
        official_constraints=list(getattr(context, "official_constraints", None) or []),
        support_candidates=list(getattr(context, "support_candidates", None) or []),
        contradiction_candidates=list(getattr(context, "contradiction_candidates", None) or []),
        historical_candidates=list(getattr(context, "historical_candidates", None) or []),
        previous_successful_version=getattr(context, "previous_successful_version", None),
        valid_artifact_ids=[str(a) for a in artifact_ids],
        valid_evidence_ids=evidence_ids,
        valid_graph_node_ids=[str(n) for n in hyp_nodes],
        valid_template_ids=template_ids,
        allowed_change_types=sorted(set(allowed_changes)),
        redaction_status=getattr(context, "redaction_status", None),
        prompt_injection_warnings=list(getattr(context, "prompt_injection_warnings", None) or []),
        excluded_sensitive_fields=list(getattr(context, "excluded_sensitive_fields", None) or []),
        missing_information=list(getattr(context, "missing_information", None) or []),
        warnings=list(getattr(context, "warnings", None) or []),
    )
