"""Deterministic structured final diagnosis explanation (no chain-of-thought)."""

from __future__ import annotations

import re

from app.ai.final_diagnosis.inputs import (
    FinalDiagnosisInputs,
    HypothesisSnapshot,
    RemediationCandidateSnapshot,
)
from app.domain.final_diagnosis.enums import FinalDiagnosisStatus
from app.domain.final_diagnosis.models import (
    AbstentionDecision,
    FinalDiagnosisExplanation,
    VerifierAggregationResult,
)

_SECRETISH = re.compile(
    r"(?i)(password|secret|token|api[_-]?key|private[_-]?key|bearer\s+|akia[0-9a-z]{16})"
)

_SECTION_ORDER = (
    "what_failed",
    "most_likely_root_cause",
    "why_ranked_highest",
    "key_supporting_evidence",
    "contradicting_evidence",
    "missing_evidence",
    "verification_summary",
    "proposed_remediation",
    "risk_and_limitations",
    "abstention_rationale",
)


class FinalDiagnosisExplanationBuilder:
    def build(
        self,
        inputs: FinalDiagnosisInputs,
        status: FinalDiagnosisStatus,
        hypothesis: HypothesisSnapshot | None,
        candidate: RemediationCandidateSnapshot | None,
        verifier: VerifierAggregationResult,
        abstention: AbstentionDecision,
        *,
        max_items: int = 10,
    ) -> FinalDiagnosisExplanation:
        limit = max(1, int(max_items or inputs.max_explanation_items or 10))
        hyp = hypothesis
        support_ids = list((hyp.supporting_evidence_ids if hyp else [])[:limit])
        contra_ids = list((hyp.contradicting_evidence_ids if hyp else [])[:limit])
        missing = list(
            dict.fromkeys([*(hyp.missing_evidence if hyp else []), *inputs.artifacts_missing])
        )[:limit]

        sections = {
            "what_failed": self._safe(
                inputs.what_failed
                or inputs.category_code
                or "Failure mode not fully characterised."
            ),
            "most_likely_root_cause": self._safe(
                (hyp.summary or hyp.title or "No eligible hypothesis selected.")
                if hyp
                else "No eligible hypothesis selected."
            ),
            "why_ranked_highest": self._safe(
                (
                    f"Ranking score={hyp.ranking_score:.3f}; "
                    f"sufficiency={hyp.sufficiency_score:.3f}; "
                    f"support={hyp.support_score:.3f}."
                )
                if hyp
                else "Hypothesis ranking unavailable."
            ),
            "key_supporting_evidence": self._safe(
                ", ".join(support_ids) if support_ids else "No supporting evidence IDs recorded."
            ),
            "contradicting_evidence": self._safe(
                ", ".join(contra_ids) if contra_ids else "No contradicting evidence IDs recorded."
            ),
            "missing_evidence": self._safe(
                ", ".join(missing) if missing else "No missing-evidence items listed."
            ),
            "verification_summary": self._safe(
                f"{verifier.summary}; support={verifier.support_level.value}; "
                f"passed={verifier.passed_count}; failed={verifier.failed_count}; "
                f"unavailable={verifier.unavailable_count}."
            ),
            "proposed_remediation": self._safe(
                (
                    f"Candidate {candidate.candidate_id}: "
                    f"{candidate.title or candidate.summary or 'n/a'} "
                    f"(risk={candidate.risk_level}; "
                    f"consensus={candidate.consensus_status or 'n/a'}). "
                    "Not applied."
                )
                if candidate
                and status
                in {
                    FinalDiagnosisStatus.DIAGNOSED,
                    FinalDiagnosisStatus.DIAGNOSED_WITH_WARNINGS,
                }
                else "No remediation proposed (abstained or unsafe)."
            ),
            "risk_and_limitations": self._safe(
                "Evidence-based diagnosis only; not mathematical proof. "
                "Verified remediation is temporary-workspace validation, not applied change. "
                f"Candidate risk={candidate.risk_level if candidate else 'n/a'}."
            ),
            "abstention_rationale": self._safe(
                abstention.explanation
                if abstention.should_abstain
                else "Proceeded: no blocking abstention conditions."
            ),
        }

        # Bound section count.
        bounded = {k: sections[k] for k in _SECTION_ORDER[:limit] if k in sections}
        warnings: list[str] = []
        if abstention.should_abstain:
            warnings.append("diagnosis_abstained")
        if verifier.warning_count:
            warnings.append("verifier_warnings_present")

        return FinalDiagnosisExplanation(
            sections=bounded,
            supporting_evidence_ids=support_ids,
            contradicting_evidence_ids=contra_ids,
            missing_evidence=missing,
            verifier_summary=sections["verification_summary"],
            remediation_summary=sections["proposed_remediation"],
            warnings=warnings,
        )

    @staticmethod
    def _safe(text: str) -> str:
        cleaned = _SECRETISH.sub("[REDACTED]", text or "")
        # Strip prompt-like markers if present.
        for banned in ("system:", "assistant:", "<|", "CHAIN_OF_THOUGHT"):
            cleaned = cleaned.replace(banned, "")
        return cleaned[:500]
