# ruff: noqa: E501
"""Explicit cross-artifact linking rules (Phase 6A.2)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from app.ai.evidence_graph.type_mapping import stable_edge_key
from app.domain.evidence_graph.enums import GraphDerivationType, GraphEdgeType, GraphNodeType
from app.domain.evidence_graph.models import EvidenceGraphEdge, EvidenceGraphNode

RULE_VERSION = "cross_artifact_rules_v1"

_TF_CMD = re.compile(r"\bterraform\b.*(plan|apply|validate|destroy)", re.I)
_OUTPUT_REF = re.compile(r"terraform_output|TF_OUTPUT|outputs?\.([A-Za-z0-9_-]+)", re.I)
_ROLE_ARN = re.compile(r"arn:aws:iam::\d+:role/([A-Za-z0-9+=,.@_-]+)")
_RESOURCE_ARN = re.compile(r"arn:aws:[a-z0-9-]+:[a-z0-9-]*:\d*:[^\\s\"']+")
_ACTION = re.compile(r"\b([a-z0-9-]+:[A-Za-z0-9*]+)\b")


@dataclass(frozen=True)
class CrossArtifactRule:
    rule_id: str
    version: str
    description: str
    apply: Callable[..., list[EvidenceGraphEdge]]


def _edge(
    *,
    analysis_id: str,
    organization_id: str,
    source: EvidenceGraphNode,
    target: EvidenceGraphNode,
    edge_type: GraphEdgeType,
    rule_id: str,
    explanation: str,
    confidence: float,
) -> EvidenceGraphEdge:
    key = stable_edge_key(
        edge_type=edge_type,
        source_key=source.stable_key,
        target_key=target.stable_key,
        rule_id=rule_id,
    )
    return EvidenceGraphEdge(
        id=str(uuid.uuid4()),
        analysis_id=analysis_id,
        organization_id=organization_id,
        source_node_id=source.id,
        target_node_id=target.id,
        edge_type=edge_type,
        stable_key=key,
        derivation_type=GraphDerivationType.CROSS_ARTIFACT_RULE,
        confidence=confidence,
        explanation=explanation,
        rule_id=rule_id,
        rule_version=RULE_VERSION,
    )


def rule_step_executes_terraform(
    nodes: list[EvidenceGraphNode],
    *,
    analysis_id: str,
    organization_id: str,
) -> list[EvidenceGraphEdge]:
    """CA-01: Workflow step/command running terraform → EXECUTES / STEP_REFERENCES_TERRAFORM."""
    edges: list[EvidenceGraphEdge] = []
    steps = [n for n in nodes if n.node_type in {GraphNodeType.STEP, GraphNodeType.COMMAND}]
    tf_nodes = [
        n
        for n in nodes
        if n.node_type
        in {
            GraphNodeType.TERRAFORM_RESOURCE,
            GraphNodeType.TERRAFORM_MODULE,
            GraphNodeType.TERRAFORM_PLAN_CHANGE,
            GraphNodeType.OTHER,
        }
        and (
            "terraform" in (n.label or "").lower()
            or n.node_type != GraphNodeType.OTHER
            or (n.metadata or {}).get("block")
        )
    ]
    for step in steps:
        text = f"{step.label} {step.metadata.get('run', '')}"
        if not _TF_CMD.search(text):
            continue
        for tf in tf_nodes[:20]:
            edges.append(
                _edge(
                    analysis_id=analysis_id,
                    organization_id=organization_id,
                    source=step,
                    target=tf,
                    edge_type=GraphEdgeType.STEP_REFERENCES_TERRAFORM,
                    rule_id="CA-01",
                    explanation="Step/command invokes terraform against parsed Terraform entities.",
                    confidence=0.7,
                )
            )
            edges.append(
                _edge(
                    analysis_id=analysis_id,
                    organization_id=organization_id,
                    source=step,
                    target=tf,
                    edge_type=GraphEdgeType.EXECUTES,
                    rule_id="CA-01b",
                    explanation="Step executes Terraform-related command.",
                    confidence=0.75,
                )
            )
    return edges


def rule_env_references_output(
    nodes: list[EvidenceGraphNode],
    *,
    analysis_id: str,
    organization_id: str,
) -> list[EvidenceGraphEdge]:
    """CA-02: Env/step text references Terraform output name."""
    edges: list[EvidenceGraphEdge] = []
    outputs = [n for n in nodes if n.node_type == GraphNodeType.TERRAFORM_OUTPUT]
    consumers = [
        n
        for n in nodes
        if n.node_type
        in {GraphNodeType.STEP, GraphNodeType.ENVIRONMENT_VARIABLE, GraphNodeType.COMMAND}
    ]
    for consumer in consumers:
        blob = f"{consumer.label} {consumer.metadata}"
        for match in _OUTPUT_REF.finditer(blob):
            name = match.group(1) if match.lastindex else match.group(0)
            for output in outputs:
                if name and name.lower() in output.label.lower():
                    edges.append(
                        _edge(
                            analysis_id=analysis_id,
                            organization_id=organization_id,
                            source=consumer,
                            target=output,
                            edge_type=GraphEdgeType.REFERENCES_OUTPUT,
                            rule_id="CA-02",
                            explanation=f"Workflow value references Terraform output '{output.label}'.",
                            confidence=0.8,
                        )
                    )
                    edges.append(
                        _edge(
                            analysis_id=analysis_id,
                            organization_id=organization_id,
                            source=output,
                            target=consumer,
                            edge_type=GraphEdgeType.TERRAFORM_OUTPUT_USED_BY_STEP,
                            rule_id="CA-02b",
                            explanation="Terraform output consumed by workflow step/env.",
                            confidence=0.75,
                        )
                    )
    return edges


def rule_output_references_role(
    nodes: list[EvidenceGraphNode],
    *,
    analysis_id: str,
    organization_id: str,
) -> list[EvidenceGraphEdge]:
    """CA-03: Terraform output value/label contains IAM role ARN/name."""
    edges: list[EvidenceGraphEdge] = []
    outputs = [n for n in nodes if n.node_type == GraphNodeType.TERRAFORM_OUTPUT]
    roles = [n for n in nodes if n.node_type == GraphNodeType.IAM_ROLE]
    # Also create IAM_ROLE nodes from output text on the fly is builder's job; here link if both exist.
    for output in outputs:
        blob = f"{output.label} {output.metadata}"
        m = _ROLE_ARN.search(blob)
        role_name = m.group(1) if m else None
        for role in roles:
            if role_name and role_name in role.label:
                edges.append(
                    _edge(
                        analysis_id=analysis_id,
                        organization_id=organization_id,
                        source=output,
                        target=role,
                        edge_type=GraphEdgeType.REFERENCES_RESOURCE,
                        rule_id="CA-03",
                        explanation="Terraform output references IAM role.",
                        confidence=0.85,
                    )
                )
    return edges


def rule_error_associated_with_principal_action(
    nodes: list[EvidenceGraphNode],
    *,
    analysis_id: str,
    organization_id: str,
) -> list[EvidenceGraphEdge]:
    """CA-04/05: AWS/log error → principal + required permission action."""
    edges: list[EvidenceGraphEdge] = []
    errors = [n for n in nodes if n.node_type == GraphNodeType.ERROR_EVENT]
    principals = [
        n for n in nodes if n.node_type in {GraphNodeType.AWS_PRINCIPAL, GraphNodeType.IAM_ROLE}
    ]
    actions = [n for n in nodes if n.node_type == GraphNodeType.PERMISSION_ACTION]
    policies = [n for n in nodes if n.node_type == GraphNodeType.IAM_POLICY]
    for err in errors:
        blob = f"{err.label} {err.metadata}"
        for principal in principals:
            if principal.label and principal.label.split("/")[-1] in blob:
                edges.append(
                    _edge(
                        analysis_id=analysis_id,
                        organization_id=organization_id,
                        source=err,
                        target=principal,
                        edge_type=GraphEdgeType.ERROR_ASSOCIATED_WITH_POLICY
                        if principal.node_type == GraphNodeType.IAM_POLICY
                        else GraphEdgeType.APPLIES_TO_PRINCIPAL,
                        rule_id="CA-04",
                        explanation="Error log references principal/role ARN.",
                        confidence=0.8,
                    )
                )
        for action in actions:
            if action.label and action.label in blob:
                edges.append(
                    _edge(
                        analysis_id=analysis_id,
                        organization_id=organization_id,
                        source=err,
                        target=action,
                        edge_type=GraphEdgeType.REQUIRES_PERMISSION,
                        rule_id="CA-05",
                        explanation="Error requests IAM action.",
                        confidence=0.85,
                    )
                )
        for policy in policies:
            edges.append(
                _edge(
                    analysis_id=analysis_id,
                    organization_id=organization_id,
                    source=err,
                    target=policy,
                    edge_type=GraphEdgeType.ERROR_ASSOCIATED_WITH_POLICY,
                    rule_id="CA-05b",
                    explanation="Error associated with available IAM policy artifact for inspection.",
                    confidence=0.4,
                )
            )
    return edges


def rule_policy_allows_denies(
    nodes: list[EvidenceGraphNode],
    *,
    analysis_id: str,
    organization_id: str,
) -> list[EvidenceGraphEdge]:
    """CA-06: Policy statement Effect+Action(+Resource) → ALLOWS/DENIES."""
    edges: list[EvidenceGraphEdge] = []
    statements = [n for n in nodes if n.node_type == GraphNodeType.POLICY_STATEMENT]
    actions = {n.label.lower(): n for n in nodes if n.node_type == GraphNodeType.PERMISSION_ACTION}
    resources = [n for n in nodes if n.node_type == GraphNodeType.AWS_RESOURCE]
    for stmt in statements:
        effect = str(stmt.metadata.get("Effect") or "").lower()
        raw_actions = stmt.metadata.get("Action") or []
        if isinstance(raw_actions, str):
            raw_actions = [raw_actions]
        edge_type = GraphEdgeType.DENIES if effect == "deny" else GraphEdgeType.ALLOWS
        for action_name in raw_actions:
            key = str(action_name).lower()
            target = actions.get(key)
            if target is None:
                continue
            edges.append(
                _edge(
                    analysis_id=analysis_id,
                    organization_id=organization_id,
                    source=stmt,
                    target=target,
                    edge_type=edge_type,
                    rule_id="CA-06",
                    explanation=f"Policy statement {effect or 'allow'}s action {action_name}.",
                    confidence=0.9,
                )
            )
        raw_resources = stmt.metadata.get("Resource") or []
        if isinstance(raw_resources, str):
            raw_resources = [raw_resources]
        for res_name in raw_resources:
            for resource in resources:
                if str(res_name) in resource.label or resource.label in str(res_name):
                    edges.append(
                        _edge(
                            analysis_id=analysis_id,
                            organization_id=organization_id,
                            source=stmt,
                            target=resource,
                            edge_type=GraphEdgeType.APPLIES_TO_RESOURCE,
                            rule_id="CA-06b",
                            explanation="Policy statement applies to AWS resource.",
                            confidence=0.85,
                        )
                    )
    return edges


def rule_changed_file_affects_resource(
    nodes: list[EvidenceGraphNode],
    *,
    analysis_id: str,
    organization_id: str,
) -> list[EvidenceGraphEdge]:
    """CA-07: Changed Terraform file ↔ resource by path/address overlap."""
    edges: list[EvidenceGraphEdge] = []
    changed = [n for n in nodes if n.node_type == GraphNodeType.CHANGED_FILE]
    resources = [
        n
        for n in nodes
        if n.node_type
        in {
            GraphNodeType.TERRAFORM_RESOURCE,
            GraphNodeType.TERRAFORM_MODULE,
            GraphNodeType.IAM_POLICY,
            GraphNodeType.WORKFLOW,
        }
    ]
    for file_node in changed:
        path = (file_node.label or file_node.source_path or "").lower()
        for resource in resources:
            src = (resource.source_path or "").lower()
            address = str(resource.metadata.get("address") or resource.label).lower()
            if path and (path in src or path.endswith(".tf") and address and path.split("/")[-1] in src):
                edges.append(
                    _edge(
                        analysis_id=analysis_id,
                        organization_id=organization_id,
                        source=file_node,
                        target=resource,
                        edge_type=GraphEdgeType.CHANGE_AFFECTS_NODE,
                        rule_id="CA-07",
                        explanation="Changed file path overlaps Terraform/resource artifact.",
                        confidence=0.7,
                    )
                )
            elif path.endswith((".yml", ".yaml")) and resource.node_type == GraphNodeType.WORKFLOW:
                edges.append(
                    _edge(
                        analysis_id=analysis_id,
                        organization_id=organization_id,
                        source=file_node,
                        target=resource,
                        edge_type=GraphEdgeType.CHANGE_AFFECTS_NODE,
                        rule_id="CA-07b",
                        explanation="Changed workflow file affects workflow node.",
                        confidence=0.75,
                    )
                )
    return edges


def rule_commit_modified_files(
    nodes: list[EvidenceGraphNode],
    *,
    analysis_id: str,
    organization_id: str,
) -> list[EvidenceGraphEdge]:
    """CA-08: COMMIT MODIFIED_BY CHANGED_FILE; WORKFLOW CHANGED_IN COMMIT."""
    edges: list[EvidenceGraphEdge] = []
    commits = [n for n in nodes if n.node_type == GraphNodeType.COMMIT]
    files = [n for n in nodes if n.node_type == GraphNodeType.CHANGED_FILE]
    workflows = [n for n in nodes if n.node_type == GraphNodeType.WORKFLOW]
    for commit in commits:
        for file_node in files:
            edges.append(
                _edge(
                    analysis_id=analysis_id,
                    organization_id=organization_id,
                    source=commit,
                    target=file_node,
                    edge_type=GraphEdgeType.MODIFIED_BY,
                    rule_id="CA-08",
                    explanation="Commit modified changed-file entry.",
                    confidence=0.9,
                )
            )
        for workflow in workflows:
            edges.append(
                _edge(
                    analysis_id=analysis_id,
                    organization_id=organization_id,
                    source=workflow,
                    target=commit,
                    edge_type=GraphEdgeType.CHANGED_IN,
                    rule_id="CA-08b",
                    explanation="Workflow associated with triggering commit.",
                    confidence=0.6,
                )
            )
    return edges


CROSS_ARTIFACT_RULES: tuple[CrossArtifactRule, ...] = (
    CrossArtifactRule("CA-01", RULE_VERSION, "step executes terraform", rule_step_executes_terraform),
    CrossArtifactRule("CA-02", RULE_VERSION, "env references output", rule_env_references_output),
    CrossArtifactRule("CA-03", RULE_VERSION, "output references role", rule_output_references_role),
    CrossArtifactRule(
        "CA-04", RULE_VERSION, "error principal/action", rule_error_associated_with_principal_action
    ),
    CrossArtifactRule("CA-06", RULE_VERSION, "policy allows/denies", rule_policy_allows_denies),
    CrossArtifactRule(
        "CA-07", RULE_VERSION, "changed file affects node", rule_changed_file_affects_resource
    ),
    CrossArtifactRule("CA-08", RULE_VERSION, "commit modified files", rule_commit_modified_files),
)


def apply_cross_artifact_rules(
    nodes: list[EvidenceGraphNode],
    *,
    analysis_id: str,
    organization_id: str,
) -> list[EvidenceGraphEdge]:
    edges: list[EvidenceGraphEdge] = []
    for rule in CROSS_ARTIFACT_RULES:
        edges.extend(rule.apply(nodes, analysis_id=analysis_id, organization_id=organization_id))
    return edges


def maybe_synthesize_nodes_from_text(
    nodes: list[EvidenceGraphNode],
    *,
    analysis_id: str,
    organization_id: str,
    project_id: str | None,
) -> list[EvidenceGraphNode]:
    """Create IAM_ROLE / AWS_RESOURCE / PERMISSION_ACTION nodes from error text when missing."""
    from app.ai.evidence_graph.type_mapping import stable_node_key

    existing_keys = {n.stable_key for n in nodes}
    created: list[EvidenceGraphNode] = []
    for node in list(nodes):
        if node.node_type != GraphNodeType.ERROR_EVENT:
            continue
        blob = f"{node.label} {node.metadata}"
        for m in _ROLE_ARN.finditer(blob):
            label = m.group(0)
            key = stable_node_key(
                artifact_id=node.artifact_id,
                parser_entity_id=f"synth:role:{m.group(1)}",
                node_type=GraphNodeType.IAM_ROLE,
            )
            if key in existing_keys:
                continue
            created.append(
                EvidenceGraphNode(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    node_type=GraphNodeType.IAM_ROLE,
                    label=label,
                    stable_key=key,
                    artifact_id=node.artifact_id,
                    parser_entity_id=f"synth:role:{m.group(1)}",
                    metadata={"synthesized": True, "from": node.id},
                    extraction_method="cross_artifact_synthesis",
                    confidence=0.7,
                )
            )
            existing_keys.add(key)
        for m in _RESOURCE_ARN.finditer(blob):
            label = m.group(0)
            if ":role/" in label:
                continue
            key = stable_node_key(
                artifact_id=node.artifact_id,
                parser_entity_id=f"synth:resource:{label}",
                node_type=GraphNodeType.AWS_RESOURCE,
            )
            if key in existing_keys:
                continue
            created.append(
                EvidenceGraphNode(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    node_type=GraphNodeType.AWS_RESOURCE,
                    label=label,
                    stable_key=key,
                    artifact_id=node.artifact_id,
                    parser_entity_id=f"synth:resource:{label}",
                    metadata={"synthesized": True},
                    extraction_method="cross_artifact_synthesis",
                    confidence=0.65,
                )
            )
            existing_keys.add(key)
        for m in _ACTION.finditer(blob):
            action = m.group(1)
            if action.count(":") != 1:
                continue
            key = stable_node_key(
                artifact_id=node.artifact_id,
                parser_entity_id=f"synth:action:{action}",
                node_type=GraphNodeType.PERMISSION_ACTION,
            )
            if key in existing_keys:
                continue
            created.append(
                EvidenceGraphNode(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    node_type=GraphNodeType.PERMISSION_ACTION,
                    label=action,
                    stable_key=key,
                    artifact_id=node.artifact_id,
                    parser_entity_id=f"synth:action:{action}",
                    metadata={"synthesized": True},
                    extraction_method="cross_artifact_synthesis",
                    confidence=0.7,
                )
            )
            existing_keys.add(key)
    return created
