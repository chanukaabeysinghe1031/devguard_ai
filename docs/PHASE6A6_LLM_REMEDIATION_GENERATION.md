# Phase 6A.6 Part 2 — LLM Remediation Generation

Structured LLM proposals are optional and untrusted until reference + constraint + safety validation.

- Prompt: `counterfactual_remediation_prompt_v1`
- Schema: `counterfactual_remediation_schema_v1`
- Flag: `LLM_REMEDIATION_GENERATION_ENABLED` (default OFF)
- Injectable callable in tests; no client bypass of server flags
- Fabricated artifact/graph/template IDs and wildcards/secrets are rejected
