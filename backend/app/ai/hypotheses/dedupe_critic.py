"""Hypothesis deduplication, critic, and generation prior score (Phase 6A.4)."""

from __future__ import annotations

import hashlib
import re

from app.domain.hypotheses.enums import (
    CriticDecision,
    HypothesisEvidenceRelation,
    HypothesisStatus,
)
from app.domain.hypotheses.models import (
    CausalHypothesis,
    HypothesisCriticResult,
    HypothesisGenerationContext,
)
from app.domain.hypotheses.templates import DOWNSTREAM_SYMPTOM_TOKENS


def hypothesis_fingerprint(hypothesis: CausalHypothesis) -> str:
    claim = re.sub(r"\s+", " ", (hypothesis.causal_claim or "").lower()).strip()
    claim = re.sub(r"[^a-z0-9 _-]", "", claim)[:200]
    raw = "|".join(
        [
            hypothesis.category_code or "",
            hypothesis.template_id or "",
            hypothesis.root_cause_node_id or "",
            hypothesis.affected_path or "",
            claim,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class HypothesisDeduplicator:
    def __init__(self, *, similarity_threshold: float = 0.92) -> None:
        self._threshold = similarity_threshold

    def deduplicate(
        self, hypotheses: list[CausalHypothesis]
    ) -> tuple[list[CausalHypothesis], int]:
        kept: list[CausalHypothesis] = []
        removed = 0
        seen_fps: list[str] = []
        seen_buckets: dict[str, str] = {}
        for hyp in hypotheses:
            fp = hypothesis_fingerprint(hyp)
            if fp in seen_fps:
                hyp.status = HypothesisStatus.DUPLICATE
                removed += 1
                continue
            # Same template id → duplicate.
            if hyp.template_id and any(h.template_id == hyp.template_id for h in kept):
                hyp.status = HypothesisStatus.DUPLICATE
                removed += 1
                continue
            # Near-identical claim token Jaccard.
            if any(self._similar(hyp.causal_claim, h.causal_claim) for h in kept):
                hyp.status = HypothesisStatus.DUPLICATE
                removed += 1
                continue
            # Preserve diversity across buckets when template-derived.
            bucket = (hyp.template_id or "").split(".", 1)[0]
            # Weaker same-family extras may be dropped later by max-hypothesis bounds.
            seen_fps.append(fp)
            kept.append(hyp)
            if bucket:
                seen_buckets[bucket] = hyp.hypothesis_key
        return kept, removed

    def _similar(self, a: str, b: str) -> bool:
        ta = set(re.findall(r"[a-z0-9]+", (a or "").lower()))
        tb = set(re.findall(r"[a-z0-9]+", (b or "").lower()))
        if not ta or not tb:
            return False
        inter = len(ta & tb)
        union = len(ta | tb)
        return (inter / union) >= self._threshold


class CausalHypothesisCritic:
    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled

    def critique(
        self, hypothesis: CausalHypothesis, context: HypothesisGenerationContext
    ) -> HypothesisCriticResult:
        if not self._enabled:
            return HypothesisCriticResult(
                decision=CriticDecision.ACCEPT_FOR_RANKING,
                explanation="Critic disabled.",
                recommended_status=hypothesis.status,
            )

        contradictions: list[str] = []
        missing = list(hypothesis.missing_evidence)
        unsupported: list[str] = []
        graph_conflicts: list[str] = []
        temporal_conflicts: list[str] = []
        specificity: str | None = None

        for link in hypothesis.evidence_links:
            if link.relation == HypothesisEvidenceRelation.CONTRADICTS:
                contradictions.append(link.explanation or "contradicting_evidence_link")
            if link.relation == HypothesisEvidenceRelation.MISSING:
                missing.append(link.explanation or "missing_evidence_link")

        # Downstream symptom as root cause.
        root_label = ""
        for node in context.relevant_graph_nodes:
            key = str(node.get("stable_key") or node.get("id") or "")
            if key == hypothesis.root_cause_node_id:
                root_label = str(node.get("label") or "").lower()
                break
        claim_l = hypothesis.causal_claim.lower()
        if any(tok in root_label or tok in claim_l for tok in DOWNSTREAM_SYMPTOM_TOKENS):
            temporal = context.temporal_primary_failure or {}
            if temporal.get("primary_failure_summary") and "fail" in claim_l:
                temporal_conflicts.append("hypothesis_targets_downstream_symptom")

        if hypothesis.path_validation_status.value == "INVALID":
            graph_conflicts.append("invalid_causal_path")
        if hypothesis.path_validation_warnings:
            graph_conflicts.extend(hypothesis.path_validation_warnings[:5])

        # Over-specific IAM action without evidence.
        if "s3:putobject" in claim_l and "s3:putobject" not in (
            context.combined_text_excerpt or ""
        ).lower():
            specificity = "Claim names a specific IAM action not present in supplied evidence."
            unsupported.append("over_specific_action_without_evidence")

        open_unknown = (context.open_set_status or "").upper() == "UNKNOWN"
        if open_unknown and hypothesis.category_code not in {None, "unknown_failure"}:
            unsupported.append("known_category_under_open_set_unknown")

        has_support = any(
            link.relation == HypothesisEvidenceRelation.SUPPORTS
            for link in hypothesis.evidence_links
        )
        if contradictions and not has_support:
            decision = CriticDecision.CONTRADICTED
            status = HypothesisStatus.CONTRADICTED
        elif temporal_conflicts and "downstream_symptom" in ",".join(temporal_conflicts):
            decision = CriticDecision.REJECT
            status = HypothesisStatus.REJECTED
        elif unsupported or graph_conflicts:
            if missing:
                decision = CriticDecision.INCOMPLETE
                status = HypothesisStatus.INCOMPLETE
            else:
                decision = CriticDecision.ACCEPT_WITH_WARNINGS
                status = HypothesisStatus.READY_FOR_RANKING
        elif missing:
            decision = CriticDecision.INCOMPLETE
            status = HypothesisStatus.INCOMPLETE
        elif specificity:
            decision = CriticDecision.ACCEPT_WITH_WARNINGS
            status = HypothesisStatus.READY_FOR_RANKING
        else:
            decision = CriticDecision.ACCEPT_FOR_RANKING
            status = HypothesisStatus.READY_FOR_RANKING

        return HypothesisCriticResult(
            decision=decision,
            explanation=(
                f"Critic decision={decision.value}; contradictions={len(contradictions)}; "
                f"missing={len(missing)}; unsupported={len(unsupported)}."
            ),
            contradictions=list(dict.fromkeys(contradictions)),
            missing_evidence=list(dict.fromkeys(missing))[:12],
            unsupported_claims=list(dict.fromkeys(unsupported)),
            graph_conflicts=list(dict.fromkeys(graph_conflicts))[:12],
            temporal_conflicts=list(dict.fromkeys(temporal_conflicts)),
            specificity_warning=specificity,
            recommended_status=status,
        )


class GenerationPriorScorer:
    """Initial generation_prior_score only — not final causal ranking."""

    def score(
        self, hypothesis: CausalHypothesis, context: HypothesisGenerationContext
    ) -> float:
        score = float(hypothesis.generation_confidence) * 0.35
        if hypothesis.template_id:
            score += 0.15
        hier = context.hierarchical_classification or {}
        if hier.get("final_legacy_category_code") == hypothesis.category_code:
            score += 0.12
        if context.temporal_primary_failure:
            score += 0.08
        if hypothesis.path_validation_status.value in {"VALID", "VALID_WITH_WARNINGS"}:
            score += 0.1
        elif hypothesis.path_validation_status.value == "PARTIAL":
            score += 0.04
        supports = sum(
            1
            for link in hypothesis.evidence_links
            if link.relation == HypothesisEvidenceRelation.SUPPORTS
        )
        score += min(0.1, 0.03 * supports)
        if hypothesis.affected_path:
            score += 0.05
        # Penalties
        score -= 0.08 * sum(
            1
            for link in hypothesis.evidence_links
            if link.relation == HypothesisEvidenceRelation.CONTRADICTS
        )
        score -= min(0.15, 0.03 * len(hypothesis.missing_evidence))
        if (context.open_set_status or "").upper() == "UNKNOWN":
            score -= 0.12
        if (context.open_set_status or "").upper() == "UNCERTAIN":
            score -= 0.05
        disagreement = (context.disagreement_result or {}).get("agreement_level")
        if disagreement == "SEVERE":
            score -= 0.1
        elif disagreement == "LOW":
            score -= 0.05
        if hypothesis.critic and hypothesis.critic.decision == CriticDecision.REJECT:
            score -= 0.2
        return round(max(0.0, min(0.99, score)), 4)
