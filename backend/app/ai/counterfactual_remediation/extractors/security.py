"""Security / policy remediation constraint extractor."""

from __future__ import annotations

from app.ai.counterfactual_remediation.extractors._helpers import (
    base_constraint,
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

_UNIVERSAL_RULES: tuple[tuple[str, ConstraintType, str, dict], ...] = (
    (
        "security.no_plaintext_secrets",
        ConstraintType.SECURITY,
        "No plaintext secrets or embedded credentials",
        {"rule": "no_plaintext_secrets", "source": "system_policy"},
    ),
    (
        "security.no_wildcard_admin",
        ConstraintType.LEAST_PRIVILEGE,
        "No wildcard admin permissions",
        {"rule": "no_wildcard_admin", "prohibited": ["*", "AdministratorAccess"]},
    ),
    (
        "security.no_public_access",
        ConstraintType.PUBLIC_ACCESS,
        "No public access unless explicitly required by evidence",
        {"rule": "no_public_access_default", "allow_only_with_explicit_requirement": True},
    ),
    (
        "security.keep_encryption",
        ConstraintType.ENCRYPTION,
        "Encryption must remain enabled",
        {"rule": "preserve_encryption", "prohibit_disable": True},
    ),
    (
        "security.keep_tls",
        ConstraintType.ENCRYPTION,
        "TLS must not be disabled",
        {"rule": "preserve_tls", "prohibit_disable": True},
    ),
    (
        "security.keep_scanners",
        ConstraintType.SECURITY,
        "Security scanning / policy gates must not be removed",
        {"rule": "no_remove_scanners_or_policy_gates"},
    ),
    (
        "security.keep_tests",
        ConstraintType.SECURITY,
        "Test stages must not be bypassed as a fix",
        {"rule": "no_remove_or_skip_tests"},
    ),
    (
        "security.keep_approvals",
        ConstraintType.SECURITY,
        "Approval gates / branch protections must not be removed or weakened",
        {"rule": "no_remove_approvals_or_branch_protection"},
    ),
)


class SecurityRemediationConstraintExtractor(BaseRemediationConstraintExtractor):
    extractor_name = "security_remediation_constraint_extractor"
    extractor_version = CONSTRAINT_EXTRACTOR_VERSION
    supported_artifact_types = frozenset(set(RemediationArtifactType))

    def extract(
        self,
        context: CounterfactualRemediationContext,
        current_state: RemediationCurrentState,
    ) -> ConstraintExtractionResult:
        started = now_ms()
        constraints: list[RemediationConstraint] = []
        for key, ctype, description, rule in _UNIVERSAL_RULES:
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key=key,
                    constraint_type=ctype,
                    severity=ConstraintSeverity.BLOCKING,
                    source_type=ConstraintSourceType.SYSTEM_POLICY,
                    description=description,
                    machine_readable_rule=dict(rule),
                    is_blocking=True,
                    extractor_name=self.extractor_name,
                    limitations=["universal_system_safety_rule"],
                )
            )

        for finding in current_state.current_security_findings:
            finding_key = (
                str(finding.get("finding") or finding.get("id") or finding)
                if isinstance(finding, dict)
                else str(finding)
            )
            constraints.append(
                base_constraint(
                    context=context,
                    current_state=current_state,
                    constraint_key=f"security.finding:{finding_key}",
                    constraint_type=ConstraintType.SECURITY,
                    severity=ConstraintSeverity.HIGH,
                    source_type=ConstraintSourceType.SECURITY_POLICY,
                    description=f"Existing security finding must not be worsened: {finding_key}",
                    machine_readable_rule={
                        "rule": "do_not_worsen_security_finding",
                        "finding": finding
                        if isinstance(finding, dict)
                        else {"finding": finding_key},
                        "source": "inferred_from_current_state",
                    },
                    is_blocking=True,
                    extractor_name=self.extractor_name,
                    limitations=["inferred_constraint"],
                )
            )

        return finalize_result(
            extractor_name=self.extractor_name,
            constraints=constraints,
            started_ms=started,
            artifact_ids=[a for a in [current_state.artifact_id] if a],
            limitations=self.limitations(),
        )

    def limitations(self) -> list[str]:
        return super().limitations() + [
            "distinguishes_system_vs_inferred_via_limitations_field",
            "project_org_policy_hooks_partial",
        ]
