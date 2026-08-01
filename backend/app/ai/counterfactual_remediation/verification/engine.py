"""Independent verifier engine / counterfactual verifier service (Part 3)."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Sequence

from app.ai.counterfactual_remediation.verification._helpers import (
    bound_float,
    bound_int,
    candidate_ready_for_verification,
    enum_str,
    flag,
)
from app.ai.counterfactual_remediation.verification.actionlint import ActionlintVerifier
from app.ai.counterfactual_remediation.verification.base import BaseVerifier
from app.ai.counterfactual_remediation.verification.checkov import CheckovVerifier
from app.ai.counterfactual_remediation.verification.consensus import (
    VerifierConsensusEngine,
)
from app.ai.counterfactual_remediation.verification.dependency_manifest import (
    DependencyManifestVerifier,
)
from app.ai.counterfactual_remediation.verification.hcl_fragment import HclFragmentVerifier
from app.ai.counterfactual_remediation.verification.iam_structural import IamStructuralVerifier
from app.ai.counterfactual_remediation.verification.json_schema import JsonSchemaVerifier
from app.ai.counterfactual_remediation.verification.opa import OpaVerifier
from app.ai.counterfactual_remediation.verification.persist import (
    NoOpVerificationPersistService,
    VerificationPersistService,
)
from app.ai.counterfactual_remediation.verification.registry import VerifierRegistry
from app.ai.counterfactual_remediation.verification.runner import VerifierRunner
from app.ai.counterfactual_remediation.verification.security_static import SecurityStaticVerifier
from app.ai.counterfactual_remediation.verification.terraform_plan import TerraformPlanVerifier
from app.ai.counterfactual_remediation.verification.terraform_validate import (
    TerraformValidateVerifier,
)
from app.ai.counterfactual_remediation.verification.yaml_validator import YamlValidatorVerifier
from app.domain.counterfactual_remediation.enums import CounterfactualCandidateStatus
from app.domain.counterfactual_remediation.generation_enums import CandidatePriorityStatus
from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate
from app.domain.counterfactual_remediation.verification_enums import (
    VerificationConsensusStatus,
    VerificationRunStatus,
)
from app.domain.counterfactual_remediation.verification_models import (
    VerificationReport,
    VerificationRun,
)
from app.domain.counterfactual_remediation.verification_versions import VERIFIER_ENGINE_VERSION

logger = logging.getLogger(__name__)

_PRIORITY_ORDER = {
    CandidatePriorityStatus.PRIORITY_CANDIDATE.value: 0,
    CandidatePriorityStatus.ALTERNATIVE_CANDIDATE.value: 1,
    CandidatePriorityStatus.HIGH_RISK_CANDIDATE.value: 2,
    CandidatePriorityStatus.INCOMPLETE_CANDIDATE.value: 3,
    CandidatePriorityStatus.REJECTED_CANDIDATE.value: 4,
    CandidatePriorityStatus.NO_SAFE_CANDIDATE.value: 5,
}


def _default_adapters(settings: Any | None) -> list[BaseVerifier]:
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
        OpaVerifier.from_settings(settings),
    ]


class IndependentVerifierEngine:
    """
    Flag-gated independent verifier engine.

    Soft-fail. Never applies patches to the repo. LLMs are not verifiers.
    """

    version = VERIFIER_ENGINE_VERSION

    def __init__(
        self,
        settings: Any | None = None,
        *,
        adapters: Sequence[BaseVerifier] | None = None,
        registry: VerifierRegistry | None = None,
        runner: VerifierRunner | None = None,
        consensus: VerifierConsensusEngine | None = None,
        persist: VerificationPersistService | None = None,
        persist_service: Any | None = None,
        verify_rollback: bool = True,
    ) -> None:
        self._settings = settings
        self._enabled = flag(settings, "verifier_engine_enabled", False)
        self._max_candidates = bound_int(settings, "max_candidates_for_verification", 5)
        self._verify_rollback = verify_rollback
        adapter_list = list(adapters) if adapters is not None else _default_adapters(settings)
        self._adapters = adapter_list
        self._registry = registry or VerifierRegistry(settings, verifiers=list(adapter_list))
        self._consensus = consensus or VerifierConsensusEngine()
        self._runner = runner or VerifierRunner(
            registry=self._registry,
            consensus=self._consensus,
            max_files=bound_int(settings, "max_temp_workspace_files", 20),
            max_bytes=bound_int(settings, "max_temp_workspace_bytes", 5_000_000),
            stage_timeout_seconds=bound_float(
                settings, "max_verifier_stage_timeout_seconds", 180.0
            ),
        )
        self._persist = persist or persist_service or NoOpVerificationPersistService()

    def is_enabled(self) -> bool:
        return self._enabled

    # Alias used by some draft callers.
    enabled = is_enabled

    def select_candidates(
        self,
        candidates: Sequence[CounterfactualRemediationCandidate | Any],
        *,
        limit: int | None = None,
    ) -> list[CounterfactualRemediationCandidate | Any]:
        max_n = limit if limit is not None else self._max_candidates
        eligible = [c for c in candidates if candidate_ready_for_verification(c)]
        eligible.sort(key=self._sort_key)
        return eligible[: max(0, max_n)]

    @staticmethod
    def _sort_key(candidate: Any) -> tuple[int, float, str]:
        priority = enum_str(getattr(candidate, "priority_status", None))
        rank = _PRIORITY_ORDER.get(priority, 50)
        score = getattr(candidate, "priority_score", None)
        try:
            score_f = -float(score) if score is not None else 0.0
        except (TypeError, ValueError):
            score_f = 0.0
        return (rank, score_f, str(getattr(candidate, "id", "")))

    def verify_candidate(
        self,
        candidate: CounterfactualRemediationCandidate | Any,
        *,
        remediation_run_id: str | None = None,
    ) -> VerificationRun:
        run = self._runner.run_candidate(
            candidate,
            organization_id=getattr(candidate, "organization_id", None),
            project_id=getattr(candidate, "project_id", None),
            incident_id=getattr(candidate, "incident_id", None),
            analysis_id=getattr(candidate, "analysis_id", None),
            remediation_run_id=remediation_run_id
            or getattr(candidate, "remediation_run_id", None),
        )
        if self._verify_rollback:
            run.rollback_parse_status = self._check_rollback_parse(candidate)
            if run.rollback_parse_status == "FAIL":
                run.warnings.append("rollback_fragment_parse_failed")
        self._annotate_candidate(candidate, run)
        return run

    def verify_candidates(
        self,
        candidates: Sequence[CounterfactualRemediationCandidate | Any],
        *,
        organization_id: str = "",
        project_id: str = "",
        incident_id: str = "",
        analysis_id: str = "",
        remediation_run_id: str | None = None,
    ) -> VerificationReport:
        return self.run(
            organization_id=organization_id,
            project_id=project_id,
            incident_id=incident_id,
            analysis_id=analysis_id,
            candidates=candidates,
            remediation_run_id=remediation_run_id,
        )

    def run(
        self,
        *,
        organization_id: str,
        project_id: str,
        incident_id: str,
        analysis_id: str,
        candidates: Sequence[CounterfactualRemediationCandidate | Any],
        remediation_run_id: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> VerificationReport:
        del options  # clients cannot force verifier flags ON
        started = time.perf_counter()
        report = VerificationReport(
            organization_id=organization_id,
            project_id=project_id,
            incident_id=incident_id,
            analysis_id=analysis_id,
            remediation_run_id=remediation_run_id,
            status=VerificationRunStatus.RUNNING,
            engine_version=self.version,
        )

        if not self._enabled:
            report.status = VerificationRunStatus.DISABLED
            report.warnings.append("verifier_engine_disabled")
            report.completed_at = datetime.now(UTC)
            return report

        stage_timeout = bound_float(
            self._settings, "max_verifier_stage_timeout_seconds", 180.0
        )
        selected = self.select_candidates(candidates)
        report.candidate_ids_selected = [
            str(getattr(c, "id", "")) for c in selected if getattr(c, "id", None)
        ]

        if not selected:
            report.status = VerificationRunStatus.PARTIAL
            report.warnings.append("no_eligible_candidates")
            report.completed_at = datetime.now(UTC)
            return report

        timed_out = False
        for candidate in selected:
            if (time.perf_counter() - started) > stage_timeout:
                timed_out = True
                report.warnings.append("verifier_stage_timeout")
                break
            try:
                run = self.verify_candidate(
                    candidate,
                    remediation_run_id=remediation_run_id,
                )
                report.runs.append(run)
                self._bucket_candidate(report, run)
            except Exception as exc:  # noqa: BLE001 — soft-fail per candidate
                logger.exception(
                    "verifier engine soft-fail for candidate %s",
                    getattr(candidate, "id", None),
                )
                report.warnings.append(
                    f"candidate_soft_fail:{getattr(candidate, 'id', None)}:{type(exc).__name__}"
                )

        if timed_out:
            report.status = VerificationRunStatus.TIMED_OUT
        elif not report.runs:
            report.status = VerificationRunStatus.FAILED
        elif any(
            enum_str(r.status) == VerificationRunStatus.FAILED.value for r in report.runs
        ):
            report.status = VerificationRunStatus.PARTIAL
        else:
            report.status = VerificationRunStatus.COMPLETE

        report.completed_at = datetime.now(UTC)
        try:
            self._persist.save_report(report)
        except Exception:  # noqa: BLE001
            logger.warning("verification persist soft-fail")
        return report

    async def run_async(self, **kwargs: Any) -> VerificationReport:
        report = self.run(**kwargs)
        persist = self._persist
        if persist is not None and flag(self._settings, "verifier_persistence_enabled", False):
            try:
                if hasattr(persist, "persist_report"):
                    await persist.persist_report(report)
                else:
                    persist.save_report(report)
            except Exception as exc:  # noqa: BLE001
                logger.warning("verifier_persist_failed: %s", type(exc).__name__)
                report.warnings.append(f"persist_failed:{type(exc).__name__}")
        return report

    @staticmethod
    def _bucket_candidate(report: VerificationReport, run: VerificationRun) -> None:
        cid = run.candidate_id
        if not cid:
            return
        consensus = run.consensus
        status = enum_str(getattr(consensus, "status", None)) if consensus else ""
        if status == VerificationConsensusStatus.VERIFIED.value:
            report.candidate_ids_verified.append(cid)
        elif status == VerificationConsensusStatus.FAILED.value:
            report.candidate_ids_failed.append(cid)
        else:
            report.candidate_ids_inconclusive.append(cid)

    @staticmethod
    def _annotate_candidate(
        candidate: CounterfactualRemediationCandidate | Any,
        run: VerificationRun,
    ) -> None:
        """Store consensus on string fields; do not add VERIFIED to Part 1 enum."""
        consensus = run.consensus
        if consensus is None:
            return
        status = enum_str(consensus.status)
        try:
            candidate.validation_status = status
        except Exception:  # noqa: BLE001
            pass
        current = enum_str(getattr(candidate, "status", None))
        if current == CounterfactualCandidateStatus.READY_FOR_VERIFICATION.value:
            pass
        provenance = getattr(candidate, "generation_provenance", None)
        if isinstance(provenance, dict):
            provenance["verification_consensus"] = status
            provenance["verification_run_id"] = run.id
            provenance["verification_rationale"] = consensus.rationale

    def _check_rollback_parse(self, candidate: Any) -> str:
        plan = getattr(candidate, "rollback_plan", None)
        if plan is None:
            return "SKIPPED"
        steps: list[Any] = []
        if isinstance(plan, dict):
            steps = list(plan.get("rollback_steps") or [])
        else:
            steps = list(getattr(plan, "rollback_steps", None) or [])
        if not steps:
            for change in getattr(candidate, "changes", None) or []:
                original = (
                    change.get("original_fragment")
                    if isinstance(change, dict)
                    else getattr(change, "original_fragment", None)
                )
                if isinstance(original, str) and original.strip():
                    return self._parse_fragment(original)
            return "SKIPPED"
        for step in steps:
            if not isinstance(step, dict):
                continue
            frag = step.get("original_fragment") or step.get("content") or step.get("fragment")
            if isinstance(frag, str) and frag.strip():
                if self._parse_fragment(frag) == "FAIL":
                    return "FAIL"
        return "PASS"

    @staticmethod
    def _parse_fragment(text: str) -> str:
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                json.loads(text)
                return "PASS"
            except json.JSONDecodeError:
                return "FAIL"
        if stripped.startswith("---") or ":" in stripped.split("\n", 1)[0]:
            try:
                import yaml

                yaml.safe_load(text)
                return "PASS"
            except Exception:  # noqa: BLE001
                if text.count("{") == text.count("}"):
                    return "PASS"
                return "FAIL"
        if text.count("{") == text.count("}"):
            return "PASS"
        return "FAIL"


def build_summary(report: VerificationReport) -> dict[str, Any]:
    """Compact summary for context.options — never overwrites recommendations."""
    return {
        "status": enum_str(report.status),
        "engine_version": report.engine_version,
        "candidate_ids_selected": list(report.candidate_ids_selected),
        "candidate_ids_verified": list(report.candidate_ids_verified),
        "candidate_ids_failed": list(report.candidate_ids_failed),
        "candidate_ids_inconclusive": list(report.candidate_ids_inconclusive),
        "run_count": len(report.runs),
        "runs": [
            {
                "id": r.id,
                "candidate_id": r.candidate_id,
                "status": enum_str(r.status),
                "consensus_status": enum_str(r.consensus.status) if r.consensus else None,
                "selected_verifiers": list(r.selected_verifiers),
                "duration_ms": r.duration_ms,
                "warnings": list(r.warnings),
            }
            for r in report.runs
        ],
        "warnings": list(report.warnings),
        "limitations": list(report.limitations),
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
    }


# Alias requested by the Part 3 contract.
CounterfactualVerifierService = IndependentVerifierEngine
