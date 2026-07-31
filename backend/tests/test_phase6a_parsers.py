"""Deterministic Phase 6A.1 domain model and deep parser tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.artifacts.parsers import (
    AwsPolicyParser,
    ChangeParser,
    LogParser,
    TerraformParser,
    TerraformPlanParser,
    WorkflowParser,
    build_default_parser_registry,
)
from app.domain.artifacts import (
    AcquisitionStatus,
    ArtifactKind,
    ArtifactRecord,
    ArtifactSource,
    IncidentArtifactBundle,
    ParseStatus,
    RedactionStatus,
    content_sha256,
    map_failure_category,
)
from app.domain.artifacts.taxonomy_hierarchy import (
    LEVEL1_APPLICATION,
    LEVEL1_DEPENDENCY,
    LEVEL1_INFRASTRUCTURE,
    LEVEL1_NETWORK,
    LEVEL1_RESOURCE,
    LEVEL1_SECURITY,
    LEVEL1_TEST,
    LEVEL1_UNKNOWN,
    LEVEL1_WORKFLOW,
)

FIXTURES = Path(__file__).parent / "fixtures" / "phase6a"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_content_sha256_is_stable() -> None:
    assert content_sha256("hello") == content_sha256("hello")
    assert content_sha256("hello") != content_sha256("world")
    assert len(content_sha256("")) == 64


def test_incident_artifact_bundle_defaults() -> None:
    bundle = IncidentArtifactBundle(
        incident_id="inc-1",
        organization_id="org-1",
    )
    assert bundle.artifacts == []
    assert bundle.missing_artifacts == []
    record = ArtifactRecord(
        id="a1",
        kind=ArtifactKind.EXECUTION_LOG,
        source=ArtifactSource.UPLOAD,
        filename="fail.log",
        content_hash=content_sha256("x"),
        content="x",
        acquisition_status=AcquisitionStatus.COLLECTED,
        redaction_status=RedactionStatus.NOT_REQUIRED,
    )
    bundle.artifacts.append(record)
    assert bundle.artifacts[0].kind == ArtifactKind.EXECUTION_LOG


@pytest.mark.parametrize(
    ("code", "level_1"),
    [
        ("build_failure", LEVEL1_APPLICATION),
        ("test_failure", LEVEL1_TEST),
        ("dependency_failure", LEVEL1_DEPENDENCY),
        ("configuration_failure", LEVEL1_WORKFLOW),
        ("terraform_failure", LEVEL1_INFRASTRUCTURE),
        ("docker_failure", LEVEL1_INFRASTRUCTURE),
        ("deployment_failure", LEVEL1_INFRASTRUCTURE),
        ("aws_permission_failure", LEVEL1_SECURITY),
        ("security_misconfiguration", LEVEL1_SECURITY),
        ("network_failure", LEVEL1_NETWORK),
        ("ci_runner_failure", LEVEL1_RESOURCE),
        ("unknown_failure", LEVEL1_UNKNOWN),
    ],
)
def test_map_failure_category_hierarchy(code: str, level_1: str) -> None:
    mapped = map_failure_category(code)
    assert mapped["level_1"] == level_1
    assert mapped["legacy_code"] == code
    assert mapped["level_2"]
    assert mapped["level_3"] is None


def test_map_failure_category_unknown_preserves_legacy() -> None:
    mapped = map_failure_category("custom_future_code")
    assert mapped["level_1"] == LEVEL1_UNKNOWN
    assert mapped["legacy_code"] == "custom_future_code"


def test_workflow_parser_extracts_jobs_needs_secrets_matrix() -> None:
    content = _load("sample_workflow.yml")
    result = WorkflowParser().parse(
        content,
        filename="deploy.yml",
        kind=ArtifactKind.WORKFLOW_YAML,
    )
    assert result.status == ParseStatus.SUCCESS
    assert result.parser_version == "1.0.0"
    types = {e.type for e in result.entities}
    assert {"WORKFLOW", "JOB", "STEP", "ACTION_REF", "SECRET_REFERENCE", "COMMAND"} <= types
    rel_types = {r.type for r in result.relationships}
    assert {"CONTAINS", "NEEDS", "USES", "EXECUTES", "REFERENCES"} <= rel_types
    assert any(e.label == "terraform" for e in result.entities if e.type == "JOB")
    assert any(r.type == "NEEDS" for r in result.relationships)
    assert any("NPM_TOKEN" in e.label for e in result.entities if e.type == "SECRET_REFERENCE")
    assert result.raw_summary["secret_reference_count"] >= 2
    assert any(
        e.metadata.get("matrix") for e in result.entities if e.type == "JOB"
    )
    assert any(
        e.metadata.get("reusable_local") for e in result.entities if e.type == "ACTION_REF"
    )


def test_log_parser_detects_access_denied_cascade_and_ordering() -> None:
    content = _load("sample_log.txt")
    result = LogParser().parse(
        content,
        filename="job.log",
        kind=ArtifactKind.EXECUTION_LOG,
    )
    assert result.status == ParseStatus.SUCCESS
    assert result.raw_summary["access_denied_count"] >= 2
    assert result.raw_summary["first_error"] is not None
    assert any(e.type == "ERROR_EVENT" for e in result.entities)
    assert any(r.type == "OCCURRED_BEFORE" for r in result.relationships)
    assert result.evidence_candidates
    assert result.raw_summary["stack_trace_lines"] >= 1


def test_terraform_parser_declares_and_depends_on() -> None:
    content = _load("sample_main.tf")
    result = TerraformParser().parse(
        content,
        filename="main.tf",
        kind=ArtifactKind.TERRAFORM_FILE,
    )
    assert result.status == ParseStatus.SUCCESS
    addresses = set(result.raw_summary["addresses"])
    assert "aws_s3_bucket.logs" in addresses
    assert "module.network" in addresses
    assert "var.region" in addresses
    assert any(r.type == "DECLARES" for r in result.relationships)
    assert any(r.type == "DEPENDS_ON" for r in result.relationships)
    assert any(r.type == "REFERENCES" for r in result.relationships)


def test_terraform_plan_parser_resource_changes() -> None:
    content = _load("sample_plan.json")
    result = TerraformPlanParser().parse(
        content,
        filename="plan.json",
        kind=ArtifactKind.TERRAFORM_PLAN_JSON,
    )
    assert result.status == ParseStatus.SUCCESS
    assert result.raw_summary["resource_change_count"] == 2
    assert any(e.type == "PLAN_RESOURCE_CHANGE" for e in result.entities)
    assert result.raw_summary["change_counts"]["create"] == 1
    assert result.raw_summary["change_counts"]["update"] == 1


def test_terraform_plan_parser_invalid_json() -> None:
    result = TerraformPlanParser().parse(
        "not-json",
        filename="bad.json",
        kind=ArtifactKind.TERRAFORM_PLAN_JSON,
    )
    assert result.status == ParseStatus.FAILED
    assert result.errors
    assert any(d.code == "invalid_plan_json" for d in result.diagnostics)


def test_aws_policy_parser_iam_statements() -> None:
    content = _load("sample_iam_policy.json")
    result = AwsPolicyParser().parse(
        content,
        filename="policy.json",
        kind=ArtifactKind.IAM_POLICY_JSON,
    )
    assert result.status == ParseStatus.SUCCESS
    types = {e.type for e in result.entities}
    assert "IAM_POLICY" in types
    assert "POLICY_STATEMENT" in types
    assert result.raw_summary["statement_count"] == 2
    assert any(e.kind == "iam_deny_statement" for e in result.evidence_candidates)


def test_aws_policy_parser_access_denied_text() -> None:
    text = (
        "AccessDenied: User is not authorized to perform: s3:CreateBucket "
        "on resource: arn:aws:s3:::app-logs"
    )
    result = AwsPolicyParser().parse(
        text,
        filename="aws-error.txt",
        kind=ArtifactKind.AWS_ERROR_METADATA,
    )
    assert result.status == ParseStatus.SUCCESS
    assert any(e.type == "AWS_ERROR" for e in result.entities)
    assert result.evidence_candidates


def test_change_parser_json_list() -> None:
    content = _load("sample_changed_files.json")
    result = ChangeParser().parse(
        content,
        filename="changed.json",
        kind=ArtifactKind.CHANGED_FILES_METADATA,
    )
    assert result.status == ParseStatus.SUCCESS
    assert result.raw_summary["changed_file_count"] == 3
    paths = {e.label for e in result.entities if e.type == "CHANGED_FILE"}
    assert "infra/main.tf" in paths
    assert "scripts/deploy.py" in paths


def test_change_parser_newline_paths() -> None:
    result = ChangeParser().parse(
        "M infra/main.tf\nA scripts/boot.sh\n",
        filename="paths.txt",
        kind=ArtifactKind.CHANGED_FILES_METADATA,
    )
    assert result.status == ParseStatus.SUCCESS
    assert result.raw_summary["changed_file_count"] == 2


def test_default_registry_parse_all() -> None:
    registry = build_default_parser_registry()
    assert registry.get("workflow_parser") is not None
    assert registry.get("log_parser") is not None
    assert len(registry.list_parsers()) == 6

    workflow_results = registry.parse_all(
        _load("sample_workflow.yml"),
        filename="deploy.yml",
        kind=ArtifactKind.WORKFLOW_YAML,
    )
    assert len(workflow_results) == 1
    assert workflow_results[0].status == ParseStatus.SUCCESS

    skipped = registry.parse_all(
        "{}",
        filename="lock.hcl",
        kind=ArtifactKind.TERRAFORM_LOCK,
    )
    assert len(skipped) == 1
    assert skipped[0].status == ParseStatus.SKIPPED
