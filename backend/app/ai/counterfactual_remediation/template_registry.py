"""Remediation template registry (brief §29)."""

from __future__ import annotations

import logging
from typing import Iterable

from app.ai.counterfactual_remediation.model_types import RemediationTemplate
from app.ai.counterfactual_remediation.templates import build_initial_template_skeletons

logger = logging.getLogger(__name__)


def template_family(template: RemediationTemplate) -> str:
    for note in template.risk_notes:
        if note.startswith("family:"):
            return note.split(":", 1)[1]
    for path in template.hierarchy_paths:
        if path.startswith("family/"):
            return path.split("/", 1)[1]
    if "." in template.template_id:
        return template.template_id.split(".", 1)[0]
    return ""


def candidate_builder_implemented(template: RemediationTemplate) -> bool:
    """Part 1 skeletons must remain unimplemented."""
    markers = {m.lower() for m in template.limitations}
    if "candidate_builder_implemented=false" in markers:
        return False
    if "candidate_builder_not_implemented" in markers:
        return False
    if "candidate_builder_implemented=true" in markers:
        return True
    return False


class RemediationTemplateRegistry:
    """Register / resolve versioned template skeletons."""

    def __init__(self, *, load_defaults: bool = True) -> None:
        self._templates: dict[str, RemediationTemplate] = {}
        if load_defaults:
            for template in build_initial_template_skeletons():
                self.register(template)

    def register(self, template: RemediationTemplate) -> None:
        if not template.template_id:
            raise ValueError("template_id_required")
        if template.template_id in self._templates:
            raise ValueError(f"duplicate_template_id:{template.template_id}")
        errors = self.validate_template(template)
        if errors:
            raise ValueError(f"invalid_template:{','.join(errors)}")
        self._templates[template.template_id] = template
        logger.debug("template_registered id=%s", template.template_id)

    def validate_template(self, template: RemediationTemplate) -> list[str]:
        errors: list[str] = []
        if not template.template_id:
            errors.append("missing_template_id")
        if not template.supported_artifact_types and not template.category_codes:
            errors.append("missing_category_or_artifact_types")
        if candidate_builder_implemented(template):
            errors.append("part_1_requires_candidate_builder_implemented_false")
        return errors

    def get(self, template_id: str) -> RemediationTemplate | None:
        return self._templates.get(template_id)

    def all_templates(self) -> list[RemediationTemplate]:
        return [self._templates[k] for k in sorted(self._templates)]

    def unsupported_categories(self, category_codes: Iterable[str]) -> list[str]:
        supported: set[str] = set()
        for template in self._templates.values():
            supported.update(c.lower() for c in template.category_codes)
        return sorted({c for c in category_codes if c.lower() not in supported})

    def resolve(
        self,
        *,
        category: str | None = None,
        artifact_type: str | None = None,
        hypothesis_text: str | None = None,
        active_conditions: Iterable[str] | None = None,
    ) -> list[RemediationTemplate]:
        """Resolve templates by category/artifact; skip prohibited conditions."""
        active = {c.lower() for c in (active_conditions or [])}
        category_l = (category or "").lower()
        artifact_l = (artifact_type or "").upper()
        text = (hypothesis_text or "").lower()
        matched: list[RemediationTemplate] = []

        for template in self.all_templates():
            prohibited = {p.lower() for p in template.prohibited_conditions}
            if prohibited & active:
                continue
            cat_hit = (
                any(c.lower() in category_l or category_l in c.lower() for c in template.category_codes)
                if category_l
                else False
            )
            art_hit = False
            if artifact_l:
                for a in template.supported_artifact_types:
                    aval = a.value if hasattr(a, "value") else str(a)
                    if aval.upper() == artifact_l:
                        art_hit = True
                        break
            pattern_hit = (
                any(p.lower() in text for p in template.supported_hypothesis_patterns)
                if text
                else False
            )
            if cat_hit or art_hit or pattern_hit:
                matched.append(template)

        matched.sort(key=lambda t: (template_family(t), t.template_id))
        return matched
