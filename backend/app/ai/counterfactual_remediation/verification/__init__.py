"""Phase 6A.6 Part 3 — independent verifier engine package."""

from __future__ import annotations

from app.ai.counterfactual_remediation.verification.actionlint import ActionlintVerifier
from app.ai.counterfactual_remediation.verification.base import BaseVerifier, Verifier
from app.ai.counterfactual_remediation.verification.checkov import CheckovVerifier
from app.ai.counterfactual_remediation.verification.consensus import (
    VerifierConsensusEngine,
    compute_consensus,
)
from app.ai.counterfactual_remediation.verification.dependency_manifest import (
    DependencyManifestVerifier,
)
from app.ai.counterfactual_remediation.verification.engine import (
    CounterfactualVerifierService,
    IndependentVerifierEngine,
    build_summary,
)
from app.ai.counterfactual_remediation.verification.hcl_fragment import HclFragmentVerifier
from app.ai.counterfactual_remediation.verification.iam_structural import IamStructuralVerifier
from app.ai.counterfactual_remediation.verification.json_schema import JsonSchemaVerifier
from app.ai.counterfactual_remediation.verification.opa import OpaVerifier
from app.ai.counterfactual_remediation.verification.persist import (
    NoOpVerificationPersistService,
    VerificationPersistService,
    build_persist_service,
)
from app.ai.counterfactual_remediation.verification.registry import (
    VerifierRegistry,
    build_default_registry,
)
from app.ai.counterfactual_remediation.verification.runner import VerifierRunner
from app.ai.counterfactual_remediation.verification.security_static import SecurityStaticVerifier
from app.ai.counterfactual_remediation.verification.subprocess_runner import (
    SubprocessResult,
    run_tool,
)
from app.ai.counterfactual_remediation.verification.terraform_plan import TerraformPlanVerifier
from app.ai.counterfactual_remediation.verification.terraform_validate import (
    TerraformValidateVerifier,
)
from app.ai.counterfactual_remediation.verification.workspace import (
    PathTraversalError,
    TempCounterfactualWorkspace,
    TempWorkspaceError,
    TempWorkspaceManager,
)
from app.ai.counterfactual_remediation.verification.yaml_validator import YamlValidatorVerifier

__all__ = [
    "ActionlintVerifier",
    "BaseVerifier",
    "CheckovVerifier",
    "CounterfactualVerifierService",
    "DependencyManifestVerifier",
    "HclFragmentVerifier",
    "IamStructuralVerifier",
    "IndependentVerifierEngine",
    "JsonSchemaVerifier",
    "NoOpVerificationPersistService",
    "OpaVerifier",
    "PathTraversalError",
    "SecurityStaticVerifier",
    "SubprocessResult",
    "TempCounterfactualWorkspace",
    "TempWorkspaceError",
    "TempWorkspaceManager",
    "TerraformPlanVerifier",
    "TerraformValidateVerifier",
    "VerificationPersistService",
    "Verifier",
    "VerifierConsensusEngine",
    "VerifierRegistry",
    "VerifierRunner",
    "YamlValidatorVerifier",
    "build_default_registry",
    "build_persist_service",
    "build_summary",
    "compute_consensus",
    "run_tool",
]
