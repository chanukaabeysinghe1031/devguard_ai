"""Structured-output and grounding validators for LLM responses."""

from __future__ import annotations

from typing import Any

from app.ai.orchestration.analysis_context import AnalysisContext


class GroundingValidationError(ValueError):
    """Raised when LLM output fails structural or grounding checks."""


def validate_root_cause_output(
    payload: dict[str, Any],
    context: AnalysisContext,
) -> dict[str, Any]:
    if "summary" not in payload or not str(payload.get("summary") or "").strip():
        raise GroundingValidationError("Missing root-cause summary.")
    root = payload.get("root_cause")
    if not isinstance(root, dict):
        raise GroundingValidationError("Missing root_cause object.")
    if not str(root.get("explanation") or "").strip():
        raise GroundingValidationError("Missing root_cause.explanation.")
    try:
        confidence = float(root.get("confidence", 0))
    except (TypeError, ValueError) as exc:
        raise GroundingValidationError("Invalid root_cause.confidence.") from exc
    if confidence < 0 or confidence > 1:
        raise GroundingValidationError("Confidence must be between 0 and 1.")

    evidence_ids = {f"evidence-{idx}" for idx in range(1, len(context.evidence) + 1)}
    cited_evidence = [str(x) for x in payload.get("supporting_evidence_ids") or []]
    if not cited_evidence:
        raise GroundingValidationError("At least one supporting evidence ID is required.")
    unknown_evidence = [eid for eid in cited_evidence if eid not in evidence_ids]
    if unknown_evidence:
        raise GroundingValidationError(f"Unknown evidence IDs: {unknown_evidence}")

    chunk_ids = {str(c.chunk_id) for c in context.retrieved_chunks}
    cited_chunks = [str(x) for x in payload.get("documentation_chunk_ids") or []]
    if context.retrieved_chunks:
        if not cited_chunks:
            raise GroundingValidationError(
                "Documentation chunk citations required when retrieval results exist."
            )
        unknown_chunks = [cid for cid in cited_chunks if cid not in chunk_ids]
        if unknown_chunks:
            raise GroundingValidationError(f"Unknown documentation chunk IDs: {unknown_chunks}")

    # Classifier conflict soft-check: high confidence conflict is rejected.
    if context.classifications:
        predicted = context.classifications[0].category_code
        reported = str(root.get("category") or predicted)
        if reported != predicted and confidence >= 0.85 and not cited_evidence:
            raise GroundingValidationError("High-confidence category conflicts with classifier.")
        root["category"] = (
            reported
            if reported in {c.category_code for c in context.classifications}
            or reported == predicted
            else predicted
        )

    payload["root_cause"] = root
    payload["supporting_evidence_ids"] = cited_evidence
    payload["documentation_chunk_ids"] = cited_chunks
    return payload


def validate_recommendation_output(payload: dict[str, Any]) -> dict[str, Any]:
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise GroundingValidationError("Recommendations must include at least one step.")
    cleaned = []
    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        title = str(step.get("title") or "").strip()
        action = str(step.get("action") or "").strip()
        if not title or not action:
            continue
        cleaned.append(
            {
                "step_number": int(step.get("step_number") or idx),
                "step_type": str(step.get("step_type") or step.get("type") or "remediation"),
                "title": title,
                "action": action,
                "explanation": str(step.get("explanation") or action),
                "expected_result": str(
                    step.get("expected_result") or "Issue is resolved after the action."
                ),
                "risk_level": str(step.get("risk_level") or "low"),
                "difficulty": str(step.get("difficulty") or "moderate"),
                "command_template": step.get("command_template"),
            }
        )
    if not cleaned:
        raise GroundingValidationError("No valid recommendation steps after validation.")
    payload["steps"] = cleaned
    return payload
