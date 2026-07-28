"""Deterministic evidence-quality evaluation (no LLM)."""

from __future__ import annotations

from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.orchestration.models import EvidenceQualityAssessment, clamp01


class EvidenceQualityEvaluator:
    def evaluate(self, context: AnalysisContext) -> EvidenceQualityAssessment:
        evidence = context.evidence
        reasons: list[str] = []
        if not evidence:
            return EvidenceQualityAssessment(
                evidence_quality_score=0.15,
                coverage_score=0.0,
                traceability_score=0.0,
                specificity_score=0.0,
                consistency_score=0.0,
                duplicate_ratio=0.0,
                unique_file_count=0,
                direct_signature_count=0,
                reasons=["No evidence available."],
            )

        unique_files = {e.uploaded_file_id for e in evidence if e.uploaded_file_id}
        coverage = clamp01(len(unique_files) / max(1, len(context.files) or 1))
        if len(unique_files) > 1:
            reasons.append("Multiple independent source files improve coverage.")

        traced = sum(
            1 for e in evidence if e.line_start is not None and e.source_name and e.uploaded_file_id
        )
        traceability = clamp01(traced / len(evidence))
        if traced < len(evidence):
            reasons.append("Some evidence lacks line/source traceability.")

        primary = context.classifications[0].category_code if context.classifications else None
        direct = sum(
            1
            for e in evidence
            if (e.category_code == primary and primary)
            or float(e.importance_score) >= 0.85
            or "Matched rule" in (e.explanation or "")
        )
        specificity = clamp01(direct / len(evidence))
        if direct:
            reasons.append(f"Direct signature evidence count={direct}.")

        excerpts = [e.normalized_excerpt.strip()[:160] for e in evidence]
        unique_excerpts = set(excerpts)
        duplicate_ratio = clamp01(1.0 - (len(unique_excerpts) / len(excerpts)))
        if duplicate_ratio > 0:
            reasons.append("Duplicate excerpts reduce quality.")

        categories = {e.category_code for e in evidence if e.category_code}
        consistency = 1.0
        if primary and categories and primary not in categories:
            consistency = 0.4
            reasons.append("Evidence categories conflict with primary prediction.")
        elif len(categories) > 2:
            consistency = 0.55
            reasons.append("Evidence spans many conflicting categories.")
        else:
            reasons.append("Evidence is broadly consistent.")

        useful = [e for e in evidence if len(e.normalized_excerpt.strip()) >= 20]
        usefulness = clamp01(len(useful) / len(evidence))
        quality = clamp01(
            0.30 * specificity
            + 0.25 * traceability
            + 0.20 * coverage
            + 0.15 * consistency
            + 0.10 * usefulness
            - 0.20 * duplicate_ratio
        )
        return EvidenceQualityAssessment(
            evidence_quality_score=round(quality, 4),
            coverage_score=round(coverage, 4),
            traceability_score=round(traceability, 4),
            specificity_score=round(specificity, 4),
            consistency_score=round(consistency, 4),
            duplicate_ratio=round(duplicate_ratio, 4),
            unique_file_count=len(unique_files),
            direct_signature_count=direct,
            reasons=reasons,
        )
