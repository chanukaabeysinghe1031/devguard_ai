"""Deterministic multi-verifier consensus (no LLM)."""

from __future__ import annotations

from typing import Any

from app.ai.counterfactual_remediation.verification._helpers import (
    artifact_family,
    artifact_type_str,
    enum_str,
)
from app.domain.counterfactual_remediation.verification_enums import (
    VerificationConsensusStatus,
    VerifierResultStatus,
)
from app.domain.counterfactual_remediation.verification_models import (
    VerificationConsensus,
    VerifierResult,
)
from app.domain.counterfactual_remediation.verification_versions import CONSENSUS_ENGINE_VERSION


def _status(result: VerifierResult) -> str:
    return enum_str(result.status).upper()


class VerifierConsensusEngine:
    """
    Family-specific consensus rules.

    - Any blocking FAIL → not VERIFIED (FAILED)
    - Required tool UNAVAILABLE → INCONCLUSIVE or UNAVAILABLE (never VERIFIED)
    - Security FAIL → cannot VERIFIED
    - Mixed non-fail → PARTIALLY_VERIFIED
    """

    version = CONSENSUS_ENGINE_VERSION

    def evaluate(
        self,
        results: list[VerifierResult],
        *,
        candidate_id: str | None = None,
        artifact_type: str | None = None,
        candidate: Any = None,
    ) -> VerificationConsensus:
        if candidate is not None and not artifact_type:
            artifact_type = artifact_type_str(candidate)
        family = artifact_family((artifact_type or "").upper())

        by_name = {r.verifier_name: r for r in results}
        passed = [r.verifier_name for r in results if _status(r) == VerifierResultStatus.PASS.value]
        failed = [r.verifier_name for r in results if _status(r) == VerifierResultStatus.FAIL.value]
        warnings = [
            r.verifier_name for r in results if _status(r) == VerifierResultStatus.WARNING.value
        ]
        unavailable = [
            r.verifier_name for r in results if _status(r) == VerifierResultStatus.UNAVAILABLE.value
        ]

        # Security FAIL always blocks VERIFIED.
        security = by_name.get("security_static")
        if security is not None and _status(security) == VerifierResultStatus.FAIL.value:
            return VerificationConsensus(
                status=VerificationConsensusStatus.FAILED,
                candidate_id=candidate_id,
                artifact_family=family,
                required_verifiers=self._required_names(family),
                passed_verifiers=passed,
                failed_verifiers=failed,
                warning_verifiers=warnings,
                unavailable_verifiers=unavailable,
                rationale="security_static_fail_blocks_verified",
                blocking_failures=["security_static"],
            )

        if family == "terraform":
            return self._terraform(
                by_name, candidate_id, family, passed, failed, warnings, unavailable
            )
        if family == "workflow":
            return self._workflow(
                by_name, candidate_id, family, passed, failed, warnings, unavailable
            )
        if family == "iam":
            return self._iam(by_name, candidate_id, family, passed, failed, warnings, unavailable)
        if family == "dependency":
            return self._dependency(
                by_name, candidate_id, family, passed, failed, warnings, unavailable
            )
        return self._generic(by_name, candidate_id, family, passed, failed, warnings, unavailable)

    def _required_names(self, family: str) -> list[str]:
        if family == "terraform":
            return ["hcl_fragment", "terraform_validate"]
        if family == "workflow":
            return ["yaml_validator", "actionlint"]
        if family == "iam":
            return ["json_schema", "iam_structural"]
        if family == "dependency":
            return ["dependency_manifest"]
        return []

    def _terraform(
        self,
        by_name: dict[str, VerifierResult],
        candidate_id: str | None,
        family: str,
        passed: list[str],
        failed: list[str],
        warnings: list[str],
        unavailable: list[str],
    ) -> VerificationConsensus:
        required = self._required_names(family)
        validate = by_name.get("terraform_validate")
        plan = by_name.get("terraform_plan")
        checkov = by_name.get("checkov")
        hcl = by_name.get("hcl_fragment")

        blocking: list[str] = []
        if hcl and _status(hcl) == VerifierResultStatus.FAIL.value:
            blocking.append("hcl_fragment")
        if validate and _status(validate) == VerifierResultStatus.FAIL.value:
            blocking.append("terraform_validate")
        if plan and _status(plan) == VerifierResultStatus.FAIL.value:
            blocking.append("terraform_plan")
        if checkov and _status(checkov) == VerifierResultStatus.FAIL.value:
            blocking.append("checkov")
        if blocking or failed:
            return self._failed(
                candidate_id, family, required, passed, failed, warnings, unavailable, blocking
            )

        # validate PASS required for VERIFIED; plan PASS or WARNING; checkov PASS/WARNING if present
        validate_ok = validate is not None and _status(validate) == VerifierResultStatus.PASS.value
        if validate is not None and _status(validate) == VerifierResultStatus.UNAVAILABLE.value:
            return self._unavailable_or_inconclusive(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                rationale="terraform_validate_unavailable",
            )
        if not validate_ok:
            if validate is None:
                return self._inconclusive(
                    candidate_id,
                    family,
                    required,
                    passed,
                    failed,
                    warnings,
                    unavailable,
                    "terraform_validate_not_run",
                )
            return self._partial(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                "terraform_validate_not_pass",
            )

        plan_ok = True
        if plan is not None:
            plan_status = _status(plan)
            if plan_status == VerifierResultStatus.UNAVAILABLE.value:
                # Plan optional — UNAVAILABLE does not block VERIFIED if validate passed,
                # but marks PARTIALLY when it was selected as supportive.
                return self._partial(
                    candidate_id,
                    family,
                    required,
                    passed,
                    failed,
                    warnings,
                    unavailable,
                    "terraform_plan_unavailable",
                )
            plan_ok = plan_status in {
                VerifierResultStatus.PASS.value,
                VerifierResultStatus.WARNING.value,
            }
            if not plan_ok:
                return self._failed(
                    candidate_id,
                    family,
                    required,
                    passed,
                    failed,
                    warnings,
                    unavailable,
                    ["terraform_plan"],
                )

        if checkov is not None:
            ck = _status(checkov)
            if ck == VerifierResultStatus.UNAVAILABLE.value:
                return self._partial(
                    candidate_id,
                    family,
                    required,
                    passed,
                    failed,
                    warnings,
                    unavailable,
                    "checkov_unavailable",
                )
            if ck not in {
                VerifierResultStatus.PASS.value,
                VerifierResultStatus.WARNING.value,
            }:
                return self._failed(
                    candidate_id,
                    family,
                    required,
                    passed,
                    failed,
                    warnings,
                    unavailable,
                    ["checkov"],
                )

        hcl_ok = hcl is None or _status(hcl) in {
            VerifierResultStatus.PASS.value,
            VerifierResultStatus.WARNING.value,
        }
        if not hcl_ok:
            return self._partial(
                candidate_id, family, required, passed, failed, warnings, unavailable, "hcl_not_ok"
            )

        return VerificationConsensus(
            status=VerificationConsensusStatus.VERIFIED,
            candidate_id=candidate_id,
            artifact_family=family,
            required_verifiers=required,
            passed_verifiers=passed,
            failed_verifiers=failed,
            warning_verifiers=warnings,
            unavailable_verifiers=unavailable,
            rationale="terraform_validate_pass_with_supporting_checks",
        )

    def _workflow(
        self,
        by_name: dict[str, VerifierResult],
        candidate_id: str | None,
        family: str,
        passed: list[str],
        failed: list[str],
        warnings: list[str],
        unavailable: list[str],
    ) -> VerificationConsensus:
        required = self._required_names(family)
        yaml_v = by_name.get("yaml_validator")
        actionlint = by_name.get("actionlint")

        if failed:
            return self._failed(
                candidate_id, family, required, passed, failed, warnings, unavailable, list(failed)
            )

        yaml_pass = yaml_v is not None and _status(yaml_v) == VerifierResultStatus.PASS.value
        if yaml_v is not None and _status(yaml_v) == VerifierResultStatus.UNAVAILABLE.value:
            return self._unavailable_or_inconclusive(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                "yaml_validator_unavailable",
            )
        if not yaml_pass:
            return self._partial(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                "yaml_validator_not_pass",
            )

        if actionlint is None:
            return self._inconclusive(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                "actionlint_not_run",
            )
        al_status = _status(actionlint)
        if al_status == VerifierResultStatus.UNAVAILABLE.value:
            return self._inconclusive(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                "actionlint_unavailable",
            )
        if al_status != VerifierResultStatus.PASS.value:
            if al_status == VerifierResultStatus.FAIL.value:
                return self._failed(
                    candidate_id,
                    family,
                    required,
                    passed,
                    failed,
                    warnings,
                    unavailable,
                    ["actionlint"],
                )
            return self._partial(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                "actionlint_not_pass",
            )

        return VerificationConsensus(
            status=VerificationConsensusStatus.VERIFIED,
            candidate_id=candidate_id,
            artifact_family=family,
            required_verifiers=required,
            passed_verifiers=passed,
            failed_verifiers=failed,
            warning_verifiers=warnings,
            unavailable_verifiers=unavailable,
            rationale="workflow_yaml_and_actionlint_pass",
        )

    def _iam(
        self,
        by_name: dict[str, VerifierResult],
        candidate_id: str | None,
        family: str,
        passed: list[str],
        failed: list[str],
        warnings: list[str],
        unavailable: list[str],
    ) -> VerificationConsensus:
        required = self._required_names(family)
        json_v = by_name.get("json_schema")
        iam = by_name.get("iam_structural")
        opa = by_name.get("opa")

        if failed:
            return self._failed(
                candidate_id, family, required, passed, failed, warnings, unavailable, list(failed)
            )

        json_ok = json_v is not None and _status(json_v) == VerifierResultStatus.PASS.value
        iam_ok = iam is not None and _status(iam) == VerifierResultStatus.PASS.value
        for name, result, ok in (
            ("json_schema", json_v, json_ok),
            ("iam_structural", iam, iam_ok),
        ):
            if result is not None and _status(result) == VerifierResultStatus.UNAVAILABLE.value:
                return self._unavailable_or_inconclusive(
                    candidate_id,
                    family,
                    required,
                    passed,
                    failed,
                    warnings,
                    unavailable,
                    f"{name}_unavailable",
                )
            if not ok:
                return self._partial(
                    candidate_id,
                    family,
                    required,
                    passed,
                    failed,
                    warnings,
                    unavailable,
                    f"{name}_not_pass",
                )

        if opa is not None:
            opa_status = _status(opa)
            if opa_status == VerifierResultStatus.UNAVAILABLE.value:
                # OPA enabled but no policy/binary — cannot claim VERIFIED.
                return self._inconclusive(
                    candidate_id,
                    family,
                    required,
                    passed,
                    failed,
                    warnings,
                    unavailable,
                    "opa_unavailable",
                )
            if opa_status == VerifierResultStatus.FAIL.value:
                return self._failed(
                    candidate_id, family, required, passed, failed, warnings, unavailable, ["opa"]
                )
            if opa_status not in {
                VerifierResultStatus.PASS.value,
                VerifierResultStatus.WARNING.value,
            }:
                return self._partial(
                    candidate_id,
                    family,
                    required,
                    passed,
                    failed,
                    warnings,
                    unavailable,
                    "opa_not_pass",
                )

        return VerificationConsensus(
            status=VerificationConsensusStatus.VERIFIED,
            candidate_id=candidate_id,
            artifact_family=family,
            required_verifiers=required,
            passed_verifiers=passed,
            failed_verifiers=failed,
            warning_verifiers=warnings,
            unavailable_verifiers=unavailable,
            rationale="iam_json_and_structural_pass",
        )

    def _dependency(
        self,
        by_name: dict[str, VerifierResult],
        candidate_id: str | None,
        family: str,
        passed: list[str],
        failed: list[str],
        warnings: list[str],
        unavailable: list[str],
    ) -> VerificationConsensus:
        required = self._required_names(family)
        manifest = by_name.get("dependency_manifest")
        if failed:
            return self._failed(
                candidate_id, family, required, passed, failed, warnings, unavailable, list(failed)
            )
        if manifest is None:
            return self._inconclusive(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                "dependency_manifest_not_run",
            )
        status = _status(manifest)
        if status == VerifierResultStatus.UNAVAILABLE.value:
            return self._unavailable_or_inconclusive(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                "dependency_manifest_unavailable",
            )
        if status == VerifierResultStatus.PASS.value:
            return VerificationConsensus(
                status=VerificationConsensusStatus.VERIFIED,
                candidate_id=candidate_id,
                artifact_family=family,
                required_verifiers=required,
                passed_verifiers=passed,
                failed_verifiers=failed,
                warning_verifiers=warnings,
                unavailable_verifiers=unavailable,
                rationale="dependency_manifest_pass",
            )
        if status == VerifierResultStatus.WARNING.value:
            return self._partial(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                "dependency_manifest_warning",
            )
        return self._failed(
            candidate_id,
            family,
            required,
            passed,
            failed,
            warnings,
            unavailable,
            ["dependency_manifest"],
        )

    def _generic(
        self,
        by_name: dict[str, VerifierResult],
        candidate_id: str | None,
        family: str,
        passed: list[str],
        failed: list[str],
        warnings: list[str],
        unavailable: list[str],
    ) -> VerificationConsensus:
        required = list(by_name.keys())
        if failed:
            return self._failed(
                candidate_id, family, required, passed, failed, warnings, unavailable, list(failed)
            )
        if unavailable and not passed:
            return self._unavailable_or_inconclusive(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                "all_or_required_unavailable",
            )
        if passed and not unavailable and not warnings:
            return VerificationConsensus(
                status=VerificationConsensusStatus.VERIFIED,
                candidate_id=candidate_id,
                artifact_family=family,
                required_verifiers=required,
                passed_verifiers=passed,
                failed_verifiers=failed,
                warning_verifiers=warnings,
                unavailable_verifiers=unavailable,
                rationale="all_selected_verifiers_pass",
            )
        if passed or warnings:
            return self._partial(
                candidate_id,
                family,
                required,
                passed,
                failed,
                warnings,
                unavailable,
                "mixed_or_partial_results",
            )
        return self._inconclusive(
            candidate_id,
            family,
            required,
            passed,
            failed,
            warnings,
            unavailable,
            "no_decisive_results",
        )

    @staticmethod
    def _failed(
        candidate_id: str | None,
        family: str,
        required: list[str],
        passed: list[str],
        failed: list[str],
        warnings: list[str],
        unavailable: list[str],
        blocking: list[str],
    ) -> VerificationConsensus:
        return VerificationConsensus(
            status=VerificationConsensusStatus.FAILED,
            candidate_id=candidate_id,
            artifact_family=family,
            required_verifiers=required,
            passed_verifiers=passed,
            failed_verifiers=failed,
            warning_verifiers=warnings,
            unavailable_verifiers=unavailable,
            rationale="blocking_verifier_fail",
            blocking_failures=list(blocking),
        )

    @staticmethod
    def _partial(
        candidate_id: str | None,
        family: str,
        required: list[str],
        passed: list[str],
        failed: list[str],
        warnings: list[str],
        unavailable: list[str],
        rationale: str,
    ) -> VerificationConsensus:
        return VerificationConsensus(
            status=VerificationConsensusStatus.PARTIALLY_VERIFIED,
            candidate_id=candidate_id,
            artifact_family=family,
            required_verifiers=required,
            passed_verifiers=passed,
            failed_verifiers=failed,
            warning_verifiers=warnings,
            unavailable_verifiers=unavailable,
            rationale=rationale,
        )

    @staticmethod
    def _inconclusive(
        candidate_id: str | None,
        family: str,
        required: list[str],
        passed: list[str],
        failed: list[str],
        warnings: list[str],
        unavailable: list[str],
        rationale: str,
    ) -> VerificationConsensus:
        return VerificationConsensus(
            status=VerificationConsensusStatus.INCONCLUSIVE,
            candidate_id=candidate_id,
            artifact_family=family,
            required_verifiers=required,
            passed_verifiers=passed,
            failed_verifiers=failed,
            warning_verifiers=warnings,
            unavailable_verifiers=unavailable,
            rationale=rationale,
        )

    @staticmethod
    def _unavailable_or_inconclusive(
        candidate_id: str | None,
        family: str,
        required: list[str],
        passed: list[str],
        failed: list[str],
        warnings: list[str],
        unavailable: list[str],
        rationale: str,
    ) -> VerificationConsensus:
        # Prefer UNAVAILABLE when no PASS exists; else INCONCLUSIVE.
        status = (
            VerificationConsensusStatus.UNAVAILABLE
            if not passed
            else VerificationConsensusStatus.INCONCLUSIVE
        )
        return VerificationConsensus(
            status=status,
            candidate_id=candidate_id,
            artifact_family=family,
            required_verifiers=required,
            passed_verifiers=passed,
            failed_verifiers=failed,
            warning_verifiers=warnings,
            unavailable_verifiers=unavailable,
            rationale=rationale,
        )


def compute_consensus(
    results: list[VerifierResult],
    *,
    candidate: Any = None,
    candidate_id: str | None = None,
    artifact_type: str | None = None,
) -> VerificationConsensus:
    """Module-level convenience wrapper around VerifierConsensusEngine."""
    return VerifierConsensusEngine().evaluate(
        results,
        candidate=candidate,
        candidate_id=candidate_id,
        artifact_type=artifact_type,
    )
