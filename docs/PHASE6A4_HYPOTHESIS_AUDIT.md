# Phase 6A.4 — Competing Causal Hypothesis Audit

**Status:** Complete (implementation baseline)  
**Date:** 2026-07-31  
**Alembic head at audit:** `013_phase6a3_hier_class`  
**Next migration:** `014_phase6a4_hypotheses`

---

## 1. Current diagnosis (single-answer)

| Artifact | Behavior |
|----------|----------|
| `ClassificationCandidate` | Ranked labels + one `root_cause_summary` per candidate |
| Rank-1 prediction | Authoritative diagnosis after Module 8 fusion |
| `llm_root_cause` | Single grounded JSON; `alternative_causes` are free-text strings only |
| Recommendations | Category templates ± optional LLM adapt of **one** root cause |
| Evidence items | All linked to primary prediction |

There is **no** competing-hypothesis model today.

---

## 2. Reusable diagnosis logic

- `HybridClassifier` rule/keyword signals and frozen category codes
- Evidence extractor + `evidence-N` grounding IDs
- `RootCauseAnalyzer` provider interface, JSON validation, secret remask, local fallback
- OpenAI retry / circuit-breaker / budget recording patterns
- Soft-fail stage pattern from 6A.2 / 6A.3
- Hierarchical classification, open-set, disagreement, temporal, graph as **inputs**

---

## 3. Must stay separate from hypothesis generation

| Keep separate | Why |
|---------------|-----|
| Modules 6–9 primary prediction path | Flag-OFF contract |
| Baseline Module 9 RAG | Hypothesis-directed RAG = 6A.5 |
| Product recommendations | Hypothesis remediations = 6A.6 |
| Verifier execution | 6A.7 |
| Final ranking / verified confidence | 6A.5+ |
| Causal Analysis UI | 6A.9 |

---

## 4. Single-answer assumptions (must not break when OFF)

1. Rank-1 classification remains the API/UI diagnosis.
2. One primary prediction; evidence/recs attach to it.
3. Notifications use primary summary/category.
4. Fusion alternatives remain category codes, not hypotheses.
5. No `VERIFIED` status in this phase.

---

## 5. Exact insertion point

`AnalysisExecutionService.execute`:

```text
orchestrator.run(...)
→ _maybe_persist_artifact_bundle (+ 6A.2)
→ _maybe_run_phase6a3
→ _maybe_run_phase6a4   # NEW
→ _persist_results
```

Soft-fail only. Do not alter recommendations or global confidence.

---

## 6. Prompt risks

- Existing root-cause prompts bias toward “most likely” single cause — new hypothesis prompt must require **competing** explanations and forbid inventing IDs.
- Unvalidated free-text alternatives must not become persisted hypotheses.
- Full logs must not be stuffed into prompts; use bounded graph neighborhood + evidence excerpts.
- Secret masking remains mandatory before any LLM call.

---

## 7. Fallback behavior

| Condition | Behavior |
|-----------|----------|
| Flags OFF | No-op; identical to today |
| Rule generator only | Emit template hypotheses when evidence minimums met |
| LLM schema/ID fail | Reject malformed candidates; keep valid rule hypotheses |
| Open-set UNKNOWN | Do not force known-category hypotheses |
| Stage exception | Persist FAILED run summary; continue Modules 6–9 path |

---

## 8. Schema outline (additive)

- `causal_hypothesis_runs` — per-analysis generation run metadata
- `causal_hypotheses` — competing claims + prior score + path JSON + observations
- `hypothesis_evidence_links` — SUPPORTS / CONTRADICTS / MISSING / …
- `hypothesis_critic_results` — structured critic decisions

No historical backfill. Org + analysis scoped.
