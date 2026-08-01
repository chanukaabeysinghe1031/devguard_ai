"""Stable version identifiers for Phase 6A.6 Part 3 verifier engine."""

from __future__ import annotations

VERIFIER_ENGINE_VERSION = "verifier_engine_v1"
CONSENSUS_ENGINE_VERSION = "consensus_v1"
TEMP_WORKSPACE_VERSION = "temp_workspace_v1"

# Built-in adapters
JSON_SCHEMA_VERIFIER_VERSION = "json_schema_verifier_v1"
YAML_VALIDATOR_VERSION = "yaml_validator_v1"
HCL_FRAGMENT_VERIFIER_VERSION = "hcl_fragment_verifier_v1"
IAM_STRUCTURAL_VERIFIER_VERSION = "iam_structural_verifier_v1"
DEPENDENCY_MANIFEST_VERIFIER_VERSION = "dependency_manifest_verifier_v1"
SECURITY_STATIC_VERIFIER_VERSION = "security_static_verifier_v1"

# External adapters
TERRAFORM_VALIDATE_VERIFIER_VERSION = "terraform_validate_verifier_v1"
TERRAFORM_PLAN_VERIFIER_VERSION = "terraform_plan_verifier_v1"
ACTIONLINT_VERIFIER_VERSION = "actionlint_verifier_v1"
CHECKOV_VERIFIER_VERSION = "checkov_verifier_v1"
OPA_VERIFIER_VERSION = "opa_verifier_v1"
