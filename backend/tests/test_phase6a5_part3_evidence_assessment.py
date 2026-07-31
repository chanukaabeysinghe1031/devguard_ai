"""Phase 6A.5 Part 3 — evidence assessment unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.evidence_assessment.authority import authority_rank, authority_score_for_source
from app.ai.evidence_assessment.candidate_selection import HypothesisCandidateSelector
from app.ai.evidence_assessment.contradiction_analyzer import HypothesisContradictionAnalyzer
from app.ai.evidence_assessment.diversity import diversity_score
from app.ai.evidence_assessment.item_assessor import EvidenceItemAssessor
from app.ai.evidence_assessment.orchestrator import EvidenceAssessmentOrchestrator
from app.ai.evidence_assessment.ranking import HypothesisRankingEngine
from app.ai.evidence_assessment.sufficiency import EvidenceSufficiencyAssessor
from app.ai.evidence_assessment.support_analyzer import HypothesisSupportAnalyzer
from app.ai.evidence_assessment.versions import (
    CANDIDATE_SELECTION_VERSION,
    CONTRADICTION_ANALYSIS_VERSION,
    EVIDENCE_ASSESSMENT_VERSION,
    EVIDENCE_SUFFICIENCY_VERSION,
    HYPOTHESIS_RANKING_VERSION,
    SUPPORT_ANALYSIS_VERSION,
)
from app.application.services.analysis_execution_service import AnalysisExecutionService
from app.core.config import Settings
from app.domain.evidence_assessment.enums import (
    CandidateSelectionStatus,
    EvidenceAssessmentType,
    EvidenceSufficiencyLevel,
)
from app.domain.evidence_assessment.models import (
    EvidenceAssessment,
    EvidenceSufficiencyAssessment,
    HypothesisContradictionAssessment,
    HypothesisRankingResult,
    HypothesisRankingScore,
    HypothesisSupportAssessment,
)
from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalSourceType,
    RetrievalItemRelation,
)
from app.domain.hypothesis_retrieval.models import HypothesisRetrievedItem


def _base_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "PROJECT_NAME": "DevGuard AI Test",
        "APP_VERSION": "1.0.0",
        "ENVIRONMENT": "development",
        "DEBUG": False,
        "DATABASE_URL": "postgresql+asyncpg://devguard:change_me@localhost:5432/devguard_test",
        "JWT_SECRET_KEY": "x" * 32,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _item(
    *,
    item_id: str = "item-1",
    hypothesis_id: str = "hyp-1",
    relation: RetrievalItemRelation = RetrievalItemRelation.SUPPORT_CANDIDATE,
    source_type: HypothesisRetrievalSourceType = HypothesisRetrievalSourceType.ARTIFACT,
    retrieval_score: float = 0.8,
    relevance: float | None = None,
    exact_id: float = 0.0,
    path: str | None = "infra/main.tf",
    text_hash: str | None = "hash-a",
    query_id: str = "q1",
    order: int = 0,
) -> HypothesisRetrievedItem:
    meta: dict = {}
    if relevance is not None:
        meta["retrieval_relevance_score"] = relevance
    meta["features"] = {"exact_identifier_overlap": exact_id}
    return HypothesisRetrievedItem(
        id=item_id,
        source_type=source_type,
        source_system="test",
        text_excerpt="denied action sts:AssumeRole on resource",
        query_id=query_id,
        hypothesis_id=hypothesis_id,
        relation_candidate=relation,
        retrieval_score=retrieval_score,
        source_path=path,
        normalized_text_hash=text_hash,
        global_session_order=order,
        adapter_name="test",
        metadata=meta,
    )


# --- flags / config ---


def test_part3_flags_default_off() -> None:
    assert Settings.model_fields["hypothesis_evidence_assessment_enabled"].default is False
    assert Settings.model_fields["evidence_sufficiency_enabled"].default is False
    assert Settings.model_fields["contradiction_analysis_enabled"].default is False
    assert Settings.model_fields["hypothesis_ranking_enabled"].default is False
    assert Settings.model_fields["candidate_selection_enabled"].default is False


def test_part3_bounds_defaults() -> None:
    assert Settings.model_fields["max_evidence_assessments_per_hypothesis"].default == 40
    assert Settings.model_fields["max_candidate_hypotheses"].default == 5
    assert Settings.model_fields["min_ranking_score_for_top_candidate"].default == 0.40
    assert Settings.model_fields["ranking_tie_epsilon"].default == 0.02


def test_part3_score_out_of_range_raises() -> None:
    with pytest.raises(ValidationError):
        _base_settings(MIN_RANKING_SCORE_FOR_TOP_CANDIDATE=1.5)
    with pytest.raises(ValidationError):
        _base_settings(RANKING_TIE_EPSILON=-0.1)


def test_part3_zero_bound_raises() -> None:
    with pytest.raises(ValidationError):
        _base_settings(MAX_EVIDENCE_ASSESSMENTS_PER_HYPOTHESIS=0)
    with pytest.raises(ValidationError):
        _base_settings(MAX_CANDIDATE_HYPOTHESES=0)


@pytest.mark.asyncio
async def test_orchestrator_flag_off_noop() -> None:
    settings = _base_settings(HYPOTHESIS_EVIDENCE_ASSESSMENT_ENABLED=False)
    orch = EvidenceAssessmentOrchestrator(settings)

    class _Ctx:
        organization_id = None
        analysis_run_id = None

    result = await orch.run(None, _Ctx())  # type: ignore[arg-type]
    assert result is None


def test_analysis_execution_has_evidence_assessment_hook() -> None:
    assert hasattr(AnalysisExecutionService, "_maybe_run_phase6a5_evidence_assessment")
    assert callable(AnalysisExecutionService._maybe_run_phase6a5_evidence_assessment)


# --- item assessor ---


def test_support_candidate_from_relation_and_high_relevance() -> None:
    item = _item(
        relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
        relevance=0.8,
        exact_id=0.7,
    )
    assessment = EvidenceItemAssessor().assess(item)
    assert assessment.assessment_type == EvidenceAssessmentType.SUPPORT_CANDIDATE
    assert assessment.confidence > 0.0
    assert "support_candidate_relation" in assessment.reasons


def test_contradiction_candidate() -> None:
    item = _item(
        relation=RetrievalItemRelation.CONTRADICTION_CANDIDATE,
        relevance=0.7,
        exact_id=0.6,
    )
    assessment = EvidenceItemAssessor().assess(item)
    assert assessment.assessment_type == EvidenceAssessmentType.CONTRADICTION_CANDIDATE


def test_context_only_relation() -> None:
    item = _item(relation=RetrievalItemRelation.CONTEXT, relevance=0.6)
    assessment = EvidenceItemAssessor().assess(item)
    assert assessment.assessment_type == EvidenceAssessmentType.CONTEXT_ONLY


def test_weak_insufficient_evidence() -> None:
    item = _item(
        relation=RetrievalItemRelation.UNKNOWN,
        relevance=0.1,
        retrieval_score=0.1,
        exact_id=0.0,
    )
    assessment = EvidenceItemAssessor().assess(item)
    assert assessment.assessment_type in {
        EvidenceAssessmentType.INSUFFICIENT,
        EvidenceAssessmentType.UNRELATED,
    }


def test_ambiguous_support_with_weak_relevance() -> None:
    item = _item(
        relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
        relevance=0.15,
        retrieval_score=0.15,
    )
    assessment = EvidenceItemAssessor().assess(item)
    assert assessment.assessment_type in {
        EvidenceAssessmentType.AMBIGUOUS,
        EvidenceAssessmentType.INSUFFICIENT,
        EvidenceAssessmentType.UNRELATED,
    }


def test_max_assessments_cap() -> None:
    items = [
        _item(item_id=f"i{i}", order=i, relevance=0.9 - (i * 0.01))
        for i in range(10)
    ]
    results = EvidenceItemAssessor().assess_many(items, hypothesis_id="h1", max_assessments=3)
    assert len(results) == 3


# --- authority / diversity ---


def test_authority_ordering_repo_over_historical_over_vector() -> None:
    repo = authority_score_for_source(
        source_type=HypothesisRetrievalSourceType.ARTIFACT.value,
        source_path=".github/workflows/deploy.yml",
    )
    docs = authority_score_for_source(
        source_type=HypothesisRetrievalSourceType.DOCUMENTATION.value,
        official_source=True,
    )
    hist = authority_score_for_source(
        source_type=HypothesisRetrievalSourceType.HISTORICAL_INCIDENT.value,
    )
    vector = authority_score_for_source(
        source_type=HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE.value,
    )
    assert repo > docs > hist > vector
    assert authority_rank(HypothesisRetrievalSourceType.ARTIFACT.value) < authority_rank(
        HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE.value
    )


def test_terraform_path_boosts_authority() -> None:
    base = authority_score_for_source(
        source_type=HypothesisRetrievalSourceType.ARTIFACT.value,
        source_path="readme.md",
    )
    tf = authority_score_for_source(
        source_type=HypothesisRetrievalSourceType.ARTIFACT.value,
        source_path="modules/iam/main.tf",
    )
    assert tf >= base


def test_duplicate_diversity_penalty() -> None:
    diverse = diversity_score(
        source_types=["ARTIFACT", "TEMPORAL", "GRAPH", "DOCUMENTATION"],
        text_hashes=["a", "b", "c", "d"],
        source_paths=["p1", "p2", "p3", "p4"],
    )
    duped = diversity_score(
        source_types=["ARTIFACT", "ARTIFACT", "ARTIFACT", "ARTIFACT"],
        text_hashes=["same", "same", "same", "same"],
        source_paths=["p", "p", "p", "p"],
    )
    assert diverse > duped
    assert duped < 0.5


def test_empty_diversity_is_zero() -> None:
    assert diversity_score(source_types=[], text_hashes=[], source_paths=[]) == 0.0


# --- support / contradiction / sufficiency ---


def test_support_analyzer_scores_support_candidates() -> None:
    assessments = [
        EvidenceAssessment(
            item_id="a",
            hypothesis_id="h1",
            assessment_type=EvidenceAssessmentType.SUPPORT_CANDIDATE,
            confidence=0.8,
            relevance_score=0.85,
            authority_score=0.9,
            exact_identifier_overlap=0.7,
        ),
        EvidenceAssessment(
            item_id="b",
            hypothesis_id="h1",
            assessment_type=EvidenceAssessmentType.CONTEXT_ONLY,
            confidence=0.4,
            relevance_score=0.5,
            authority_score=0.5,
        ),
    ]
    result = HypothesisSupportAnalyzer().analyze(hypothesis_id="h1", assessments=assessments)
    assert result.support_item_count == 1
    assert result.support_score > 0.4
    assert "support_score_is_not_root_cause_confidence" in result.limitations
    assert "support_candidates_are_not_causal_confirmation" in result.limitations


def test_contradiction_analyzer_applies_penalty() -> None:
    assessments = [
        EvidenceAssessment(
            item_id="c1",
            hypothesis_id="h1",
            assessment_type=EvidenceAssessmentType.CONTRADICTION_CANDIDATE,
            confidence=0.8,
            relevance_score=0.75,
            authority_score=0.9,
        )
    ]
    result = HypothesisContradictionAnalyzer().analyze(
        hypothesis_id="h1", assessments=assessments
    )
    assert result.contradiction_item_count == 1
    assert result.contradiction_penalty > 0.2
    assert "contradiction_candidates_are_not_disproof" in result.limitations


def test_contradiction_empty_zero_penalty() -> None:
    result = HypothesisContradictionAnalyzer().analyze(hypothesis_id="h1", assessments=[])
    assert result.contradiction_penalty == 0.0


def test_sufficiency_insufficient_when_empty() -> None:
    result = EvidenceSufficiencyAssessor().assess(
        hypothesis_id="h1", assessments=[], items=[], context={}
    )
    assert result.level == EvidenceSufficiencyLevel.INSUFFICIENT
    assert result.sufficiency_score < 0.25


def test_sufficiency_reflects_open_set_and_graph_warnings() -> None:
    items = [
        _item(source_type=HypothesisRetrievalSourceType.ARTIFACT),
        _item(
            item_id="i2",
            source_type=HypothesisRetrievalSourceType.GRAPH,
            text_hash="h2",
            path="graph",
            order=1,
        ),
    ]
    assessments = EvidenceItemAssessor().assess_many(items, hypothesis_id="h1")
    clean = EvidenceSufficiencyAssessor().assess(
        hypothesis_id="h1", assessments=assessments, items=items, context={}
    )
    warned = EvidenceSufficiencyAssessor().assess(
        hypothesis_id="h1",
        assessments=assessments,
        items=items,
        context={
            "open_set_status": "OPEN",
            "graph_consistency_status": "INCONSISTENT",
            "graph_warnings": ["orphan_node"],
        },
    )
    assert any(w.startswith("open_set") for w in warned.warnings)
    assert "graph_inconsistency_or_partial" in warned.warnings
    assert warned.sufficiency_score <= clean.sufficiency_score


def test_sufficiency_high_with_diverse_sources() -> None:
    items = [
        _item(
            item_id=f"i{i}",
            source_type=st,
            text_hash=f"h{i}",
            path=f"p{i}",
            order=i,
            relevance=0.85,
            relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
        )
        for i, st in enumerate(
            [
                HypothesisRetrievalSourceType.ARTIFACT,
                HypothesisRetrievalSourceType.TEMPORAL,
                HypothesisRetrievalSourceType.GRAPH,
                HypothesisRetrievalSourceType.DOCUMENTATION,
                HypothesisRetrievalSourceType.HISTORICAL_INCIDENT,
            ]
        )
    ]
    assessments = EvidenceItemAssessor().assess_many(items, hypothesis_id="h1")
    result = EvidenceSufficiencyAssessor().assess(
        hypothesis_id="h1", assessments=assessments, items=items, context={}
    )
    assert result.level in {
        EvidenceSufficiencyLevel.MEDIUM,
        EvidenceSufficiencyLevel.HIGH,
    }
    assert result.diversity_score > 0.5


# --- ranking / selection ---


def _support(hid: str, score: float) -> HypothesisSupportAssessment:
    return HypothesisSupportAssessment(hypothesis_id=hid, support_score=score)


def _contradict(hid: str, penalty: float = 0.0) -> HypothesisContradictionAssessment:
    return HypothesisContradictionAssessment(
        hypothesis_id=hid, contradiction_penalty=penalty
    )


def _suff(hid: str, score: float, **kwargs: float) -> EvidenceSufficiencyAssessment:
    return EvidenceSufficiencyAssessment(
        hypothesis_id=hid,
        sufficiency_score=score,
        authority_score=kwargs.get("authority_score", score),
        diversity_score=kwargs.get("diversity_score", 0.5),
        temporal_completeness=kwargs.get("temporal_completeness", 0.5),
        graph_completeness=kwargs.get("graph_completeness", 0.5),
        documentation_completeness=kwargs.get("documentation_completeness", 0.5),
        historical_completeness=kwargs.get("historical_completeness", 0.3),
        level=EvidenceSufficiencyLevel.MEDIUM,
    )


def test_ranking_deterministic() -> None:
    engine = HypothesisRankingEngine(tie_epsilon=0.02)
    kwargs = dict(
        analysis_id="a1",
        organization_id="o1",
        hypothesis_ids=["h2", "h1"],
        hypothesis_keys={"h1": "H1", "h2": "H2"},
        support_by_id={"h1": _support("h1", 0.8), "h2": _support("h2", 0.4)},
        contradiction_by_id={"h1": _contradict("h1"), "h2": _contradict("h2", 0.3)},
        sufficiency_by_id={"h1": _suff("h1", 0.7), "h2": _suff("h2", 0.4)},
        generation_priors={"h1": 0.6, "h2": 0.5},
        mean_relevance_by_id={"h1": 0.75, "h2": 0.4},
    )
    r1 = engine.rank(**kwargs)  # type: ignore[arg-type]
    r2 = engine.rank(**kwargs)  # type: ignore[arg-type]
    assert [s.to_dict() for s in r1.scores] == [s.to_dict() for s in r2.scores]
    assert r1.scores[0].hypothesis_id == "h1"
    assert r1.scores[0].ranking_score > r1.scores[1].ranking_score
    assert "ranking_score_is_not_root_cause_confidence" in r1.scores[0].limitations


def test_ranking_contradiction_lowers_score() -> None:
    engine = HypothesisRankingEngine()
    base = engine.rank(
        analysis_id="a1",
        organization_id="o1",
        hypothesis_ids=["h1"],
        hypothesis_keys={"h1": "H1"},
        support_by_id={"h1": _support("h1", 0.8)},
        contradiction_by_id={"h1": _contradict("h1", 0.0)},
        sufficiency_by_id={"h1": _suff("h1", 0.7)},
        generation_priors={"h1": 0.5},
        mean_relevance_by_id={"h1": 0.7},
    )
    penalized = engine.rank(
        analysis_id="a1",
        organization_id="o1",
        hypothesis_ids=["h1"],
        hypothesis_keys={"h1": "H1"},
        support_by_id={"h1": _support("h1", 0.8)},
        contradiction_by_id={"h1": _contradict("h1", 0.9)},
        sufficiency_by_id={"h1": _suff("h1", 0.7)},
        generation_priors={"h1": 0.5},
        mean_relevance_by_id={"h1": 0.7},
    )
    assert penalized.scores[0].ranking_score < base.scores[0].ranking_score


def test_tie_detection_in_ranking() -> None:
    engine = HypothesisRankingEngine(tie_epsilon=0.05)
    result = engine.rank(
        analysis_id="a1",
        organization_id="o1",
        hypothesis_ids=["h1", "h2"],
        hypothesis_keys={"h1": "H1", "h2": "H2"},
        support_by_id={"h1": _support("h1", 0.5), "h2": _support("h2", 0.5)},
        contradiction_by_id={"h1": _contradict("h1"), "h2": _contradict("h2")},
        sufficiency_by_id={"h1": _suff("h1", 0.5), "h2": _suff("h2", 0.5)},
        generation_priors={"h1": 0.5, "h2": 0.5},
        mean_relevance_by_id={"h1": 0.5, "h2": 0.5},
    )
    assert "top_scores_within_tie_epsilon" in result.warnings


def _rank_score(
    hid: str,
    key: str,
    score: float,
    rank: int,
) -> HypothesisRankingScore:
    return HypothesisRankingScore(
        hypothesis_id=hid,
        hypothesis_key=key,
        ranking_score=score,
        rank=rank,
    )


def test_candidate_selection_tie() -> None:
    ranking = HypothesisRankingResult(
        analysis_id="a1",
        organization_id="o1",
        scores=[
            _rank_score("h1", "H1", 0.55, 1),
            _rank_score("h2", "H2", 0.54, 2),
        ],
        tie_epsilon=0.02,
    )
    selection = HypothesisCandidateSelector().select(
        ranking, min_ranking_score_for_top=0.40, tie_epsilon=0.02
    )
    assert selection.status == CandidateSelectionStatus.TIE
    assert selection.top_hypothesis_id is None


def test_candidate_selection_weak_evidence() -> None:
    ranking = HypothesisRankingResult(
        analysis_id="a1",
        organization_id="o1",
        scores=[_rank_score("h1", "H1", 0.2, 1)],
    )
    selection = HypothesisCandidateSelector().select(
        ranking, min_ranking_score_for_top=0.40
    )
    assert selection.status == CandidateSelectionStatus.WEAK_EVIDENCE


def test_candidate_selection_unknown_empty() -> None:
    ranking = HypothesisRankingResult(analysis_id="a1", organization_id="o1", scores=[])
    selection = HypothesisCandidateSelector().select(ranking)
    assert selection.status == CandidateSelectionStatus.UNKNOWN


def test_candidate_selection_top_n() -> None:
    ranking = HypothesisRankingResult(
        analysis_id="a1",
        organization_id="o1",
        scores=[
            _rank_score("h1", "H1", 0.8, 1),
            _rank_score("h2", "H2", 0.6, 2),
            _rank_score("h3", "H3", 0.5, 3),
        ],
    )
    selection = HypothesisCandidateSelector().select(
        ranking, max_candidates=3, min_ranking_score_for_top=0.40, tie_epsilon=0.02
    )
    assert selection.status == CandidateSelectionStatus.TOP_N
    assert selection.top_hypothesis_id == "h1"
    assert len(selection.selected_hypothesis_ids) == 3


def test_candidate_selection_single_top() -> None:
    ranking = HypothesisRankingResult(
        analysis_id="a1",
        organization_id="o1",
        scores=[_rank_score("h1", "H1", 0.8, 1)],
    )
    selection = HypothesisCandidateSelector().select(ranking, max_candidates=5)
    assert selection.status == CandidateSelectionStatus.TOP_CANDIDATE


# --- language / versions / openapi ---


def test_no_proven_verified_in_serialized_outputs() -> None:
    assessment = EvidenceItemAssessor().assess(
        _item(relation=RetrievalItemRelation.SUPPORT_CANDIDATE, relevance=0.9)
    )
    support = HypothesisSupportAnalyzer().analyze(
        hypothesis_id="h1", assessments=[assessment]
    )
    contradict = HypothesisContradictionAnalyzer().analyze(
        hypothesis_id="h1", assessments=[]
    )
    ranking = HypothesisRankingEngine().rank(
        analysis_id="a1",
        organization_id="o1",
        hypothesis_ids=["h1"],
        hypothesis_keys={"h1": "H1"},
        support_by_id={"h1": support},
        contradiction_by_id={"h1": contradict},
        sufficiency_by_id={"h1": _suff("h1", 0.6)},
        generation_priors={"h1": 0.4},
    )
    selection = HypothesisCandidateSelector().select(ranking)
    blob = json.dumps(
        {
            "a": assessment.to_dict(),
            "s": support.to_dict(),
            "c": contradict.to_dict(),
            "r": ranking.to_dict(),
            "sel": selection.to_dict(),
        }
    ).upper()
    assert "PROVEN" not in blob
    assert "VERIFIED" not in blob
    # Allowed: negation phrases like NOT_ROOT_CAUSE_CONFIDENCE
    assert "IS_NOT_ROOT_CAUSE_CONFIDENCE" in blob or "NOT_ROOT_CAUSE_CONFIDENCE" in blob



def test_versions_constants() -> None:
    assert EVIDENCE_ASSESSMENT_VERSION == "evidence_assessment_v1"
    assert EVIDENCE_SUFFICIENCY_VERSION == "evidence_sufficiency_v1"
    assert CONTRADICTION_ANALYSIS_VERSION == "contradiction_analysis_v1"
    assert SUPPORT_ANALYSIS_VERSION == "support_analysis_v1"
    assert HYPOTHESIS_RANKING_VERSION == "hypothesis_ranking_v1"
    assert CANDIDATE_SELECTION_VERSION == "candidate_selection_v1"


def test_openapi_includes_part3_paths() -> None:
    openapi_path = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
    if not openapi_path.exists():
        pytest.skip("openapi.json not generated yet")
    data = json.loads(openapi_path.read_text(encoding="utf-8"))
    paths = data.get("paths") or {}
    expected = [
        "/api/v1/analyses/{analysis_run_id}/hypothesis-ranking",
        "/api/v1/analyses/{analysis_run_id}/candidate-hypotheses",
        "/api/v1/analyses/{analysis_run_id}/evidence-assessment",
        "/api/v1/analyses/{analysis_run_id}/support-analysis",
        "/api/v1/analyses/{analysis_run_id}/contradictions",
        "/api/v1/analyses/{analysis_run_id}/evidence-sufficiency",
    ]
    for path in expected:
        assert path in paths, f"missing OpenAPI path {path}"


def test_ranking_score_field_not_named_root_cause_confidence() -> None:
    score = HypothesisRankingScore(hypothesis_id="h1", ranking_score=0.5)
    data = score.to_dict()
    assert "ranking_score" in data
    assert "root_cause_confidence" not in data
