"""Phase 6A.6 Part 3 — independent verifier engine tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.counterfactual_remediation.verification.consensus import compute_consensus
from app.ai.counterfactual_remediation.verification.engine import IndependentVerifierEngine
from app.ai.counterfactual_remediation.verification.hcl_fragment import HclFragmentVerifier
from app.ai.counterfactual_remediation.verification.iam_structural import IamStructuralVerifier
from app.ai.counterfactual_remediation.verification.json_schema import JsonSchemaVerifier
from app.ai.counterfactual_remediation.verification.security_static import SecurityStaticVerifier
from app.ai.counterfactual_remediation.verification.subprocess_runner import run_tool
from app.ai.counterfactual_remediation.verification.terraform_validate import (
    TerraformValidateVerifier,
)
from app.ai.counterfactual_remediation.verification.workspace import (
    PathTraversalError,
    TempWorkspaceManager,
)
from app.ai.counterfactual_remediation.verification.yaml_validator import YamlValidatorVerifier
from app.application.services.analysis_execution_service import AnalysisExecutionService
from app.core.config import Settings
from app.domain.counterfactual_remediation.enums import (
    CounterfactualCandidateStatus,
    RemediationArtifactType,
)
from app.domain.counterfactual_remediation.models import (
    CounterfactualChange,
    CounterfactualRemediationCandidate,
)
from app.domain.counterfactual_remediation.verification_enums import (
    VerificationConsensusStatus,
    VerifierResultStatus,
)
from app.domain.counterfactual_remediation.verification_models import VerifierResult


def _settings(**flags: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "verifier_engine_enabled": False,
        "terraform_verifier_enabled": False,
        "actionlint_verifier_enabled": False,
        "checkov_verifier_enabled": False,
        "opa_verifier_enabled": False,
        "security_verifier_enabled": True,
        "verifier_persistence_enabled": False,
        "max_candidates_for_verification": 5,
        "max_verifier_timeout_seconds": 60.0,
        "max_verifier_stage_timeout_seconds": 180.0,
        "max_verifier_stdout_chars": 20_000,
        "max_temp_workspace_files": 20,
        "max_temp_workspace_bytes": 5_000_000,
    }
    defaults.update(flags)
    return SimpleNamespace(**defaults)


def _candidate(
    *,
    artifact_type: str,
    proposed: str,
    status: str = CounterfactualCandidateStatus.READY_FOR_VERIFICATION.value,
    priority_status: str = "PRIORITY_CANDIDATE",
    path: str = "main.tf",
) -> CounterfactualRemediationCandidate:
    return CounterfactualRemediationCandidate(
        id=str(uuid4()),
        remediation_run_id=str(uuid4()),
        organization_id=str(uuid4()),
        project_id=str(uuid4()),
        incident_id=str(uuid4()),
        analysis_id=str(uuid4()),
        hypothesis_id=str(uuid4()),
        candidate_key="c1",
        title="test",
        summary="test",
        artifact_type=artifact_type,
        target_paths=[path],
        changes=[
            CounterfactualChange(
                id=str(uuid4()),
                change_type="REPLACE",
                source_path=path,
                original_fragment="old",
                proposed_fragment=proposed,
            )
        ],
        status=CounterfactualCandidateStatus(status)
        if status in {s.value for s in CounterfactualCandidateStatus}
        else CounterfactualCandidateStatus.READY_FOR_VERIFICATION,
        priority_status=priority_status,
        rendered_patch=proposed,
    )


def test_engine_flag_off_no_runs() -> None:
    engine = IndependentVerifierEngine(_settings(verifier_engine_enabled=False))
    cand = _candidate(
        artifact_type=RemediationArtifactType.TERRAFORM_CONFIGURATION.value,
        proposed='resource "aws_s3_bucket" "b" {\n  bucket = "x"\n}\n',
    )
    report = engine.run(
        organization_id=cand.organization_id,
        project_id=cand.project_id,
        incident_id=cand.incident_id,
        analysis_id=cand.analysis_id,
        candidates=[cand],
    )
    assert enum_str(report.status) == "DISABLED"
    assert report.runs == []


def enum_str(value: object) -> str:
    return str(value.value if hasattr(value, "value") else value)


def test_json_yaml_hcl_iam_structural_pass_fail() -> None:
    ws = SimpleNamespace(files_written=["f"], root=None)
    json_v = JsonSchemaVerifier()
    assert (
        enum_str(
            json_v.execute(
                ws,
                _candidate(
                    artifact_type="IAM_POLICY",
                    proposed='{"Version":"2012-10-17","Statement":[]}',
                ),
            ).status
        )
        == "PASS"
    )
    assert (
        enum_str(
            json_v.execute(
                ws, _candidate(artifact_type="IAM_POLICY", proposed="{not-json")
            ).status
        )
        == "FAIL"
    )

    yaml_v = YamlValidatorVerifier()
    assert (
        enum_str(
            yaml_v.execute(
                ws,
                _candidate(
                    artifact_type=RemediationArtifactType.GITHUB_WORKFLOW.value,
                    proposed=(
                        "name: ci\non: push\njobs:\n  build:\n"
                        "    runs-on: ubuntu-latest\n    steps: []\n"
                    ),
                    path=".github/workflows/ci.yml",
                ),
            ).status
        )
        == "PASS"
    )
    assert (
        enum_str(
            yaml_v.execute(
                ws,
                _candidate(
                    artifact_type=RemediationArtifactType.GITHUB_WORKFLOW.value,
                    proposed=":\n  - bad\n",
                    path="w.yml",
                ),
            ).status
        )
        == "FAIL"
    )

    hcl_v = HclFragmentVerifier()
    assert (
        enum_str(
            hcl_v.execute(
                ws,
                _candidate(
                    artifact_type=RemediationArtifactType.TERRAFORM_CONFIGURATION.value,
                    proposed='resource "aws_s3_bucket" "b" {\n  bucket = "ok"\n}\n',
                ),
            ).status
        )
        == "PASS"
    )
    assert (
        enum_str(
            hcl_v.execute(
                ws,
                _candidate(
                    artifact_type=RemediationArtifactType.TERRAFORM_CONFIGURATION.value,
                    proposed='resource "x" {\n',
                ),
            ).status
        )
        == "FAIL"
    )

    iam_v = IamStructuralVerifier()
    good_iam = (
        '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
        '"Action":"s3:GetObject","Resource":"arn:aws:s3:::b/*"}]}'
    )
    assert (
        enum_str(
            iam_v.execute(ws, _candidate(artifact_type="IAM_POLICY", proposed=good_iam)).status
        )
        == "PASS"
    )
    assert (
        enum_str(
            iam_v.execute(
                ws, _candidate(artifact_type="IAM_POLICY", proposed='{"Version":"2012-10-17"}')
            ).status
        )
        == "FAIL"
    )


def test_security_rejects_wildcard_and_secret() -> None:
    sec = SecurityStaticVerifier(enabled=True)
    ws = SimpleNamespace(files_written=[], root=None)
    wild = (
        '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}'
    )
    result = sec.execute(ws, _candidate(artifact_type="IAM_POLICY", proposed=wild))
    assert enum_str(result.status) == "FAIL"
    assert "wildcard_action" in result.findings or "wildcard_resource" in result.findings

    secretish = 'access_key_id = "AKIAIOSFODNN7EXAMPLE"\n'
    result2 = sec.execute(
        ws,
        _candidate(
            artifact_type=RemediationArtifactType.TERRAFORM_CONFIGURATION.value,
            proposed=secretish,
        ),
    )
    assert enum_str(result2.status) == "FAIL"
    assert "secret_material_detected" in result2.findings


def test_missing_terraform_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.ai.counterfactual_remediation.verification.terraform_validate.shutil.which",
        lambda _name: None,
    )
    v = TerraformValidateVerifier(enabled=True)
    cand = _candidate(
        artifact_type=RemediationArtifactType.TERRAFORM_CONFIGURATION.value,
        proposed='resource "aws_s3_bucket" "b" {\n  bucket = "x"\n}\n',
    )
    ws = TempWorkspaceManager()
    try:
        ws.create()
        ws.materialise_candidate(cand) if hasattr(ws, "materialise_candidate") else None
        if hasattr(ws, "write_text"):
            ws.write_text("main.tf", cand.rendered_patch or "")
        result = v.execute(ws, cand)
    finally:
        ws.cleanup()
    assert enum_str(result.status) == "UNAVAILABLE"


def test_consensus_verified_failed_inconclusive() -> None:
    cid = str(uuid4())
    cand = _candidate(
        artifact_type=RemediationArtifactType.IAM_POLICY.value,
        proposed='{"Version":"2012-10-17","Statement":[]}',
        path="policy.json",
    )
    cand.id = cid

    verified = compute_consensus(
        [
            VerifierResult("json_schema", "v1", VerifierResultStatus.PASS, candidate_id=cid),
            VerifierResult("iam_structural", "v1", VerifierResultStatus.PASS, candidate_id=cid),
        ],
        candidate=cand,
        candidate_id=cid,
    )
    assert verified.status == VerificationConsensusStatus.VERIFIED

    failed = compute_consensus(
        [
            VerifierResult("json_schema", "v1", VerifierResultStatus.FAIL, candidate_id=cid),
            VerifierResult("iam_structural", "v1", VerifierResultStatus.PASS, candidate_id=cid),
        ],
        candidate=cand,
        candidate_id=cid,
    )
    assert failed.status == VerificationConsensusStatus.FAILED

    inconclusive = compute_consensus(
        [
            VerifierResult("json_schema", "v1", VerifierResultStatus.PASS, candidate_id=cid),
            VerifierResult(
                "iam_structural", "v1", VerifierResultStatus.UNAVAILABLE, candidate_id=cid
            ),
        ],
        candidate=cand,
        candidate_id=cid,
    )
    assert inconclusive.status in {
        VerificationConsensusStatus.INCONCLUSIVE,
        VerificationConsensusStatus.UNAVAILABLE,
        VerificationConsensusStatus.PARTIALLY_VERIFIED,
    }


def test_path_traversal_rejected_in_workspace() -> None:
    ws = TempWorkspaceManager()
    try:
        ws.create()
        with pytest.raises((PathTraversalError, ValueError)):
            if hasattr(ws, "resolve_safe"):
                ws.resolve_safe("../etc/passwd")
            else:
                ws.write_text("../../escape.txt", "nope")
        with pytest.raises((PathTraversalError, ValueError)):
            ws.write_text("../../escape.txt", "nope")
    finally:
        ws.cleanup()


def test_temp_dir_cleaned() -> None:
    ws = TempWorkspaceManager()
    root = ws.create()
    assert root.exists()
    ws.write_text("a.txt", "hello")
    root_path = Path(root)
    ws.cleanup()
    assert not root_path.exists()


def test_timeout_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired(cmd=["sleep"], timeout=0.1)

    monkeypatch.setattr(
        "app.ai.counterfactual_remediation.verification.subprocess_runner.subprocess.run",
        _raise,
    )
    out = run_tool(["terraform", "validate"], cwd="/tmp", timeout=0.1)
    assert out.timed_out is True


def test_no_repository_files_modified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    marker = tmp_path / "repo_file.txt"
    marker.write_text("untouched", encoding="utf-8")
    before = marker.read_text(encoding="utf-8")
    listing_before = sorted(p.name for p in tmp_path.iterdir())

    engine = IndependentVerifierEngine(
        _settings(verifier_engine_enabled=True, security_verifier_enabled=True)
    )
    cand = _candidate(
        artifact_type=RemediationArtifactType.IAM_POLICY.value,
        proposed=(
            '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
            '"Action":"s3:GetObject","Resource":"arn:aws:s3:::b/*"}]}'
        ),
        path="policy.json",
    )
    report = engine.run(
        organization_id=cand.organization_id,
        project_id=cand.project_id,
        incident_id=cand.incident_id,
        analysis_id=cand.analysis_id,
        candidates=[cand],
    )
    assert report.runs
    assert marker.read_text(encoding="utf-8") == before
    assert sorted(p.name for p in tmp_path.iterdir()) == listing_before
    assert os.getcwd() == str(tmp_path)


def test_config_bounds() -> None:
    assert Settings.model_fields["verifier_engine_enabled"].default is False
    assert Settings.model_fields["max_candidates_for_verification"].default == 5
    values: dict[str, object] = {
        "PROJECT_NAME": "DevGuard AI Test",
        "APP_VERSION": "1.0.0",
        "ENVIRONMENT": "development",
        "DEBUG": False,
        "DATABASE_URL": "postgresql+asyncpg://devguard:change_me@localhost:5432/devguard_test",
        "JWT_SECRET_KEY": "x" * 32,
        "MAX_CANDIDATES_FOR_VERIFICATION": 99,
    }
    settings = Settings(**values)  # type: ignore[arg-type]
    problems = settings.validate_for_runtime()
    assert any("MAX_CANDIDATES_FOR_VERIFICATION" in p for p in problems)
    with pytest.raises(Exception):  # noqa: B017
        Settings(
            PROJECT_NAME="DevGuard AI Test",
            APP_VERSION="1.0.0",
            ENVIRONMENT="development",
            DEBUG=False,
            DATABASE_URL="postgresql+asyncpg://devguard:change_me@localhost:5432/devguard_test",
            JWT_SECRET_KEY="x" * 32,
            MAX_VERIFIER_TIMEOUT_SECONDS=0,
        )


def test_orchestrator_hook_exists() -> None:
    assert hasattr(AnalysisExecutionService, "_maybe_run_phase6a6_verifier_engine")
    assert callable(AnalysisExecutionService._maybe_run_phase6a6_verifier_engine)


def test_engine_runs_structural_when_enabled() -> None:
    engine = IndependentVerifierEngine(
        _settings(verifier_engine_enabled=True, security_verifier_enabled=True)
    )
    cand = _candidate(
        artifact_type=RemediationArtifactType.IAM_POLICY.value,
        proposed=(
            '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
            '"Action":"s3:GetObject","Resource":"arn:aws:s3:::bucket/*"}]}'
        ),
        path="policy.json",
    )
    report = engine.run(
        organization_id=cand.organization_id,
        project_id=cand.project_id,
        incident_id=cand.incident_id,
        analysis_id=cand.analysis_id,
        candidates=[cand],
    )
    assert report.runs
    assert report.runs[0].consensus is not None
    assert report.runs[0].results
