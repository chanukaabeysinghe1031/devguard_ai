"""Phase 6A.6 Part 2 — structural constraint validator (no verifier CLI)."""

from __future__ import annotations

from typing import Any

from app.ai.counterfactual_remediation.generation._helpers import (
    as_dict,
    as_list,
    contains_wildcard,
)
from app.ai.counterfactual_remediation.safety import contains_secret_material
from app.domain.counterfactual_remediation.generation_enums import ConstraintValidationStatus
from app.domain.counterfactual_remediation.generation_models import (
    CandidateConstraintValidationResult,
)
from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate


class RemediationConstraintValidator:
    """Structural constraint checks only — never executes actionlint/terraform/checkov."""

    def validate(
        self,
        candidate: CounterfactualRemediationCandidate,
        *,
        constraint_set: Any = None,
    ) -> CandidateConstraintValidationResult:
        blocking: list[str] = []
        warnings: list[str] = []
        satisfied: list[str] = []
        unsatisfied: list[str] = []
        unknown: list[str] = []

        for change in candidate.changes or []:
            proposed = change.proposed_fragment or ""
            if contains_wildcard(proposed):
                blocking.append("wildcard_permission_or_resource")
            if contains_secret_material(proposed):
                blocking.append("secret_material_in_proposed_fragment")
            lowered = proposed.lower()
            if any(
                token in lowered
                for token in (
                    "skip_ci",
                    "continue-on-error: true",
                    "encryption = false",
                    'acl" = "public',
                    "disable_scanner",
                )
            ):
                blocking.append("security_control_weakening")

        cset = as_dict(constraint_set)
        for item in as_list(cset.get("blocking_constraints")):
            key = None
            if hasattr(item, "constraint_key"):
                key = item.constraint_key
            elif isinstance(item, dict):
                key = item.get("constraint_key") or item.get("description")
            if key:
                # Explicit deny / permissions boundary remain blocking unless candidate
                # is a non-identity-add path that does not attempt bypass.
                key_s = str(key)
                if "explicit_deny" in key_s.lower() or "deny" in key_s.lower():
                    if any(
                        "UPDATE_PERMISSION" in str(t) or "ADD" in str(t)
                        for t in (candidate.change_types or [])
                    ):
                        blocking.append(f"blocked_by:{key_s}")
                        unsatisfied.append(key_s)
                    else:
                        unknown.append(key_s)
                else:
                    unknown.append(key_s)

        if blocking:
            status = ConstraintValidationStatus.UNSAFE
        elif unsatisfied:
            status = ConstraintValidationStatus.BLOCKED
        elif warnings:
            status = ConstraintValidationStatus.COMPLIANT_WITH_WARNINGS
        elif not candidate.changes:
            status = ConstraintValidationStatus.INCOMPLETE
        else:
            status = ConstraintValidationStatus.STRUCTURALLY_COMPLIANT
            satisfied.append("no_blocking_structural_violations")

        return CandidateConstraintValidationResult(
            status=status,
            candidate_id=candidate.id,
            satisfied_constraints=satisfied,
            unsatisfied_constraints=unsatisfied,
            unknown_constraints=unknown,
            blocking_violations=blocking,
            warnings=warnings,
        )
