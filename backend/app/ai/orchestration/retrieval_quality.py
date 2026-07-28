"""Retrieval-quality evaluation after retrieval only (no LLM). Mode-aware for Module 9."""

from __future__ import annotations

from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.orchestration.models import RetrievalQualityAssessment, clamp01


class RetrievalQualityEvaluator:
    def evaluate(self, context: AnalysisContext) -> RetrievalQualityAssessment:
        chunks = list(context.retrieved_chunks or [])
        mode = str((context.options or {}).get("retrieval_mode") or "embedding_only")
        retrieval_meta = (context.options or {}).get("retrieval_result") or {}

        if not chunks:
            return RetrievalQualityAssessment(
                retrieval_executed=True,
                retrieval_quality_score=0.15,
                relevance_score=0.0,
                coverage_score=0.0,
                diversity_score=0.0,
                duplicate_ratio=0.0,
                category_support_score=0.0,
                documents_considered=int(retrieval_meta.get("candidates_considered") or 0),
                documents_selected=0,
                reasons=["Retrieval executed but returned no documents."],
            )

        scores = [float(c.similarity_score) for c in chunks]
        relevance = clamp01(sum(scores) / len(scores))
        top = max(scores) if scores else 0.0
        providers = {
            getattr(c, "provider", None) or (c.metadata or {}).get("provider") for c in chunks
        }
        source_types = {
            (c.metadata or {}).get("source_type")
            for c in chunks
            if (c.metadata or {}).get("source_type")
        }
        diversity = clamp01(
            (len({p for p in providers if p}) + len({s for s in source_types if s}))
            / max(1, 2 * len(chunks))
        )
        contents = [str(getattr(c, "content", ""))[:180] for c in chunks]
        duplicate_ratio = clamp01(1.0 - (len(set(contents)) / len(contents)))
        if retrieval_meta.get("duplicate_count"):
            considered = max(1, int(retrieval_meta.get("candidates_considered") or len(chunks)))
            duplicate_ratio = max(
                duplicate_ratio,
                clamp01(float(retrieval_meta["duplicate_count"]) / considered),
            )

        primary = context.classifications[0].category_code if context.classifications else ""
        support_hits = 0
        exact_hits = 0
        for chunk in chunks:
            text = (getattr(chunk, "content", "") or "").lower()
            meta = getattr(chunk, "metadata", None) or {}
            if primary and any(part in text for part in primary.replace("_", " ").split()):
                support_hits += 1
            if context.signals.get("provider") and str(context.signals.get("provider")) in text:
                support_hits += 1
            cats = {str(c).lower() for c in (meta.get("failure_categories") or [])}
            if primary and primary.lower() in cats:
                support_hits += 1
            # Exact-match strength only when hybrid metadata exists.
            if mode != "embedding_only" and (
                (meta.get("error_codes") or meta.get("match_reasons"))
                and any("error code" in str(r).lower() for r in (meta.get("match_reasons") or []))
                or float(meta.get("score_breakdown", {}).get("error_code") or 0) >= 0.8
            ):
                exact_hits += 1
        category_support = clamp01(support_hits / len(chunks))
        coverage = clamp01(min(1.0, len(chunks) / 3.0) * (1.0 - 0.5 * duplicate_ratio))
        exact_strength = clamp01(exact_hits / len(chunks)) if mode != "embedding_only" else None

        # Score margin between top two.
        ordered = sorted(scores, reverse=True)
        margin = (ordered[0] - ordered[1]) if len(ordered) > 1 else ordered[0]

        historical_quality = None
        if mode == "hybrid_with_history":
            hist_scores = [
                float((c.metadata or {}).get("history_quality_score") or 0.0)
                for c in chunks
                if (c.metadata or {}).get("source_type") == "historical_incident"
            ]
            if hist_scores:
                historical_quality = clamp01(sum(hist_scores) / len(hist_scores))

        if mode == "embedding_only":
            quality = clamp01(
                0.40 * top
                + 0.25 * relevance
                + 0.15 * diversity
                + 0.10 * category_support
                + 0.10 * coverage
                - 0.25 * duplicate_ratio
            )
        else:
            quality = clamp01(
                0.28 * top
                + 0.18 * relevance
                + 0.12 * diversity
                + 0.14 * category_support
                + 0.10 * coverage
                + 0.12 * (exact_strength or 0.0)
                + 0.08 * margin
                + 0.08 * (historical_quality or 0.0)
                - 0.22 * duplicate_ratio
            )

        # Large result count alone must not create high quality.
        if len(chunks) > 5 and relevance < 0.4:
            quality = min(quality, 0.45)

        reasons = [
            f"Selected documents={len(chunks)}.",
            f"Mean relevance={relevance:.2f}.",
            f"retrieval_mode={mode}.",
        ]
        if duplicate_ratio > 0.2:
            reasons.append("Duplicate chunks reduce retrieval quality.")
        if category_support >= 0.5:
            reasons.append("Retrieved docs support predicted category.")
        else:
            reasons.append("Limited category support in retrieved docs.")
        if exact_strength is not None and exact_strength >= 0.5:
            reasons.append("Strong exact diagnostic matches present.")
        if historical_quality is not None:
            reasons.append(f"Historical quality mean={historical_quality:.2f}.")

        return RetrievalQualityAssessment(
            retrieval_executed=True,
            retrieval_quality_score=round(quality, 4),
            relevance_score=round(relevance, 4),
            coverage_score=round(coverage, 4),
            diversity_score=round(diversity, 4),
            duplicate_ratio=round(duplicate_ratio, 4),
            category_support_score=round(category_support, 4),
            documents_considered=int(retrieval_meta.get("candidates_considered") or len(chunks)),
            documents_selected=len([c for c in chunks if getattr(c, "used_in_reasoning", True)]),
            reasons=reasons,
        )
