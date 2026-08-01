"""Workflow / GitHub Actions remediation constraint extractor."""

from __future__ import annotations

from app.ai.counterfactual_remediation.extractors._helpers import (
    base_constraint,
    entity_meta,
    entity_type,
    finalize_result,
    now_ms,
)
from app.ai.counterfactual_remediation.extractors.base import BaseRemediationConstraintExtractor
from app.ai.counterfactual_remediation.model_types import (
    ConstraintExtractionResult,
    CounterfactualRemediationContext,
    RemediationConstraint,
    RemediationCurrentState,
)
from app.ai.counterfactual_remediation.versions import CONSTRAINT_EXTRACTOR_VERSION
from app.domain.counterfactual_remediation.enums import (
    ConstraintSeverity,
    ConstraintSourceType,
    ConstraintType,
    RemediationArtifactType,
)


class WorkflowRemediationConstraintExtractor(BaseRemediationConstraintExtractor):
    extractor_name = "workflow_remediation_constraint_extractor"
    extractor_version = CONSTRAINT_EXTRACTOR_VERSION
    supported_artifact_types = frozenset(
        {
            RemediationArtifactType.GITHUB_WORKFLOW,
            RemediationArtifactType.REUSABLE_WORKFLOW,
        }
    )

    def extract(
        self,
        context: CounterfactualRemediationContext,
        current_state: RemediationCurrentState,
    ) -> ConstraintExtractionResult:
        started = now_ms()
        constraints: list[RemediationConstraint] = []
        warnings: list[str] = []
        entities = list(current_state.structured_entities) or list(context.parser_entities)
        if not entities and current_state.artifact_type not in self.supported_artifact_types:
            return finalize_result(
                extractor_name=self.extractor_name,
                constraints=[],
                started_ms=started,
                artifact_ids=[],
                warnings=["workflow_entities_unavailable"],
                limitations=self.limitations() + ["source_unavailable"],
            )

        job_ids: set[str] = set()
        needs_edges: list[tuple[str, str]] = []
        secret_refs: list[str] = []
        for entity in entities:
            et = entity_type(entity)
            meta = entity_meta(entity)
            eid = str(entity.get("id") or "")
            if et == "JOB":
                job_key = str(meta.get("job_key") or entity.get("label") or eid)
                job_ids.add(job_key)
                needs = meta.get("needs")
                if isinstance(needs, list):
                    for needed in needs:
                        needs_edges.append((job_key, str(needed)))
                elif needs is not None:
                    needs_edges.append((job_key, str(needs)))
                if "permissions" in meta:
                    constraints.append(
                        base_constraint(
                            context=context,
                            current_state=current_state,
                            constraint_key=f"workflow.permissions.preserve:{job_key}",
                            constraint_type=ConstraintType.PERMISSION,
                            severity=ConstraintSeverity.HIGH,
                            source_type=ConstraintSourceType.WORKFLOW,
                            description="Permissions block must not expand without justification",
                            machine_readable_rule={
                                "rule": "no_expand_permissions_without_justification",
                                "job": job_key,
                                "current_permissions": meta.get("permissions"),
                            },
                            is_blocking=True,
                            extractor_name=self.extractor_name,
                            prohibited_value={"write-all": True, "actions": "write"},
                        )
                    )
            if et == "SECRET_REFERENCE":
                secret_refs.append(str(entity.get("label") or meta.get("expression") or eid))
            if et == "WORKFLOW" and "permissions" in meta:
                constraints.append(
                    base_constraint(
                        context=context,
                        current_state=current_state,
                        constraint_key="workflow.permissions.top_level",
                        constraint_type=ConstraintType.PERMISSION,
                        severity=ConstraintSeverity.HIGH,
                        source_type=ConstraintSourceType.WORKFLOW,
                        description="Top-level workflow permissions must remain least-privilege",
                        machine_readable_rule={
                            "rule": "preserve_or_narrow_permissions",
                            "current_permissions": meta.get("permissions"),
                        },
                        is_blocking=True,
                        extractor_name=self.extractor_name,
                    )
                )

        for job_key in sorted(job_ids):
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key=f"workflow.job.required:{job_key}",
                    constraint_type=ConstraintType.DEPENDENCY,
                    severity=ConstraintSeverity.MEDIUM,
                    source_type=ConstraintSourceType.WORKFLOW,
                    description=f"Job '{job_key}' exists and may be required by dependents",
                    machine_readable_rule={
                        "rule": "job_must_exist_if_referenced",
                        "job": job_key,
                    },
                    extractor_name=self.extractor_name,
                    expected_value=job_key,
                )
            )

        for src, dst in sorted(set(needs_edges)):
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key=f"workflow.needs:{src}->{dst}",
                    constraint_type=ConstraintType.DEPENDENCY,
                    severity=ConstraintSeverity.HIGH,
                    source_type=ConstraintSourceType.WORKFLOW,
                    description=f"Job '{src}' needs '{dst}'",
                    machine_readable_rule={
                        "rule": "preserve_needs_or_replace_with_valid_job",
                        "from_job": src,
                        "needs": dst,
                    },
                    is_blocking=True,
                    extractor_name=self.extractor_name,
                    expected_value=dst,
                )
            )
            if dst not in job_ids:
                warnings.append(f"needs_target_missing:{dst}")
                constraints.append(
                    base_constraint(
                        context=context,
                        current_state=current_state,
                        constraint_key=f"workflow.needs.missing:{src}->{dst}",
                        constraint_type=ConstraintType.REFERENCE,
                        severity=ConstraintSeverity.BLOCKING,
                        source_type=ConstraintSourceType.WORKFLOW,
                        description=f"Needs target '{dst}' is not a declared job",
                        machine_readable_rule={
                            "rule": "needs_target_must_exist",
                            "from_job": src,
                            "missing_job": dst,
                        },
                        is_blocking=True,
                        extractor_name=self.extractor_name,
                    )
                )

        # Cycle prevention as a machine-readable adjacency rule.
        constraints.append(
            base_constraint(
                context=context,
                current_state=current_state,
                constraint_key="workflow.needs.no_cycles",
                constraint_type=ConstraintType.DEPENDENCY,
                severity=ConstraintSeverity.BLOCKING,
                source_type=ConstraintSourceType.WORKFLOW,
                description="Job needs graph must remain acyclic",
                machine_readable_rule={
                    "rule": "prevent_needs_cycle",
                    "edges": [{"from": a, "to": b} for a, b in sorted(set(needs_edges))],
                },
                is_blocking=True,
                extractor_name=self.extractor_name,
            )
        )

        for secret in sorted(set(secret_refs)):
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key=f"workflow.secret.ref:{secret}",
                    constraint_type=ConstraintType.SECURITY,
                    severity=ConstraintSeverity.BLOCKING,
                    source_type=ConstraintSourceType.WORKFLOW,
                    description="Secret values must never be embedded; reference names only",
                    machine_readable_rule={
                        "rule": "no_embed_secret_values",
                        "allowed_reference": secret,
                        "prohibit_literal_secret": True,
                    },
                    is_blocking=True,
                    extractor_name=self.extractor_name,
                    expected_value=f"secrets.{secret}",
                )
            )

        constraints.append(
            base_constraint(
                context=context,
                current_state=current_state,
                constraint_key="workflow.approval_gates.preserve",
                constraint_type=ConstraintType.SECURITY,
                severity=ConstraintSeverity.BLOCKING,
                source_type=ConstraintSourceType.WORKFLOW,
                description="Remediation must not remove required deployment approvals",
                machine_readable_rule={"rule": "no_remove_environment_protection"},
                is_blocking=True,
                extractor_name=self.extractor_name,
            )
        )

        artifact_ids = [a for a in [current_state.artifact_id] if a]
        return finalize_result(
            extractor_name=self.extractor_name,
            constraints=constraints,
            started_ms=started,
            artifact_ids=artifact_ids,
            warnings=warnings,
            limitations=self.limitations(),
        )

    def limitations(self) -> list[str]:
        return super().limitations() + [
            "workflow_yaml_syntax_not_fully_validated",
            "reusable_workflow_inputs_partial",
        ]
