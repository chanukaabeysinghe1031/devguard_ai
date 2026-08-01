"""Terraform remediation constraint extractor (parser output only)."""

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


class TerraformRemediationConstraintExtractor(BaseRemediationConstraintExtractor):
    extractor_name = "terraform_remediation_constraint_extractor"
    extractor_version = CONSTRAINT_EXTRACTOR_VERSION
    supported_artifact_types = frozenset(
        {
            RemediationArtifactType.TERRAFORM_CONFIGURATION,
            RemediationArtifactType.TERRAFORM_VARIABLES,
            RemediationArtifactType.TERRAFORM_POLICY,
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
        if not entities:
            return finalize_result(
                extractor_name=self.extractor_name,
                constraints=[],
                started_ms=started,
                artifact_ids=[],
                warnings=["terraform_entities_unavailable"],
                limitations=self.limitations() + ["parser_output_missing"],
            )

        declared: set[str] = set()
        for entity in entities:
            et = entity_type(entity)
            meta = entity_meta(entity)
            address = str(meta.get("address") or entity.get("label") or entity.get("id") or "")
            if et in {"RESOURCE", "MODULE", "DATA", "OUTPUT", "VARIABLE", "PROVIDER"} and address:
                declared.add(address)
                constraints.append(
                    base_constraint(
                        context=context,
                        current_state=current_state,
                        constraint_key=f"terraform.resource.exists:{address}",
                        constraint_type=ConstraintType.REFERENCE,
                        severity=ConstraintSeverity.HIGH,
                        source_type=ConstraintSourceType.TERRAFORM,
                        description=f"Declared address '{address}' may be referenced",
                        machine_readable_rule={
                            "rule": "no_nonexistent_resource_reference",
                            "address": address,
                            "block": et.lower(),
                        },
                        is_blocking=True,
                        extractor_name=self.extractor_name,
                        expected_value=address,
                    )
                )
                if meta.get("type"):
                    constraints.append(
                        base_constraint(
                            context=context,
                            current_state=current_state,
                            constraint_key=f"terraform.type.preserve:{address}",
                            constraint_type=ConstraintType.SCHEMA,
                            severity=ConstraintSeverity.HIGH,
                            source_type=ConstraintSourceType.TERRAFORM,
                            description="Variable/resource type must be preserved",
                            machine_readable_rule={
                                "rule": "preserve_variable_or_resource_type",
                                "address": address,
                                "type": meta.get("type"),
                            },
                            is_blocking=True,
                            extractor_name=self.extractor_name,
                            expected_value=meta.get("type"),
                        )
                    )
                if meta.get("prevent_destroy") or meta.get("lifecycle_prevent_destroy"):
                    constraints.append(
                        base_constraint(
                            context=context,
                            current_state=current_state,
                            constraint_key=f"terraform.prevent_destroy:{address}",
                            constraint_type=ConstraintType.DELETION_PROTECTION,
                            severity=ConstraintSeverity.BLOCKING,
                            source_type=ConstraintSourceType.TERRAFORM,
                            description="Candidate must not bypass prevent_destroy",
                            machine_readable_rule={
                                "rule": "honor_prevent_destroy",
                                "address": address,
                            },
                            is_blocking=True,
                            extractor_name=self.extractor_name,
                            prohibited_value={"destroy": True, "bypass_prevent_destroy": True},
                        )
                    )
                if meta.get("sensitive") is True:
                    constraints.append(
                        base_constraint(
                            context=context,
                            current_state=current_state,
                            constraint_key=f"terraform.sensitive:{address}",
                            constraint_type=ConstraintType.SECURITY,
                            severity=ConstraintSeverity.BLOCKING,
                            source_type=ConstraintSourceType.TERRAFORM,
                            description="Candidate must not expose a sensitive value",
                            machine_readable_rule={
                                "rule": "no_expose_sensitive_value",
                                "address": address,
                            },
                            is_blocking=True,
                            extractor_name=self.extractor_name,
                        )
                    )

        region = current_state.current_region or current_state.current_values.get("provider_region")
        if region:
            from app.ai.counterfactual_remediation.extractors._helpers import context_category

            category = context_category(context)
            region_related = "region" in category
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key=f"terraform.region:{region}",
                    constraint_type=ConstraintType.REGION,
                    severity=(
                        ConstraintSeverity.MEDIUM if region_related else ConstraintSeverity.BLOCKING
                    ),
                    source_type=ConstraintSourceType.TERRAFORM,
                    description=(
                        "Provider region must not change unless hypothesis is region-related"
                    ),
                    machine_readable_rule={
                        "rule": "preserve_provider_region_unless_hypothesis_region",
                        "region": region,
                        "region_change_allowed": region_related,
                    },
                    is_blocking=not region_related,
                    extractor_name=self.extractor_name,
                    expected_value=region,
                )
            )

        for ref in sorted(set(current_state.current_references)):
            if ref and ref not in declared and not ref.startswith(("var.", "local.")):
                # Soft warning — references may be cross-file.
                warnings.append(f"reference_not_in_declared_set:{ref}")

        constraints.append(
            base_constraint(
                context=context,
                current_state=current_state,
                constraint_key="terraform.no_unrelated_replacement",
                constraint_type=ConstraintType.REPLACEMENT_RISK,
                severity=ConstraintSeverity.HIGH,
                source_type=ConstraintSourceType.TERRAFORM,
                description="Candidate must not replace unrelated resources",
                machine_readable_rule={
                    "rule": "no_unrelated_resource_replacement",
                    "declared_addresses": sorted(declared),
                },
                is_blocking=True,
                extractor_name=self.extractor_name,
            )
        )

        return finalize_result(
            extractor_name=self.extractor_name,
            constraints=constraints,
            started_ms=started,
            artifact_ids=[a for a in [current_state.artifact_id] if a],
            warnings=warnings,
            limitations=self.limitations(),
        )

    def limitations(self) -> list[str]:
        return super().limitations() + [
            "terraform_never_executed",
            "parser_output_only",
            "implicit_dependencies_partial",
        ]
