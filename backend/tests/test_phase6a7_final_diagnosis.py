"""Phase 6A.7 — final diagnosis, confidence, abstention, explanation tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.ai.final_diagnosis.abstention import DiagnosisAbstentionEngine
from app.ai.final_diagnosis.aggregator import VerifierResultAggregator
from app.ai.final_diagnosis.confidence import FinalDiagnosisConfidenceCalculator
from app.ai.final_diagnosis.decision_engine import FinalDiagnosisDecisionEngine
from app.ai.final_diagnosis.explanation import FinalDiagnosisExplanationBuilder
from app.ai.final_diagnosis.inputs import (
    FinalDiagnosisInputs,
    HypothesisSnapshot,
    RemediationCandidateSnapshot,
)
from app.application.services.analysis_execution_service import AnalysisExecutionService
from app.domain.final_diagnosis.enums import (
    AbstentionReasonCode,
    FinalConfidenceBand,
    FinalDiagnosisStatus,
    VerifierSupportLevel,
)


def _flags(**overrides: bool) -> dict[str, bool]:
    base = {
        "final_diagnosis_enabled": True,
        "final_confidence_enabled": True,
        "diagnosis_abstention_enabled": True,
        "final_explanation_enabled": True,
    }
    base.update(overrides)
    return base


def _thresholds(**overrides: float) -> dict[str, float]:
    base = {
        "min_final_diagnosis_score": 0.70,
        "min_final_evidence_sufficiency": 0.60,
        "min_final_verifier_support": 0.60,
        "max_final_contradiction_penalty": 0.40,
        "min_top_hypothesis_margin": 0.08,
    }
    base.update(overrides)
    return base


def _strong_iam_inputs(**kwargs: object) -> FinalDiagnosisInputs:
    hid = str(uuid4())
    cid = str(uuid4())
    data = dict(
        analysis_id=str(uuid4()),
        organization_id=str(uuid4()),
        incident_id=str(uuid4()),
        project_id=str(uuid4()),
        hypotheses=[
            HypothesisSnapshot(
                hypothesis_id=hid,
                ranking_score=0.88,
                support_score=0.82,
                sufficiency_score=0.80,
                contradiction_penalty=0.05,
                temporal_confidence=0.75,
                graph_consistency=0.78,
                title="IAM permission missing for deploy role",
                category_code="IAM_PERMISSION_DENIED",
                summary="Deploy role lacks s3:PutObject on target bucket.",
                supporting_evidence_ids=["ev-1", "ev-2"],
                contradicting_evidence_ids=[],
                missing_evidence=[],
            ),
            HypothesisSnapshot(
                hypothesis_id=str(uuid4()),
                ranking_score=0.55,
                support_score=0.40,
                sufficiency_score=0.50,
                contradiction_penalty=0.10,
                title="Network timeout",
                category_code="NETWORK_TIMEOUT",
            ),
        ],
        candidates=[
            RemediationCandidateSnapshot(
                candidate_id=cid,
                hypothesis_id=hid,
                risk_level="LOW",
                risk_score=0.15,
                priority_status="PRIORITY_CANDIDATE",
                priority_score=0.9,
                consensus_status="VERIFIED",
                constraint_status="STRUCTURALLY_COMPLIANT",
                title="Grant least-privilege S3 put on bucket",
                summary="Add s3:PutObject for specific bucket ARN.",
                artifact_type="IAM_POLICY",
                required_verifiers=["json_schema", "iam_structural", "security_static"],
                verifier_results=[
                    {"verifier_name": "json_schema", "status": "PASS"},
                    {"verifier_name": "iam_structural", "status": "PASS"},
                    {"verifier_name": "security_static", "status": "PASS"},
                ],
            )
        ],
        open_set_status="KNOWN",
        classifier_agreement=0.85,
        open_set_confidence=0.9,
        graph_completeness=0.8,
        artifacts_missing=[],
        what_failed="GitHub Actions deploy failed with AccessDenied",
        category_code="IAM_PERMISSION_DENIED",
        top_hypothesis_margin=0.33,
        flags=_flags(),
        thresholds=_thresholds(),
        max_explanation_items=10,
    )
    data.update(kwargs)
    return FinalDiagnosisInputs(**data)  # type: ignore[arg-type]


class TestVerifierAggregator:
    def test_all_pass_strong(self) -> None:
        agg = VerifierResultAggregator().aggregate(
            RemediationCandidateSnapshot(
                candidate_id="c1",
                consensus_status="VERIFIED",
                required_verifiers=["json_schema", "iam_structural"],
                verifier_results=[
                    {"verifier_name": "json_schema", "status": "PASS"},
                    {"verifier_name": "iam_structural", "status": "PASS"},
                ],
            )
        )
        assert agg.support_level == VerifierSupportLevel.STRONG
        assert agg.failed_count == 0
        assert agg.unavailable_count == 0

    def test_optional_unavailable_moderate(self) -> None:
        agg = VerifierResultAggregator().aggregate(
            RemediationCandidateSnapshot(
                candidate_id="c1",
                consensus_status="PARTIALLY_VERIFIED",
                required_verifiers=["json_schema", "iam_structural", "opa"],
                verifier_results=[
                    {"verifier_name": "json_schema", "status": "PASS"},
                    {"verifier_name": "iam_structural", "status": "PASS"},
                    {"verifier_name": "opa", "status": "UNAVAILABLE"},
                ],
            )
        )
        assert agg.support_level == VerifierSupportLevel.MODERATE
        assert agg.unavailable_count == 1
        assert not agg.blocking_failure

    def test_required_fail_none(self) -> None:
        agg = VerifierResultAggregator().aggregate(
            RemediationCandidateSnapshot(
                candidate_id="c1",
                consensus_status="FAILED",
                required_verifiers=["terraform_validate"],
                verifier_results=[
                    {"verifier_name": "terraform_validate", "status": "FAIL"},
                ],
            )
        )
        assert agg.support_level == VerifierSupportLevel.NONE
        assert agg.blocking_failure

    def test_no_results_unavailable(self) -> None:
        agg = VerifierResultAggregator().aggregate(
            RemediationCandidateSnapshot(candidate_id="c1", verifier_results=[])
        )
        assert agg.support_level == VerifierSupportLevel.UNAVAILABLE

    def test_warnings_moderate(self) -> None:
        agg = VerifierResultAggregator().aggregate(
            RemediationCandidateSnapshot(
                candidate_id="c1",
                consensus_status="PARTIALLY_VERIFIED",
                required_verifiers=["yaml_validator", "actionlint"],
                verifier_results=[
                    {"verifier_name": "yaml_validator", "status": "PASS"},
                    {"verifier_name": "actionlint", "status": "WARNING"},
                ],
            )
        )
        assert agg.support_level == VerifierSupportLevel.MODERATE
        assert agg.warning_count == 1


class TestConfidence:
    def test_high_confidence(self) -> None:
        inputs = _strong_iam_inputs()
        hyp = inputs.hypotheses[0]
        ver = VerifierResultAggregator().aggregate(inputs.candidates[0])
        conf = FinalDiagnosisConfidenceCalculator().calculate(inputs, hyp, ver, risk_score=0.1)
        assert conf.final_confidence >= 0.70
        assert conf.confidence_band in {
            FinalConfidenceBand.HIGH,
            FinalConfidenceBand.MEDIUM,
        }

    def test_low_evidence(self) -> None:
        inputs = _strong_iam_inputs()
        hyp = HypothesisSnapshot(
            hypothesis_id="h",
            ranking_score=0.4,
            sufficiency_score=0.2,
            support_score=0.2,
            contradiction_penalty=0.1,
        )
        ver = VerifierResultAggregator().aggregate(inputs.candidates[0])
        conf = FinalDiagnosisConfidenceCalculator().calculate(inputs, hyp, ver)
        assert conf.final_confidence < 0.70

    def test_high_contradiction(self) -> None:
        inputs = _strong_iam_inputs()
        hyp = inputs.hypotheses[0]
        hyp.contradiction_penalty = 0.9
        ver = VerifierResultAggregator().aggregate(inputs.candidates[0])
        conf = FinalDiagnosisConfidenceCalculator().calculate(inputs, hyp, ver)
        assert conf.components["contradiction_penalty"] == pytest.approx(0.9)
        assert conf.final_confidence < 0.85

    def test_bounds_and_repeatability(self) -> None:
        inputs = _strong_iam_inputs()
        hyp = inputs.hypotheses[0]
        ver = VerifierResultAggregator().aggregate(inputs.candidates[0])
        calc = FinalDiagnosisConfidenceCalculator()
        a = calc.calculate(inputs, hyp, ver, risk_score=0.1, margin=0.3)
        b = calc.calculate(inputs, hyp, ver, risk_score=0.1, margin=0.3)
        assert a.final_confidence == b.final_confidence
        assert 0.0 <= a.final_confidence <= 1.0


class TestAbstention:
    def test_unknown_open_set(self) -> None:
        inputs = _strong_iam_inputs(open_set_status="UNKNOWN")
        decision = FinalDiagnosisDecisionEngine().decide(inputs)
        assert decision.status == FinalDiagnosisStatus.UNKNOWN
        assert AbstentionReasonCode.OPEN_SET_UNKNOWN.value in decision.abstention_reason_codes

    def test_verifier_fail(self) -> None:
        inputs = _strong_iam_inputs()
        inputs.candidates[0].verifier_results = [
            {"verifier_name": "json_schema", "status": "FAIL"},
            {"verifier_name": "iam_structural", "status": "PASS"},
            {"verifier_name": "security_static", "status": "PASS"},
        ]
        inputs.candidates[0].consensus_status = "FAILED"
        decision = FinalDiagnosisDecisionEngine().decide(inputs)
        assert decision.abstention and decision.abstention.should_abstain
        assert decision.selected_remediation_candidate_id is None
        assert decision.status in {
            FinalDiagnosisStatus.INSUFFICIENT_EVIDENCE,
            FinalDiagnosisStatus.CONFLICTED,
        }

    def test_tie(self) -> None:
        inputs = _strong_iam_inputs(top_hypothesis_margin=0.01)
        inputs.hypotheses[1].ranking_score = inputs.hypotheses[0].ranking_score - 0.01
        decision = FinalDiagnosisDecisionEngine().decide(inputs)
        assert decision.status == FinalDiagnosisStatus.CONFLICTED
        assert AbstentionReasonCode.HYPOTHESES_TIED.value in decision.abstention_reason_codes

    def test_no_safe_candidate(self) -> None:
        inputs = _strong_iam_inputs(candidates=[])
        decision = FinalDiagnosisDecisionEngine().decide(inputs)
        assert decision.abstention and decision.abstention.should_abstain
        assert AbstentionReasonCode.NO_SAFE_REMEDIATION.value in decision.abstention_reason_codes

    def test_high_risk(self) -> None:
        inputs = _strong_iam_inputs()
        inputs.candidates[0].risk_level = "CRITICAL"
        inputs.candidates[0].risk_score = 0.95
        decision = FinalDiagnosisDecisionEngine().decide(inputs)
        assert decision.abstention and decision.abstention.should_abstain
        assert AbstentionReasonCode.HIGH_RISK_REMEDIATION.value in decision.abstention_reason_codes

    def test_valid_no_abstention(self) -> None:
        decision = FinalDiagnosisDecisionEngine().decide(_strong_iam_inputs())
        assert decision.abstention is not None
        assert decision.abstention.should_abstain is False


class TestDecisionEngine:
    def test_diagnosed_strong_iam(self) -> None:
        decision = FinalDiagnosisDecisionEngine().decide(_strong_iam_inputs())
        assert decision.status == FinalDiagnosisStatus.DIAGNOSED
        assert decision.selected_hypothesis_id is not None
        assert decision.selected_remediation_candidate_id is not None
        assert "proven" not in (decision.root_cause_statement or "").lower()
        assert "guaranteed" not in (decision.final_summary or "").lower()

    def test_diagnosed_with_warnings_moderate(self) -> None:
        inputs = _strong_iam_inputs()
        inputs.candidates[0].verifier_results = [
            {"verifier_name": "json_schema", "status": "PASS"},
            {"verifier_name": "iam_structural", "status": "PASS"},
            {"verifier_name": "opa", "status": "UNAVAILABLE"},
        ]
        inputs.candidates[0].required_verifiers = [
            "json_schema",
            "iam_structural",
            "opa",
        ]
        inputs.candidates[0].consensus_status = "PARTIALLY_VERIFIED"
        decision = FinalDiagnosisDecisionEngine().decide(inputs)
        assert decision.status == FinalDiagnosisStatus.DIAGNOSED_WITH_WARNINGS
        assert decision.verifier_support == VerifierSupportLevel.MODERATE

    def test_insufficient_low_evidence(self) -> None:
        inputs = _strong_iam_inputs()
        inputs.hypotheses[0].sufficiency_score = 0.2
        inputs.artifacts_missing = ["workflow.yml", "policy.json"]
        decision = FinalDiagnosisDecisionEngine().decide(inputs)
        assert decision.status == FinalDiagnosisStatus.INSUFFICIENT_EVIDENCE

    def test_flags_off_disabled(self) -> None:
        inputs = _strong_iam_inputs(flags=_flags(final_diagnosis_enabled=False))
        decision = FinalDiagnosisDecisionEngine().decide(inputs)
        assert decision.status == FinalDiagnosisStatus.DISABLED

    def test_orchestrator_hook_exists(self) -> None:
        assert hasattr(AnalysisExecutionService, "_maybe_run_phase6a7_final_decision")
        assert callable(AnalysisExecutionService._maybe_run_phase6a7_final_decision)


class TestExplanation:
    def test_sections_and_safety(self) -> None:
        inputs = _strong_iam_inputs()
        decision = FinalDiagnosisDecisionEngine().decide(inputs)
        assert decision.explanation is not None
        sections = decision.explanation.sections
        assert "what_failed" in sections
        assert "most_likely_root_cause" in sections
        assert "verification_summary" in sections
        blob = " ".join(sections.values()).lower()
        assert "password" not in blob or "[redacted]" in blob
        assert "chain_of_thought" not in blob
        assert "<|" not in blob

    def test_redacts_secrets(self) -> None:
        builder = FinalDiagnosisExplanationBuilder()
        inputs = _strong_iam_inputs(what_failed="failed with api_key=AKIA1234567890ABCDEF")
        explanation = builder.build(
            inputs,
            FinalDiagnosisStatus.DIAGNOSED,
            inputs.hypotheses[0],
            inputs.candidates[0],
            VerifierResultAggregator().aggregate(inputs.candidates[0]),
            DiagnosisAbstentionEngine().evaluate(
                inputs,
                inputs.hypotheses[0],
                inputs.candidates[0],
                VerifierResultAggregator().aggregate(inputs.candidates[0]),
                FinalDiagnosisConfidenceCalculator().calculate(
                    inputs,
                    inputs.hypotheses[0],
                    VerifierResultAggregator().aggregate(inputs.candidates[0]),
                ),
                margin=0.3,
            ),
        )
        assert "AKIA" not in explanation.sections["what_failed"]
        assert "[REDACTED]" in explanation.sections["what_failed"]
