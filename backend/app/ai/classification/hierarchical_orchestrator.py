"""Multi-stage hierarchical classification orchestrator (Phase 6A.3).

Extends — does not replace — the existing hybrid classifier. Stages:
A rules → B keyword/learned → C optional LLM (validated) → D open-set →
E disagreement + fusion.
"""

from __future__ import annotations

import time
from typing import Any

from app.ai.classification.confidence_breakdown import ClassificationConfidenceDecomposer
from app.ai.classification.disagreement_analyzer import ClassificationDisagreementAnalyzer
from app.ai.classification.open_set_detector import OpenSetFailureDetector, OpenSetThresholds
from app.ai.orchestration.analysis_context import AnalysisContext, ClassificationCandidate
from app.domain.classification.enums import ClassificationStatus, OpenSetStatus
from app.domain.classification.models import (
    ClassificationCandidateDetail,
    HierarchicalClassificationResult,
    StageClassifierResult,
)
from app.domain.classification.taxonomy_registry import (
    MAPPING_VERSION,
    FailureTaxonomyRegistry,
    get_taxonomy_registry,
)

MAX_TOP_K = 5
MAX_EVIDENCE_IDS = 32


class HierarchicalClassificationOrchestrator:
    """Produce hierarchical / open-set / disagreement outputs from existing signals."""

    def __init__(
        self,
        *,
        registry: FailureTaxonomyRegistry | None = None,
        open_set_thresholds: OpenSetThresholds | None = None,
        hierarchical_enabled: bool = False,
        open_set_enabled: bool = False,
        disagreement_enabled: bool = False,
        confidence_breakdown_enabled: bool = False,
        llm_classification_enabled: bool = False,
    ) -> None:
        self._registry = registry or get_taxonomy_registry()
        self._hierarchical_enabled = hierarchical_enabled
        self._open_set_enabled = open_set_enabled
        self._disagreement_enabled = disagreement_enabled
        self._confidence_breakdown_enabled = confidence_breakdown_enabled
        self._llm_classification_enabled = llm_classification_enabled
        self._open_set = OpenSetFailureDetector(
            registry=self._registry,
            thresholds=open_set_thresholds or OpenSetThresholds(),
            enabled=open_set_enabled,
        )
        self._disagreement = ClassificationDisagreementAnalyzer(
            registry=self._registry,
            enabled=disagreement_enabled,
        )
        self._confidence = ClassificationConfidenceDecomposer(enabled=confidence_breakdown_enabled)

    def run(
        self,
        context: AnalysisContext,
        *,
        llm_candidates: list[dict[str, Any]] | None = None,
    ) -> HierarchicalClassificationResult:
        started = time.perf_counter()
        analysis_id = str(context.analysis_run_id)
        result = HierarchicalClassificationResult(
            analysis_id=analysis_id,
            organization_id=str(context.organization_id) if context.organization_id else None,
            project_id=str(context.options.get("project_id") or "") or None,
            incident_id=str(context.incident_id) if context.incident_id else None,
            mapping_version=MAPPING_VERSION,
            model_versions={
                "classifier": f"{context.model_name}-{context.model_version}",
                "taxonomy": MAPPING_VERSION,
            },
        )

        if not self._hierarchical_enabled:
            result.classification_status = ClassificationStatus.DISABLED
            result.duration_ms = int((time.perf_counter() - started) * 1000)
            return result

        try:
            rule_result = self._stage_rules(context)
            learned_result = self._stage_learned(context)
            llm_result = self._stage_llm(context, llm_candidates=llm_candidates)

            fused_candidates = self._fuse_candidates(rule_result, learned_result, llm_result)
            if not fused_candidates and context.classifications:
                fused_candidates = [
                    self._candidate_from_legacy(c, source="legacy_hybrid")
                    for c in context.classifications[:MAX_TOP_K]
                ]

            evidence_ids = self._collect_evidence_ids(context)
            missing = self._missing_evidence(context)
            evidence_coverage = self._evidence_coverage(context)
            temporal_support, temporal_hint = self._temporal_signals(context)
            graph_support, graph_hint = self._graph_signals(context)

            disagreement = self._disagreement.analyze(
                rule_result=rule_result,
                learned_result=learned_result,
                llm_result=llm_result,
                graph_category_hint=graph_hint,
                temporal_category_hint=temporal_hint,
            )

            open_set = self._open_set.assess(
                candidates=fused_candidates,
                rule_result=rule_result,
                learned_result=learned_result,
                llm_result=llm_result,
                evidence_coverage=evidence_coverage,
                disagreement_level=disagreement.agreement_level.value,
                graph_coverage=graph_support,
                temporal_confidence=temporal_support if temporal_support > 0 else None,
                parser_novel_signature=bool(
                    context.options.get("parser_novel_signature")
                    or context.options.get("novel_tool_signature")
                ),
            )

            breakdown = self._confidence.decompose(
                rule_result=rule_result,
                learned_result=learned_result,
                llm_result=llm_result,
                taxonomy_mapping_ok=bool(
                    fused_candidates
                    and self._registry.is_valid_category(fused_candidates[0].category_code)
                ),
                evidence_coverage=evidence_coverage,
                temporal_support=temporal_support,
                graph_support=graph_support,
                disagreement=disagreement,
                open_set=open_set,
                missing_evidence_count=len(missing),
            )

            final_code, status, final_conf = self._resolve_final(
                fused_candidates=fused_candidates,
                open_set=open_set,
                disagreement=disagreement,
                breakdown_confidence=breakdown.final_confidence,
                legacy=context.classifications[0] if context.classifications else None,
            )
            path = (
                self._registry.map_code(final_code) if final_code else self._registry.unknown_path()
            )

            result.final_legacy_category_code = final_code
            result.level_1_code = path.level_1_code
            result.level_2_code = path.level_2_code
            result.level_3_code = path.level_3_code
            result.classification_status = status
            result.top_candidates = fused_candidates[:MAX_TOP_K]
            result.rule_result = rule_result
            result.learned_result = learned_result
            result.llm_result = llm_result
            result.open_set_result = open_set
            result.disagreement_result = disagreement
            result.confidence_breakdown = breakdown
            result.evidence_ids = evidence_ids[:MAX_EVIDENCE_IDS]
            result.missing_evidence = missing
            result.final_confidence = final_conf
            result.evaluation_export = self._evaluation_export(result, context)
        except Exception as exc:  # noqa: BLE001 - soft-fail enhanced stage
            result.classification_status = ClassificationStatus.FAILED
            result.warnings.append(f"hierarchical_classification_failed:{type(exc).__name__}")
            if context.classifications:
                legacy = context.classifications[0]
                path = self._registry.map_code(legacy.category_code)
                result.final_legacy_category_code = legacy.category_code
                result.level_1_code = path.level_1_code
                result.level_2_code = path.level_2_code
                result.level_3_code = path.level_3_code
                result.final_confidence = float(legacy.confidence)

        result.duration_ms = int((time.perf_counter() - started) * 1000)
        return result

    def _stage_rules(self, context: AnalysisContext) -> StageClassifierResult:
        primary = context.classifications[0] if context.classifications else None
        if primary is None:
            return StageClassifierResult(
                stage="rule",
                executed=False,
                skipped_reason="no_classifications",
            )
        rule_names = [
            r
            for r in primary.matched_rules
            if not r.startswith(("keyword:", "policy:", "fallback:"))
        ]
        # Prefer candidates that have deterministic rules.
        rule_candidates: list[ClassificationCandidateDetail] = []
        for cand in context.classifications:
            det = [
                r
                for r in cand.matched_rules
                if not r.startswith(("keyword:", "policy:", "fallback:"))
            ]
            if det:
                path = self._registry.map_code(cand.category_code)
                rule_candidates.append(
                    ClassificationCandidateDetail(
                        category_code=cand.category_code,
                        level_1_code=path.level_1_code,
                        level_2_code=path.level_2_code,
                        level_3_code=path.level_3_code,
                        score=float(cand.confidence),
                        source_classifier="rule",
                        supporting_evidence=det[:8],
                        rank=len(rule_candidates) + 1,
                        matched_rules=det,
                    )
                )
        top = rule_candidates[0] if rule_candidates else None
        return StageClassifierResult(
            stage="rule",
            category_code=top.category_code if top else None,
            confidence=top.score if top else 0.0,
            top_candidates=rule_candidates[:MAX_TOP_K],
            matched_rules=rule_names,
            model_version=f"{context.model_name}-{context.model_version}",
            limitations=[] if rule_names else ["no_deterministic_rule_match"],
            executed=True,
        )

    def _stage_learned(self, context: AnalysisContext) -> StageClassifierResult:
        """Reuse keyword / hybrid signals as the learned stage (no new ML model)."""
        keyword_candidates: list[ClassificationCandidateDetail] = []
        for cand in context.classifications:
            kw = [r for r in cand.matched_rules if r.startswith("keyword:")]
            # Also include hybrid confidence as representation quality proxy.
            path = self._registry.map_code(cand.category_code)
            keyword_candidates.append(
                ClassificationCandidateDetail(
                    category_code=cand.category_code,
                    level_1_code=path.level_1_code,
                    level_2_code=path.level_2_code,
                    level_3_code=path.level_3_code,
                    score=float(cand.confidence),
                    source_classifier="learned_keyword",
                    supporting_evidence=kw[:8],
                    rank=len(keyword_candidates) + 1,
                    matched_rules=kw or list(cand.matched_rules[:3]),
                )
            )
        if not keyword_candidates:
            return StageClassifierResult(
                stage="learned",
                executed=False,
                skipped_reason="no_classifications",
                limitations=["no_separate_ml_classifier_in_phase_6a3"],
            )
        top = keyword_candidates[0]
        margin = None
        if len(keyword_candidates) > 1:
            margin = round(keyword_candidates[0].score - keyword_candidates[1].score, 4)
        return StageClassifierResult(
            stage="learned",
            category_code=top.category_code,
            confidence=top.score,
            top_candidates=keyword_candidates[:MAX_TOP_K],
            matched_rules=list(top.matched_rules),
            model_version="hybrid-keyword-1.0.0",
            representation_quality=min(1.0, top.score),
            margin=margin,
            limitations=["keyword_proxy_not_trained_embedding_classifier"],
            executed=True,
        )

    def _stage_llm(
        self,
        context: AnalysisContext,
        *,
        llm_candidates: list[dict[str, Any]] | None,
    ) -> StageClassifierResult:
        if not self._llm_classification_enabled:
            return StageClassifierResult(
                stage="llm",
                executed=False,
                skipped_reason="llm_classification_disabled",
            )
        if not context.enable_llm:
            return StageClassifierResult(
                stage="llm",
                executed=False,
                skipped_reason="enable_llm_false",
            )
        # Prefer explicit structured candidates; never invent codes.
        raw_list = llm_candidates or context.options.get("llm_classification_candidates") or []
        if not isinstance(raw_list, list) or not raw_list:
            # Soft reuse of reasoner category only when already a frozen code.
            reasoner_cat = None
            if context.fusion_result:
                reasoner_cat = getattr(context.fusion_result, "category_code", None)
            meta = context.options.get("llm_classification") or {}
            if isinstance(meta, dict) and meta.get("category_code"):
                reasoner_cat = meta.get("category_code")
            if reasoner_cat and self._registry.is_valid_category(str(reasoner_cat)):
                path = self._registry.map_code(str(reasoner_cat))
                detail = ClassificationCandidateDetail(
                    category_code=path.legacy_category_code,
                    level_1_code=path.level_1_code,
                    level_2_code=path.level_2_code,
                    level_3_code=path.level_3_code,
                    score=float(meta.get("confidence", 0.5)) if isinstance(meta, dict) else 0.5,
                    source_classifier="llm",
                    rank=1,
                )
                return StageClassifierResult(
                    stage="llm",
                    category_code=detail.category_code,
                    confidence=detail.score,
                    top_candidates=[detail],
                    model_version=str(context.reasoning_provider_name or "llm"),
                    executed=True,
                )
            return StageClassifierResult(
                stage="llm",
                executed=False,
                skipped_reason="no_llm_classification_candidates",
            )

        validated: list[ClassificationCandidateDetail] = []
        rejected: list[str] = []
        for idx, item in enumerate(raw_list[:MAX_TOP_K]):
            if not isinstance(item, dict):
                rejected.append(f"invalid_item_{idx}")
                continue
            code = str(item.get("category_code") or item.get("category") or "").strip().lower()
            if not self._registry.is_valid_category(code):
                rejected.append(code or f"empty_{idx}")
                continue
            path = self._registry.map_code(code)
            evidence = item.get("evidence_ids") or item.get("supporting_evidence") or []
            if not isinstance(evidence, list):
                evidence = []
            validated.append(
                ClassificationCandidateDetail(
                    category_code=path.legacy_category_code,
                    level_1_code=path.level_1_code,
                    level_2_code=path.level_2_code,
                    level_3_code=path.level_3_code,
                    score=float(item.get("score") or item.get("confidence") or 0.0),
                    source_classifier="llm",
                    supporting_evidence=[str(e) for e in evidence[:8]],
                    rank=len(validated) + 1,
                )
            )
        if not validated:
            return StageClassifierResult(
                stage="llm",
                executed=True,
                category_code=None,
                confidence=0.0,
                limitations=[f"rejected_invalid_codes:{','.join(rejected[:5])}"],
                raw={"rejected": rejected},
            )
        top = validated[0]
        return StageClassifierResult(
            stage="llm",
            category_code=top.category_code,
            confidence=top.score,
            top_candidates=validated,
            evidence_ids=list(top.supporting_evidence),
            model_version=str(context.reasoning_provider_name or "llm"),
            limitations=[f"rejected_invalid_codes:{','.join(rejected)}"] if rejected else [],
            executed=True,
            raw={"rejected": rejected},
        )

    def _fuse_candidates(
        self,
        rule: StageClassifierResult,
        learned: StageClassifierResult,
        llm: StageClassifierResult,
    ) -> list[ClassificationCandidateDetail]:
        """Weighted fusion — not a simple average of all scores."""
        weights = {"rule": 0.5, "learned_keyword": 0.3, "learned": 0.3, "llm": 0.2}
        scores: dict[str, float] = {}
        support: dict[str, list[str]] = {}
        sources: dict[str, set[str]] = {}
        for stage_name, stage, default_source in (
            ("rule", rule, "rule"),
            ("learned", learned, "learned_keyword"),
            ("llm", llm, "llm"),
        ):
            if not stage or not stage.executed:
                continue
            w = weights.get(default_source, 0.2)
            # Prefer stage top candidates; boost deterministic rules.
            for cand in stage.top_candidates or []:
                code = cand.category_code
                if not self._registry.is_valid_category(code):
                    continue
                boost = 1.15 if stage_name == "rule" and cand.matched_rules else 1.0
                scores[code] = max(scores.get(code, 0.0), float(cand.score) * w * boost)
                support.setdefault(code, []).extend(cand.supporting_evidence[:4])
                sources.setdefault(code, set()).add(cand.source_classifier)

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        out: list[ClassificationCandidateDetail] = []
        for idx, (code, score) in enumerate(ranked[:MAX_TOP_K], start=1):
            path = self._registry.map_code(code)
            out.append(
                ClassificationCandidateDetail(
                    category_code=code,
                    level_1_code=path.level_1_code,
                    level_2_code=path.level_2_code,
                    level_3_code=path.level_3_code,
                    score=round(min(0.99, score), 4),
                    source_classifier="+".join(sorted(sources.get(code, {"fusion"}))),
                    supporting_evidence=list(dict.fromkeys(support.get(code, [])))[:8],
                    rank=idx,
                )
            )
        return out

    def _resolve_final(
        self,
        *,
        fused_candidates: list[ClassificationCandidateDetail],
        open_set: Any,
        disagreement: Any,
        breakdown_confidence: float,
        legacy: ClassificationCandidate | None,
    ) -> tuple[str | None, ClassificationStatus, float]:
        from app.domain.classification.enums import AgreementLevel, DisagreementRecommendedAction

        if open_set.status == OpenSetStatus.UNKNOWN:
            return "unknown_failure", ClassificationStatus.UNKNOWN, min(breakdown_confidence, 0.4)

        if disagreement.agreement_level == AgreementLevel.SEVERE:
            if disagreement.recommended_action == DisagreementRecommendedAction.MARK_UNKNOWN:
                return (
                    "unknown_failure",
                    ClassificationStatus.UNKNOWN,
                    min(breakdown_confidence, 0.35),
                )
            return (
                (fused_candidates[0].category_code if fused_candidates else None)
                or (legacy.category_code if legacy else "unknown_failure"),
                ClassificationStatus.CONFLICTED,
                max(0.0, breakdown_confidence - disagreement.confidence_penalty),
            )

        if open_set.status == OpenSetStatus.UNCERTAIN:
            code = (
                fused_candidates[0].category_code
                if fused_candidates
                else (legacy.category_code if legacy else "unknown_failure")
            )
            status = ClassificationStatus.UNCERTAIN
            if breakdown_confidence >= 0.55 and code != "unknown_failure":
                status = ClassificationStatus.KNOWN_LOW_CONFIDENCE
            return code, status, breakdown_confidence

        code = (
            fused_candidates[0].category_code
            if fused_candidates
            else (legacy.category_code if legacy else "unknown_failure")
        )
        if code == "unknown_failure":
            return code, ClassificationStatus.UNKNOWN, breakdown_confidence
        if breakdown_confidence < 0.5:
            return code, ClassificationStatus.KNOWN_LOW_CONFIDENCE, breakdown_confidence
        return code, ClassificationStatus.KNOWN, breakdown_confidence

    def _candidate_from_legacy(
        self, cand: ClassificationCandidate, *, source: str
    ) -> ClassificationCandidateDetail:
        path = self._registry.map_code(cand.category_code)
        return ClassificationCandidateDetail(
            category_code=cand.category_code,
            level_1_code=path.level_1_code,
            level_2_code=path.level_2_code,
            level_3_code=path.level_3_code,
            score=float(cand.confidence),
            source_classifier=source,
            supporting_evidence=list(cand.matched_rules[:8]),
            rank=cand.rank,
            matched_rules=list(cand.matched_rules),
        )

    def _collect_evidence_ids(self, context: AnalysisContext) -> list[str]:
        ids: list[str] = []
        for item in context.evidence or []:
            eid = getattr(item, "id", None) or getattr(item, "evidence_id", None)
            if eid:
                ids.append(str(eid))
        bundle = context.options.get("artifact_bundle") or {}
        if isinstance(bundle, dict) and bundle.get("bundle_id"):
            ids.append(f"bundle:{bundle['bundle_id']}")
        return ids

    def _missing_evidence(self, context: AnalysisContext) -> list[str]:
        missing: list[str] = []
        bundle = context.options.get("artifact_bundle") or {}
        if isinstance(bundle, dict):
            missing.extend(str(x) for x in (bundle.get("missing_artifacts") or [])[:12])
        if not context.options.get("evidence_graph"):
            missing.append("evidence_graph")
        if not context.options.get("temporal_localisation"):
            missing.append("temporal_localisation")
        return missing

    def _evidence_coverage(self, context: AnalysisContext) -> float:
        score = 0.0
        if context.classifications:
            score += 0.35
        if context.evidence:
            score += 0.2
        if context.options.get("artifact_bundle"):
            score += 0.15
        if context.options.get("temporal_localisation"):
            score += 0.15
        if context.options.get("evidence_graph"):
            score += 0.15
        return min(1.0, score)

    def _temporal_signals(self, context: AnalysisContext) -> tuple[float, str | None]:
        meta = context.options.get("temporal_localisation") or {}
        if not isinstance(meta, dict) or not meta:
            return 0.0, None
        conf = float(meta.get("confidence") or 0.0)
        hint = meta.get("primary_failure_type")
        # Map coarse types to frozen codes when obvious.
        mapping = {
            "access_denied": "aws_permission_failure",
            "permission": "aws_permission_failure",
            "terraform": "terraform_failure",
            "docker": "docker_failure",
            "test": "test_failure",
            "dependency": "dependency_failure",
            "network": "network_failure",
        }
        code = None
        if isinstance(hint, str):
            lowered = hint.lower()
            for key, val in mapping.items():
                if key in lowered:
                    code = val
                    break
        return conf, code

    def _graph_signals(self, context: AnalysisContext) -> tuple[float, str | None]:
        meta = context.options.get("evidence_graph") or {}
        if not isinstance(meta, dict) or not meta:
            return 0.0, None
        nodes = int(meta.get("node_count") or 0)
        edges = int(meta.get("edge_count") or 0)
        coverage = min(1.0, (nodes + edges) / 40.0)
        hint = meta.get("category_hint")
        if isinstance(hint, str) and self._registry.is_valid_category(hint):
            return coverage, hint.lower()
        return coverage, None

    def _evaluation_export(
        self, result: HierarchicalClassificationResult, context: AnalysisContext
    ) -> dict[str, Any]:
        return {
            "case_id": result.analysis_id,
            "legacy_category": result.final_legacy_category_code,
            "hierarchy": {
                "level_1": result.level_1_code,
                "level_2": result.level_2_code,
                "level_3": result.level_3_code,
            },
            "top_k_candidates": [c.to_dict() for c in result.top_candidates],
            "open_set_status": (
                result.open_set_result.status.value if result.open_set_result else None
            ),
            "unknown_score": (
                result.open_set_result.unknown_score if result.open_set_result else None
            ),
            "classifier_outputs": {
                "rule": result.rule_result.to_dict() if result.rule_result else None,
                "learned": result.learned_result.to_dict() if result.learned_result else None,
                "llm": result.llm_result.to_dict() if result.llm_result else None,
            },
            "disagreement_level": (
                result.disagreement_result.agreement_level.value
                if result.disagreement_result
                else None
            ),
            "evidence_coverage": (
                result.open_set_result.evidence_coverage if result.open_set_result else None
            ),
            "final_classification_confidence": result.final_confidence,
            "model_versions": dict(result.model_versions),
            "latency_ms": result.duration_ms,
            "metrics_hooks": [
                "top1_accuracy",
                "top3_accuracy",
                "macro_f1",
                "hierarchical_accuracy",
                "unknown_detection_precision_recall",
                "open_set_auroc",
                "selective_accuracy",
                "coverage",
                "false_known_rate",
                "false_unknown_rate",
            ],
        }
