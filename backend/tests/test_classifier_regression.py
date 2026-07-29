"""Regression tests for the hybrid classifier — CI runner vs Terraform misclassification.

These tests verify:
- GHA runner failures → ci_runner_failure
- Terraform failures → terraform_failure
- Mixed GHA+Terraform context → correct primary category
- False-positive controls (generic runner words, test runners, Docker runner-like wording)
- Case-insensitive and multiline matching
"""

from __future__ import annotations

import uuid

import pytest

from app.ai.classification.hybrid_classifier import HybridClassifier
from app.ai.orchestration.analysis_context import AnalysisContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx(text: str, top_k: int = 3) -> AnalysisContext:
    ctx = AnalysisContext(
        analysis_run_id=uuid.uuid4(),
        incident_id=uuid.uuid4(),
        combined_text=text,
        options={"top_k_predictions": top_k},
    )
    return ctx


def _classify(text: str, top_k: int = 3) -> list[tuple[str, float]]:
    ctx = _ctx(text, top_k)
    candidates = HybridClassifier().classify(ctx)
    return [(c.category_code, c.confidence) for c in candidates]


def _primary(text: str) -> str:
    return _classify(text)[0][0]


# ---------------------------------------------------------------------------
# CASES 1–8: GitHub Actions runner failures → ci_runner_failure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "log_text",
    [
        # Case 1 — Self-hosted runner offline
        (
            "##[error]The self-hosted runner is offline.\n"
            "Waiting for a self-hosted runner to become available…\n"
            "runs-on: [self-hosted, linux, x64]"
        ),
        # Case 2 — No runner matching requested labels
        (
            "Job is waiting for a runner.\n"
            "No runner matching the requested labels was found.\n"
            "Requested labels: ubuntu-latest, large"
        ),
        # Case 3 — Job waiting for a hosted runner
        (
            "Waiting for a hosted runner to become available.\n"
            "github-hosted runner\n"
            "GITHUB_ACTIONS=true\nGITHUB_RUN_ID=12345678"
        ),
        # Case 4 — Runner disconnected during a job
        ("Runner is not connected.\nrunner disconnected\nactions/checkout@v4"),
        # Case 5 — Runner registration failure
        (
            "Failed to create a session with the server.\n"
            "runner registration failed\n"
            "actions.runner exiting"
        ),
        # Case 6 — Runner service stopped
        (
            "The runner service stopped unexpectedly.\n"
            "actions-runner service exited with code 1\n"
            "runs-on: ubuntu-latest"
        ),
        # Case 7 — Runner failed to create a session
        ("Failed to create a session.\nrunner listener exited\nself-hosted runner offline"),
        # Case 8 — Workflow queued because no runner is available
        ("queued waiting for runner\nrunner did not pick up job\ngithub-hosted runner unavailable"),
    ],
    ids=[f"case{i}" for i in range(1, 9)],
)
def test_gha_runner_classified_as_ci_runner_failure(log_text: str) -> None:
    result = _primary(log_text)
    assert result == "ci_runner_failure", (
        f"Expected ci_runner_failure, got {result!r} for log: {log_text[:80]!r}"
    )


def test_gha_runner_technology_detection() -> None:
    """Technology signals should include GitHub Actions for runner logs."""
    from app.ai.rag.signals import DiagnosticSignalExtractor

    log = "The self-hosted runner is offline.\nruns-on: [self-hosted, linux]\nGITHUB_ACTIONS=true"
    ctx = _ctx(log)
    HybridClassifier().classify(ctx)
    extractor = DiagnosticSignalExtractor()
    signals = extractor.extract(ctx)
    assert "GitHub Actions" in signals.technologies, (
        f"Expected 'GitHub Actions' in technologies, got {signals.technologies}"
    )


# ---------------------------------------------------------------------------
# CASES 9–12: Terraform failures → terraform_failure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "log_text",
    [
        # Case 9 — Terraform undeclared resource
        (
            "Error: Reference to undeclared resource\n"
            '  on main.tf line 12, in resource "aws_instance" "web":\n'
            "terraform validate failed"
        ),
        # Case 10 — Terraform state lock
        (
            "Error acquiring the state lock\n"
            "terraform apply -auto-approve\n"
            "state locked by another process"
        ),
        # Case 11 — Terraform provider configuration failure
        (
            "Error: Invalid provider configuration\n"
            "provider configuration for aws\n"
            'provider "aws" { region = "us-east-1" }'
        ),
        # Case 12 — Terraform init backend failure
        (
            "terraform init\n"
            "Error: Failed to get existing workspaces: backend configuration\n"
            "Initializing the backend..."
        ),
    ],
    ids=[f"case{i}" for i in range(9, 13)],
)
def test_terraform_classified_correctly(log_text: str) -> None:
    result = _primary(log_text)
    assert result == "terraform_failure", (
        f"Expected terraform_failure, got {result!r} for log: {log_text[:80]!r}"
    )


# ---------------------------------------------------------------------------
# CASE 13: GHA executing Terraform — runner offline BEFORE Terraform starts
# ---------------------------------------------------------------------------


def test_case13_gha_runner_offline_before_terraform() -> None:
    """Runner fails before any Terraform command runs → ci_runner_failure."""
    log = (
        "Workflow: deploy-infrastructure\n"
        "Job: terraform-apply\n"
        "runs-on: [self-hosted, linux]\n"
        "Error: The self-hosted runner is offline.\n"
        "runner is not connected\n"
        "No Terraform commands were executed."
    )
    result = _primary(log)
    assert result == "ci_runner_failure", (
        f"Expected ci_runner_failure (runner offline before TF), got {result!r}"
    )


# ---------------------------------------------------------------------------
# CASE 14: GHA executing Terraform — terraform plan fails
# ---------------------------------------------------------------------------


def test_case14_terraform_plan_fails_in_gha() -> None:
    """Terraform plan failure inside GHA → terraform_failure (actual TF error)."""
    log = (
        "Run terraform plan\n"
        "terraform plan -out=tfplan\n"
        "Error: Reference to undeclared resource\n"
        "  on main.tf line 8\n"
        "GITHUB_ACTIONS=true\nGITHUB_RUN_ID=99887766"
    )
    result = _primary(log)
    assert result == "terraform_failure", (
        f"Expected terraform_failure (TF plan error), got {result!r}"
    )


# ---------------------------------------------------------------------------
# CASES 15–16: Runner label/path contains "terraform" but failure is runner
# ---------------------------------------------------------------------------


def test_case15_runner_label_named_terraform() -> None:
    """Label 'terraform' on runner should not cause terraform_failure."""
    log = (
        "runs-on: [self-hosted, terraform]\n"
        "No runner matching the requested labels was found.\n"
        "runner is offline"
    )
    result = _primary(log)
    assert result == "ci_runner_failure", (
        f"Expected ci_runner_failure (runner label 'terraform'), got {result!r}"
    )


def test_case16_repo_path_contains_terraform_runner_unavailable() -> None:
    """Repo path contains 'terraform' but runner is unavailable → ci_runner_failure."""
    log = (
        "Repository: myorg/terraform-infra\n"
        "Workflow: .github/workflows/deploy.yml\n"
        "The self-hosted runner is offline.\n"
        "Waiting for a runner to become available."
    )
    result = _primary(log)
    assert result == "ci_runner_failure", (
        f"Expected ci_runner_failure (repo path has terraform), got {result!r}"
    )


# ---------------------------------------------------------------------------
# CASES 17–19: Negative controls — must NOT produce ci_runner_failure
# ---------------------------------------------------------------------------


def test_case17_generic_application_runner_process() -> None:
    """Generic application 'runner' process failure without GHA context."""
    log = (
        "ApplicationRunner process exited with code 1\n"
        "Spring Boot runner failed to start\n"
        "Port 8080 already in use"
    )
    result = _primary(log)
    assert result != "ci_runner_failure", (
        f"Should not classify generic app runner as ci_runner_failure, got {result!r}"
    )


def test_case18_test_runner_failed() -> None:
    """pytest / test runner failure → test_failure, not ci_runner_failure."""
    log = (
        "FAILED tests/test_api.py::test_health - AssertionError\n"
        "===== 3 failed, 12 passed in 4.20s =====\n"
        "pytest runner exited with code 1"
    )
    result = _primary(log)
    assert result != "ci_runner_failure", (
        f"pytest failure should not be ci_runner_failure, got {result!r}"
    )


def test_case19_docker_runner_like_wording_no_gha() -> None:
    """Docker container 'runner' wording without GHA context."""
    log = "docker run --rm myapp/runner:latest\nContainer exited with status 137\nOOM killed"
    result = _primary(log)
    assert result != "ci_runner_failure", (
        f"Docker runner wording without GHA should not be ci_runner_failure, got {result!r}"
    )


# ---------------------------------------------------------------------------
# CASE 20: Successful GHA job mentioning Terraform — must not be a failure
# ---------------------------------------------------------------------------


def test_case20_successful_gha_terraform_mention() -> None:
    """Success markers without failure markers should return unknown_failure."""
    log = (
        "Run terraform init\n"
        "Terraform has been successfully initialized!\n"
        "Run terraform plan\n"
        "Plan: 3 to add, 0 to change, 0 to destroy.\n"
        "Job succeeded\n"
        "GITHUB_ACTIONS=true"
    )
    result = _primary(log)
    assert result == "unknown_failure", (
        f"Successful Terraform job should be filtered to unknown_failure, got {result!r}"
    )


# ---------------------------------------------------------------------------
# Additional: case-insensitive and multiline matching
# ---------------------------------------------------------------------------


def test_case_insensitive_runner_offline() -> None:
    log = "THE SELF-HOSTED RUNNER IS OFFLINE\nRUNS-ON: [SELF-HOSTED, LINUX]"
    assert _primary(log) == "ci_runner_failure"


def test_multiline_runner_log() -> None:
    log = (
        "2024-01-15T10:23:45Z Job queued\n"
        "2024-01-15T10:23:46Z Waiting for a hosted runner to become available...\n"
        "2024-01-15T10:33:46Z ##[error]No runner matching the requested labels was found.\n"
        "2024-01-15T10:33:47Z runner did not pick up job after 600s\n"
    )
    assert _primary(log) == "ci_runner_failure"


def test_original_phase3_gha_runner_log() -> None:
    """Regression: the exact Phase 3 test case that was wrongly terraform_failure."""
    log = (
        "##[error]No runner matching the requested labels was found.\n"
        "  Labels: self-hosted, linux\n"
        "The self-hosted runner is offline.\n"
        "Waiting for a self-hosted runner to become available...\n"
        "Job is waiting for a runner.\n"
        "Error: The runner for this request was not found.\n"
    )
    result = _primary(log)
    assert result == "ci_runner_failure", (
        f"Phase 3 GHA runner log must be ci_runner_failure, got {result!r}"
    )
