# Phase 6A.6 Part 3 — Counterfactual Validation

**Status:** Implemented (flags OFF)  
**Scope:** Independent validation of remediation **candidates** only

## What is validated

1. Structural integrity of proposed fragments (JSON / YAML / HCL / IAM / dependency manifests)
2. Static security regressions (wildcards, secret-like material)
3. Optional tool checks inside a disposable temp workspace

## What is not validated

- Live cloud resources
- Production IAM / Terraform state
- GitHub write / PR apply
- Root-cause certainty
- Module 6–9 recommendation quality (unchanged)

## Safety non-negotiables

1. No repository mutation  
2. No `terraform apply`, no AWS/kubectl, no git writes  
3. No LLM-as-verifier  
4. No fake PASS when tools are missing  
5. Flags default OFF; clients cannot force ON  
6. Stdout/stderr truncated and secret-redacted before persist/API  
7. Timeouts and stage budgets  

## Relationship to Parts 1–2

| Part | Output |
|------|--------|
| 1 | Constraints, current/counterfactual snapshots, skeletons |
| 2 | Generated patches, risk, priority (`READY_FOR_VERIFICATION`) |
| 3 | Verifier results + consensus over temporary state |

Candidates remain hypothesis-conditional. See `docs/PHASE6A6_VERIFIER_ENGINE.md` and `docs/PHASE6A6_CONSENSUS.md`.

## Stop line

Phase 6A.7 (abstention / Causal UI polish / apply path) is **not** started by this work.
