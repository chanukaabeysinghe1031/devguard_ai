"""Build FinalDiagnosisInputs from analysis context.options (best-effort)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.ai.final_diagnosis.inputs import (
    FinalDiagnosisInputs,
    HypothesisSnapshot,
    RemediationCandidateSnapshot,
    as_float,
    as_str,
)
from app.core.config import Settings


def build_inputs_from_context(
    *,
    settings: Settings,
    analysis_id: str | UUID,
    organization_id: str | UUID,
    incident_id: str | UUID | None,
    project_id: str | UUID | None,
    options: dict[str, Any],
) -> FinalDiagnosisInputs:
    detail = options.get("hypothesis_evidence_assessment_detail")
    if not isinstance(detail, dict):
        detail = {}
    summary = options.get("hypothesis_evidence_assessment")
    if not isinstance(summary, dict):
        summary = {}

    hypotheses = _hypotheses_from_assessment(detail, summary, options)
    candidates = _candidates_from_options(options)
    open_set = _open_set_status(options)
    hier = options.get("hierarchical_classification") or {}
    if not isinstance(hier, dict):
        hier = {}

    category = as_str(hier.get("primary_category") or hier.get("category_code") or "")
    what_failed = as_str(
        hier.get("summary")
        or options.get("what_failed")
        or category
        or "Incident failure under analysis"
    )

    graph = options.get("evidence_graph") or {}
    graph_completeness = 0.5
    if isinstance(graph, dict):
        graph_completeness = as_float(graph.get("completeness") or graph.get("coverage_score"), 0.5)

    artifacts_missing: list[str] = []
    for key in ("artifacts_missing", "missing_artifacts"):
        raw = options.get(key)
        if isinstance(raw, list):
            artifacts_missing.extend(str(x) for x in raw)

    margin = None
    ranking_raw = detail.get("ranking")
    ranking: dict[str, Any] = ranking_raw if isinstance(ranking_raw, dict) else {}
    if ranking.get("top_margin") is not None:
        margin = as_float(ranking.get("top_margin"))
    elif summary.get("top_hypothesis_margin") is not None:
        margin = as_float(summary.get("top_hypothesis_margin"))

    return FinalDiagnosisInputs(
        analysis_id=str(analysis_id),
        organization_id=str(organization_id),
        incident_id=str(incident_id) if incident_id else None,
        project_id=str(project_id) if project_id else None,
        hypotheses=hypotheses,
        candidates=candidates,
        open_set_status=open_set,
        classifier_agreement=as_float(
            hier.get("classifier_agreement") or hier.get("agreement_score"), 0.5
        ),
        open_set_confidence=as_float(
            (options.get("open_set") or {}).get("confidence")
            if isinstance(options.get("open_set"), dict)
            else 0.5,
            0.5,
        ),
        graph_completeness=graph_completeness,
        artifacts_missing=artifacts_missing,
        what_failed=what_failed,
        category_code=category or None,
        top_hypothesis_margin=margin,
        flags={
            "final_diagnosis_enabled": bool(settings.final_diagnosis_enabled),
            "final_confidence_enabled": bool(settings.final_confidence_enabled),
            "diagnosis_abstention_enabled": bool(settings.diagnosis_abstention_enabled),
            "final_explanation_enabled": bool(settings.final_explanation_enabled),
        },
        thresholds={
            "min_final_diagnosis_score": float(settings.min_final_diagnosis_score),
            "min_final_evidence_sufficiency": float(settings.min_final_evidence_sufficiency),
            "min_final_verifier_support": float(settings.min_final_verifier_support),
            "max_final_contradiction_penalty": float(settings.max_final_contradiction_penalty),
            "min_top_hypothesis_margin": float(settings.min_top_hypothesis_margin),
        },
        max_explanation_items=int(settings.max_final_explanation_items),
    )


def _open_set_status(options: dict[str, Any]) -> str | None:
    for key in ("open_set_status",):
        if options.get(key):
            return as_str(options.get(key)).upper()
    open_set = options.get("open_set")
    if isinstance(open_set, dict) and open_set.get("status"):
        return as_str(open_set.get("status")).upper()
    hier = options.get("hierarchical_classification")
    if isinstance(hier, dict):
        nested = hier.get("open_set_result") or hier.get("open_set")
        if isinstance(nested, dict) and nested.get("status"):
            return as_str(nested.get("status")).upper()
        if hier.get("open_set_status"):
            return as_str(hier.get("open_set_status")).upper()
    return None


def _hypotheses_from_assessment(
    detail: dict[str, Any],
    summary: dict[str, Any],
    options: dict[str, Any],
) -> list[HypothesisSnapshot]:
    out: list[HypothesisSnapshot] = []
    ranking_raw = detail.get("ranking")
    ranking: dict[str, Any] = ranking_raw if isinstance(ranking_raw, dict) else {}
    scores_raw = ranking.get("scores")
    scores = scores_raw if isinstance(scores_raw, list) else []
    support_by = detail.get("support_by_hypothesis") or {}
    contra_by = detail.get("contradiction_by_hypothesis") or {}
    suff_by = detail.get("sufficiency_by_hypothesis") or {}

    if scores:
        for row in scores:
            if not isinstance(row, dict):
                continue
            hid = as_str(row.get("hypothesis_id"))
            if not hid:
                continue
            support = support_by.get(hid) if isinstance(support_by, dict) else {}
            contra = contra_by.get(hid) if isinstance(contra_by, dict) else {}
            suff = suff_by.get(hid) if isinstance(suff_by, dict) else {}
            if not isinstance(support, dict):
                support = {}
            if not isinstance(contra, dict):
                contra = {}
            if not isinstance(suff, dict):
                suff = {}
            out.append(
                HypothesisSnapshot(
                    hypothesis_id=hid,
                    ranking_score=as_float(row.get("ranking_score")),
                    support_score=as_float(
                        support.get("support_score") or row.get("support_score")
                    ),
                    sufficiency_score=as_float(
                        suff.get("sufficiency_score") or row.get("sufficiency_score")
                    ),
                    contradiction_penalty=as_float(
                        contra.get("contradiction_penalty") or row.get("contradiction_penalty")
                    ),
                    temporal_confidence=as_float(
                        suff.get("temporal_completeness") or row.get("temporal_completeness")
                    ),
                    graph_consistency=as_float(
                        suff.get("graph_completeness") or row.get("graph_completeness")
                    ),
                    title=as_str(row.get("title") or row.get("hypothesis_key")),
                    category_code=as_str(row.get("category_code")),
                    summary=as_str(row.get("summary") or row.get("statement")),
                    supporting_evidence_ids=[
                        as_str(x) for x in (support.get("support_candidate_ids") or [])
                    ],
                    contradicting_evidence_ids=[
                        as_str(x) for x in (contra.get("contradiction_candidate_ids") or [])
                    ],
                    missing_evidence=[as_str(x) for x in (suff.get("missing_evidence") or [])],
                )
            )
        return out

    # Compact summary fallback — single top hypothesis stub.
    top_id = as_str(summary.get("top_hypothesis_id"))
    if top_id:
        out.append(
            HypothesisSnapshot(
                hypothesis_id=top_id,
                ranking_score=as_float(summary.get("top_ranking_score")),
                sufficiency_score=as_float(summary.get("top_sufficiency_score"), 0.0),
            )
        )

    # Causal hypotheses fallback.
    causal = options.get("causal_hypotheses")
    if isinstance(causal, dict):
        items = causal.get("hypotheses") or causal.get("items") or []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                hid = as_str(item.get("id") or item.get("hypothesis_id"))
                if not hid or any(h.hypothesis_id == hid for h in out):
                    continue
                out.append(
                    HypothesisSnapshot(
                        hypothesis_id=hid,
                        ranking_score=as_float(item.get("score") or item.get("confidence")),
                        title=as_str(item.get("title") or item.get("label")),
                        category_code=as_str(item.get("category_code")),
                        summary=as_str(item.get("summary") or item.get("statement")),
                    )
                )
    return out


def _candidates_from_options(options: dict[str, Any]) -> list[RemediationCandidateSnapshot]:
    raw = options.get("_remediation_candidates_for_decision") or options.get(
        "remediation_candidates_for_decision"
    )
    out: list[RemediationCandidateSnapshot] = []
    if not isinstance(raw, list):
        # Derive sparse stubs from verification summary runs.
        verification = options.get("counterfactual_verification") or {}
        if isinstance(verification, dict):
            for run in verification.get("runs") or []:
                if not isinstance(run, dict):
                    continue
                cid = as_str(run.get("candidate_id"))
                if not cid:
                    continue
                out.append(
                    RemediationCandidateSnapshot(
                        candidate_id=cid,
                        consensus_status=as_str(run.get("consensus_status")) or None,
                        verifier_results=[],
                        required_verifiers=list(run.get("selected_verifiers") or []),
                    )
                )
        return out

    for row in raw:
        if not isinstance(row, dict):
            continue
        out.append(
            RemediationCandidateSnapshot(
                candidate_id=as_str(row.get("candidate_id") or row.get("id")),
                hypothesis_id=as_str(row.get("hypothesis_id")) or None,
                risk_level=as_str(row.get("risk_level") or "UNKNOWN").upper(),
                risk_score=as_float(row.get("risk_score")),
                priority_status=as_str(row.get("priority_status")),
                priority_score=as_float(row.get("priority_score")),
                consensus_status=as_str(row.get("consensus_status")) or None,
                constraint_status=as_str(row.get("constraint_status")) or None,
                title=as_str(row.get("title")),
                summary=as_str(row.get("summary")),
                artifact_type=as_str(row.get("artifact_type")),
                verifier_results=list(row.get("verifier_results") or []),
                required_verifiers=list(row.get("required_verifiers") or []),
            )
        )
    return [c for c in out if c.candidate_id]
