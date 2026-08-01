"""Phase 6A.6 Part 2 — patch renderer (stdlib difflib; never mutates originals)."""

from __future__ import annotations

import copy
import difflib
import json
from typing import Any

from app.ai.counterfactual_remediation.generation._helpers import (
    contains_wildcard,
    sha256_text,
)
from app.ai.counterfactual_remediation.safety import contains_secret_material
from app.domain.counterfactual_remediation.generation_enums import PatchFormat
from app.domain.counterfactual_remediation.generation_models import RenderedPatch
from app.domain.counterfactual_remediation.generation_versions import (
    REMEDIATION_PATCH_RENDERER_VERSION,
)


class RemediationPatchRenderer:
    """Render bounded unified diffs without mutating source artifacts."""

    version = REMEDIATION_PATCH_RENDERER_VERSION

    def __init__(
        self,
        *,
        max_patch_characters: int = 30_000,
        max_changed_lines: int = 200,
    ) -> None:
        self._max_chars = max(256, max_patch_characters)
        self._max_lines = max(1, max_changed_lines)

    def render(
        self,
        *,
        original_fragment: str | None,
        proposed_fragment: str | None,
        patch_format: PatchFormat | str | None = None,
        artifact_type: Any = None,
        source_path: str | None = None,
        max_characters: int | None = None,
        max_changed_lines: int | None = None,
    ) -> RenderedPatch:
        del artifact_type  # optional hint; format resolved from path/content
        max_characters = self._max_chars if max_characters is None else max_characters
        max_changed_lines = self._max_lines if max_changed_lines is None else max_changed_lines
        # Defensive copies — never mutate caller strings/structures.
        original = "" if original_fragment is None else str(original_fragment)
        proposed = "" if proposed_fragment is None else str(proposed_fragment)
        original_copy = copy.copy(original)
        proposed_copy = copy.copy(proposed)

        fmt = self._resolve_format(patch_format, original_copy, proposed_copy, source_path)
        warnings: list[str] = []
        incomplete = False

        if contains_secret_material(proposed_copy):
            return RenderedPatch(
                patch_format=PatchFormat.UNSUPPORTED,
                original_fragment=original_copy,
                proposed_fragment=None,
                content_hash_before=sha256_text(original_copy),
                incomplete=True,
                warnings=["secret_material_in_proposed_fragment"],
            )
        if contains_wildcard(proposed_copy):
            return RenderedPatch(
                patch_format=fmt,
                original_fragment=original_copy,
                proposed_fragment=None,
                content_hash_before=sha256_text(original_copy),
                incomplete=True,
                warnings=["wildcard_in_proposed_fragment"],
            )

        if fmt == PatchFormat.IAM_POLICY_JSON or fmt == PatchFormat.JSON_FRAGMENT:
            try:
                # Normalize JSON whitespace without claiming semantic policy correctness.
                if original_copy.strip():
                    original_copy = json.dumps(json.loads(original_copy), indent=2, sort_keys=True)
                if proposed_copy.strip():
                    proposed_copy = json.dumps(json.loads(proposed_copy), indent=2, sort_keys=True)
            except (json.JSONDecodeError, TypeError, ValueError):
                warnings.append("json_normalize_failed")
                incomplete = True

        if fmt == PatchFormat.HCL_FRAGMENT:
            warnings.append("hcl_fragment_only_no_ast_roundtrip")

        before_lines = original_copy.splitlines(keepends=True)
        after_lines = proposed_copy.splitlines(keepends=True)
        if not before_lines and original_copy:
            before_lines = [original_copy]
        if not after_lines and proposed_copy:
            after_lines = [proposed_copy]

        diff_lines = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"a/{source_path or 'original'}",
                tofile=f"b/{source_path or 'proposed'}",
                lineterm="",
            )
        )
        # Keep line endings stable when both sides omit trailing newline.
        normalized = "\n".join(diff_lines)
        if normalized and not normalized.endswith("\n"):
            normalized = normalized + "\n"

        changed = sum(
            1 for line in diff_lines if line.startswith("+") or line.startswith("-")
        ) - sum(1 for line in diff_lines if line.startswith("+++") or line.startswith("---"))
        changed = max(0, changed)

        if len(normalized) > max_characters:
            warnings.append("patch_exceeds_max_characters")
            incomplete = True
            normalized = normalized[:max_characters]
        if changed > max_changed_lines:
            warnings.append("patch_exceeds_max_changed_lines")
            incomplete = True

        return RenderedPatch(
            patch_format=fmt,
            normalized_diff=normalized or None,
            original_fragment=original_copy,
            proposed_fragment=proposed_copy,
            content_hash_before=sha256_text(original_copy),
            content_hash_after=sha256_text(proposed_copy),
            changed_line_count=changed,
            incomplete=incomplete,
            warnings=warnings,
        )

    def _resolve_format(
        self,
        patch_format: PatchFormat | str | None,
        original: str,
        proposed: str,
        source_path: str | None,
    ) -> PatchFormat:
        if isinstance(patch_format, PatchFormat):
            return patch_format
        if patch_format:
            try:
                return PatchFormat(str(patch_format))
            except ValueError:
                pass
        path = (source_path or "").lower()
        sample = (proposed or original or "").lstrip()
        if path.endswith((".json", ".json.tpl")) or sample.startswith("{"):
            if '"Action"' in sample or '"Resource"' in sample or '"Statement"' in sample:
                return PatchFormat.IAM_POLICY_JSON
            return PatchFormat.JSON_FRAGMENT
        if path.endswith((".yml", ".yaml")) or sample.startswith(("name:", "jobs:", "on:")):
            return PatchFormat.YAML_FRAGMENT
        if path.endswith(".tf") or "resource \"" in sample or "provider \"" in sample:
            return PatchFormat.HCL_FRAGMENT
        if path.endswith(("package.json", "requirements.txt", "Cargo.toml", "go.mod")):
            return PatchFormat.DEPENDENCY_MANIFEST
        return PatchFormat.UNIFIED_DIFF


def render_change_patch(
    *,
    original_fragment: str | None,
    proposed_fragment: str | None,
    **kwargs: Any,
) -> RenderedPatch:
    return RemediationPatchRenderer().render(
        original_fragment=original_fragment,
        proposed_fragment=proposed_fragment,
        **kwargs,
    )
