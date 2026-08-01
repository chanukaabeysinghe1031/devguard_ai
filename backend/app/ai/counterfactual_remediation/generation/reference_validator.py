"""Phase 6A.6 Part 2 — candidate reference validator (rejects fabricated IDs)."""

from __future__ import annotations

from typing import Any

from app.ai.counterfactual_remediation.generation._helpers import as_dict, as_list
from app.domain.counterfactual_remediation.generation_versions import (
    REMEDIATION_REFERENCE_VALIDATOR_VERSION,
)
from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate


class RemediationReferenceValidator:
    """Validate that candidate references stay within known allowlists."""

    version = REMEDIATION_REFERENCE_VALIDATOR_VERSION

    def validate(
        self,
        candidate: CounterfactualRemediationCandidate,
        *,
        valid_artifact_ids: list[str] | None = None,
        valid_evidence_ids: list[str] | None = None,
        valid_graph_node_ids: list[str] | None = None,
        valid_template_ids: list[str] | None = None,
        context: Any = None,
    ) -> dict[str, Any]:
        ctx = as_dict(context) if context is not None else {}
        artifacts = set(valid_artifact_ids or as_list(ctx.get("valid_artifact_ids")))
        evidence = set(valid_evidence_ids or as_list(ctx.get("valid_evidence_ids")))
        nodes = set(valid_graph_node_ids or as_list(ctx.get("valid_graph_node_ids")))
        templates = set(valid_template_ids or as_list(ctx.get("valid_template_ids")))

        errors: list[str] = []
        warnings: list[str] = []

        for aid in candidate.affected_artifact_ids or []:
            if artifacts and str(aid) not in artifacts:
                errors.append(f"fabricated_artifact_id:{aid}")
        if candidate.primary_artifact_id and artifacts:
            if str(candidate.primary_artifact_id) not in artifacts:
                errors.append(f"fabricated_artifact_id:{candidate.primary_artifact_id}")

        if candidate.template_id and templates and candidate.template_id not in templates:
            errors.append(f"unknown_template_id:{candidate.template_id}")

        for change in candidate.changes or []:
            if change.artifact_id and artifacts and str(change.artifact_id) not in artifacts:
                errors.append(f"fabricated_artifact_id:{change.artifact_id}")
            for eid in change.evidence_ids or []:
                if evidence and str(eid) not in evidence:
                    errors.append(f"fabricated_evidence_id:{eid}")
            for nid in change.graph_node_ids or []:
                if nodes and str(nid) not in nodes:
                    errors.append(f"fabricated_graph_node_id:{nid}")

        status = "VALID" if not errors else "REJECTED"
        return {
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "validator_version": self.version,
            "limitations": [
                "reference_validation_is_not_semantic_verification",
                "candidates_are_not_verified",
            ],
        }
