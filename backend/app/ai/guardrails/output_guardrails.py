"""Output guardrails for analysis pipeline results."""

from __future__ import annotations

from app.ai.orchestration.analysis_context import AnalysisContext
from app.domain.services.secret_masker import mask_secrets

_DANGEROUS = (
    "rm -rf /",
    "terraform destroy",
    "drop database",
    "mkfs.",
    "shutdown -h",
)


class OutputGuardrails:
    def validate(self, context: AnalysisContext) -> None:
        if not context.classifications:
            context.warnings.append("No classifications produced.")
        if context.generate_recommendations and context.recommendation is None:
            context.warnings.append("Recommendations were requested but not produced.")

        # Re-scan evidence and recommendation text for secrets / dangerous commands.
        for item in context.evidence:
            masked, count = mask_secrets(item.normalized_excerpt)
            if count:
                item.normalized_excerpt = masked
                item.raw_excerpt = masked
                context.warnings.append("Re-masked secrets in evidence excerpts.")

        if context.recommendation is not None:
            for step in context.recommendation.steps:
                if step.command_template and any(
                    bad in step.command_template.lower() for bad in _DANGEROUS
                ):
                    step.command_template = None
                    context.warnings.append("Removed dangerous recommendation command.")
                if step.action:
                    masked, count = mask_secrets(step.action)
                    if count:
                        step.action = masked
