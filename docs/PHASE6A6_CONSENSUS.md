# Phase 6A.6 Part 3 — Verification Consensus

**Status:** Implemented  
**Version:** `consensus_v1`  
**LLM role:** none — consensus is deterministic rule evaluation only

## Meaning of VERIFIED

`VERIFIED` means: required verifiers for the candidate’s artifact family returned PASS (or allowed WARNING on optional tools), with **no blocking FAIL**, and **no required UNAVAILABLE**.

It does **not** mean:

- proven root cause
- applied remediation
- safe for production mutate
- LLM agreement

## Artifact-family required sets

| Family | Required verifiers (minimum) |
|--------|------------------------------|
| terraform | `hcl_fragment`, `terraform_validate` |
| workflow | `yaml_validator`, `actionlint` |
| iam | `json_schema`, `iam_structural` |
| dependency | `dependency_manifest` |

`security_static` FAIL always blocks `VERIFIED` when that verifier ran. Optional CLI tools (`terraform_plan`, `checkov`, `opa`) strengthen evidence when enabled and available; required-tool UNAVAILABLE never invents PASS.

## Decision table

| Condition | Consensus |
|-----------|-----------|
| Any required/blocking FAIL | `FAILED` |
| Required verifier missing or UNAVAILABLE | `INCONCLUSIVE` (never `VERIFIED`) |
| Required set PASS; warnings only | `PARTIALLY_VERIFIED` or `VERIFIED` |
| No results | `UNAVAILABLE` |

## Scientific position

Consensus validates the **temporary counterfactual workspace**, not the original incident diagnosis. Product recommendations remain independent.
