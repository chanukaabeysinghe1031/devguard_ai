# Phase 6A.6 — Terraform Constraints

Extractor: `TerraformRemediationConstraintExtractor` (parser entities only; no `terraform` CLI).

## Extracts

- Declared resource/module/output/variable addresses
- Type preservation
- `prevent_destroy` / lifecycle protection
- Sensitive fields (no plaintext secret material)
- Provider region preservation signals
- Replacement-risk hints when plan metadata present

## Out of scope (Part 1)

`terraform plan/apply`, Checkov/OPA execution, remote state access.
