"""Per-candidate verifier pipeline: workspace → adapters → consensus → cleanup."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.ai.counterfactual_remediation.verification.base import Verifier
from app.ai.counterfactual_remediation.verification.consensus import VerifierConsensusEngine
from app.ai.counterfactual_remediation.verification.registry import VerifierRegistry
from app.ai.counterfactual_remediation.verification.workspace import (
    TempWorkspaceError,
    TempWorkspaceManager,
)
from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate
from app.domain.counterfactual_remediation.verification_enums import (
    VerificationRunStatus,
    VerifierResultStatus,
)
from app.domain.counterfactual_remediation.verification_models import (
    VerificationRun,
    VerifierResult,
)
from app.domain.counterfactual_remediation.verification_versions import VERIFIER_ENGINE_VERSION

logger = logging.getLogger(__name__)


class VerifierRunner:
    """Prepare temp workspace, run selected verifiers, collect results, always cleanup."""

    def __init__(
        self,
        *,
        registry: VerifierRegistry | None = None,
        consensus: VerifierConsensusEngine | None = None,
        max_files: int = 20,
        max_bytes: int = 5_000_000,
        stage_timeout_seconds: float = 180.0,
    ) -> None:
        self._registry = registry or VerifierRegistry()
        self._consensus = consensus or VerifierConsensusEngine()
        self._max_files = max_files
        self._max_bytes = max_bytes
        self._stage_timeout = stage_timeout_seconds

    def run_candidate(
        self,
        candidate: CounterfactualRemediationCandidate | Any,
        *,
        organization_id: str | None = None,
        project_id: str | None = None,
        incident_id: str | None = None,
        analysis_id: str | None = None,
        remediation_run_id: str | None = None,
    ) -> VerificationRun:
        started = time.perf_counter()
        run = VerificationRun(
            id=str(uuid.uuid4()),
            organization_id=organization_id or getattr(candidate, "organization_id", "") or "",
            project_id=project_id or getattr(candidate, "project_id", "") or "",
            incident_id=incident_id or getattr(candidate, "incident_id", "") or "",
            analysis_id=analysis_id or getattr(candidate, "analysis_id", "") or "",
            remediation_run_id=remediation_run_id or getattr(candidate, "remediation_run_id", None),
            candidate_id=getattr(candidate, "id", None),
            hypothesis_id=getattr(candidate, "hypothesis_id", None),
            status=VerificationRunStatus.RUNNING,
            engine_version=VERIFIER_ENGINE_VERSION,
        )

        workspace = TempWorkspaceManager(
            max_files=self._max_files,
            max_bytes=self._max_bytes,
        )
        results: list[VerifierResult] = []
        selected: list[Verifier] = []

        try:
            selected = self._registry.select(candidate)
            run.selected_verifiers = [getattr(v, "name", "unknown") for v in selected]
            if not selected:
                run.status = VerificationRunStatus.PARTIAL
                run.warnings.append("no_verifiers_selected")
                run.consensus = self._consensus.evaluate(
                    [],
                    candidate_id=run.candidate_id,
                    candidate=candidate,
                )
                return run

            root = workspace.create()
            run.workspace_root = str(root)
            try:
                workspace.materialize_candidate(candidate, apply_proposed=True)
            except TempWorkspaceError as exc:
                run.status = VerificationRunStatus.FAILED
                run.error_message = f"workspace_error:{exc}"
                run.warnings.extend(workspace.warnings)
                return run

            run.warnings.extend(workspace.warnings)

            for verifier in selected:
                if (time.perf_counter() - started) > self._stage_timeout:
                    run.status = VerificationRunStatus.TIMED_OUT
                    run.warnings.append("stage_timeout_before_all_verifiers")
                    results.append(
                        VerifierResult(
                            verifier_name=getattr(verifier, "name", "unknown"),
                            verifier_version=getattr(verifier, "version", ""),
                            status=VerifierResultStatus.UNAVAILABLE,
                            candidate_id=run.candidate_id,
                            message="stage_timeout_skipped",
                        )
                    )
                    continue
                results.append(self._execute_one(verifier, workspace, candidate))

            run.results = results
            run.consensus = self._consensus.evaluate(
                results,
                candidate_id=run.candidate_id,
                candidate=candidate,
            )
            if run.status == VerificationRunStatus.TIMED_OUT:
                pass
            elif any(
                str(getattr(r.status, "value", r.status)) == VerifierResultStatus.FAIL.value
                for r in results
            ):
                run.status = VerificationRunStatus.COMPLETE
            else:
                run.status = VerificationRunStatus.COMPLETE
        except Exception as exc:  # noqa: BLE001 — soft-fail
            logger.exception("verifier runner soft-fail for candidate %s", run.candidate_id)
            run.status = VerificationRunStatus.FAILED
            run.error_message = type(exc).__name__
            run.results = results
        finally:
            import contextlib

            for verifier in selected:
                with contextlib.suppress(Exception):
                    verifier.cleanup()
            workspace.cleanup()
            # Never leave a live temp path reference after cleanup.
            run.workspace_root = None
            run.duration_ms = (time.perf_counter() - started) * 1000.0
            run.completed_at = datetime.now(UTC)

        return run

    def _execute_one(
        self,
        verifier: Verifier,
        workspace: TempWorkspaceManager,
        candidate: Any,
    ) -> VerifierResult:
        name = getattr(verifier, "name", "unknown")
        version = getattr(verifier, "version", "")
        try:
            if not verifier.is_available():
                return VerifierResult(
                    verifier_name=name,
                    verifier_version=version,
                    status=VerifierResultStatus.UNAVAILABLE,
                    candidate_id=getattr(candidate, "id", None),
                    required=bool(getattr(verifier, "required", True)),
                    message="verifier_unavailable",
                    findings=["unavailable_before_execute"],
                )
            verifier.prepare(workspace, candidate)
            result = verifier.execute(workspace, candidate)
            if result is None:
                return VerifierResult(
                    verifier_name=name,
                    verifier_version=version,
                    status=VerifierResultStatus.UNKNOWN,
                    candidate_id=getattr(candidate, "id", None),
                    message="empty_result",
                )
            return result
        except Exception as exc:  # noqa: BLE001 — soft-fail per adapter
            logger.warning("verifier %s failed: %s", name, type(exc).__name__)
            return VerifierResult(
                verifier_name=name,
                verifier_version=version,
                status=VerifierResultStatus.UNAVAILABLE,
                candidate_id=getattr(candidate, "id", None),
                message=f"verifier_exception:{type(exc).__name__}",
                findings=["soft_fail_exception"],
            )
