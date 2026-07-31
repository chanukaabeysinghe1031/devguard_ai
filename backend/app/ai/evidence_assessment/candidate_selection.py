"""Candidate hypothesis selection (not final diagnosis)."""

from __future__ import annotations

from app.ai.evidence_assessment.versions import CANDIDATE_SELECTION_VERSION
from app.domain.evidence_assessment.enums import CandidateSelectionStatus
from app.domain.evidence_assessment.models import (
    HypothesisCandidateSelectionResult,
    HypothesisRankingResult,
)


class HypothesisCandidateSelector:
    def select(
        self,
        ranking: HypothesisRankingResult,
        *,
        max_candidates: int = 5,
        min_ranking_score_for_top: float = 0.40,
        tie_epsilon: float = 0.02,
    ) -> HypothesisCandidateSelectionResult:
        scores = list(ranking.scores)
        if not scores:
            return HypothesisCandidateSelectionResult(
                analysis_id=ranking.analysis_id,
                organization_id=ranking.organization_id,
                status=CandidateSelectionStatus.UNKNOWN,
                max_candidates=max_candidates,
                min_ranking_score_for_top=min_ranking_score_for_top,
                tie_epsilon=tie_epsilon,
                reasons=["no_ranked_hypotheses"],
                selector_version=CANDIDATE_SELECTION_VERSION,
            )

        top_n = scores[: max(1, max_candidates)]
        top = scores[0]
        selected_ids = [s.hypothesis_id for s in top_n]
        selected_keys = [s.hypothesis_key for s in top_n]

        if top.ranking_score < min_ranking_score_for_top:
            return HypothesisCandidateSelectionResult(
                analysis_id=ranking.analysis_id,
                organization_id=ranking.organization_id,
                status=CandidateSelectionStatus.WEAK_EVIDENCE,
                top_hypothesis_id=top.hypothesis_id,
                top_hypothesis_key=top.hypothesis_key,
                top_ranking_score=top.ranking_score,
                selected_hypothesis_ids=selected_ids,
                selected_hypothesis_keys=selected_keys,
                max_candidates=max_candidates,
                min_ranking_score_for_top=min_ranking_score_for_top,
                tie_epsilon=tie_epsilon,
                reasons=["top_ranking_score_below_minimum"],
                warnings=["weak_evidence_selection"],
                selector_version=CANDIDATE_SELECTION_VERSION,
            )

        if (
            len(scores) >= 2
            and abs(scores[0].ranking_score - scores[1].ranking_score) <= tie_epsilon
        ):
            return HypothesisCandidateSelectionResult(
                analysis_id=ranking.analysis_id,
                organization_id=ranking.organization_id,
                status=CandidateSelectionStatus.TIE,
                top_hypothesis_id=None,
                top_hypothesis_key=None,
                top_ranking_score=top.ranking_score,
                selected_hypothesis_ids=selected_ids,
                selected_hypothesis_keys=selected_keys,
                max_candidates=max_candidates,
                min_ranking_score_for_top=min_ranking_score_for_top,
                tie_epsilon=tie_epsilon,
                reasons=["top_scores_within_tie_epsilon"],
                warnings=["tie_no_single_top_candidate"],
                selector_version=CANDIDATE_SELECTION_VERSION,
            )

        # Clear winner always sets top_*; TOP_N when multiple candidates listed.
        status = (
            CandidateSelectionStatus.TOP_N
            if len(top_n) > 1
            else CandidateSelectionStatus.TOP_CANDIDATE
        )
        reasons = ["clear_top_candidate"]
        if status == CandidateSelectionStatus.TOP_N:
            reasons.append("top_n_candidates_listed")

        return HypothesisCandidateSelectionResult(
            analysis_id=ranking.analysis_id,
            organization_id=ranking.organization_id,
            status=status,
            top_hypothesis_id=top.hypothesis_id,
            top_hypothesis_key=top.hypothesis_key,
            top_ranking_score=top.ranking_score,
            selected_hypothesis_ids=selected_ids,
            selected_hypothesis_keys=selected_keys,
            max_candidates=max_candidates,
            min_ranking_score_for_top=min_ranking_score_for_top,
            tie_epsilon=tie_epsilon,
            reasons=reasons,
            selector_version=CANDIDATE_SELECTION_VERSION,
        )
