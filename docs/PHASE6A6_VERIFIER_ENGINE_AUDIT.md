# Phase 6A.6 Part 3 — Independent Verifier Engine Audit

**Status:** Complete (audit before implementation)  
**Part 2 HEAD:** `eadaabf`  
**Alembic head:** `017_phase6a6_cf_generation`  
**OpenAPI paths:** 127  
**Date:** 2026-08-01  

**Scientific position:** Independent, deterministic, tool-based validation of counterfactual remediation candidates. LLMs are **not** verifiers. A PASS from structural or CLI tools validates the **temporary counterfactual state**, never claims the candidate is a proven root-cause fix or an applied repair.

---

## 1. Part 2 assets reused

| Asset | Real name |
|-------|-----------|
| Candidates | `CounterfactualRemediationCandidate` with `READY_FOR_VERIFICATION`, patches, risk, priority |
| Changes | `CounterfactualChange` + `rendered_patch` / fragments |
| Patch renderer | `RemediationPatchRenderer` |
| Rollback | `RemediationRollbackPlan` / generator |
| Verification requirements | `RemediationVerificationRequirement` + reserved `VerifierType` enums |
| Execution | `_maybe_run_phase6a6_counterfactual_foundation` then `_maybe_run_phase6a6_counterfactual_generation` |
| Persist | `CounterfactualRemediationPersistService` + tables from 016/017 |
| Safety | `contains_secret_material`, temp-only mutation rule |

Product `recommendations` remain untouched.

---

## 2. Insertion point

```
… → foundation
  → generation (Part 2)
  → _maybe_run_phase6a6_verifier_engine   # NEW Part 3
  → _persist_results
```

Only candidates with concrete changes / rendered patches and eligible priority statuses are verified when flags ON.

---

## 3. Temporary workspace strategy

- `tempfile.TemporaryDirectory` under OS temp (not the git worktree)
- Copy or write **only** candidate-relevant fragments into the temp tree
- Apply patch **only** inside that tree
- Run tools with `cwd=temp_dir`, fixed argv, timeout, no shell=`True`
- Always cleanup (finally)
- Never write under the repository root, never `git`, never `terraform apply`, never AWS/kubectl

---

## 4. Tool availability

| Tool | Adapter | If missing |
|------|---------|------------|
| Built-in JSON/YAML/HCL fragment/IAM/deps/security | Always available | N/A |
| `terraform` | validate + plan (`-refresh=false`, no apply) | `UNAVAILABLE` |
| `actionlint` | workflow YAML | `UNAVAILABLE` |
| `checkov` | IaC security | `UNAVAILABLE` |
| `opa` | policy eval | `UNAVAILABLE` |

Never invent PASS when a required tool is missing.

---

## 5. Consensus (non-LLM)

Deterministic rules by artifact family (Terraform / Workflow / IAM / Dependency / Security).  
Blocking FAIL → not VERIFIED. Required tool UNAVAILABLE → INCONCLUSIVE or UNAVAILABLE consensus, never VERIFIED.

---

## 6. Persistence decision

**Create `018_phase6a6_verifiers`** (≤32 chars) with:

- `remediation_verification_runs`
- `remediation_verification_results`
- Optional consensus columns/JSONB on run

Additive; no backfill; org/analysis/candidate scoped.

---

## 7. Docker

Extend `backend/Dockerfile` to optionally install terraform/actionlint/checkov/opa **or** document multi-stage/optional layers. Runtime must degrade to UNAVAILABLE if binaries absent. Do not fail container start if tools missing.

---

## 8. Safety non-negotiables

1. No repository mutation  
2. No infrastructure mutation / apply  
3. No LLM-as-verifier  
4. No fake PASS  
5. Flags default OFF  
6. Mask secrets in persisted logs (truncate stdout/stderr; redact)  
7. Timeouts and cancellation  

---

## 9. Conclusion

Part 3 implements a flag-gated independent verifier engine over temporary counterfactual workspaces, consensus without LLMs, persistence, debug APIs, Docker optional tools, and tests — then **STOP** before Phase 6A.7.
