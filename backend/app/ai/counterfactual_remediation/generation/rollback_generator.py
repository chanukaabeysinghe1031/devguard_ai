"""Structured rollback plan generation (no shell commands)."""

from __future__ import annotations

import logging
from uuid import uuid4

from app.ai.counterfactual_remediation.generation._helpers import as_dict, sha256_text
from app.domain.counterfactual_remediation.enums import RollbackType
from app.domain.counterfactual_remediation.generation_versions import (
    REMEDIATION_ROLLBACK_VERSION,
)
from app.domain.counterfactual_remediation.models import (
    CounterfactualRemediationCandidate,
    RemediationRollbackPlan,
)

logger = logging.getLogger(__name__)


class RemediationRollbackGenerator:
    """Build structured rollback plans from original fragments/hashes."""

    def __init__(self, *, max_steps: int = 20) -> None:
        self._max_steps = max_steps
        self.version = REMEDIATION_ROLLBACK_VERSION

    def generate(self, candidate: CounterfactualRemediationCandidate) -> RemediationRollbackPlan:
        steps: list[dict[str, object]] = []
        hashes: list[str] = []
        artifacts: list[str] = []
        can_restore = True
        limitations: list[str] = ["no_shell_commands", "structured_steps_only"]

        for idx, change in enumerate(candidate.changes, start=1):
            if idx > self._max_steps:
                limitations.append("rollback_steps_truncated")
                break
            original = change.original_fragment
            before_hash = change.content_hash_before or sha256_text(original)
            if before_hash:
                hashes.append(before_hash)
            if change.artifact_id:
                artifacts.append(change.artifact_id)
            if not original:
                can_restore = False
                steps.append(
                    {
                        "step": idx,
                        "action": "manual_restore_required",
                        "artifact_id": change.artifact_id,
                        "reason": "original_fragment_unavailable",
                    }
                )
                continue
            steps.append(
                {
                    "step": idx,
                    "action": "restore_original_fragment",
                    "artifact_id": change.artifact_id,
                    "source_path": change.source_path,
                    "target_property": change.target_property,
                    "content_hash": before_hash,
                    # Do not embed full fragment bodies in logs; keep in structured plan only.
                    "original_fragment_present": True,
                }
            )

        if not steps:
            existing = as_dict(candidate.rollback_plan)
            if existing:
                return RemediationRollbackPlan(
                    candidate_id=candidate.id,
                    rollback_type=RollbackType.RESTORE_ORIGINAL_FRAGMENT,
                    original_content_hashes=list(existing.get("original_content_hashes") or []),
                    affected_artifacts=list(existing.get("affected_artifacts") or []),
                    rollback_steps=list(existing.get("rollback_steps") or [])[: self._max_steps],
                    can_restore_exactly=bool(existing.get("can_restore_exactly")),
                    rollback_limitations=list(existing.get("rollback_limitations") or limitations),
                )
            can_restore = False
            steps.append(
                {
                    "step": 1,
                    "action": "manual_restore_required",
                    "reason": "no_changes_to_revert",
                }
            )

        rollback_type = (
            RollbackType.RESTORE_ORIGINAL_FRAGMENT
            if can_restore
            else RollbackType.MANUAL_REQUIRED
        )
        # Prefer version restore when only version properties changed.
        if candidate.changes and all(
            (
                c.change_type.value
                if hasattr(c.change_type, "value")
                else str(c.change_type)
            )
            == "UPDATE_VERSION"
            for c in candidate.changes
        ):
            rollback_type = RollbackType.RESTORE_VERSION

        logger.debug(
            "rollback_generated candidate=%s steps=%s can_restore=%s",
            candidate.id,
            len(steps),
            can_restore,
        )
        return RemediationRollbackPlan(
            candidate_id=candidate.id or str(uuid4()),
            rollback_type=rollback_type,
            original_content_hashes=hashes,
            affected_artifacts=sorted({a for a in artifacts if a}),
            rollback_steps=steps,
            rollback_preconditions=["original_content_hash_available"] if can_restore else [],
            rollback_limitations=limitations,
            rollback_risk="rollback_not_risk_free",
            can_restore_exactly=can_restore,
        )
