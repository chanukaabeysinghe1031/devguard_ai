"""Deterministic diversity selection (MMR-style)."""

from __future__ import annotations

from app.ai.rag.models import RetrievalCandidate
from app.ai.rag.weight_profiles import HybridWeightProfile


class DiverseCandidateSelector:
    def select(
        self,
        candidates: list[RetrievalCandidate],
        profile: HybridWeightProfile,
    ) -> list[RetrievalCandidate]:
        if not candidates:
            return []
        if not profile.enable_diversity:
            return candidates[: profile.max_final_results]

        selected: list[RetrievalCandidate] = []
        per_doc: dict[str, int] = {}
        historical_count = 0
        remaining = list(candidates)
        lam = profile.diversity_lambda

        while remaining and len(selected) < profile.max_final_results:
            best_idx = None
            best_score = float("-inf")
            for idx, candidate in enumerate(remaining):
                relevance = float(
                    candidate.hybrid_score
                    if candidate.hybrid_score is not None
                    else candidate.semantic_score or 0.0
                )
                redundancy = 0.0
                if selected:
                    redundancy = max(_overlap(candidate, prior) for prior in selected)
                mmr = lam * relevance - (1.0 - lam) * redundancy
                doc_key = candidate.source_id
                if per_doc.get(doc_key, 0) >= profile.max_chunks_per_document:
                    continue
                if (
                    candidate.source_type.value == "historical_incident"
                    and historical_count >= profile.max_historical_results
                ):
                    continue
                if (
                    best_idx is None
                    or mmr > best_score
                    or (
                        abs(mmr - best_score) < 1e-12
                        and candidate.candidate_id < remaining[best_idx].candidate_id
                    )
                ):
                    best_score = mmr
                    best_idx = idx
            if best_idx is None:
                break
            chosen = remaining.pop(best_idx)
            selected.append(chosen)
            per_doc[chosen.source_id] = per_doc.get(chosen.source_id, 0) + 1
            if chosen.source_type.value == "historical_incident":
                historical_count += 1
        return selected


def _overlap(a: RetrievalCandidate, b: RetrievalCandidate) -> float:
    if a.source_id == b.source_id:
        return 0.85
    if a.source_type == b.source_type:
        ta = set((a.content_excerpt or "").lower().split())
        tb = set((b.content_excerpt or "").lower().split())
        if not ta or not tb:
            return 0.2
        return len(ta & tb) / len(ta | tb)
    ta = set((a.content_excerpt or "").lower().split())
    tb = set((b.content_excerpt or "").lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
