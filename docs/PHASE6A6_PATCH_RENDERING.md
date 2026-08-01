# Phase 6A.6 Part 2 — Patch Rendering

`RemediationPatchRenderer` builds bounded unified diffs with stdlib `difflib`.

- Version: `remediation_patch_renderer_v1`
- Formats: YAML/JSON/IAM JSON/HCL fragment/text/dependency/unified diff
- Original artifacts are never mutated; before/after hashes recorded
- HCL is fragment-only (no AST round-trip claim)
- Flag: `REMEDIATION_PATCH_RENDERING_ENABLED` (default OFF)
