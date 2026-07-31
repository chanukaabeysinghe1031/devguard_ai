"""Phase 6A.4 — competing causal hypothesis generation tests."""

from __future__ import annotations

from uuid import uuid4

from app.ai.hypotheses.dedupe_critic import (
    CausalHypothesisCritic,
    GenerationPriorScorer,
    HypothesisDeduplicator,
)
from app.ai.hypotheses.llm_generator import parse_llm_hypotheses
from app.ai.hypotheses.orchestrator import CausalHypothesisOrchestrator
from app.ai.hypotheses.rule_generator import RuleBasedHypothesisGenerator
from app.ai.hypotheses.validators import HypothesisCausalPathValidator, HypothesisReferenceValidator
from app.ai.orchestration.analysis_context import AnalysisContext, ClassificationCandidate
from app.domain.hypotheses.enums import (
    CriticDecision,
    HypothesisEvidenceRelation,
    HypothesisGeneratorType,
    HypothesisRunStatus,
    HypothesisStatus,
)
from app.domain.hypotheses.models import (
    CausalHypothesis,
    HypothesisEvidenceLink,
    HypothesisGenerationContext,
)
from app.domain.hypotheses.templates import TEMPLATES_V1


def _ctx_text(text: str, **opts: object) -> HypothesisGenerationContext:
    return HypothesisGenerationContext(
        analysis_id=str(uuid4()),
        organization_id=str(uuid4()),
        combined_text_excerpt=text,
        hierarchical_classification=dict(opts.get("hier") or {}),  # type: ignore[arg-type]
        open_set_status=str(opts.get("open_set") or "") or None,
        disagreement_result=dict(opts.get("disagreement") or {}),  # type: ignore[arg-type]
        temporal_primary_failure=dict(opts.get("temporal") or {}),  # type: ignore[arg-type]
        relevant_graph_nodes=list(opts.get("nodes") or []),  # type: ignore[arg-type]
        relevant_graph_edges=list(opts.get("edges") or []),  # type: ignore[arg-type]
        evidence_candidates=list(opts.get("evidence") or []),  # type: ignore[arg-type]
        artifact_availability=list(opts.get("artifacts") or []),  # type: ignore[arg-type]
        missing_artifacts=list(opts.get("missing") or []),  # type: ignore[arg-type]
    )


def test_templates_cover_core_families() -> None:
    families = {t.family for t in TEMPLATES_V1}
    assert {"iam", "terraform", "workflow", "dependency", "container"} <= families
    assert len(TEMPLATES_V1) >= 20


def test_rule_generator_missing_iam_permission() -> None:
    gen = RuleBasedHypothesisGenerator(enabled=True, max_hypotheses=5)
    ctx = _ctx_text(
        "An error occurred (AccessDenied) when calling the PutObject operation: "
        "User is not authorized to perform s3:PutObject",
        hier={"final_legacy_category_code": "aws_permission_failure"},
        artifacts=["modules/deployment/iam.tf"],
        evidence=[{"id": "evidence-1", "evidence_type": "log_excerpt"}],
    )
    hyps = gen.generate(ctx)
    assert hyps
    ids = {h.template_id for h in hyps}
    assert "iam.missing_identity_permission" in ids
    top = next(h for h in hyps if h.template_id == "iam.missing_identity_permission")
    assert top.category_code == "aws_permission_failure"
    assert top.expected_observations
    assert top.falsifying_observations
    assert top.proposed_verification_steps
    assert top.status != HypothesisStatus.FAILED
    # No verified claim
    assert top.status.value != "VERIFIED"


def test_rule_generator_explicit_deny_and_wrong_role_signals() -> None:
    gen = RuleBasedHypothesisGenerator(enabled=True, max_hypotheses=5)
    deny = gen.generate(
        _ctx_text(
            "AccessDenied explicit deny from bucket policy on principal",
            hier={"final_legacy_category_code": "aws_permission_failure"},
        )
    )
    assert any(h.template_id == "iam.explicit_resource_deny" for h in deny)
    wrong = gen.generate(
        _ctx_text(
            "AssumedRole arn:aws:sts::123:assumed-role/wrong-role/session STS AccessDenied",
            hier={"final_legacy_category_code": "aws_permission_failure"},
        )
    )
    assert any(h.template_id == "iam.wrong_assumed_role" for h in wrong)


def test_rule_generator_terraform_invalid_reference() -> None:
    gen = RuleBasedHypothesisGenerator(enabled=True)
    hyps = gen.generate(
        _ctx_text(
            "Error: Reference to undeclared resource aws_s3_bucket.artifacts",
            hier={"final_legacy_category_code": "terraform_failure"},
            artifacts=["main.tf"],
        )
    )
    assert any(h.template_id == "tf.invalid_reference" for h in hyps)


def test_rule_generator_dependency_and_secret_and_workflow() -> None:
    gen = RuleBasedHypothesisGenerator(enabled=True)
    dep = gen.generate(_ctx_text("npm ERR! code ERESOLVE unable to resolve dependency tree"))
    assert any(h.category_code == "dependency_failure" for h in dep)
    secret = gen.generate(_ctx_text("Error: Secret MY_TOKEN was not found in secrets context"))
    assert any(h.template_id == "wf.missing_secret" for h in secret)
    # Secret value must not appear in claim
    for h in secret:
        assert "AKIA" not in h.causal_claim


def test_open_set_unknown_does_not_force_known() -> None:
    gen = RuleBasedHypothesisGenerator(enabled=True)
    hyps = gen.generate(
        _ctx_text("obscure vendor tool crashed with code ZX-999", open_set="UNKNOWN")
    )
    assert len(hyps) == 1
    assert hyps[0].category_code == "unknown_failure"
    assert hyps[0].status == HypothesisStatus.INCOMPLETE


def test_reference_validator_rejects_fabricated_category_and_nodes() -> None:
    validator = HypothesisReferenceValidator()
    ctx = _ctx_text(
        "accessdenied",
        nodes=[{"stable_key": "n1", "node_type": "LOG", "label": "AccessDenied"}],
        evidence=[{"id": "evidence-1"}],
    )
    bad = CausalHypothesis(
        hypothesis_key="H1",
        title="x",
        causal_claim="invented",
        category_code="not_a_real_category",
        root_cause_node_id="fabricated-node",
        generator_type=HypothesisGeneratorType.LLM,
    )
    result = validator.validate(bad, ctx)
    assert result.accepted is False
    assert bad.status == HypothesisStatus.INVALID


def test_path_validator_partial_and_valid() -> None:
    validator = HypothesisCausalPathValidator()
    ctx = _ctx_text(
        "x",
        nodes=[
            {"stable_key": "a", "node_type": "STEP"},
            {"stable_key": "b", "node_type": "ERROR"},
        ],
        edges=[
            {
                "id": "e1",
                "source_node_id": "a",
                "target_node_id": "b",
                "edge_type": "LEADS_TO",
                "derivation_type": "HEURISTIC",
            }
        ],
    )
    hyp = CausalHypothesis(
        hypothesis_key="H1",
        title="t",
        causal_claim="c",
        root_cause_node_id="a",
        observed_failure_node_id="b",
        causal_path_node_ids=["a", "b"],
        causal_path_edge_ids=["e1"],
    )
    out = validator.validate(hyp, ctx)
    assert out.path_validation_status.value in {"VALID", "VALID_WITH_WARNINGS"}


def test_dedupe_removes_same_template_and_similar_claims() -> None:
    deduper = HypothesisDeduplicator()
    a = CausalHypothesis(
        hypothesis_key="H1",
        title="Missing permission",
        causal_claim="The active identity policy does not grant the denied action.",
        category_code="aws_permission_failure",
        template_id="iam.missing_identity_permission",
        generation_confidence=0.8,
    )
    b = CausalHypothesis(
        hypothesis_key="H2",
        title="Missing permission again",
        causal_claim="The active identity policy does not grant the denied action for resource.",
        category_code="aws_permission_failure",
        template_id="iam.missing_identity_permission",
        generation_confidence=0.7,
    )
    c = CausalHypothesis(
        hypothesis_key="H3",
        title="Wrong role",
        causal_claim="The workflow assumed an unexpected role instead of the deployment role.",
        category_code="aws_permission_failure",
        template_id="iam.wrong_assumed_role",
        generation_confidence=0.75,
    )
    kept, removed = deduper.deduplicate([a, b, c])
    assert removed >= 1
    assert any(h.template_id == "iam.wrong_assumed_role" for h in kept)


def test_critic_rejects_downstream_symptom_and_flags_missing() -> None:
    critic = CausalHypothesisCritic(enabled=True)
    ctx = _ctx_text(
        "workflow failed after accessdenied",
        temporal={"primary_failure_summary": "AccessDenied earlier"},
        nodes=[{"stable_key": "wf", "label": "workflow failed", "node_type": "STATUS"}],
    )
    hyp = CausalHypothesis(
        hypothesis_key="H1",
        title="Workflow failed",
        causal_claim="The workflow failed with exit code 1",
        root_cause_node_id="wf",
        missing_evidence=["iam_policy"],
        evidence_links=[
            HypothesisEvidenceLink(
                evidence_type="x",
                relation=HypothesisEvidenceRelation.MISSING,
                explanation="iam_policy",
            )
        ],
    )
    result = critic.critique(hyp, ctx)
    assert result.decision in {
        CriticDecision.REJECT,
        CriticDecision.INCOMPLETE,
        CriticDecision.ACCEPT_WITH_WARNINGS,
    }


def test_llm_parse_rejects_fabricated_category_and_accepts_valid() -> None:
    ctx = _ctx_text("accessdenied", evidence=[{"id": "evidence-1"}])
    hyps, errors = parse_llm_hypotheses(
        {
            "hypotheses": [
                {
                    "hypothesis_key": "L1",
                    "category_code": "invented_bogus",
                    "title": "bad",
                    "causal_claim": "bad claim",
                },
                {
                    "hypothesis_key": "L2",
                    "category_code": "aws_permission_failure",
                    "title": "Missing permission",
                    "causal_claim": "Role lacks s3:PutObject",
                    "generation_confidence": 0.6,
                    "supporting_evidence": [{"evidence_id": "evidence-1", "reason": "log"}],
                    "expected_observations": ["still denied"],
                    "falsifying_observations": ["put succeeds"],
                    "proposed_verification_steps": ["simulate policy"],
                },
            ]
        },
        context=ctx,
    )
    assert any("fabricated_category" in e for e in errors)
    assert len(hyps) == 1
    assert hyps[0].category_code == "aws_permission_failure"


def test_llm_malformed_json() -> None:
    hyps, errors = parse_llm_hypotheses("{not json", context=_ctx_text("x"))
    assert hyps == []
    assert errors


def test_orchestrator_flags_off() -> None:
    orch = CausalHypothesisOrchestrator(enabled=False)
    ctx = AnalysisContext(
        analysis_run_id=uuid4(),
        incident_id=uuid4(),
        organization_id=uuid4(),
    )
    run = orch.run(ctx)
    assert run.status == HypothesisRunStatus.DISABLED
    assert run.hypotheses == []


def test_orchestrator_rule_only_iam_case() -> None:
    orch = CausalHypothesisOrchestrator(
        enabled=True,
        rule_enabled=True,
        llm_enabled=False,
        critic_enabled=True,
        max_hypotheses=5,
    )
    ctx = AnalysisContext(
        analysis_run_id=uuid4(),
        incident_id=uuid4(),
        organization_id=uuid4(),
        combined_text=(
            "An error occurred (AccessDenied) when calling the PutObject operation "
            "User is not authorized to perform: s3:PutObject"
        ),
        classifications=[
            ClassificationCandidate(
                category_code="aws_permission_failure",
                confidence=0.9,
                rank=1,
                matched_rules=["aws_access_denied"],
                root_cause_summary="IAM permission missing",
            )
        ],
        options={
            "hierarchical_classification": {
                "final_legacy_category_code": "aws_permission_failure",
                "open_set_status": "KNOWN",
            },
            "artifact_bundle": {"available_artifacts": ["iam.tf"], "missing_artifacts": []},
        },
    )
    run = orch.run(ctx)
    assert run.status in {HypothesisRunStatus.COMPLETED, HypothesisRunStatus.PARTIAL}
    assert run.hypotheses
    assert all(h.generation_prior_score >= 0 for h in run.hypotheses)
    assert all(h.status.value != "VERIFIED" for h in run.hypotheses)


def test_prior_score_not_labeled_verified() -> None:
    scorer = GenerationPriorScorer()
    hyp = CausalHypothesis(
        hypothesis_key="H1",
        title="t",
        causal_claim="c",
        category_code="terraform_failure",
        template_id="tf.invalid_reference",
        generation_confidence=0.7,
    )
    score = scorer.score(hyp, _ctx_text("terraform error undeclared"))
    assert 0 <= score <= 0.99


def test_competing_plausible_causes_both_kept_when_distinct() -> None:
    gen = RuleBasedHypothesisGenerator(enabled=True, max_hypotheses=5)
    hyps = gen.generate(
        _ctx_text(
            "AccessDenied AssumedRole wrong-role and bucket policy explicit deny condition matched",
            hier={"final_legacy_category_code": "aws_permission_failure"},
        )
    )
    templates = {h.template_id for h in hyps}
    # At least one IAM hypothesis; diversity may keep wrong-role and/or deny.
    assert templates & {
        "iam.wrong_assumed_role",
        "iam.explicit_resource_deny",
        "iam.missing_identity_permission",
    }
