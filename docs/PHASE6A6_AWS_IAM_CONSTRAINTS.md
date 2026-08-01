# Phase 6A.6 — AWS / IAM Constraints

Extractor: `AwsIamRemediationConstraintExtractor`.

## Extracts

- Scoped allow for known denied action
- Explicit deny → blocking (`explicit_deny_blocks_add_allow`)
- Prohibition of `Action: "*"` / `Resource: "*"` introduction
- Principal / wrong-role: prefer correcting intended principal over broadening unrelated role
- Resource scope when known

## Conflict example

Explicit deny vs proposed `add_allow_over_deny` → must-stop conflict.
