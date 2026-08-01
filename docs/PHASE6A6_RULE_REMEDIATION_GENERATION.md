# Phase 6A.6 Part 2 — Rule Remediation Generation

Deterministic template builders produce hypothesis-conditional candidates from known current-state values only.

- Version: `rule_remediation_generator_v1`
- Flag: `RULE_REMEDIATION_GENERATION_ENABLED` (default OFF)
- Implemented builders: IAM missing action / wrong role / region / resource-policy deny; Terraform reference/variable/provider/dependency; GHA needs/secret-name/expression/action version; deps version/lockfile/runtime; container image/registry/env
- Never invents principals, ARNs, secret values, or wildcards
- Candidates remain unverified and are never applied
