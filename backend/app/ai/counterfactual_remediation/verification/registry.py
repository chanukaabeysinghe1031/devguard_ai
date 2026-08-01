"""Select verifier adapters by candidate artifact type and feature flags."""

from __future__ import annotations

from typing import Any

from app.ai.counterfactual_remediation.verification.actionlint import ActionlintVerifier
from app.ai.counterfactual_remediation.verification.base import Verifier
from app.ai.counterfactual_remediation.verification.checkov import CheckovVerifier
from app.ai.counterfactual_remediation.verification.dependency_manifest import (
    DependencyManifestVerifier,
)
from app.ai.counterfactual_remediation.verification.hcl_fragment import HclFragmentVerifier
from app.ai.counterfactual_remediation.verification.iam_structural import IamStructuralVerifier
from app.ai.counterfactual_remediation.verification.json_schema import JsonSchemaVerifier
from app.ai.counterfactual_remediation.verification.opa import OpaVerifier
from app.ai.counterfactual_remediation.verification.security_static import SecurityStaticVerifier
from app.ai.counterfactual_remediation.verification.terraform_plan import TerraformPlanVerifier
from app.ai.counterfactual_remediation.verification.terraform_validate import (
    TerraformValidateVerifier,
)
from app.ai.counterfactual_remediation.verification.yaml_validator import YamlValidatorVerifier
from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate


class VerifierRegistry:
    """Builds and filters verifier adapters for a candidate."""

    def __init__(
        self,
        settings: Any = None,
        *,
        verifiers: list[Verifier] | None = None,
        opa_policy_path: str | None = None,
    ) -> None:
        self._settings = settings
        if verifiers is not None:
            self._verifiers = list(verifiers)
        else:
            self._verifiers = self._default_adapters(settings, opa_policy_path=opa_policy_path)

    @staticmethod
    def _default_adapters(
        settings: Any,
        *,
        opa_policy_path: str | None = None,
    ) -> list[Verifier]:
        return [
            JsonSchemaVerifier(),
            YamlValidatorVerifier(),
            HclFragmentVerifier(),
            IamStructuralVerifier(),
            DependencyManifestVerifier(),
            SecurityStaticVerifier.from_settings(settings),
            TerraformValidateVerifier.from_settings(settings),
            TerraformPlanVerifier.from_settings(settings),
            ActionlintVerifier.from_settings(settings),
            CheckovVerifier.from_settings(settings),
            OpaVerifier.from_settings(settings, policy_path=opa_policy_path),
        ]

    def all_verifiers(self) -> list[Verifier]:
        return list(self._verifiers)

    def select(
        self,
        candidate: CounterfactualRemediationCandidate | Any,
    ) -> list[Verifier]:
        selected: list[Verifier] = []
        for verifier in self._verifiers:
            try:
                if verifier.supports(candidate):
                    selected.append(verifier)
            except Exception:  # noqa: BLE001 — soft-fail selection
                continue
        return selected

    def health(self) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        for verifier in self._verifiers:
            try:
                if hasattr(verifier, "health"):
                    reports.append(verifier.health())
                else:
                    reports.append(
                        {
                            "name": getattr(verifier, "name", "unknown"),
                            "available": verifier.is_available(),
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                reports.append(
                    {
                        "name": getattr(verifier, "name", "unknown"),
                        "available": False,
                        "error": type(exc).__name__,
                    }
                )
        return reports


def build_default_registry(
    settings: Any = None,
    *,
    opa_policy_path: str | None = None,
) -> VerifierRegistry:
    return VerifierRegistry(settings, opa_policy_path=opa_policy_path)
