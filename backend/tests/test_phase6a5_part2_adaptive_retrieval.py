"""Phase 6A.5 Part 2 — adaptive hypothesis-directed retrieval unit tests."""

from __future__ import annotations

from uuid import uuid4

from app.ai.hypothesis_retrieval.adaptive_planner import AdaptiveHypothesisRetrievalPlanner
from app.ai.hypothesis_retrieval.features import RetrievalCandidateFeatureExtractor
from app.ai.hypothesis_retrieval.follow_up import HypothesisRetrievalFollowUpPlanner
from app.ai.hypothesis_retrieval.identifiers import RetrievalIdentifierExtractor
from app.ai.hypothesis_retrieval.intents import HypothesisQueryIntentGenerator
from app.ai.hypothesis_retrieval.plan_builder import HypothesisRetrievalPlanBuilder
from app.ai.hypothesis_retrieval.query_deduplicator import HypothesisQueryDeduplicator
from app.ai.hypothesis_retrieval.query_generator import HypothesisSpecificQueryGenerator
from app.ai.hypothesis_retrieval.query_sanitizer import RetrievalQuerySanitizer
from app.ai.hypothesis_retrieval.relevance import HypothesisRetrievalRelevanceScorer
from app.ai.hypothesis_retrieval.source_router import HypothesisRetrievalSourceRouter
from app.ai.hypothesis_retrieval.validator import RetrievalResultValidator
from app.ai.hypothesis_retrieval.versions import (
    ADAPTIVE_RETRIEVAL_PLANNER_VERSION,
    PLAN_VERSION_V2,
)
from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.rag.hybrid_query_builder import HybridDiagnosticQueryBuilder
from app.ai.rag.signals import DiagnosticSignalExtractor
from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalSourceType,
    QueryIntentType,
    RetrievalQueryType,
    RetrievalValidationStatus,
)
from app.domain.hypothesis_retrieval.models import (
    PLAN_VERSION,
    HypothesisRetrievalContext,
    HypothesisRetrievalQuerySpec,
    HypothesisRetrievedItem,
    RetrievalCandidateFeatureVector,
    RetrievalItemRelation,
)


def _ctx(**overrides: object) -> HypothesisRetrievalContext:
    base = HypothesisRetrievalContext(
        analysis_id=str(uuid4()),
        organization_id=str(uuid4()),
        incident_id=str(uuid4()),
        hypothesis_id=str(uuid4()),
        hypothesis_key="H1",
        category_code="IAM_PERMISSION",
        title="missing permission",
        causal_claim="deployment IAM role missing s3:PutObject permission",
        expected_observations=["policy simulation allows PutObject"],
        falsifying_observations=["role already has s3:PutObject"],
        missing_evidence=["identity policy document"],
        permission_actions=["s3:PutObject"],
        resource_identifiers=["arn:aws:iam::123456789012:role/deploy"],
        error_signature="AccessDenied",
        affected_path=".github/workflows/deploy.yml",
        changed_files=[".github/workflows/deploy.yml", "iam/role.tf"],
        commit_sha="abc1234",
        workflow_path=".github/workflows/deploy.yml",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_flags_off_plan_builder_unchanged_single_query() -> None:
    builder = HypothesisRetrievalPlanBuilder(multi_query_enabled=False)
    plan = builder.build(_ctx())
    assert plan.plan_version == PLAN_VERSION
    assert len(plan.query_specs) == 1
    assert plan.query_specs[0].query_id == "q_causal_claim"


def test_intent_generation_iam_missing() -> None:
    intents = HypothesisQueryIntentGenerator().generate(_ctx())
    types = {i.intent_type for i in intents}
    assert QueryIntentType.CONFIRM_CAUSAL_CLAIM in types
    assert QueryIntentType.FIND_PERMISSION_RELATIONSHIP in types
    assert QueryIntentType.FIND_CONTRADICTION_CANDIDATE in types
    assert QueryIntentType.FIND_POLICY_BEHAVIOR in types


def test_intent_generation_wrong_role() -> None:
    intents = HypothesisQueryIntentGenerator().generate(
        _ctx(causal_claim="workflow assumes wrong role ARN for deploy")
    )
    types = {i.intent_type for i in intents}
    assert QueryIntentType.VERIFY_ARTIFACT_RELATIONSHIP in types
    assert QueryIntentType.FIND_PRIOR_SUCCESS_DIFFERENCE in types


def test_intent_generation_unknown_open_set() -> None:
    intents = HypothesisQueryIntentGenerator().generate(
        _ctx(
            category_code=None,
            causal_claim="unknown failure signature XYZ",
            open_set_status="UNKNOWN",
            permission_actions=[],
        )
    )
    types = {i.intent_type for i in intents}
    assert QueryIntentType.FIND_EXACT_FAILURE_SIGNATURE in types
    assert QueryIntentType.EXPLORE_NOVEL_SIGNATURE in types


def test_identifier_extraction_action_arn_tf() -> None:
    ids = RetrievalIdentifierExtractor().extract(
        _ctx(
            causal_claim=(
                "AccessDenied s3:PutObject on arn:aws:s3:::bucket/key aws_iam_role.deploy_role"
            ),
            permission_actions=["s3:PutObject"],
            resource_identifiers=["arn:aws:iam::123456789012:role/deploy"],
        )
    )
    assert "s3:PutObject" in ids.aws_actions
    assert any(a.startswith("arn:aws:") for a in ids.aws_arns)
    assert any(r.startswith("aws_iam_role.") for r in ids.terraform_resources)


def test_identifier_extraction_excludes_secrets() -> None:
    ids = RetrievalIdentifierExtractor().extract(
        _ctx(
            causal_claim="password=supersecret token=abcd api_key=xyz",
            permission_actions=[],
            resource_identifiers=[],
        )
    )
    joined = " ".join(ids.all_identifiers).lower()
    assert "supersecret" not in joined
    assert "abcd" not in joined


def test_query_sanitizer_accepts_clean() -> None:
    result = RetrievalQuerySanitizer().sanitize("AccessDenied s3:PutObject")
    assert result.accepted
    assert result.normalized == "accessdenied s3:putobject"


def test_query_sanitizer_rejects_secret() -> None:
    result = RetrievalQuerySanitizer().sanitize("password=hunter2 AccessDenied")
    assert not result.accepted
    assert result.rejection_reason == "secret_like"


def test_query_sanitizer_rejects_empty() -> None:
    result = RetrievalQuerySanitizer().sanitize("   ")
    assert not result.accepted


def test_source_routing_iam() -> None:
    router = HypothesisRetrievalSourceRouter(graph_enabled=True, artifact_enabled=True)
    spec = HypothesisRetrievalQuerySpec(
        query_id="q1",
        query_type=RetrievalQueryType.PERMISSION_ACTION,
        query_text="s3:PutObject",
        normalized_query="s3:putobject",
        source_types=[HypothesisRetrievalSourceType.STATIC_KNOWLEDGE],
    )
    decision = router.route(_ctx(), spec)
    assert HypothesisRetrievalSourceType.ARTIFACT in decision.selected_sources
    assert HypothesisRetrievalSourceType.GRAPH in decision.selected_sources


def test_source_routing_terraform() -> None:
    router = HypothesisRetrievalSourceRouter(graph_enabled=True)
    spec = HypothesisRetrievalQuerySpec(
        query_id="q1",
        query_type=RetrievalQueryType.FAILURE_CATEGORY,
        query_text="invalid reference",
        normalized_query="invalid reference",
    )
    decision = router.route(
        _ctx(category_code="TERRAFORM_ERROR", causal_claim="terraform invalid reference"),
        spec,
    )
    assert HypothesisRetrievalSourceType.ARTIFACT in decision.selected_sources
    assert HypothesisRetrievalSourceType.GRAPH in decision.selected_sources


def test_source_routing_dependency() -> None:
    router = HypothesisRetrievalSourceRouter()
    spec = HypothesisRetrievalQuerySpec(
        query_id="q1",
        query_type=RetrievalQueryType.FAILURE_CATEGORY,
        query_text="dependency conflict",
        normalized_query="dependency conflict",
    )
    decision = router.route(
        _ctx(category_code="DEPENDENCY", causal_claim="package dependency conflict"),
        spec,
    )
    assert HypothesisRetrievalSourceType.ARTIFACT in decision.selected_sources


def test_source_routing_unknown() -> None:
    router = HypothesisRetrievalSourceRouter()
    spec = HypothesisRetrievalQuerySpec(
        query_id="q1",
        query_type=RetrievalQueryType.ERROR_SIGNATURE,
        query_text="mystery",
        normalized_query="mystery",
    )
    decision = router.route(
        _ctx(category_code="UNKNOWN", causal_claim="mystery boom", permission_actions=[]),
        spec,
    )
    assert HypothesisRetrievalSourceType.LEXICAL_KNOWLEDGE in decision.selected_sources


def test_validator_accept() -> None:
    item = HypothesisRetrievedItem(
        source_type=HypothesisRetrievalSourceType.ARTIFACT,
        source_system="test",
        text_excerpt="role missing s3:PutObject",
        query_id="q1",
        hypothesis_id="h1",
        adapter_name="artifact_evidence",
        retrieval_score=0.8,
    )
    result = RetrievalResultValidator().validate(item, _ctx())
    assert result.status == RetrievalValidationStatus.ACCEPTED


def test_validator_reject_org_mismatch() -> None:
    ctx = _ctx()
    item = HypothesisRetrievedItem(
        source_type=HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
        source_system="kb",
        text_excerpt="doc",
        query_id="q1",
        hypothesis_id="h1",
        adapter_name="hybrid",
        retrieval_score=0.5,
        metadata={"organization_id": "other-org"},
    )
    result = RetrievalResultValidator().validate(item, ctx)
    assert result.status == RetrievalValidationStatus.REJECTED_SCOPE


def test_validator_reject_empty() -> None:
    item = HypothesisRetrievedItem(
        source_type=HypothesisRetrievalSourceType.ARTIFACT,
        source_system="test",
        text_excerpt="  ",
        query_id="q1",
        hypothesis_id="h1",
        adapter_name="a",
    )
    result = RetrievalResultValidator().validate(item, _ctx())
    assert result.status == RetrievalValidationStatus.REJECTED_EMPTY


def test_validator_reject_secret() -> None:
    item = HypothesisRetrievedItem(
        source_type=HypothesisRetrievalSourceType.ARTIFACT,
        source_system="test",
        text_excerpt="password=supersecret",
        query_id="q1",
        hypothesis_id="h1",
        adapter_name="a",
        retrieval_score=0.4,
    )
    result = RetrievalResultValidator().validate(item, _ctx())
    assert result.status == RetrievalValidationStatus.REJECTED_SECRET_RISK


def test_relevance_exact_match_boost_and_active_weights() -> None:
    features = RetrievalCandidateFeatureVector(
        exact_identifier_overlap=1.0,
        lexical_similarity=0.5,
        vector_similarity=None,
    )
    scorer = HypothesisRetrievalRelevanceScorer(exact_identifier_boost_enabled=True)
    assessment = scorer.score(item_id="i1", features=features, retrieval_score=0.4)
    assert "retrieval_relevance_score" in assessment.to_dict()
    assert assessment.retrieval_relevance_score == assessment.normalized_score
    assert "causal" not in assessment.to_dict()
    assert assessment.active_weights
    assert "exact_identifier_boost" in assessment.contribution_by_component
    # Score name must not be causal confidence.
    assert not hasattr(assessment, "causal_confidence")


def test_relevance_without_boost() -> None:
    features = RetrievalCandidateFeatureVector(exact_identifier_overlap=1.0)
    boosted = HypothesisRetrievalRelevanceScorer(exact_identifier_boost_enabled=True).score(
        item_id="a", features=features
    )
    plain = HypothesisRetrievalRelevanceScorer(exact_identifier_boost_enabled=False).score(
        item_id="a", features=features
    )
    assert boosted.retrieval_relevance_score >= plain.retrieval_relevance_score


def test_follow_up_triggers_on_weak() -> None:
    decision = HypothesisRetrievalFollowUpPlanner().plan(
        _ctx(),
        accepted_items=[],
        existing_specs=[],
        current_round=0,
        max_relevance=0.1,
        had_exact_identifier_match=False,
    )
    assert decision.should_follow_up
    assert decision.round_number == 1
    assert decision.follow_up_specs


def test_follow_up_not_on_strong() -> None:
    items = [
        HypothesisRetrievedItem(
            source_type=HypothesisRetrievalSourceType.ARTIFACT,
            source_system="t",
            text_excerpt="policy simulation allows PutObject",
            query_id="q",
            hypothesis_id="h",
            adapter_name="a",
            retrieval_score=0.9,
        ),
        HypothesisRetrievedItem(
            source_type=HypothesisRetrievalSourceType.GRAPH,
            source_system="t",
            text_excerpt="s3:PutObject path",
            query_id="q",
            hypothesis_id="h",
            adapter_name="a",
            retrieval_score=0.8,
        ),
    ]
    decision = HypothesisRetrievalFollowUpPlanner().plan(
        _ctx(),
        accepted_items=items,
        existing_specs=[],
        required_source_types=[HypothesisRetrievalSourceType.ARTIFACT],
        current_round=0,
        max_relevance=0.9,
        had_exact_identifier_match=True,
    )
    assert not decision.should_follow_up


def test_follow_up_one_round_max() -> None:
    decision = HypothesisRetrievalFollowUpPlanner(max_rounds=1).plan(
        _ctx(),
        accepted_items=[],
        existing_specs=[],
        current_round=1,
        max_relevance=0.0,
        had_exact_identifier_match=False,
    )
    assert not decision.should_follow_up
    assert "max_rounds_reached" in decision.trigger_reasons


def test_query_dedupe_within_session() -> None:
    spec_a = HypothesisRetrievalQuerySpec(
        query_id="a",
        query_type=RetrievalQueryType.CAUSAL_CLAIM,
        query_text="claim",
        normalized_query="claim",
        source_types=[HypothesisRetrievalSourceType.ARTIFACT],
        expected_relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
        metadata={"intent_type": "CONFIRM_CAUSAL_CLAIM"},
    )
    spec_b = HypothesisRetrievalQuerySpec(
        query_id="b",
        query_type=RetrievalQueryType.CAUSAL_CLAIM,
        query_text="claim",
        normalized_query="claim",
        source_types=[HypothesisRetrievalSourceType.ARTIFACT],
        expected_relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
        metadata={"intent_type": "CONFIRM_CAUSAL_CLAIM"},
    )
    kept, dups = HypothesisQueryDeduplicator().deduplicate([spec_a, spec_b])
    assert len(kept) == 1
    assert dups == 1


def test_query_dedupe_preserves_distinct_relation() -> None:
    spec_a = HypothesisRetrievalQuerySpec(
        query_id="a",
        query_type=RetrievalQueryType.CAUSAL_CLAIM,
        query_text="claim",
        normalized_query="claim",
        source_types=[HypothesisRetrievalSourceType.ARTIFACT],
        expected_relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
        metadata={"intent_type": "CONFIRM_CAUSAL_CLAIM"},
    )
    spec_b = HypothesisRetrievalQuerySpec(
        query_id="b",
        query_type=RetrievalQueryType.FALSIFYING_OBSERVATION,
        query_text="claim",
        normalized_query="claim",
        source_types=[HypothesisRetrievalSourceType.ARTIFACT],
        expected_relation=RetrievalItemRelation.CONTRADICTION_CANDIDATE,
        metadata={"intent_type": "FIND_CONTRADICTION_CANDIDATE"},
    )
    kept, dups = HypothesisQueryDeduplicator().deduplicate([spec_a, spec_b])
    assert len(kept) == 2
    assert dups == 0


def test_adaptive_planner_deterministic() -> None:
    planner = AdaptiveHypothesisRetrievalPlanner(
        source_routing_enabled=True,
        expansion_enabled=False,
        max_total_queries=10,
        graph_enabled=True,
    )
    basic = HypothesisRetrievalPlanBuilder(multi_query_enabled=True).build(_ctx())
    a = planner.plan(_ctx(hypothesis_id="hid"), basic, session_id="s1")
    b = planner.plan(_ctx(hypothesis_id="hid"), basic, session_id="s1")
    assert a.adaptive_plan_version == PLAN_VERSION_V2
    assert a.planner_version == ADAPTIVE_RETRIEVAL_PLANNER_VERSION
    assert [q.query_id for q in a.query_specs] == [q.query_id for q in b.query_specs]
    assert a.basic_plan_snapshot["plan_version"] == PLAN_VERSION
    # Never mutate basic plan in place.
    assert basic.plan_version == PLAN_VERSION


def test_adaptive_planner_does_not_mutate_basic_plan_object() -> None:
    planner = AdaptiveHypothesisRetrievalPlanner(max_total_queries=8)
    basic = HypothesisRetrievalPlanBuilder(multi_query_enabled=True).build(_ctx())
    original_ids = [q.query_id for q in basic.query_specs]
    planner.plan(_ctx(), basic)
    assert [q.query_id for q in basic.query_specs] == original_ids


def test_query_generator_records_intent_metadata() -> None:
    ctx = _ctx()
    intents = HypothesisQueryIntentGenerator().generate(ctx)
    ids = RetrievalIdentifierExtractor().extract(ctx)
    specs = HypothesisSpecificQueryGenerator().generate(
        ctx, intents[:3], ids, expansion_enabled=False
    )
    assert specs
    assert all(s.metadata.get("intent_id") for s in specs)


def test_hybrid_structured_options_override_rank1() -> None:
    from app.ai.orchestration.analysis_context import ClassificationCandidate

    analysis_id = uuid4()
    ctx = AnalysisContext(
        analysis_run_id=analysis_id,
        organization_id=uuid4(),
        incident_id=uuid4(),
        options={
            "hypothesis_directed_query": "role missing s3:PutObject",
            "hypothesis_directed_structured": {
                "failure_category": "IAM_PERMISSION",
                "error_codes": ["AccessDenied"],
                "keywords": ["s3:PutObject", "deploy_role"],
                "aws_services": ["s3"],
            },
        },
        classifications=[
            ClassificationCandidate(
                category_code="NETWORK",
                confidence=0.99,
                rank=1,
                root_cause_summary="rank1 leak",
            )
        ],
    )
    query = HybridDiagnosticQueryBuilder(DiagnosticSignalExtractor()).build(ctx)
    assert query.failure_category == "IAM_PERMISSION"
    assert "AccessDenied" in query.error_codes
    assert "s3:PutObject" in query.keywords


def test_hybrid_without_structured_keeps_baseline_path() -> None:
    ctx = AnalysisContext(
        analysis_run_id=uuid4(),
        organization_id=uuid4(),
        incident_id=uuid4(),
        options={},
    )
    query = HybridDiagnosticQueryBuilder().build(ctx)
    assert query.sanitised_text is not None


def test_feature_extractor_null_safe() -> None:
    item = HypothesisRetrievedItem(
        source_type=HypothesisRetrievalSourceType.ARTIFACT,
        source_system="t",
        text_excerpt="AccessDenied s3:PutObject",
        query_id="q",
        hypothesis_id="h",
        adapter_name="a",
        retrieval_score=0.5,
        vector_score=None,
        lexical_score=0.4,
    )
    features = RetrievalCandidateFeatureExtractor().extract(item, _ctx())
    assert features.vector_similarity is None
    assert features.lexical_similarity == 0.4
    assert features.exact_error_match == 1.0


def test_versions_constants_present() -> None:
    from app.ai.hypothesis_retrieval import versions as v

    assert v.ADAPTIVE_RETRIEVAL_PLANNER_VERSION == "adaptive_retrieval_planner_v1"
    assert v.HYPOTHESIS_QUERY_INTENTS_VERSION == "hypothesis_query_intents_v1"
    assert v.HYPOTHESIS_QUERY_GENERATOR_VERSION == "hypothesis_query_generator_v1"
    assert v.RETRIEVAL_IDENTIFIER_EXTRACTOR_VERSION == "retrieval_identifier_extractor_v1"
    assert v.HYPOTHESIS_SOURCE_ROUTER_VERSION == "hypothesis_source_router_v1"
    assert v.HYPOTHESIS_GRAPH_RETRIEVAL_VERSION == "hypothesis_graph_retrieval_v1"
    assert v.HYPOTHESIS_ARTIFACT_RETRIEVAL_VERSION == "hypothesis_artifact_retrieval_v1"
    assert v.HYPOTHESIS_TEMPORAL_RETRIEVAL_VERSION == "hypothesis_temporal_retrieval_v1"
    assert v.RETRIEVAL_RESULT_VALIDATOR_VERSION == "retrieval_result_validator_v1"
    assert v.RETRIEVAL_CANDIDATE_FEATURES_VERSION == "retrieval_candidate_features_v1"
    assert v.HYPOTHESIS_RETRIEVAL_RELEVANCE_VERSION == "hypothesis_retrieval_relevance_v1"
    assert v.HYPOTHESIS_FOLLOW_UP_VERSION == "hypothesis_follow_up_v1"
    assert v.PLAN_VERSION_V2 == "retrieval_plan_v2"
    assert v.RETRIEVAL_PIPELINE_VERSION_V2 == "hypothesis_directed_v2"


def test_cache_key_includes_intelligence_fingerprints() -> None:
    from app.ai.hypothesis_retrieval.cache import build_retrieval_cache_key

    a = build_retrieval_cache_key(
        organization_id="o",
        project_id=None,
        knowledge_base_version="kb",
        embedding_model_version="e",
        adapter_name="hybrid",
        adapter_version="v1",
        normalized_query="q",
        source_filters=["ARTIFACT"],
        repository_commit=None,
        artifact_constraints={},
        top_k=5,
        plan_version="retrieval_plan_v2",
        intent_fingerprint="confirm",
        routing_fingerprint="ARTIFACT,GRAPH",
        filter_fingerprint="s3:PutObject",
    )
    b = build_retrieval_cache_key(
        organization_id="o",
        project_id=None,
        knowledge_base_version="kb",
        embedding_model_version="e",
        adapter_name="hybrid",
        adapter_version="v1",
        normalized_query="q",
        source_filters=["ARTIFACT"],
        repository_commit=None,
        artifact_constraints={},
        top_k=5,
        plan_version="retrieval_plan_v2",
        intent_fingerprint="other",
        routing_fingerprint="ARTIFACT,GRAPH",
        filter_fingerprint="s3:PutObject",
    )
    assert a != b


def test_repository_adapter_from_context_only() -> None:
    from app.ai.hypothesis_retrieval.adapters.repository import (
        RepositoryChangeRetrievalAdapter,
    )

    adapter = RepositoryChangeRetrievalAdapter()
    spec = HypothesisRetrievalQuerySpec(
        query_id="q",
        query_type=RetrievalQueryType.CUSTOM_RULE,
        query_text="workflow change",
        normalized_query="workflow change",
        source_types=[HypothesisRetrievalSourceType.REPOSITORY_CHANGE],
    )
    result = adapter.retrieve(_ctx(), spec)
    assert result.status in {"COMPLETE", "NO_EVIDENCE"}
    assert all(
        i.source_type == HypothesisRetrievalSourceType.REPOSITORY_CHANGE for i in result.items
    )


def test_adaptive_planner_caps_total_queries() -> None:
    planner = AdaptiveHypothesisRetrievalPlanner(
        max_total_queries=3,
        expansion_enabled=True,
        source_routing_enabled=False,
    )
    basic = HypothesisRetrievalPlanBuilder(multi_query_enabled=True, max_queries=6).build(_ctx())
    plan = planner.plan(_ctx(), basic)
    assert len(plan.query_specs) <= 3
    assert plan.was_downgraded


def test_query_intent_types_complete() -> None:
    expected = {
        "CONFIRM_CAUSAL_CLAIM",
        "FIND_CONTRADICTION_CANDIDATE",
        "RESOLVE_MISSING_EVIDENCE",
        "VERIFY_ARTIFACT_RELATIONSHIP",
        "FIND_HISTORICAL_ANALOGUE",
        "FIND_OFFICIAL_CONSTRAINT",
        "FIND_POLICY_BEHAVIOR",
        "FIND_CONFIGURATION_REQUIREMENT",
        "FIND_PRIOR_SUCCESS_DIFFERENCE",
        "FIND_EXACT_FAILURE_SIGNATURE",
        "FIND_RESOURCE_RELATIONSHIP",
        "FIND_PERMISSION_RELATIONSHIP",
        "EXPLORE_NOVEL_SIGNATURE",
    }
    assert {m.value for m in QueryIntentType} == expected


def test_orchestrator_disabled_path_still_exists() -> None:
    from app.ai.hypothesis_retrieval.orchestrator import (
        HypothesisDirectedRetrievalOrchestrator,
    )
    from app.core.config import Settings

    settings = Settings(
        PROJECT_NAME="t",
        APP_VERSION="1",
        ENVIRONMENT="development",
        DEBUG=False,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
        JWT_SECRET_KEY="x" * 32,
        HYPOTHESIS_DIRECTED_RAG_ENABLED=False,
        ADAPTIVE_HYPOTHESIS_RETRIEVAL_ENABLED=False,
    )
    orch = HypothesisDirectedRetrievalOrchestrator(settings)
    assert orch._settings.adaptive_hypothesis_retrieval_enabled is False
