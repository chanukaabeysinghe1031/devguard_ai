"""Deterministic rule-based causal hypothesis generator (Phase 6A.4)."""

from __future__ import annotations

from app.domain.classification.taxonomy_registry import get_taxonomy_registry
from app.domain.hypotheses.enums import (
    HypothesisEvidenceRelation,
    HypothesisGeneratorType,
    HypothesisStatus,
)
from app.domain.hypotheses.models import (
    CausalHypothesis,
    HypothesisEvidenceLink,
    HypothesisGenerationContext,
)
from app.domain.hypotheses.templates import TEMPLATES_V1, HypothesisTemplate


class RuleBasedHypothesisGenerator:
    """Emit hypotheses only when template minimum evidence is met."""

    def __init__(self, *, enabled: bool = True, max_hypotheses: int = 5) -> None:
        self._enabled = enabled
        self._max = max(1, min(max_hypotheses, 10))
        self._registry = get_taxonomy_registry()

    def generate(self, context: HypothesisGenerationContext) -> list[CausalHypothesis]:
        if not self._enabled:
            return []
        if (context.open_set_status or "").upper() == "UNKNOWN":
            # Do not force known-category template hypotheses.
            return self._unknown_placeholder(context)

        text = (context.combined_text_excerpt or "").lower()
        scored: list[tuple[float, HypothesisTemplate, int]] = []
        for template in TEMPLATES_V1:
            req_hits = sum(1 for tok in template.required_signal_tokens if tok in text)
            if req_hits < template.min_required_hits:
                continue
            contra = sum(1 for tok in template.contradicting_signal_tokens if tok in text)
            opt_hits = sum(1 for tok in template.optional_signal_tokens if tok in text)
            score = template.base_confidence + 0.05 * req_hits + 0.02 * opt_hits - 0.12 * contra
            # Prefer templates aligning with hierarchical classification when present.
            hier_cat = (context.hierarchical_classification or {}).get(
                "final_legacy_category_code"
            ) or (context.hierarchical_classification or {}).get("level_3_code")
            if hier_cat and hier_cat == template.category_code:
                score += 0.08
            scored.append((score, template, contra))

        scored.sort(key=lambda item: item[0], reverse=True)
        # Diversity: keep first of each diversity_bucket preferentially.
        selected: list[tuple[float, HypothesisTemplate, int]] = []
        buckets: set[str] = set()
        for score, template, contra in scored:
            same_bucket = template.diversity_bucket in buckets and len(selected) >= 2
            if same_bucket and (score < 0.75 or len(selected) >= self._max):
                continue
            selected.append((score, template, contra))
            buckets.add(template.diversity_bucket)
            if len(selected) >= self._max:
                break

        out: list[CausalHypothesis] = []
        failure_node = self._pick_failure_node(context)
        for idx, (score, template, contra) in enumerate(selected, start=1):
            path = self._registry.map_code(template.category_code)
            missing = self._missing_for_template(template, context)
            links = self._links_for_template(template, context, contra > 0)
            status = HypothesisStatus.GENERATED
            if missing and score < 0.6:
                status = HypothesisStatus.INCOMPLETE
            if contra > 0 and score < 0.55:
                status = HypothesisStatus.CONTRADICTED
            out.append(
                CausalHypothesis(
                    hypothesis_key=f"H{idx}",
                    title=template.title,
                    causal_claim=template.causal_claim_template,
                    category_code=template.category_code,
                    level_1_code=path.level_1_code,
                    level_2_code=path.level_2_code,
                    level_3_code=path.level_3_code,
                    root_cause_node_id=self._pick_root_node(context, template),
                    observed_failure_node_id=failure_node,
                    affected_path=self._pick_affected_path(context, template),
                    evidence_links=links,
                    expected_observations=list(template.expected_observations),
                    falsifying_observations=list(template.falsifying_observations),
                    proposed_verification_steps=list(template.verification_steps),
                    limitations=list(template.limitations),
                    missing_evidence=missing,
                    generator_type=HypothesisGeneratorType.RULE,
                    generator_name="rule_templates",
                    generator_version=template.template_version,
                    template_id=template.template_id,
                    generation_confidence=round(min(0.95, max(0.1, score)), 4),
                    status=status,
                    rank_placeholder=idx,
                )
            )
        return out

    def _unknown_placeholder(
        self, context: HypothesisGenerationContext
    ) -> list[CausalHypothesis]:
        path = self._registry.unknown_path()
        return [
            CausalHypothesis(
                hypothesis_key="H1",
                title="Unknown / insufficient taxonomy evidence",
                causal_claim=(
                    "Available evidence is insufficient to support a known frozen-category "
                    "causal hypothesis; missing evidence should be collected before ranking."
                ),
                category_code="unknown_failure",
                level_1_code=path.level_1_code,
                level_2_code=path.level_2_code,
                level_3_code=path.level_3_code,
                observed_failure_node_id=self._pick_failure_node(context),
                expected_observations=(
                    "Additional tool-specific diagnostics or policies become available",
                ),
                falsifying_observations=(
                    "A deterministic signature maps confidently to a frozen category",
                ),
                proposed_verification_steps=(
                    "Collect missing artifacts listed in the open-set assessment",
                    "Re-run analysis after acquiring policy/plan/workflow evidence",
                ),
                limitations=("Open-set status UNKNOWN — no forced known cause.",),
                missing_evidence=list(context.missing_artifacts)[:12]
                or ["additional_diagnostic_artifacts"],
                generator_type=HypothesisGeneratorType.RULE,
                generator_name="open_set_unknown",
                generator_version="v1",
                template_id="unknown.insufficient_evidence",
                generation_confidence=0.25,
                status=HypothesisStatus.INCOMPLETE,
                rank_placeholder=1,
            )
        ]

    def _pick_failure_node(self, context: HypothesisGenerationContext) -> str | None:
        temporal = context.temporal_primary_failure or {}
        if temporal.get("primary_failure_event_id"):
            return str(temporal["primary_failure_event_id"])
        for node in context.relevant_graph_nodes:
            ntype = str(node.get("node_type") or "").upper()
            label = str(node.get("label") or "").lower()
            if "FAIL" in ntype or "error" in label or "denied" in label:
                return str(node.get("stable_key") or node.get("id") or "") or None
        return None

    def _pick_root_node(
        self, context: HypothesisGenerationContext, template: HypothesisTemplate
    ) -> str | None:
        prefer = {
            "iam": ("IAM", "POLICY", "ROLE", "PERMISSION"),
            "terraform": ("TERRAFORM", "RESOURCE", "OUTPUT", "PROVIDER"),
            "workflow": ("WORKFLOW", "JOB", "STEP", "SECRET"),
            "dependency": ("PACKAGE", "DEPENDENCY", "LOCK"),
            "container": ("IMAGE", "CONTAINER", "DEPLOY", "REGISTRY"),
        }.get(template.family, ())
        for node in context.relevant_graph_nodes:
            blob = f"{node.get('node_type', '')} {node.get('label', '')}".upper()
            if any(tok in blob for tok in prefer):
                return str(node.get("stable_key") or node.get("id") or "") or None
        return None

    def _pick_affected_path(
        self, context: HypothesisGenerationContext, template: HypothesisTemplate
    ) -> str | None:
        hints = {
            "iam": (".tf", "iam", "policy"),
            "terraform": (".tf", "terraform"),
            "workflow": (".yml", ".yaml", "workflow"),
            "dependency": ("package.json", "requirements", "pom.xml", "lock"),
            "container": ("dockerfile", "compose", "deployment"),
        }.get(template.family, ())
        for node in context.relevant_graph_nodes:
            path = str(node.get("source_path") or "")
            if path and any(h in path.lower() for h in hints):
                return path
        for art in context.artifact_availability:
            if any(h in art.lower() for h in hints):
                return art
        return None

    def _missing_for_template(
        self, template: HypothesisTemplate, context: HypothesisGenerationContext
    ) -> list[str]:
        missing = list(context.missing_artifacts)[:8]
        if template.family == "iam" and not any(
            "iam" in a.lower() or ".tf" in a.lower() for a in context.artifact_availability
        ):
            missing.append("iam_or_terraform_policy_artifact")
        if template.family == "terraform" and not any(
            ".tf" in a.lower() for a in context.artifact_availability
        ):
            missing.append("terraform_configuration")
        return list(dict.fromkeys(missing))

    def _links_for_template(
        self,
        template: HypothesisTemplate,
        context: HypothesisGenerationContext,
        contradicted: bool,
    ) -> list[HypothesisEvidenceLink]:
        links: list[HypothesisEvidenceLink] = []
        for ev in context.evidence_candidates[:6]:
            links.append(
                HypothesisEvidenceLink(
                    evidence_type=str(ev.get("evidence_type") or "log_excerpt"),
                    relation=HypothesisEvidenceRelation.SUPPORTS,
                    explanation=f"Template {template.template_id} matched log/evidence signals.",
                    confidence=0.55,
                    evidence_item_id=str(ev.get("id")) if ev.get("id") else None,
                    source_path=ev.get("source_path"),
                    line_start=ev.get("line_start"),
                    line_end=ev.get("line_end"),
                    extraction_method="rule_template",
                )
            )
        if contradicted:
            links.append(
                HypothesisEvidenceLink(
                    evidence_type="signal",
                    relation=HypothesisEvidenceRelation.CONTRADICTS,
                    explanation="Contradicting signal tokens for this template were present.",
                    confidence=0.5,
                    extraction_method="rule_template",
                )
            )
        for miss in self._missing_for_template(template, context)[:4]:
            links.append(
                HypothesisEvidenceLink(
                    evidence_type="missing_artifact",
                    relation=HypothesisEvidenceRelation.MISSING,
                    explanation=miss,
                    confidence=0.4,
                    extraction_method="rule_template",
                )
            )
        return links
