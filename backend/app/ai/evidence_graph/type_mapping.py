# ruff: noqa: E501
"""Map Phase 6A.1 parser entity/relationship types onto graph enums."""

from __future__ import annotations

from app.domain.evidence_graph.enums import GraphEdgeType, GraphNodeType

_ENTITY_MAP: dict[str, GraphNodeType] = {
    "WORKFLOW": GraphNodeType.WORKFLOW,
    "JOB": GraphNodeType.JOB,
    "STEP": GraphNodeType.STEP,
    "COMMAND": GraphNodeType.COMMAND,
    "ACTION_REF": GraphNodeType.OTHER,
    "SECRET_REFERENCE": GraphNodeType.SECRET_REFERENCE,
    "ENVIRONMENT_VARIABLE": GraphNodeType.ENVIRONMENT_VARIABLE,
    "ERROR_EVENT": GraphNodeType.ERROR_EVENT,
    "LOG_EVENT": GraphNodeType.LOG_EVENT,
    "CHANGED_FILE": GraphNodeType.CHANGED_FILE,
    "TERRAFORM_FILE": GraphNodeType.OTHER,
    "RESOURCE": GraphNodeType.TERRAFORM_RESOURCE,
    "DATA": GraphNodeType.TERRAFORM_DATA_SOURCE,
    "MODULE": GraphNodeType.TERRAFORM_MODULE,
    "VARIABLE": GraphNodeType.TERRAFORM_VARIABLE,
    "OUTPUT": GraphNodeType.TERRAFORM_OUTPUT,
    "PROVIDER": GraphNodeType.TERRAFORM_PROVIDER,
    "REFERENCE": GraphNodeType.OTHER,
    "TERRAFORM_PLAN": GraphNodeType.OTHER,
    "PLAN_RESOURCE_CHANGE": GraphNodeType.TERRAFORM_PLAN_CHANGE,
    "IAM_POLICY": GraphNodeType.IAM_POLICY,
    "POLICY_STATEMENT": GraphNodeType.POLICY_STATEMENT,
    "AWS_ERROR": GraphNodeType.ERROR_EVENT,
    "AWS_ACTION": GraphNodeType.PERMISSION_ACTION,
    "COMMIT": GraphNodeType.COMMIT,
}

_REL_MAP: dict[str, GraphEdgeType] = {
    "CONTAINS": GraphEdgeType.CONTAINS,
    "USES": GraphEdgeType.USES_ACTION,
    "NEEDS": GraphEdgeType.NEEDS,
    "EXECUTES": GraphEdgeType.EXECUTES,
    "REFERENCES": GraphEdgeType.REFERENCES,
    "DECLARES": GraphEdgeType.DECLARES,
    "DEPENDS_ON": GraphEdgeType.DEPENDS_ON,
    "OCCURRED_BEFORE": GraphEdgeType.OCCURRED_BEFORE,
}


def map_entity_type(raw: str) -> GraphNodeType:
    return _ENTITY_MAP.get(raw.upper(), GraphNodeType.OTHER)


def map_relationship_type(raw: str) -> GraphEdgeType:
    return _REL_MAP.get(raw.upper(), GraphEdgeType.REFERENCES)


def stable_node_key(
    *, artifact_id: str | None, parser_entity_id: str, node_type: GraphNodeType
) -> str:
    art = artifact_id or "none"
    return f"{node_type.value}:{art}:{parser_entity_id}"


def stable_edge_key(
    *,
    edge_type: GraphEdgeType,
    source_key: str,
    target_key: str,
    rule_id: str | None = None,
) -> str:
    rule = rule_id or "parser"
    return f"{edge_type.value}:{source_key}->{target_key}:{rule}"
