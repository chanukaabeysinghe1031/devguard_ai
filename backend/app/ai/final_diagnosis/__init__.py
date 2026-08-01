"""Phase 6A.7 final diagnosis AI package."""

from app.ai.final_diagnosis.abstention import DiagnosisAbstentionEngine
from app.ai.final_diagnosis.aggregator import VerifierResultAggregator
from app.ai.final_diagnosis.confidence import FinalDiagnosisConfidenceCalculator
from app.ai.final_diagnosis.context_builder import build_inputs_from_context
from app.ai.final_diagnosis.decision_engine import FinalDiagnosisDecisionEngine
from app.ai.final_diagnosis.explanation import FinalDiagnosisExplanationBuilder
from app.ai.final_diagnosis.inputs import (
    FinalDiagnosisInputs,
    HypothesisSnapshot,
    RemediationCandidateSnapshot,
)

__all__ = [
    "DiagnosisAbstentionEngine",
    "FinalDiagnosisConfidenceCalculator",
    "FinalDiagnosisDecisionEngine",
    "FinalDiagnosisExplanationBuilder",
    "FinalDiagnosisInputs",
    "HypothesisSnapshot",
    "RemediationCandidateSnapshot",
    "VerifierResultAggregator",
    "build_inputs_from_context",
]
