"""Phase 6A.3 — hierarchical classification, open-set, and disagreement tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.ai.classification.confidence_breakdown import ClassificationConfidenceDecomposer
from app.ai.classification.disagreement_analyzer import ClassificationDisagreementAnalyzer
from app.ai.classification.hierarchical_orchestrator import HierarchicalClassificationOrchestrator
from app.ai.classification.open_set_detector import (
    OpenSetFailureDetector,
    OpenSetThresholds,
    parse_category_thresholds_json,
)
from app.ai.orchestration.analysis_context import AnalysisContext, ClassificationCandidate
from app.domain.classification.enums import (
    AgreementLevel,
    ClassificationConflictType,
    ClassificationStatus,
    OpenSetStatus,
)
from app.domain.classification.models import (
    ClassificationCandidateDetail,
    StageClassifierResult,
)
from app.domain.classification.taxonomy_registry import (
    FROZEN_CATEGORY_CODES,
    FailureTaxonomyRegistry,
    get_taxonomy_registry,
)


def _ctx(*, options: dict | None = None, **kwargs: object) -> AnalysisContext:
    merged_options = {"project_id": str(uuid4())}
    if options:
        merged_options.update(options)
    base = AnalysisContext(
        analysis_run_id=uuid4(),
        incident_id=uuid4(),
        organization_id=uuid4(),
        file_ids=[],
        options=merged_options,
        files=[],
        model_name="rules-hybrid",
        model_version="1.0.0",
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def _cand(
    code: str,
    conf: float,
    rules: list[str],
    rank: int = 1,
) -> ClassificationCandidate:
    return ClassificationCandidate(
        category_code=code,
        confidence=conf,
        rank=rank,
        matched_rules=rules,
        root_cause_summary="rc",
        technical_explanation="te",
        impact_summary="im",
    )


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


def test_every_frozen_category_mapped() -> None:
    registry = get_taxonomy_registry()
    assert set(p.legacy_category_code for p in registry.all_paths()) == set(
        FROZEN_CATEGORY_CODES
    )
    for code in FROZEN_CATEGORY_CODES:
        path = registry.map_code(code)
        assert path.level_3_code == code
        assert path.is_active
        assert path.level_1_code
        assert path.level_2_code


def test_duplicate_mappings_rejected() -> None:
    # Simulate duplicate detection by feeding two entries that share level-3
    # with different keys — registry rejects duplicate L3 when != key.
    with pytest.raises(ValueError, match="Duplicate|Unmapped"):
        FailureTaxonomyRegistry(
            mappings={
                **{c: ("UNKNOWN", "UNKNOWN", c) for c in FROZEN_CATEGORY_CODES},
                "extra_alias_row": ("APPLICATION", "COMPILATION", "build_failure"),
            }
        )


def test_unmapped_frozen_reporting() -> None:
    with pytest.raises(ValueError, match="Unmapped frozen"):
        FailureTaxonomyRegistry(
            mappings={
                "test_failure": ("TEST", "UNIT_TEST", "test_failure"),
            }
        )


def test_aliases_resolved() -> None:
    registry = get_taxonomy_registry()
    path = registry.map_code("aws_access_denied")
    assert path.legacy_category_code == "aws_permission_failure"
    assert path.level_1_code == "SECURITY"


def test_unknown_path_and_version() -> None:
    registry = get_taxonomy_registry()
    path = registry.map_code("totally_invented")
    assert path.level_1_code == "UNKNOWN"
    assert path.level_2_code == "LEGACY_UNMAPPED"
    assert path.is_active is False
    assert registry.mapping_version == "v1"
    assert registry.unknown_path().legacy_category_code == "unknown_failure"


# ---------------------------------------------------------------------------
# Open-set
# ---------------------------------------------------------------------------


def test_open_set_high_confidence_known() -> None:
    registry = get_taxonomy_registry()
    detector = OpenSetFailureDetector(registry=registry, enabled=True)
    cands = [
        ClassificationCandidateDetail(
            category_code="aws_permission_failure",
            score=0.92,
            source_classifier="rule",
            matched_rules=["aws_access_denied"],
            rank=1,
        ),
        ClassificationCandidateDetail(
            category_code="security_misconfiguration",
            score=0.2,
            source_classifier="learned_keyword",
            rank=2,
        ),
    ]
    rule = StageClassifierResult(
        stage="rule",
        category_code="aws_permission_failure",
        confidence=0.92,
        matched_rules=["aws_access_denied"],
        top_candidates=cands[:1],
        executed=True,
    )
    result = detector.assess(
        candidates=cands,
        rule_result=rule,
        learned_result=None,
        llm_result=None,
        evidence_coverage=0.8,
        disagreement_level="HIGH",
    )
    assert result.status == OpenSetStatus.KNOWN


def test_open_set_low_confidence_unknown() -> None:
    registry = get_taxonomy_registry()
    detector = OpenSetFailureDetector(registry=registry, enabled=True)
    cands = [
        ClassificationCandidateDetail(
            category_code="unknown_failure",
            score=0.2,
            source_classifier="fallback",
            rank=1,
        )
    ]
    result = detector.assess(
        candidates=cands,
        rule_result=StageClassifierResult(stage="rule", executed=True, matched_rules=[]),
        learned_result=None,
        llm_result=None,
        evidence_coverage=0.05,
        disagreement_level="SEVERE",
        parser_novel_signature=True,
    )
    assert result.status in {OpenSetStatus.UNKNOWN, OpenSetStatus.UNCERTAIN}
    assert result.unknown_score > 0
    assert result.triggered_conditions


def test_open_set_low_margin_uncertain() -> None:
    registry = get_taxonomy_registry()
    detector = OpenSetFailureDetector(
        registry=registry,
        thresholds=OpenSetThresholds(margin_threshold=0.15),
        enabled=True,
    )
    cands = [
        ClassificationCandidateDetail(category_code="test_failure", score=0.56, rank=1),
        ClassificationCandidateDetail(category_code="build_failure", score=0.54, rank=2),
    ]
    result = detector.assess(
        candidates=cands,
        rule_result=StageClassifierResult(
            stage="rule",
            executed=True,
            matched_rules=["test_assertion"],
            category_code="test_failure",
            confidence=0.56,
        ),
        learned_result=None,
        llm_result=None,
        evidence_coverage=0.4,
        disagreement_level="MODERATE",
    )
    assert result.status in {OpenSetStatus.UNCERTAIN, OpenSetStatus.KNOWN}
    assert any("margin" in c for c in result.triggered_conditions)


def test_open_set_category_specific_threshold() -> None:
    registry = get_taxonomy_registry()
    detector = OpenSetFailureDetector(
        registry=registry,
        thresholds=OpenSetThresholds(
            confidence_threshold=0.4,
            category_thresholds={"aws_permission_failure": {"confidence": 0.95}},
        ),
        enabled=True,
    )
    cands = [
        ClassificationCandidateDetail(
            category_code="aws_permission_failure", score=0.7, rank=1
        )
    ]
    result = detector.assess(
        candidates=cands,
        rule_result=StageClassifierResult(
            stage="rule",
            executed=True,
            matched_rules=["aws_access_denied"],
            category_code="aws_permission_failure",
            confidence=0.7,
        ),
        learned_result=None,
        llm_result=None,
        evidence_coverage=0.5,
    )
    assert any("confidence_below_threshold" in c for c in result.triggered_conditions)


def test_malformed_threshold_config_raises() -> None:
    with pytest.raises(ValueError):
        parse_category_thresholds_json('{"aws_permission_failure": {"confidence": "x"}}')
    with pytest.raises(ValueError):
        parse_category_thresholds_json('{"aws_permission_failure": {"nope": 0.1}}')
    assert parse_category_thresholds_json("{}") == {}
    assert parse_category_thresholds_json(
        '{"test_failure": {"margin": 0.2}}'
    ) == {"test_failure": {"margin": 0.2}}


# ---------------------------------------------------------------------------
# Disagreement
# ---------------------------------------------------------------------------


def test_disagreement_full_agreement() -> None:
    analyzer = ClassificationDisagreementAnalyzer(registry=get_taxonomy_registry())
    result = analyzer.analyze(
        rule_result=StageClassifierResult(
            stage="rule",
            category_code="terraform_failure",
            confidence=0.9,
            executed=True,
        ),
        learned_result=StageClassifierResult(
            stage="learned",
            category_code="terraform_failure",
            confidence=0.8,
            executed=True,
        ),
        llm_result=None,
    )
    assert result.agreement_level == AgreementLevel.HIGH
    assert result.agreed_level_3 == "terraform_failure"


def test_disagreement_same_domain_different_subcategory() -> None:
    analyzer = ClassificationDisagreementAnalyzer(registry=get_taxonomy_registry())
    result = analyzer.analyze(
        rule_result=StageClassifierResult(
            stage="rule",
            category_code="docker_failure",
            confidence=0.8,
            executed=True,
        ),
        learned_result=StageClassifierResult(
            stage="learned",
            category_code="deployment_failure",
            confidence=0.7,
            executed=True,
        ),
        llm_result=None,
    )
    assert result.conflict_type == ClassificationConflictType.SAME_DOMAIN_DIFFERENT_SUBCATEGORY
    assert result.agreement_level in {
        AgreementLevel.LOW,
        AgreementLevel.MODERATE,
        AgreementLevel.SEVERE,
    }


def test_disagreement_different_domains_severe() -> None:
    analyzer = ClassificationDisagreementAnalyzer(registry=get_taxonomy_registry())
    result = analyzer.analyze(
        rule_result=StageClassifierResult(
            stage="rule",
            category_code="aws_permission_failure",
            confidence=0.9,
            executed=True,
        ),
        learned_result=StageClassifierResult(
            stage="learned",
            category_code="dependency_failure",
            confidence=0.8,
            executed=True,
        ),
        llm_result=None,
        graph_category_hint="terraform_failure",
    )
    assert result.agreement_level == AgreementLevel.SEVERE
    assert result.conflict_type == ClassificationConflictType.DIFFERENT_DOMAIN
    assert result.confidence_penalty > 0
    # No majority-vote winner at L3 under severe disagreement
    assert result.agreed_level_3 is None


def test_disagreement_known_vs_unknown() -> None:
    analyzer = ClassificationDisagreementAnalyzer(registry=get_taxonomy_registry())
    result = analyzer.analyze(
        rule_result=StageClassifierResult(
            stage="rule",
            category_code="test_failure",
            confidence=0.7,
            executed=True,
        ),
        learned_result=StageClassifierResult(
            stage="learned",
            category_code="unknown_failure",
            confidence=0.5,
            executed=True,
        ),
        llm_result=None,
    )
    assert result.conflict_type == ClassificationConflictType.KNOWN_VS_UNKNOWN


# ---------------------------------------------------------------------------
# Orchestrator scenarios
# ---------------------------------------------------------------------------


def test_orchestrator_flags_off_disabled() -> None:
    orch = HierarchicalClassificationOrchestrator(hierarchical_enabled=False)
    ctx = _ctx(classifications=[_cand("aws_permission_failure", 0.9, ["aws_access_denied"])])
    result = orch.run(ctx)
    assert result.classification_status == ClassificationStatus.DISABLED


def test_orchestrator_iam_permission_known() -> None:
    orch = HierarchicalClassificationOrchestrator(
        hierarchical_enabled=True,
        open_set_enabled=True,
        disagreement_enabled=True,
        confidence_breakdown_enabled=True,
    )
    ctx = _ctx(
        classifications=[
            _cand("aws_permission_failure", 0.93, ["aws_access_denied"]),
            _cand("security_misconfiguration", 0.2, ["keyword:security_misconfiguration"], 2),
        ],
        options={"artifact_bundle": {"bundle_id": "b1", "missing_artifacts": []}},
    )
    result = orch.run(ctx)
    assert result.final_legacy_category_code == "aws_permission_failure"
    assert result.level_1_code == "SECURITY"
    assert result.level_2_code == "IAM_POLICY"
    assert result.level_3_code == "aws_permission_failure"
    assert result.classification_status in {
        ClassificationStatus.KNOWN,
        ClassificationStatus.KNOWN_LOW_CONFIDENCE,
    }
    assert result.open_set_result is not None
    assert result.disagreement_result is not None
    assert result.confidence_breakdown is not None
    assert result.evaluation_export.get("metrics_hooks")


def test_orchestrator_terraform_hierarchy() -> None:
    orch = HierarchicalClassificationOrchestrator(
        hierarchical_enabled=True,
        open_set_enabled=True,
        disagreement_enabled=True,
        confidence_breakdown_enabled=True,
    )
    ctx = _ctx(
        classifications=[_cand("terraform_failure", 0.91, ["terraform_error"])],
    )
    result = orch.run(ctx)
    assert result.level_1_code == "INFRASTRUCTURE"
    assert result.level_2_code == "TERRAFORM"
    assert result.level_3_code == "terraform_failure"


def test_orchestrator_dependency_and_test_and_workflow() -> None:
    orch = HierarchicalClassificationOrchestrator(
        hierarchical_enabled=True,
        open_set_enabled=True,
        disagreement_enabled=True,
        confidence_breakdown_enabled=True,
    )
    for code, l1, l2, rules in (
        ("dependency_failure", "DEPENDENCY", "PACKAGE_RESOLUTION", ["npm_dependency"]),
        ("test_failure", "TEST", "UNIT_TEST", ["test_assertion"]),
        ("configuration_failure", "WORKFLOW", "YAML_CONFIGURATION", ["config_invalid"]),
    ):
        result = orch.run(_ctx(classifications=[_cand(code, 0.88, rules)]))
        assert result.level_1_code == l1
        assert result.level_2_code == l2
        assert result.level_3_code == code


def test_orchestrator_generic_unknown_not_forced() -> None:
    orch = HierarchicalClassificationOrchestrator(
        hierarchical_enabled=True,
        open_set_enabled=True,
        disagreement_enabled=True,
        confidence_breakdown_enabled=True,
    )
    ctx = _ctx(
        classifications=[_cand("unknown_failure", 0.35, ["fallback:unknown"])],
        options={"novel_tool_signature": True},
    )
    result = orch.run(ctx)
    assert result.classification_status in {
        ClassificationStatus.UNKNOWN,
        ClassificationStatus.UNCERTAIN,
    }
    assert result.open_set_result is not None
    assert result.open_set_result.status in {OpenSetStatus.UNKNOWN, OpenSetStatus.UNCERTAIN}


def test_orchestrator_conflicting_evidence_no_majority_vote() -> None:
    orch = HierarchicalClassificationOrchestrator(
        hierarchical_enabled=True,
        open_set_enabled=True,
        disagreement_enabled=True,
        confidence_breakdown_enabled=True,
        llm_classification_enabled=True,
    )
    ctx = _ctx(
        classifications=[
            _cand("aws_permission_failure", 0.9, ["aws_access_denied"]),
            _cand("deployment_failure", 0.85, ["keyword:deployment_failure"], 2),
        ],
        options={
            "enable_llm": True,
            "llm_classification_candidates": [
                {"category_code": "terraform_failure", "confidence": 0.8, "evidence_ids": ["e1"]}
            ],
            "evidence_graph": {
                "node_count": 10,
                "edge_count": 8,
                "category_hint": "security_misconfiguration",
            },
        },
    )
    # Force learned top to differ by rewriting classifications order after learned uses same list
    result = orch.run(ctx)
    assert result.disagreement_result is not None
    if result.disagreement_result.agreement_level == AgreementLevel.SEVERE:
        assert result.classification_status in {
            ClassificationStatus.CONFLICTED,
            ClassificationStatus.UNCERTAIN,
            ClassificationStatus.UNKNOWN,
        }
        assert (
            result.disagreement_result.agreed_level_3 is None
            or result.classification_status != ClassificationStatus.KNOWN
        )


def test_orchestrator_rejects_invalid_llm_category() -> None:
    orch = HierarchicalClassificationOrchestrator(
        hierarchical_enabled=True,
        open_set_enabled=True,
        disagreement_enabled=True,
        confidence_breakdown_enabled=True,
        llm_classification_enabled=True,
    )
    ctx = _ctx(
        classifications=[_cand("test_failure", 0.8, ["test_assertion"])],
        options={
            "enable_llm": True,
            "llm_classification_candidates": [
                {"category_code": "invented_bogus_category", "confidence": 0.99},
                {"category_code": "test_failure", "confidence": 0.7, "evidence_ids": ["e1"]},
            ],
        },
    )
    result = orch.run(ctx)
    assert result.llm_result is not None
    assert result.llm_result.executed
    assert result.llm_result.category_code == "test_failure"
    assert any("rejected" in lim for lim in result.llm_result.limitations)
    assert all(c.category_code != "invented_bogus_category" for c in result.top_candidates)


def test_orchestrator_log_only_partial_missing_graph() -> None:
    orch = HierarchicalClassificationOrchestrator(
        hierarchical_enabled=True,
        open_set_enabled=True,
        disagreement_enabled=True,
        confidence_breakdown_enabled=True,
    )
    ctx = _ctx(classifications=[_cand("network_failure", 0.8, ["network_timeout"])])
    result = orch.run(ctx)
    assert result.level_1_code == "NETWORK"
    assert "evidence_graph" in result.missing_evidence
    assert result.confidence_breakdown is not None


def test_confidence_components_present() -> None:
    breakdown = ClassificationConfidenceDecomposer(enabled=True).decompose(
        rule_result=StageClassifierResult(
            stage="rule", confidence=0.9, executed=True, category_code="build_failure"
        ),
        learned_result=StageClassifierResult(
            stage="learned", confidence=0.7, executed=True, representation_quality=0.6
        ),
        llm_result=None,
        taxonomy_mapping_ok=True,
        evidence_coverage=0.5,
        temporal_support=0.0,
        graph_support=0.0,
        disagreement=None,
        open_set=None,
        missing_evidence_count=2,
    )
    names = {c.component_name for c in breakdown.components}
    assert "rule_confidence" in names
    assert "contradiction_penalty" in names
    assert "missing_evidence_penalty" in names
    assert 0.0 <= breakdown.final_confidence <= 1.0
