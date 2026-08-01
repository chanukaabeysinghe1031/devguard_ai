"""Phase 6A.2 evidence graph builder and consistency tests."""

from __future__ import annotations

from app.ai.evidence_graph.builder import CrossArtifactEvidenceGraphBuilder
from app.ai.evidence_graph.consistency import GraphConsistencyEngine
from app.ai.temporal.localizer import TemporalRootCauseLocalizer
from app.domain.artifacts.enums import ParseStatus
from app.domain.artifacts.models import (
    GraphEntityPreview,
    GraphRelationshipPreview,
    IncidentArtifactBundle,
    StructuredParseResult,
)
from app.domain.evidence_graph.enums import (
    EvidenceGraphStatus,
    GraphConsistencyStatus,
    GraphEdgeType,
    GraphNodeType,
)


def _iam_chain_parse() -> dict[str, list[StructuredParseResult]]:
    workflow = StructuredParseResult(
        parser_name="workflow",
        parser_version="1.0.0",
        status=ParseStatus.SUCCESS,
        entities=[
            GraphEntityPreview(id="wf", type="WORKFLOW", label="ci"),
            GraphEntityPreview(id="job", type="JOB", label="deploy"),
            GraphEntityPreview(
                id="step",
                type="STEP",
                label="Terraform apply",
                metadata={"job": "deploy", "run": "terraform apply"},
            ),
            GraphEntityPreview(
                id="cmd",
                type="COMMAND",
                label="terraform apply",
                metadata={"run": "terraform apply", "job": "deploy"},
            ),
        ],
        relationships=[
            GraphRelationshipPreview(source_id="wf", target_id="job", type="CONTAINS"),
            GraphRelationshipPreview(source_id="job", target_id="step", type="CONTAINS"),
            GraphRelationshipPreview(source_id="step", target_id="cmd", type="EXECUTES"),
        ],
        extraction_quality=0.9,
    )
    tf = StructuredParseResult(
        parser_name="terraform",
        parser_version="1.0.0",
        status=ParseStatus.SUCCESS,
        entities=[
            GraphEntityPreview(
                id="out",
                type="OUTPUT",
                label="deploy_role_arn",
                metadata={"address": "output.deploy_role_arn"},
            ),
            GraphEntityPreview(
                id="role_res",
                type="RESOURCE",
                label="aws_iam_role.deploy",
                metadata={"address": "aws_iam_role.deploy"},
            ),
        ],
        relationships=[
            GraphRelationshipPreview(source_id="out", target_id="role_res", type="REFERENCES"),
        ],
        extraction_quality=0.9,
    )
    policy = StructuredParseResult(
        parser_name="aws",
        parser_version="1.0.0",
        status=ParseStatus.SUCCESS,
        entities=[
            GraphEntityPreview(id="pol", type="IAM_POLICY", label="deploy-policy"),
            GraphEntityPreview(
                id="stmt",
                type="POLICY_STATEMENT",
                label="AllowS3",
                metadata={"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": ["*"]},
            ),
            GraphEntityPreview(id="act", type="AWS_ACTION", label="s3:GetObject"),
        ],
        relationships=[
            GraphRelationshipPreview(source_id="pol", target_id="stmt", type="CONTAINS"),
        ],
        extraction_quality=0.9,
    )
    log = StructuredParseResult(
        parser_name="log",
        parser_version="1.0.0",
        status=ParseStatus.SUCCESS,
        entities=[
            GraphEntityPreview(
                id="err",
                type="ERROR_EVENT",
                label=(
                    "AccessDenied: User arn:aws:iam::123:role/deploy-role "
                    "is not authorized to perform s3:PutObject"
                ),
                metadata={"timestamp": "2026-07-31T10:00:01Z"},
            ),
            GraphEntityPreview(
                id="exit",
                type="ERROR_EVENT",
                label="Process completed with exit code 1",
                metadata={"timestamp": "2026-07-31T10:00:02Z"},
            ),
        ],
        extraction_quality=0.85,
    )
    changed = StructuredParseResult(
        parser_name="change",
        parser_version="1.0.0",
        status=ParseStatus.SUCCESS,
        entities=[
            GraphEntityPreview(
                id="cf",
                type="CHANGED_FILE",
                label="iam.tf",
                metadata={"status": "modified"},
            )
        ],
        extraction_quality=0.8,
    )
    return {
        "wf": [workflow],
        "tf": [tf],
        "pol": [policy],
        "log": [log],
        "chg": [changed],
    }


def test_iam_chain_graph_builds_cross_artifact_links() -> None:
    parse = _iam_chain_parse()
    temporal = TemporalRootCauseLocalizer().localize(
        analysis_id="a1",
        organization_id="o1",
        project_id="p1",
        parse_by_artifact=parse,
        enabled=True,
    )
    graph = CrossArtifactEvidenceGraphBuilder().build(
        analysis_id="a1",
        organization_id="o1",
        project_id="p1",
        incident_id="i1",
        artifact_bundle_id=None,
        bundle=IncidentArtifactBundle(
            incident_id="i1",
            organization_id="o1",
            workflow_name="ci",
        ),
        parse_by_artifact=parse,
        temporal=temporal,
        enabled=True,
    )
    assert graph.status in {EvidenceGraphStatus.COMPLETE, EvidenceGraphStatus.PARTIAL}
    assert graph.metrics.node_count > 5
    assert graph.metrics.edge_count > 3
    types = {n.node_type for n in graph.nodes}
    assert GraphNodeType.STEP in types
    assert GraphNodeType.ERROR_EVENT in types
    assert any(
        e.edge_type
        in {
            GraphEdgeType.REQUIRES_PERMISSION,
            GraphEdgeType.STEP_REFERENCES_TERRAFORM,
            GraphEdgeType.DOWNSTREAM_SYMPTOM_OF,
        }
        for e in graph.edges
    )


def test_stable_node_identity_dedupes() -> None:
    parse = {
        "a": [
            StructuredParseResult(
                parser_name="t",
                parser_version="1",
                status=ParseStatus.SUCCESS,
                entities=[
                    GraphEntityPreview(id="r1", type="RESOURCE", label="aws_s3_bucket.b"),
                    GraphEntityPreview(id="r1", type="RESOURCE", label="aws_s3_bucket.b"),
                ],
            )
        ]
    }
    graph = CrossArtifactEvidenceGraphBuilder().build(
        analysis_id="a1",
        organization_id="o1",
        project_id=None,
        incident_id=None,
        artifact_bundle_id=None,
        bundle=None,
        parse_by_artifact=parse,
        temporal=None,
        enabled=True,
    )
    resources = [n for n in graph.nodes if n.node_type == GraphNodeType.TERRAFORM_RESOURCE]
    assert len(resources) == 1


def test_log_only_partial_graph() -> None:
    parse = {
        "log": [
            StructuredParseResult(
                parser_name="log",
                parser_version="1",
                status=ParseStatus.SUCCESS,
                entities=[
                    GraphEntityPreview(id="e1", type="ERROR_EVENT", label="build failed"),
                ],
            )
        ]
    }
    temporal = TemporalRootCauseLocalizer().localize(
        analysis_id="a1", organization_id="o1", parse_by_artifact=parse, enabled=True
    )
    graph = CrossArtifactEvidenceGraphBuilder().build(
        analysis_id="a1",
        organization_id="o1",
        project_id=None,
        incident_id=None,
        artifact_bundle_id=None,
        bundle=IncidentArtifactBundle(
            incident_id="i1",
            organization_id="o1",
            missing_artifacts=["terraform_file", "workflow_yaml"],
        ),
        parse_by_artifact=parse,
        temporal=temporal,
        enabled=True,
    )
    assert graph.status == EvidenceGraphStatus.PARTIAL
    assert not any(n.node_type == GraphNodeType.TERRAFORM_RESOURCE for n in graph.nodes)


def test_consistency_org_mismatch_invalid() -> None:
    parse = _iam_chain_parse()
    graph = CrossArtifactEvidenceGraphBuilder().build(
        analysis_id="a1",
        organization_id="o1",
        project_id="p1",
        incident_id="i1",
        artifact_bundle_id=None,
        bundle=None,
        parse_by_artifact=parse,
        temporal=None,
        enabled=True,
    )
    graph.nodes[0].organization_id = "other-org"
    report = GraphConsistencyEngine().validate(graph, enabled=True, expected_organization_id="o1")
    assert report.status in {
        GraphConsistencyStatus.INVALID,
        GraphConsistencyStatus.VALID_WITH_WARNINGS,
        GraphConsistencyStatus.PARTIAL,
    }
    assert any("org_mismatch" in e for e in report.errors)


def test_graph_disabled() -> None:
    graph = CrossArtifactEvidenceGraphBuilder().build(
        analysis_id="a1",
        organization_id="o1",
        project_id=None,
        incident_id=None,
        artifact_bundle_id=None,
        bundle=None,
        parse_by_artifact={},
        temporal=None,
        enabled=False,
    )
    assert graph.status == EvidenceGraphStatus.DISABLED


def test_flags_default_off() -> None:
    from app.core.config import Settings

    settings = Settings(
        PROJECT_NAME="t",
        APP_VERSION="1",
        ENVIRONMENT="development",
        DEBUG=False,
        DATABASE_URL="postgresql+asyncpg://x:y@localhost/z",
    )
    assert settings.temporal_localisation_enabled is False
    assert settings.evidence_graph_enabled is False
    assert settings.graph_consistency_enabled is False
