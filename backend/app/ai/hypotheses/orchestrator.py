"""Competing causal hypothesis orchestrator (Phase 6A.4)."""

from __future__ import annotations

import time
from typing import Any

from app.ai.hypotheses.dedupe_critic import (
    CausalHypothesisCritic,
    GenerationPriorScorer,
    HypothesisDeduplicator,
    hypothesis_fingerprint,
)
from app.ai.hypotheses.graph_context import HypothesisGraphContextExtractor
from app.ai.hypotheses.llm_generator import HYPOTHESIS_PROMPT_VERSION, LLMCausalHypothesisGenerator
from app.ai.hypotheses.rule_generator import RuleBasedHypothesisGenerator
from app.ai.hypotheses.validators import HypothesisCausalPathValidator, HypothesisReferenceValidator
from app.ai.orchestration.analysis_context import AnalysisContext
from app.domain.hypotheses.enums import HypothesisRunStatus, HypothesisStatus
from app.domain.hypotheses.models import CausalHypothesisRun, HypothesisGenerationContext


class CausalHypothesisOrchestrator:
    def __init__(
        self,
        *,
        enabled: bool = False,
        rule_enabled: bool = False,
        llm_enabled: bool = False,
        critic_enabled: bool = False,
        max_hypotheses: int = 5,
        min_hypotheses: int = 1,
        graph_max_depth: int = 4,
        graph_max_nodes: int = 100,
        graph_max_edges: int = 200,
        max_evidence_items: int = 40,
        duplicate_similarity_threshold: float = 0.92,
        llm_complete_json: Any | None = None,
    ) -> None:
        self._enabled = enabled
        self._rule_enabled = rule_enabled
        self._llm_enabled = llm_enabled
        self._critic_enabled = critic_enabled
        self._max = max_hypotheses
        self._min = min_hypotheses
        self._max_evidence = max_evidence_items
        self._graph = HypothesisGraphContextExtractor(
            max_depth=graph_max_depth,
            max_nodes=graph_max_nodes,
            max_edges=graph_max_edges,
        )
        self._rules = RuleBasedHypothesisGenerator(
            enabled=rule_enabled, max_hypotheses=max_hypotheses
        )
        self._llm = LLMCausalHypothesisGenerator(
            enabled=llm_enabled,
            complete_json=llm_complete_json,
            max_hypotheses=max_hypotheses,
        )
        self._ref_validator = HypothesisReferenceValidator()
        self._path_validator = HypothesisCausalPathValidator()
        self._deduper = HypothesisDeduplicator(
            similarity_threshold=duplicate_similarity_threshold
        )
        self._critic = CausalHypothesisCritic(enabled=critic_enabled)
        self._prior = GenerationPriorScorer()

    def run(
        self,
        context: AnalysisContext,
        *,
        graph_nodes: list[dict[str, Any]] | None = None,
        graph_edges: list[dict[str, Any]] | None = None,
    ) -> CausalHypothesisRun:
        started = time.perf_counter()
        org_id = str(context.organization_id or "")
        run = CausalHypothesisRun(
            analysis_id=str(context.analysis_run_id),
            organization_id=org_id,
            project_id=str(context.options.get("project_id") or "") or None,
            incident_id=str(context.incident_id) if context.incident_id else None,
            prompt_version=HYPOTHESIS_PROMPT_VERSION if self._llm_enabled else None,
        )
        if not self._enabled or not org_id:
            run.status = HypothesisRunStatus.DISABLED
            run.duration_ms = int((time.perf_counter() - started) * 1000)
            return run

        try:
            gen_ctx = self._build_context(
                context, graph_nodes=graph_nodes or [], graph_edges=graph_edges or []
            )
            run.truncation_notes = list(gen_ctx.truncation_notes)

            rule_hyps = self._rules.generate(gen_ctx) if self._rule_enabled else []
            run.deterministic_count = len(rule_hyps)

            llm_hyps: list = []
            if self._llm_enabled:
                llm_hyps, llm_errors, usage = self._llm.generate(gen_ctx)
                run.llm_count = len(llm_hyps)
                run.token_usage = usage
                run.warnings.extend(llm_errors)

            combined = rule_hyps + llm_hyps
            validated = []
            invalid = 0
            for hyp in combined:
                ref = self._ref_validator.validate(hyp, gen_ctx)
                if not ref.accepted:
                    invalid += 1
                    continue
                hyp = self._path_validator.validate(ref.hypothesis, gen_ctx)
                validated.append(hyp)
            run.invalid_reference_count = invalid

            deduped, removed = self._deduper.deduplicate(validated)
            run.duplicate_removed_count = removed

            # Critic + prior
            finals = []
            for hyp in deduped:
                if self._critic_enabled:
                    hyp.critic = self._critic.critique(hyp, gen_ctx)
                    hyp.status = hyp.critic.recommended_status
                else:
                    if hyp.status == HypothesisStatus.GENERATED:
                        hyp.status = HypothesisStatus.READY_FOR_RANKING
                hyp.generation_prior_score = self._prior.score(hyp, gen_ctx)
                finals.append(hyp)

            # Prefer READY/INCOMPLETE over REJECTED/DUPLICATE; bound max.
            finals.sort(key=lambda h: h.generation_prior_score, reverse=True)
            kept = [
                h
                for h in finals
                if h.status
                not in {
                    HypothesisStatus.INVALID,
                    HypothesisStatus.DUPLICATE,
                    HypothesisStatus.REJECTED,
                    HypothesisStatus.FAILED,
                }
            ][: self._max]
            if len(kept) < self._min and finals:
                # Keep best incomplete if nothing ready.
                kept = finals[: max(self._min, 1)]

            for idx, hyp in enumerate(kept, start=1):
                hyp.rank_placeholder = idx
                hyp.hypothesis_key = f"H{idx}"
            run.hypotheses = kept
            run.status = (
                HypothesisRunStatus.PARTIAL
                if run.warnings or invalid or removed
                else HypothesisRunStatus.COMPLETED
            )
            if not kept and (rule_hyps or llm_hyps):
                run.status = HypothesisRunStatus.PARTIAL
                run.warnings.append("all_candidates_rejected_or_deduplicated")
        except Exception as exc:  # noqa: BLE001
            run.status = HypothesisRunStatus.FAILED
            run.warnings.append(f"hypothesis_pipeline_failed:{type(exc).__name__}")

        run.duration_ms = int((time.perf_counter() - started) * 1000)
        return run

    def _build_context(
        self,
        context: AnalysisContext,
        *,
        graph_nodes: list[dict[str, Any]],
        graph_edges: list[dict[str, Any]],
    ) -> HypothesisGenerationContext:
        temporal = context.options.get("temporal_localisation") or {}
        if not isinstance(temporal, dict):
            temporal = {}
        hier = context.options.get("hierarchical_classification") or {}
        if not isinstance(hier, dict):
            hier = {}
        graph_meta = context.options.get("evidence_graph") or {}
        if not isinstance(graph_meta, dict):
            graph_meta = {}
        bundle = context.options.get("artifact_bundle") or {}
        if not isinstance(bundle, dict):
            bundle = {}

        seeds: list[str] = []
        if temporal.get("primary_failure_event_id"):
            seeds.append(str(temporal["primary_failure_event_id"]))
        nodes, edges, notes = self._graph.extract(
            nodes=graph_nodes,
            edges=graph_edges,
            seed_keys=seeds,
            consistency_warnings=list(graph_meta.get("warnings") or [])[:5],
        )

        evidence = []
        for idx, item in enumerate(context.evidence[: self._max_evidence], start=1):
            evidence.append(
                {
                    "id": getattr(item, "metadata", {}).get("evidence_id")
                    if isinstance(getattr(item, "metadata", None), dict)
                    else f"evidence-{idx}",
                    "evidence_type": getattr(item, "evidence_type", None),
                    "excerpt": getattr(item, "normalized_excerpt", None)
                    or getattr(item, "raw_excerpt", None),
                    "source_path": getattr(item, "source_name", None),
                    "line_start": getattr(item, "line_start", None),
                    "line_end": getattr(item, "line_end", None),
                }
            )

        primary = context.classifications[0] if context.classifications else None
        text = (context.combined_text or "")[:8000]
        return HypothesisGenerationContext(
            analysis_id=str(context.analysis_run_id),
            organization_id=str(context.organization_id),
            project_id=str(context.options.get("project_id") or "") or None,
            incident_id=str(context.incident_id) if context.incident_id else None,
            hierarchical_classification=dict(hier),
            top_classification_candidates=[
                {
                    "category_code": c.category_code,
                    "confidence": c.confidence,
                    "rank": c.rank,
                    "matched_rules": list(c.matched_rules),
                }
                for c in context.classifications[:5]
            ],
            open_set_status=hier.get("open_set_status"),
            disagreement_result={
                "agreement_level": hier.get("disagreement_level"),
            },
            temporal_primary_failure=dict(temporal),
            downstream_symptom_summary=list(temporal.get("warnings") or [])[:8],
            graph_consistency_status=graph_meta.get("consistency_status"),
            relevant_graph_nodes=nodes,
            relevant_graph_edges=edges,
            artifact_availability=list(bundle.get("available_artifacts") or [])[:40],
            missing_artifacts=list(bundle.get("missing_artifacts") or [])[:20],
            evidence_candidates=evidence,
            previous_diagnosis_summary=primary.root_cause_summary if primary else None,
            combined_text_excerpt=text,
            truncation_notes=notes,
            parser_novel_signature=bool(
                context.options.get("novel_tool_signature")
                or context.options.get("parser_novel_signature")
            ),
        )


# Re-export fingerprint helper for persistence.
__all__ = ["CausalHypothesisOrchestrator", "hypothesis_fingerprint"]
