# ruff: noqa: E501
"""Graph consistency validation (Phase 6A.2)."""

from __future__ import annotations

import re

import structlog

from app.domain.evidence_graph.enums import (
    GraphConsistencyStatus,
    GraphDerivationType,
    GraphEdgeType,
    GraphNodeType,
)
from app.domain.evidence_graph.models import (
    EvidenceGraph,
    GraphConsistencyReport,
    GraphConsistencyRuleResult,
)

logger = structlog.get_logger(__name__)

RULE_VERSION = "graph_consistency_v1"
_ARN_RE = re.compile(r"^arn:aws:([a-z0-9-]+):([a-z0-9-]*):(\d*):(.+)$")

# Allowed (source_type, edge_type, target_type) pairs — permissive allowlist.
_COMPAT: set[tuple[str, str, str]] = set()


def _add_compat(sources: list[GraphNodeType], edge: GraphEdgeType, targets: list[GraphNodeType]) -> None:
    for s in sources:
        for t in targets:
            _COMPAT.add((s.value, edge.value, t.value))


_add_compat([GraphNodeType.WORKFLOW, GraphNodeType.JOB, GraphNodeType.STEP], GraphEdgeType.CONTAINS, [GraphNodeType.JOB, GraphNodeType.STEP, GraphNodeType.ENVIRONMENT_VARIABLE, GraphNodeType.COMMAND])
_add_compat([GraphNodeType.STEP], GraphEdgeType.EXECUTES, [GraphNodeType.COMMAND, GraphNodeType.TERRAFORM_RESOURCE, GraphNodeType.TERRAFORM_MODULE, GraphNodeType.TERRAFORM_PLAN_CHANGE, GraphNodeType.OTHER])
_add_compat([GraphNodeType.JOB], GraphEdgeType.NEEDS, [GraphNodeType.JOB])
_add_compat([GraphNodeType.ERROR_EVENT], GraphEdgeType.REQUIRES_PERMISSION, [GraphNodeType.PERMISSION_ACTION])
_add_compat([GraphNodeType.ERROR_EVENT], GraphEdgeType.DOWNSTREAM_SYMPTOM_OF, [GraphNodeType.ERROR_EVENT, GraphNodeType.LOG_EVENT])
_add_compat([GraphNodeType.ERROR_EVENT], GraphEdgeType.OCCURRED_BEFORE, [GraphNodeType.ERROR_EVENT, GraphNodeType.LOG_EVENT])
_add_compat([GraphNodeType.POLICY_STATEMENT], GraphEdgeType.ALLOWS, [GraphNodeType.PERMISSION_ACTION])
_add_compat([GraphNodeType.POLICY_STATEMENT], GraphEdgeType.DENIES, [GraphNodeType.PERMISSION_ACTION])
_add_compat([GraphNodeType.CHANGED_FILE], GraphEdgeType.CHANGE_AFFECTS_NODE, list(GraphNodeType))
_add_compat([GraphNodeType.COMMIT], GraphEdgeType.MODIFIED_BY, [GraphNodeType.CHANGED_FILE])
_add_compat([GraphNodeType.TERRAFORM_RESOURCE, GraphNodeType.TERRAFORM_MODULE], GraphEdgeType.DEPENDS_ON, list(GraphNodeType))


class GraphConsistencyEngine:
    """Detect impossible / unsupported evidence-graph links."""

    def validate(
        self,
        graph: EvidenceGraph,
        *,
        enabled: bool = True,
        expected_organization_id: str | None = None,
        expected_project_id: str | None = None,
    ) -> GraphConsistencyReport:
        if not enabled:
            return GraphConsistencyReport(status=GraphConsistencyStatus.DISABLED)

        results: list[GraphConsistencyRuleResult] = []
        warnings: list[str] = []
        errors: list[str] = []
        invalid_edges: list[str] = []
        orphans: list[str] = []
        missing_links: list[str] = []
        conflicts: list[str] = []

        nodes = {n.id: n for n in graph.nodes}
        edges = list(graph.edges)

        # GC-01: step references missing terraform output
        outputs = {n.label.lower() for n in graph.nodes if n.node_type == GraphNodeType.TERRAFORM_OUTPUT}
        for edge in edges:
            if edge.edge_type not in {
                GraphEdgeType.REFERENCES_OUTPUT,
                GraphEdgeType.TERRAFORM_OUTPUT_USED_BY_STEP,
            }:
                continue
            src = nodes.get(edge.source_node_id)
            tgt = nodes.get(edge.target_node_id)
            if tgt and tgt.node_type == GraphNodeType.TERRAFORM_OUTPUT:
                continue
            if src and src.node_type == GraphNodeType.TERRAFORM_OUTPUT:
                continue
            if not outputs:
                invalid_edges.append(edge.id)
                missing_links.append("missing_terraform_output_for_reference")
                results.append(
                    GraphConsistencyRuleResult(
                        rule_id="GC-01",
                        rule_version=RULE_VERSION,
                        passed=False,
                        message="Step references Terraform output but none parsed.",
                        related_edge_ids=[edge.id],
                    )
                )
        if not any(r.rule_id == "GC-01" and not r.passed for r in results):
            results.append(
                GraphConsistencyRuleResult(
                    rule_id="GC-01",
                    rule_version=RULE_VERSION,
                    passed=True,
                    message="No unsupported output references.",
                )
            )

        # GC-02: IAM policy explaining error for unrelated principal
        for edge in edges:
            if edge.edge_type != GraphEdgeType.ERROR_ASSOCIATED_WITH_POLICY:
                continue
            err = nodes.get(edge.source_node_id)
            policy = nodes.get(edge.target_node_id)
            if not err or not policy:
                continue
            principals = [
                n
                for n in graph.nodes
                if n.node_type in {GraphNodeType.IAM_ROLE, GraphNodeType.AWS_PRINCIPAL}
            ]
            if not principals:
                continue
            blob = f"{err.label} {err.metadata}".lower()
            if not any(p.label.split("/")[-1].lower() in blob for p in principals if p.label):
                conflicts.append(edge.id)
                warnings.append("policy_error_principal_mismatch")
                results.append(
                    GraphConsistencyRuleResult(
                        rule_id="GC-02",
                        rule_version=RULE_VERSION,
                        passed=False,
                        severity="warning",
                        message="Policy association lacks matching principal evidence.",
                        related_edge_ids=[edge.id],
                    )
                )
        if not any(r.rule_id == "GC-02" for r in results):
            results.append(
                GraphConsistencyRuleResult(
                    rule_id="GC-02", rule_version=RULE_VERSION, passed=True, message="OK"
                )
            )

        # GC-03: ARN service/resource context
        for node in graph.nodes:
            if node.node_type != GraphNodeType.AWS_RESOURCE:
                continue
            m = _ARN_RE.match(node.label or "")
            if node.label.startswith("arn:aws:") and not m:
                warnings.append(f"malformed_arn:{node.id}")
                results.append(
                    GraphConsistencyRuleResult(
                        rule_id="GC-03",
                        rule_version=RULE_VERSION,
                        passed=False,
                        severity="warning",
                        message="AWS resource label is not a parseable ARN.",
                        related_node_ids=[node.id],
                    )
                )
        if not any(r.rule_id == "GC-03" for r in results):
            results.append(
                GraphConsistencyRuleResult(
                    rule_id="GC-03", rule_version=RULE_VERSION, passed=True, message="OK"
                )
            )

        # GC-04: changed-file must relate to a commit when commit nodes exist
        commits = [n for n in graph.nodes if n.node_type == GraphNodeType.COMMIT]
        changed = [n for n in graph.nodes if n.node_type == GraphNodeType.CHANGED_FILE]
        if commits and changed:
            linked_files = {
                e.target_node_id
                for e in edges
                if e.edge_type == GraphEdgeType.MODIFIED_BY and e.source_node_id in {c.id for c in commits}
            }
            for file_node in changed:
                if file_node.id not in linked_files:
                    missing_links.append(f"changed_file_without_commit:{file_node.id}")
                    warnings.append("changed_file_missing_commit_link")
        results.append(
            GraphConsistencyRuleResult(
                rule_id="GC-04",
                rule_version=RULE_VERSION,
                passed=not any(m.startswith("changed_file_without_commit") for m in missing_links),
                severity="warning",
                message="Changed-file/commit linkage check.",
            )
        )

        # GC-05: temporal symptom must not point backward without explanation
        seq = {
            n.id: int((n.metadata or {}).get("sequence_index") or 0)
            for n in graph.nodes
            if "temporal_event_id" in (n.metadata or {})
        }
        # fallback: use line_start as proxy
        for node in graph.nodes:
            if node.id not in seq and node.line_start is not None:
                seq[node.id] = node.line_start
        for edge in edges:
            if edge.edge_type != GraphEdgeType.DOWNSTREAM_SYMPTOM_OF:
                continue
            # source symptom → target primary; symptom should be later
            src_seq = seq.get(edge.source_node_id)
            tgt_seq = seq.get(edge.target_node_id)
            if src_seq is not None and tgt_seq is not None and src_seq < tgt_seq:
                invalid_edges.append(edge.id)
                errors.append("temporal_symptom_points_backward")
                results.append(
                    GraphConsistencyRuleResult(
                        rule_id="GC-05",
                        rule_version=RULE_VERSION,
                        passed=False,
                        message="Downstream symptom edge points to a later event.",
                        related_edge_ids=[edge.id],
                    )
                )
        if not any(r.rule_id == "GC-05" and not r.passed for r in results):
            results.append(
                GraphConsistencyRuleResult(
                    rule_id="GC-05", rule_version=RULE_VERSION, passed=True, message="OK"
                )
            )

        # GC-06: Terraform DEPENDS_ON must be deterministic/reference derivation
        for edge in edges:
            if edge.edge_type != GraphEdgeType.DEPENDS_ON:
                continue
            if edge.derivation_type not in {
                GraphDerivationType.PARSER_DETERMINISTIC,
                GraphDerivationType.TERRAFORM_REFERENCE,
                GraphDerivationType.WORKFLOW_STRUCTURE,
            }:
                invalid_edges.append(edge.id)
                errors.append("terraform_depends_on_unsupported_derivation")
                results.append(
                    GraphConsistencyRuleResult(
                        rule_id="GC-06",
                        rule_version=RULE_VERSION,
                        passed=False,
                        message="DEPENDS_ON edge lacks Terraform/parser derivation.",
                        related_edge_ids=[edge.id],
                    )
                )
        if not any(r.rule_id == "GC-06" and not r.passed for r in results):
            results.append(
                GraphConsistencyRuleResult(
                    rule_id="GC-06", rule_version=RULE_VERSION, passed=True, message="OK"
                )
            )

        # GC-07: org/project ownership
        org_id = expected_organization_id or graph.organization_id
        for node in graph.nodes:
            if node.organization_id != org_id:
                errors.append(f"org_mismatch_node:{node.id}")
                orphans.append(node.id)
        for edge in edges:
            if edge.organization_id != org_id:
                invalid_edges.append(edge.id)
                errors.append(f"org_mismatch_edge:{edge.id}")
        if expected_project_id:
            for node in graph.nodes:
                if node.project_id and node.project_id != expected_project_id:
                    warnings.append(f"project_mismatch_node:{node.id}")
        results.append(
            GraphConsistencyRuleResult(
                rule_id="GC-07",
                rule_version=RULE_VERSION,
                passed=not any(e.startswith("org_mismatch") for e in errors),
                message="Organization ownership check.",
            )
        )

        # GC-08: node-type compatibility (soft — only when pair known and mismatched)
        for edge in edges:
            src = nodes.get(edge.source_node_id)
            tgt = nodes.get(edge.target_node_id)
            if not src or not tgt:
                invalid_edges.append(edge.id)
                orphans.append(edge.source_node_id if not src else edge.target_node_id)
                continue
            key = (src.node_type.value, edge.edge_type.value, tgt.node_type.value)
            # Only enforce for edges we explicitly catalogued with same edge type present
            catalogued = any(k[1] == edge.edge_type.value for k in _COMPAT)
            if catalogued and key not in _COMPAT and edge.derivation_type == GraphDerivationType.CROSS_ARTIFACT_RULE:
                warnings.append(f"unusual_node_type_pair:{edge.id}")

        # Orphan nodes
        connected = {e.source_node_id for e in edges} | {e.target_node_id for e in edges}
        for node in graph.nodes:
            if node.id not in connected and node.node_type not in {
                GraphNodeType.PIPELINE_RUN,
                GraphNodeType.COMMIT,
            }:
                orphans.append(node.id)

        hard_errors = [e for e in errors if not e.startswith("project_")]
        score = 1.0
        score -= 0.1 * len(set(invalid_edges))
        score -= 0.05 * len(warnings)
        score -= 0.15 * len(hard_errors)
        score = max(0.0, min(1.0, score))

        if hard_errors or len(set(invalid_edges)) > 3:
            status = GraphConsistencyStatus.INVALID
        elif graph.status.value == "PARTIAL" or missing_links or warnings:
            status = (
                GraphConsistencyStatus.VALID_WITH_WARNINGS
                if not hard_errors
                else GraphConsistencyStatus.PARTIAL
            )
            if missing_links and not hard_errors:
                status = GraphConsistencyStatus.PARTIAL
            elif warnings and not hard_errors and not missing_links:
                status = GraphConsistencyStatus.VALID_WITH_WARNINGS
        else:
            status = GraphConsistencyStatus.VALID

        report = GraphConsistencyReport(
            status=status,
            valid_node_count=len(graph.nodes) - len(set(orphans)),
            valid_edge_count=len(edges) - len(set(invalid_edges)),
            invalid_edge_ids=sorted(set(invalid_edges)),
            warnings=warnings,
            errors=errors,
            orphan_nodes=sorted(set(orphans)),
            missing_expected_links=missing_links,
            conflicting_links=conflicts,
            consistency_score=score,
            rule_results=results,
        )
        logger.info(
            "graph_consistency_completed",
            analysis_id=graph.analysis_id,
            organization_id=graph.organization_id,
            graph_id=graph.id,
            consistency_status=status.value,
            consistency_score=score,
        )
        return report
