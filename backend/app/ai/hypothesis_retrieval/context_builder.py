"""Build bounded hypothesis retrieval context from persisted Phase 6A artifacts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.hypothesis_retrieval.models import (
    CONTEXT_VERSION,
    TRUNCATION_RULE_VERSION,
    HypothesisRetrievalContext,
)
from app.domain.services.secret_masker import mask_secrets
from app.infrastructure.database.models.analysis_artifact_bundle import (
    AnalysisArtifact,
    AnalysisArtifactBundle,
    ArtifactParseResult,
)
from app.infrastructure.database.models.causal_hypotheses import (
    CausalHypothesisRow,
    HypothesisCriticResultRow,
    HypothesisEvidenceLinkRow,
)
from app.infrastructure.database.models.hierarchical_classification import (
    ClassificationCandidateRow,
    ClassificationDisagreementResultRow,
    HierarchicalClassificationResultRow,
    OpenSetAssessmentRow,
)
from app.infrastructure.database.models.temporal_evidence_graph import (
    EvidenceGraphEdgeRow,
    EvidenceGraphNodeRow,
    EvidenceGraphRow,
    GraphConsistencyReportRow,
    TemporalEventRow,
    TemporalLocalisationResultRow,
)

# Truncation priority: higher kept longer. Lower values truncated first.
_SECTION_PRIORITY: dict[str, int] = {
    "causal_claim": 100,
    "category": 95,
    "root_observed_nodes": 90,
    "missing_evidence": 88,
    "temporal_primary": 85,
    "causal_path": 80,
    "affected_artifact": 78,
    "expected_falsifying": 70,
    "parser_evidence": 50,
    "graph_neighborhood": 40,
    "upstream_downstream": 35,
    "classification_candidates": 30,
    "changed_files": 25,
    "warnings_misc": 10,
}


class HypothesisRetrievalContextBuilder:
    """Assemble existing evidence for one hypothesis. Does not retrieve documents."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        max_context_chars: int = 60_000,
        max_graph_nodes: int = 80,
        max_graph_edges: int = 150,
        max_artifact_evidence: int = 40,
    ) -> None:
        self._session = session
        self._max_chars = max(1000, max_context_chars)
        self._max_graph_nodes = max(1, max_graph_nodes)
        self._max_graph_edges = max(1, max_graph_edges)
        self._max_artifact_evidence = max(1, max_artifact_evidence)

    async def build(
        self,
        *,
        organization_id: str,
        analysis_id: str,
        hypothesis_id: str,
        project_id: str | None = None,
        signals: dict[str, Any] | None = None,
    ) -> HypothesisRetrievalContext:
        org_uuid = UUID(organization_id)
        analysis_uuid = UUID(analysis_id)
        hyp_uuid = UUID(hypothesis_id)

        hyp = await self._session.scalar(
            select(CausalHypothesisRow).where(
                CausalHypothesisRow.id == hyp_uuid,
                CausalHypothesisRow.organization_id == org_uuid,
                CausalHypothesisRow.analysis_run_id == analysis_uuid,
            )
        )
        if hyp is None:
            raise ValueError("hypothesis_not_found_in_scope")

        if project_id and hyp.project_id and str(hyp.project_id) != project_id:
            raise ValueError("hypothesis_project_scope_mismatch")

        critic, links = await self._load_hypothesis_related(hyp_uuid, org_uuid, analysis_uuid)
        temporal, events_by_key = await self._load_temporal(org_uuid, analysis_uuid)
        graph_row, nodes, edges, consistency = await self._load_graph(org_uuid, analysis_uuid)
        hier, open_set, disagreement, class_candidates = await self._load_classification(
            org_uuid, analysis_uuid
        )
        bundle, parse_evidence = await self._load_artifacts(org_uuid, analysis_uuid)

        signals = signals or {}
        permission_actions = _sorted_unique(
            list(signals.get("permission_actions") or [])
            + _extract_actions_from_links(links)
            + _extract_actions_from_nodes(nodes)
        )
        resource_ids = _sorted_unique(
            list(signals.get("resource_identifiers") or [])
            + _extract_resources_from_nodes(nodes)
        )
        error_signature = (
            str(signals.get("error_signature") or signals.get("error_code") or "") or None
        )
        if not error_signature and temporal and temporal.primary_failure_summary:
            error_signature = temporal.primary_failure_type

        upstream_ids = list(temporal.upstream_context_event_ids or []) if temporal else []
        downstream_ids = list(temporal.downstream_symptom_event_ids or []) if temporal else []
        upstream_summaries = [
            _event_summary(events_by_key[eid])
            for eid in sorted(upstream_ids)
            if eid in events_by_key
        ]
        downstream_summaries = [
            _event_summary(events_by_key[eid])
            for eid in sorted(downstream_ids)
            if eid in events_by_key
        ]

        seed_keys = {
            k
            for k in [
                hyp.root_cause_node_id,
                hyp.observed_failure_node_id,
                *(hyp.causal_path_node_ids or []),
            ]
            if k
        }
        neighborhood_nodes, neighborhood_edges = _select_neighborhood(
            nodes,
            edges,
            seed_keys=seed_keys,
            max_nodes=self._max_graph_nodes,
            max_edges=self._max_graph_edges,
        )

        parser_evidence = parse_evidence[: self._max_artifact_evidence]
        changed_files = _sorted_unique(
            [
                str(n.get("source_path"))
                for n in neighborhood_nodes
                if n.get("source_path")
            ]
            + ([hyp.affected_path] if hyp.affected_path else [])
        )

        ctx = HypothesisRetrievalContext(
            analysis_id=analysis_id,
            organization_id=organization_id,
            incident_id=str(hyp.incident_id) if hyp.incident_id else None,
            hypothesis_id=str(hyp.id),
            hypothesis_key=hyp.hypothesis_key,
            project_id=str(hyp.project_id) if hyp.project_id else project_id,
            category_code=hyp.category_code,
            level_1_code=hyp.level_1_code,
            level_2_code=hyp.level_2_code,
            level_3_code=hyp.level_3_code,
            title=_mask(hyp.title),
            causal_claim=_mask(hyp.causal_claim),
            expected_observations=[_mask(str(x)) for x in (hyp.expected_observations or [])],
            falsifying_observations=[
                _mask(str(x)) for x in (hyp.falsifying_observations or [])
            ],
            missing_evidence=[_mask(str(x)) for x in (hyp.missing_evidence or [])],
            proposed_verification_steps=[
                _mask(str(x)) for x in (hyp.proposed_verification_steps or [])
            ],
            generation_prior_score=float(hyp.generation_prior_score or 0.0),
            critic_decision=critic.decision if critic else None,
            hypothesis_status=hyp.status,
            temporal_primary_summary=_mask(temporal.primary_failure_summary)
            if temporal and temporal.primary_failure_summary
            else None,
            temporal_primary_event_id=temporal.primary_failure_event_id if temporal else None,
            upstream_event_summaries=[_mask(s) for s in upstream_summaries],
            downstream_symptom_summaries=[_mask(s) for s in downstream_summaries],
            temporal_confidence=temporal.confidence if temporal else None,
            temporal_warnings=[str(w) for w in (temporal.warnings or [])] if temporal else [],
            root_cause_node_id=hyp.root_cause_node_id,
            observed_failure_node_id=hyp.observed_failure_node_id,
            causal_path_node_ids=list(hyp.causal_path_node_ids or []),
            causal_path_edge_ids=list(hyp.causal_path_edge_ids or []),
            graph_neighborhood_nodes=neighborhood_nodes,
            graph_neighborhood_edges=neighborhood_edges,
            graph_consistency_status=consistency.status if consistency else (
                graph_row.status if graph_row else None
            ),
            graph_warnings=[str(w) for w in (graph_row.warnings or [])] if graph_row else [],
            missing_graph_links=[
                str(x) for x in (graph_row.missing_link_diagnostics or [])
            ]
            if graph_row
            else [],
            affected_artifact_id=hyp.affected_artifact_id,
            affected_path=hyp.affected_path,
            related_artifacts=_related_artifact_ids(links, hyp.affected_artifact_id),
            changed_files=changed_files,
            parser_evidence=parser_evidence,
            artifact_availability=[str(x) for x in (bundle.available_artifacts or [])]
            if bundle
            else [],
            missing_artifacts=[str(x) for x in (bundle.missing_artifacts or [])]
            if bundle
            else [],
            open_set_status=open_set.status if open_set else None,
            disagreement_status=disagreement.agreement_level if disagreement else None,
            classification_candidates=class_candidates,
            commit_sha=bundle.commit_sha if bundle else None,
            workflow_path=bundle.workflow_name if bundle else None,
            secret_redaction_status="applied",
            excluded_sensitive_fields=["raw_logs", "credentials", "terraform_state"],
            context_version=CONTEXT_VERSION,
            truncation_rule_version=TRUNCATION_RULE_VERSION,
            error_signature=_mask(error_signature) if error_signature else None,
            permission_actions=permission_actions,
            resource_identifiers=resource_ids,
            source_counts={
                "evidence_links": len(links),
                "graph_nodes": len(neighborhood_nodes),
                "graph_edges": len(neighborhood_edges),
                "parser_evidence": len(parser_evidence),
                "upstream_events": len(upstream_summaries),
                "downstream_events": len(downstream_summaries),
            },
        )
        return self._apply_truncation(ctx)

    async def _load_hypothesis_related(
        self,
        hyp_uuid: UUID,
        org_uuid: UUID,
        analysis_uuid: UUID,
    ) -> tuple[HypothesisCriticResultRow | None, list[HypothesisEvidenceLinkRow]]:
        critic = await self._session.scalar(
            select(HypothesisCriticResultRow).where(
                HypothesisCriticResultRow.hypothesis_id == hyp_uuid,
                HypothesisCriticResultRow.organization_id == org_uuid,
                HypothesisCriticResultRow.analysis_run_id == analysis_uuid,
            )
        )
        links = list(
            (
                await self._session.scalars(
                    select(HypothesisEvidenceLinkRow)
                    .where(
                        HypothesisEvidenceLinkRow.hypothesis_id == hyp_uuid,
                        HypothesisEvidenceLinkRow.organization_id == org_uuid,
                        HypothesisEvidenceLinkRow.analysis_run_id == analysis_uuid,
                    )
                    .order_by(HypothesisEvidenceLinkRow.created_at.asc())
                )
            ).all()
        )
        return critic, links

    async def _load_temporal(
        self,
        org_uuid: UUID,
        analysis_uuid: UUID,
    ) -> tuple[TemporalLocalisationResultRow | None, dict[str, TemporalEventRow]]:
        temporal = await self._session.scalar(
            select(TemporalLocalisationResultRow).where(
                TemporalLocalisationResultRow.organization_id == org_uuid,
                TemporalLocalisationResultRow.analysis_run_id == analysis_uuid,
            )
        )
        events_by_key: dict[str, TemporalEventRow] = {}
        if temporal is not None:
            events = list(
                (
                    await self._session.scalars(
                        select(TemporalEventRow)
                        .where(
                            TemporalEventRow.localisation_id == temporal.id,
                            TemporalEventRow.organization_id == org_uuid,
                        )
                        .order_by(TemporalEventRow.sequence_index.asc())
                    )
                ).all()
            )
            events_by_key = {e.event_key: e for e in events}
        return temporal, events_by_key

    async def _load_graph(
        self,
        org_uuid: UUID,
        analysis_uuid: UUID,
    ) -> tuple[
        EvidenceGraphRow | None,
        list[EvidenceGraphNodeRow],
        list[EvidenceGraphEdgeRow],
        GraphConsistencyReportRow | None,
    ]:
        graph = await self._session.scalar(
            select(EvidenceGraphRow).where(
                EvidenceGraphRow.organization_id == org_uuid,
                EvidenceGraphRow.analysis_run_id == analysis_uuid,
            )
        )
        if graph is None:
            return None, [], [], None
        nodes = list(
            (
                await self._session.scalars(
                    select(EvidenceGraphNodeRow)
                    .where(
                        EvidenceGraphNodeRow.graph_id == graph.id,
                        EvidenceGraphNodeRow.organization_id == org_uuid,
                    )
                    .order_by(EvidenceGraphNodeRow.stable_key.asc())
                )
            ).all()
        )
        edges = list(
            (
                await self._session.scalars(
                    select(EvidenceGraphEdgeRow)
                    .where(
                        EvidenceGraphEdgeRow.graph_id == graph.id,
                        EvidenceGraphEdgeRow.organization_id == org_uuid,
                    )
                    .order_by(EvidenceGraphEdgeRow.stable_key.asc())
                )
            ).all()
        )
        consistency = await self._session.scalar(
            select(GraphConsistencyReportRow)
            .where(
                GraphConsistencyReportRow.graph_id == graph.id,
                GraphConsistencyReportRow.organization_id == org_uuid,
            )
            .order_by(GraphConsistencyReportRow.created_at.desc())
            .limit(1)
        )
        return graph, nodes, edges, consistency

    async def _load_classification(
        self,
        org_uuid: UUID,
        analysis_uuid: UUID,
    ) -> tuple[
        HierarchicalClassificationResultRow | None,
        OpenSetAssessmentRow | None,
        ClassificationDisagreementResultRow | None,
        list[dict[str, Any]],
    ]:
        hier = await self._session.scalar(
            select(HierarchicalClassificationResultRow).where(
                HierarchicalClassificationResultRow.organization_id == org_uuid,
                HierarchicalClassificationResultRow.analysis_run_id == analysis_uuid,
            )
        )
        if hier is None:
            return None, None, None, []
        open_set = await self._session.scalar(
            select(OpenSetAssessmentRow).where(
                OpenSetAssessmentRow.hierarchical_result_id == hier.id
            )
        )
        disagreement = await self._session.scalar(
            select(ClassificationDisagreementResultRow).where(
                ClassificationDisagreementResultRow.hierarchical_result_id == hier.id
            )
        )
        candidates = list(
            (
                await self._session.scalars(
                    select(ClassificationCandidateRow)
                    .where(ClassificationCandidateRow.hierarchical_result_id == hier.id)
                    .order_by(ClassificationCandidateRow.rank.asc())
                )
            ).all()
        )
        class_candidates = [
            {
                "category_code": c.category_code,
                "level_1_code": c.level_1_code,
                "level_2_code": c.level_2_code,
                "level_3_code": c.level_3_code,
                "score": c.score,
                "source_classifier": c.source_classifier,
                "rank": c.rank,
            }
            for c in candidates[:10]
        ]
        return hier, open_set, disagreement, class_candidates

    async def _load_artifacts(
        self,
        org_uuid: UUID,
        analysis_uuid: UUID,
    ) -> tuple[AnalysisArtifactBundle | None, list[dict[str, Any]]]:
        bundle = await self._session.scalar(
            select(AnalysisArtifactBundle)
            .where(
                AnalysisArtifactBundle.organization_id == org_uuid,
                AnalysisArtifactBundle.analysis_run_id == analysis_uuid,
            )
            .order_by(AnalysisArtifactBundle.created_at.desc())
            .limit(1)
        )
        if bundle is None:
            return None, []
        artifacts = list(
            (
                await self._session.scalars(
                    select(AnalysisArtifact)
                    .where(
                        AnalysisArtifact.bundle_id == bundle.id,
                        AnalysisArtifact.organization_id == org_uuid,
                    )
                    .order_by(AnalysisArtifact.filename.asc())
                )
            ).all()
        )
        artifact_ids = [a.id for a in artifacts]
        if not artifact_ids:
            return bundle, []
        parses = list(
            (
                await self._session.scalars(
                    select(ArtifactParseResult)
                    .where(
                        ArtifactParseResult.artifact_id.in_(artifact_ids),
                        ArtifactParseResult.organization_id == org_uuid,
                    )
                    .order_by(ArtifactParseResult.created_at.asc())
                )
            ).all()
        )
        evidence: list[dict[str, Any]] = []
        artifact_by_id = {a.id: a for a in artifacts}
        for parse in parses:
            art = artifact_by_id.get(parse.artifact_id)
            for cand in list(parse.evidence_candidates or [])[:20]:
                if not isinstance(cand, dict):
                    continue
                evidence.append(
                    {
                        "artifact_id": str(parse.artifact_id),
                        "parser_name": parse.parser_name,
                        "filename": art.filename if art else None,
                        "excerpt": _mask(str(cand.get("excerpt") or cand.get("text") or ""))[:500],
                        "source_path": cand.get("source_path") or (art.filename if art else None),
                        "line_start": cand.get("line_start"),
                        "line_end": cand.get("line_end"),
                        "confidence": cand.get("confidence"),
                        "title": cand.get("title") or parse.parser_name,
                    }
                )
            for diag in list(parse.diagnostics or [])[:10]:
                if isinstance(diag, dict):
                    msg = str(diag.get("message") or diag.get("summary") or "")
                else:
                    msg = str(diag)
                if not msg:
                    continue
                evidence.append(
                    {
                        "artifact_id": str(parse.artifact_id),
                        "parser_name": parse.parser_name,
                        "diagnostic": _mask(msg)[:500],
                        "excerpt": _mask(msg)[:500],
                        "title": "diagnostic",
                    }
                )
        evidence.sort(key=lambda e: (e.get("artifact_id") or "", e.get("title") or ""))
        return bundle, evidence

    def _apply_truncation(self, ctx: HypothesisRetrievalContext) -> HypothesisRetrievalContext:
        sections = _section_payloads(ctx)
        original = sum(len(v) for _, v in sections)
        ctx.original_size = original
        ctx.total_character_count = original
        if original <= self._max_chars:
            ctx.final_size = original
            ctx.combined_text_excerpt = _mask("\n".join(v for _, v in sections if v))[:4000]
            return ctx

        # Drop lowest-priority sections until under budget.
        ranked = sorted(sections, key=lambda kv: _SECTION_PRIORITY.get(kv[0], 0))
        truncated_sections: list[str] = []
        kept = {name: value for name, value in sections}
        current = original
        for name, value in ranked:
            if current <= self._max_chars:
                break
            if not value:
                continue
            if _SECTION_PRIORITY.get(name, 0) >= 85:
                # Hard-keep core sections; soft-trim instead.
                trimmed = value[: max(200, len(value) // 2)]
                saved = len(value) - len(trimmed)
                if saved <= 0:
                    continue
                kept[name] = trimmed
                current -= saved
                truncated_sections.append(name)
                continue
            current -= len(value)
            kept[name] = ""
            truncated_sections.append(name)

        _apply_section_payloads(ctx, kept)
        final = sum(len(v) for v in kept.values())
        ctx.was_truncated = True
        ctx.final_size = final
        ctx.total_character_count = final
        ctx.truncated_sections = sorted(set(truncated_sections))
        ctx.truncation_reasons = [
            f"exceeded_max_retrieval_context_chars:{self._max_chars}",
            f"truncated_sections:{','.join(ctx.truncated_sections)}",
        ]
        ctx.combined_text_excerpt = _mask("\n".join(v for v in kept.values() if v))[:4000]
        return ctx


def _mask(text: str | None) -> str:
    if not text:
        return ""
    masked, _ = mask_secrets(str(text))
    return masked


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted({str(v).strip() for v in values if v and str(v).strip()})


def _event_summary(event: TemporalEventRow) -> str:
    parts = [
        event.event_type,
        event.job_name or "",
        event.step_name or "",
        (event.message or "")[:240],
    ]
    return _mask(" | ".join(p for p in parts if p))


def _extract_actions_from_links(links: list[HypothesisEvidenceLinkRow]) -> list[str]:
    out: list[str] = []
    for link in links:
        if link.explanation and "action" in link.explanation.lower():
            out.append(link.explanation[:120])
    return out


def _extract_actions_from_nodes(nodes: list[EvidenceGraphNodeRow]) -> list[str]:
    out: list[str] = []
    for node in nodes:
        meta = node.node_metadata or {}
        for key in ("action", "permission_action", "iam_action"):
            if meta.get(key):
                out.append(str(meta[key]))
        if node.node_type.lower() in {"iam_action", "permission", "action"}:
            out.append(node.label)
    return out


def _extract_resources_from_nodes(nodes: list[EvidenceGraphNodeRow]) -> list[str]:
    out: list[str] = []
    for node in nodes:
        meta = node.node_metadata or {}
        for key in ("resource_arn", "arn", "resource_id", "resource"):
            if meta.get(key):
                out.append(str(meta[key]))
        if "arn:aws" in (node.label or "").lower():
            out.append(node.label)
    return out


def _related_artifact_ids(
    links: list[HypothesisEvidenceLinkRow],
    affected: str | None,
) -> list[str]:
    ids = {link.artifact_id for link in links if link.artifact_id}
    if affected:
        ids.add(affected)
    return sorted(ids)


def _select_neighborhood(
    nodes: list[EvidenceGraphNodeRow],
    edges: list[EvidenceGraphEdgeRow],
    *,
    seed_keys: set[str],
    max_nodes: int,
    max_edges: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id = {n.id: n for n in nodes}
    by_key = {n.stable_key: n for n in nodes}
    selected_ids: set[UUID] = set()
    for key in sorted(seed_keys):
        node = by_key.get(key)
        if node is not None:
            selected_ids.add(node.id)

    # One-hop expansion.
    for edge in edges:
        src = by_id.get(edge.source_node_id)
        tgt = by_id.get(edge.target_node_id)
        if src and src.id in selected_ids and tgt:
            selected_ids.add(tgt.id)
        if tgt and tgt.id in selected_ids and src:
            selected_ids.add(src.id)

    if not selected_ids and nodes:
        # Fallback: highest-confidence nodes.
        ordered = sorted(
            nodes,
            key=lambda n: (-(n.confidence or 0.0), n.stable_key),
        )
        selected_ids = {n.id for n in ordered[: max_nodes]}

    selected_nodes = sorted(
        [n for n in nodes if n.id in selected_ids],
        key=lambda n: n.stable_key,
    )[:max_nodes]
    selected_id_set = {n.id for n in selected_nodes}
    selected_edges = sorted(
        [
            e
            for e in edges
            if e.source_node_id in selected_id_set and e.target_node_id in selected_id_set
        ],
        key=lambda e: e.stable_key,
    )[:max_edges]

    node_dicts = [
        {
            "id": str(n.id),
            "stable_key": n.stable_key,
            "node_id": n.stable_key,
            "node_type": n.node_type,
            "label": _mask(n.label),
            "source_path": n.source_path,
            "line_start": n.line_start,
            "line_end": n.line_end,
            "confidence": n.confidence,
            "artifact_id": str(n.artifact_id) if n.artifact_id else None,
        }
        for n in selected_nodes
    ]
    edge_dicts = [
        {
            "id": str(e.id),
            "stable_key": e.stable_key,
            "edge_id": e.stable_key,
            "edge_type": e.edge_type,
            "explanation": _mask(e.explanation or ""),
            "confidence": e.confidence,
            "source_node_id": str(e.source_node_id),
            "target_node_id": str(e.target_node_id),
        }
        for e in selected_edges
    ]
    return node_dicts, edge_dicts


def _section_payloads(ctx: HypothesisRetrievalContext) -> list[tuple[str, str]]:
    return [
        ("causal_claim", ctx.causal_claim or ""),
        (
            "category",
            " ".join(
                filter(
                    None,
                    [
                        ctx.category_code,
                        ctx.level_1_code,
                        ctx.level_2_code,
                        ctx.level_3_code,
                    ],
                )
            ),
        ),
        (
            "root_observed_nodes",
            " ".join(filter(None, [ctx.root_cause_node_id, ctx.observed_failure_node_id])),
        ),
        ("missing_evidence", "\n".join(ctx.missing_evidence)),
        ("temporal_primary", ctx.temporal_primary_summary or ""),
        ("causal_path", " ".join(ctx.causal_path_node_ids + ctx.causal_path_edge_ids)),
        (
            "affected_artifact",
            " ".join(filter(None, [ctx.affected_artifact_id, ctx.affected_path])),
        ),
        (
            "expected_falsifying",
            "\n".join(ctx.expected_observations + ctx.falsifying_observations),
        ),
        (
            "parser_evidence",
            "\n".join(str(p.get("excerpt") or "") for p in ctx.parser_evidence),
        ),
        (
            "graph_neighborhood",
            "\n".join(str(n.get("label") or "") for n in ctx.graph_neighborhood_nodes),
        ),
        (
            "upstream_downstream",
            "\n".join(ctx.upstream_event_summaries + ctx.downstream_symptom_summaries),
        ),
        (
            "classification_candidates",
            "\n".join(str(c.get("category_code") or "") for c in ctx.classification_candidates),
        ),
        ("changed_files", "\n".join(ctx.changed_files)),
        (
            "warnings_misc",
            "\n".join(ctx.temporal_warnings + ctx.graph_warnings + ctx.missing_artifacts),
        ),
    ]


def _apply_section_payloads(ctx: HypothesisRetrievalContext, kept: dict[str, str]) -> None:
    if "parser_evidence" in kept and not kept["parser_evidence"]:
        ctx.parser_evidence = []
    if "graph_neighborhood" in kept and not kept["graph_neighborhood"]:
        ctx.graph_neighborhood_nodes = []
        ctx.graph_neighborhood_edges = []
    if "upstream_downstream" in kept and not kept["upstream_downstream"]:
        ctx.upstream_event_summaries = []
        ctx.downstream_symptom_summaries = []
    if "changed_files" in kept and not kept["changed_files"]:
        ctx.changed_files = []
    if "classification_candidates" in kept and not kept["classification_candidates"]:
        ctx.classification_candidates = []
    if "expected_falsifying" in kept and kept["expected_falsifying"]:
        # Soft-trim lists proportionally when section was trimmed.
        max_len = max(1, len(kept["expected_falsifying"]) // 40)
        ctx.expected_observations = ctx.expected_observations[:max_len]
        ctx.falsifying_observations = ctx.falsifying_observations[:max_len]
