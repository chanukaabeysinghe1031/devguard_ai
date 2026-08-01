# Phase 6A.6 Part 2 — Generation Audit

**Status:** Complete (audit only — generation begins after this document)  
**Baseline tag:** `v1.1.0-phase6a5-complete` (`482745e`)  
**Part 1 HEAD:** `acfcf0d`  
**Alembic head:** `016_phase6a6_cf_foundation`  
**OpenAPI paths:** 120  
**Date:** 2026-08-01  

**Scientific position:** A hypothesis-conditioned counterfactual remediation generator that constructs minimal candidate changes under explicit workflow, infrastructure, security, repository, and operational constraints — **not** “generate a recommendation using an LLM.”

Part 2 produces **structured remediation candidates** for later independent verification. It does not execute, apply, or verify them.

---

## 1. Part 1 commits reused

| Hash | Subject |
|------|---------|
| `4f54179` | docs: audit Phase 6A.6 counterfactual remediation foundation |
| `abb565c` | feat: add Phase 6A.6 Part 1 flags and counterfactual contracts |
| `9bf71b9` | feat: add Phase 6A.6 counterfactual remediation persistence |
| `1e211a3` | feat: wire Phase 6A.6 counterfactual foundation into analysis execution |
| `a2eef0f` | feat: expose Phase 6A.6 counterfactual remediation debug APIs |
| `a12fa68` | test: cover Phase 6A.6 counterfactual foundation safety contracts |
| `c45cf70` | docs: document Phase 6A.6 Part 1 counterfactual remediation foundation |
| `7d0085f` | fix: harden Phase 6A.6 typing and remove domain stubs |
| `acfcf0d` | fix: clarify current-state content hash typing |

---

## 2. Exact Part 1 components reused

| Component | Real name / path |
|-----------|------------------|
| Foundation | `CounterfactualRemediationFoundationService` |
| Context | `CounterfactualRemediationContextBuilder` |
| Current state | `RemediationCurrentStateBuilder` |
| Constraints | `RemediationConstraintOrchestrator` + six extractors |
| Conflicts | `RemediationConstraintConflictDetector` |
| Planner | `DeterministicMinimalChangePlanner` |
| Templates | `RemediationTemplateRegistry` + 26 skeletons |
| Validator | `CounterfactualCandidateStructuralValidator` |
| Eligibility | `CounterfactualHypothesisEligibilityEvaluator` |
| Safety | `mask_for_context`, `contains_secret_material`, `sanitize_untrusted_instructions` |
| Persist | `CounterfactualRemediationPersistService` + `CounterfactualRemediationRepositoryImpl` |
| Execution hook | `AnalysisExecutionService._maybe_run_phase6a6_counterfactual_foundation` |
| Debug APIs | `Phase6A6CounterfactualService` — 8 GET routes |
| Domain models | `CounterfactualRemediationCandidate`, `CounterfactualChange`, `MinimalChangePlan`, … |

Product path that **must stay separate:** `RecommendationGenerator` → `recommendations` / `recommendation_steps`.

---

## 3. Incomplete template builders

All **26** templates set `candidate_builder_implemented=false` / `candidate_builder_not_implemented`.  
`RemediationTemplateRegistry` rejects any template claiming `candidate_builder_implemented=true` in Part 1.

Part 2 must implement deterministic builders for core families and flip markers only for those that produce real structured changes.

---

## 4. Candidate skeleton limitations

Part 1 creates skeletons when plan status ∈ `{READY_FOR_GENERATION, INCOMPLETE}`:

- `changes` is **empty**
- `counterfactual_state_snapshot` is a stub
- `generator_type="deterministic_skeleton"`
- assumptions include `part_1_skeleton_only`, `builder_unimplemented`
- no rendered patch, risk score, priority, or fingerprint

Part 2 replaces/extends skeletons with concrete changes for eligible plans.

---

## 5. Source-format limitations

| Format | Capability | Round-trip? |
|--------|------------|-------------|
| YAML (workflows) | `yaml.safe_load` / limited dump | Lossy (comments/anchors) — prefer fragment edits |
| JSON / IAM policy | `json.loads` / dumps | Acceptable for policy fragments |
| Terraform HCL | **Regex extract-only** (`TerraformParser`) — no HCL library | **Not safe** — no AST round-trip |
| Plan JSON | Parse only | Not an editor |

No `python-hcl2` dependency. Part 2 must use **bounded fragment / string replacement**, not pretend HCL AST editing.

---

## 6. Available diff utilities

- **None** under `backend/app` for `difflib` / unified diff / jsonpatch.
- Part 2 will introduce a small `RemediationPatchRenderer` using stdlib `difflib` for normalized diffs.

---

## 7. What can be generated without executing tools

Structurally safe:

- Exact property / reference / version replacements from known current-state values
- Narrow IAM action/resource additions when action/principal/resource known and no explicit deny
- Workflow `needs` / secret-reference **name** / role ARN reference corrections
- Dependency version alignment when compatible range known
- Previous-success property restoration when commit provenance exists
- Constrained LLM structured proposals **after** reference validation

Cannot claim without later verifiers: operational correctness, security correctness, Terraform plan outcomes.

---

## 8. What requires LLM assistance

Useful when:

- Multiple plausible fragment shapes need structured drafting
- Expressing assumptions / expected effects in natural language
- Alternative minimal candidates within allowed templates

Still untrusted until reference + constraint + safety validation. Strict JSON schema required.

---

## 9. What must remain unsupported

1. Source-code rewrites without exact causal fragment  
2. Verifier CLI execution (actionlint, terraform, checkov, opa, …)  
3. Repository / infrastructure mutation / apply / PR  
4. Shell commands from generated text  
5. Wildcards / admin / disable TLS/encryption/tests/scanners/approvals  
6. Secret **values** in patches  
7. Labels: VERIFIED / FIXED / APPLIED / SUCCESSFUL  
8. Merging into product `recommendations`  
9. HCL AST round-trip editing  
10. Client bypass of server flags  

---

## 10. Persistence gaps

**016 already has:** `generator_type/name/version`, snapshots, `risk_summary` JSONB, change-level fragments/diffs/hashes, risk_signals table.

**Missing for Part 2 query/filter APIs:**

- candidate-level `rendered_patch` / `patch_format` / `patch_hash`
- `risk_score`, `risk_level`, `blast_radius`
- `priority_score`, `priority_status`
- `deduplication_fingerprint`
- `validation_status` / `constraint_status`
- `changed_file_count` / `changed_line_count`
- `prompt_version` / generation provenance JSONB
- `side_effects_json` / `quality_components_json` / `rollback_json` (rollback may already live in snapshot)

---

## 11. Migration decision

**Create additive migration `017_phase6a6_cf_generation`.**

Justification: Part 2 APIs filter by risk/priority/generator/fingerprint; first-class columns are safer than overloaded JSONB alone. No historical backfill. Head confirmed as `016_phase6a6_cf_foundation` before naming.

Keep revision id ≤32 chars.

---

## 12. Part 2 insertion point (confirmed)

```
_maybe_run_phase6a5_hypothesis_retrieval
→ _maybe_run_phase6a5_evidence_assessment
→ _maybe_run_phase6a6_counterfactual_foundation
    → Part 1: context / constraints / plan / skeletons
    → Part 2: CounterfactualRemediationGenerationService  # NEW, flag-gated
    → persist (when persistence enabled)
→ _persist_results   # product recommendations unchanged
```

Preferred wiring: call generation from foundation `run_async` after plans/skeletons and before persist, **or** as a sibling soft-fail method immediately after foundation that updates the same remediation run. Do not invent a second RAG engine or overwrite diagnosis.

Gates: `RULE_REMEDIATION_GENERATION_ENABLED`, `LLM_REMEDIATION_GENERATION_ENABLED`, plus nested validation/risk/ranking flags — all default OFF.

---

## 13. LLM infrastructure to reuse

- `OpenAIReasoningProvider` / `LocalGroundedReasoningProvider` patterns (JSON, circuit breaker, retries)
- New remediation-specific prompt + schema versions (not `validate_recommendation_output`)
- Secret masking before any prompt assembly

---

## 14. Test baseline note

Part 1 added 28 dedicated tests. Container closeout after Part 1: **544 passed, 3 skipped, 2 deselected**. Host vs container collect gap remains corpus/benchmark mount + `embedding_integration` deselection (documented in Part 1 audit).

---

## 15. Audit conclusion

Part 1 is a complete foundation with empty-change skeletons and unimplemented template builders. Part 2 implements deterministic and structured generators, patch rendering without mutating originals, static risk/blast/side-effect analysis, dedupe/diversity, and prioritisation for **future** verification — still never applying or executing verifiers.

Implementation may proceed after this audit lands.
