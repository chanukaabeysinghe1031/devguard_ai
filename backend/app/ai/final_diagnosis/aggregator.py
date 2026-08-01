"""Aggregate per-candidate verifier results into a support level."""

from __future__ import annotations

from typing import Any

from app.ai.final_diagnosis.inputs import RemediationCandidateSnapshot, as_str
from app.domain.counterfactual_remediation.verification_enums import (
    VerificationConsensusStatus,
    VerifierResultStatus,
)
from app.domain.final_diagnosis.enums import VerifierSupportLevel
from app.domain.final_diagnosis.models import VerifierAggregationResult

_CORE_STRUCTURAL = {
    "json_schema",
    "yaml_validator",
    "hcl_fragment",
    "iam_structural",
    "dependency_manifest",
    "terraform_validate",
    "actionlint",
}

_BLOCKING_SECURITY = {"security_static"}


class VerifierResultAggregator:
    """Deterministic verifier aggregation. Never maps UNAVAILABLE → PASS."""

    def aggregate(
        self,
        candidate: RemediationCandidateSnapshot | None,
        *,
        required_verifiers: list[str] | None = None,
        consensus_status: str | None = None,
    ) -> VerifierAggregationResult:
        if candidate is None:
            return VerifierAggregationResult(
                support_level=VerifierSupportLevel.UNAVAILABLE,
                summary="no_candidate",
                limitations=[
                    "verifier_support_is_not_applied_remediation",
                    "unavailable_never_counts_as_pass",
                    "no_candidate_for_aggregation",
                ],
            )

        required = list(required_verifiers or candidate.required_verifiers or [])
        results = list(candidate.verifier_results or [])
        by_name: dict[str, Any] = {}
        for row in results:
            name = as_str(row.get("verifier_name") or row.get("tool") or row.get("name"))
            if name:
                by_name[name] = row

        if not required and results:
            required = list(by_name.keys())

        check_names = required or list(by_name.keys())
        passed: list[str] = []
        failed: list[str] = []
        unavailable: list[str] = []
        warning_names: list[str] = []
        warnings: list[str] = []

        for name in check_names:
            raw_row = by_name.get(name)
            result_row: dict[str, Any] = raw_row if isinstance(raw_row, dict) else {}
            status = as_str(
                result_row.get("status") or VerifierResultStatus.UNAVAILABLE.value
            ).upper()
            if status == VerifierResultStatus.PASS.value:
                passed.append(name)
            elif status == VerifierResultStatus.FAIL.value:
                failed.append(name)
            elif status == VerifierResultStatus.WARNING.value:
                warning_names.append(name)
                warnings.append(f"{name}:WARNING")
            elif status == VerifierResultStatus.UNAVAILABLE.value:
                unavailable.append(name)
            else:
                unavailable.append(name)

        for name, extra_row in by_name.items():
            if name in check_names:
                continue
            status = as_str(extra_row.get("status")).upper()
            if status == VerifierResultStatus.WARNING.value:
                warning_names.append(name)
                warnings.append(f"{name}:WARNING")
            elif status == VerifierResultStatus.FAIL.value and name in _BLOCKING_SECURITY:
                failed.append(name)

        consensus = as_str(consensus_status or candidate.consensus_status).upper() or None
        blocking = bool(failed) or consensus == VerificationConsensusStatus.FAILED.value
        for name in failed:
            if name in _BLOCKING_SECURITY:
                blocking = True

        support = self._support_level(
            required=set(required) if required else set(check_names),
            passed=set(passed) | set(warning_names),
            pure_pass=set(passed),
            failed=set(failed),
            unavailable=set(unavailable),
            warning_count=len(warning_names),
            by_name=by_name,
            blocking=blocking,
            consensus=consensus,
        )

        return VerifierAggregationResult(
            candidate_id=candidate.candidate_id,
            required_count=len(check_names),
            passed_count=len(passed),
            failed_count=len(failed),
            unavailable_count=len(unavailable),
            warning_count=len(warning_names),
            support_level=support,
            blocking_failure=blocking,
            consensus_status=consensus,
            summary=f"support={support.value};consensus={consensus or 'none'}",
            warnings=warnings,
            unavailable_tools=unavailable,
            failed_tools=failed,
        )

    def _support_level(
        self,
        *,
        required: set[str],
        passed: set[str],
        pure_pass: set[str],
        failed: set[str],
        unavailable: set[str],
        warning_count: int,
        by_name: dict[str, Any],
        blocking: bool,
        consensus: str | None,
    ) -> VerifierSupportLevel:
        if not by_name and not required:
            return VerifierSupportLevel.UNAVAILABLE
        if blocking or failed:
            return VerifierSupportLevel.NONE
        if not by_name or (required and unavailable == required):
            return VerifierSupportLevel.UNAVAILABLE
        if consensus == VerificationConsensusStatus.UNAVAILABLE.value:
            return VerifierSupportLevel.UNAVAILABLE
        if consensus == VerificationConsensusStatus.FAILED.value:
            return VerifierSupportLevel.NONE

        all_required_executed_ok = required.issubset(passed) and not unavailable.intersection(
            required
        )
        core = required.intersection(_CORE_STRUCTURAL) or set(required)
        core_pass = core.issubset(passed)

        if (
            all_required_executed_ok
            and warning_count == 0
            and required.issubset(pure_pass)
            and consensus
            in {
                VerificationConsensusStatus.VERIFIED.value,
                None,
                "",
            }
        ):
            return VerifierSupportLevel.STRONG
        if all_required_executed_ok and warning_count == 0 and required.issubset(pure_pass):
            return VerifierSupportLevel.STRONG
        if (
            consensus == VerificationConsensusStatus.VERIFIED.value
            and not unavailable.intersection(required)
            and warning_count == 0
        ):
            return VerifierSupportLevel.STRONG
        if core_pass and unavailable and not failed:
            return VerifierSupportLevel.MODERATE
        if consensus == VerificationConsensusStatus.PARTIALLY_VERIFIED.value and not failed:
            return VerifierSupportLevel.MODERATE
        if core_pass and warning_count > 0:
            return VerifierSupportLevel.MODERATE
        if not failed and (pure_pass or warning_count):
            return VerifierSupportLevel.WEAK
        return VerifierSupportLevel.WEAK
