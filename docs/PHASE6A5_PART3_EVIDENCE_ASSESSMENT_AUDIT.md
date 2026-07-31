# Phase 6A.5 Part 3 — Evidence Assessment Audit

**Status:** Approved for implementation (Part 3)  
**Scope:** Evidence sufficiency, contradiction analysis, hypothesis ranking, candidate selection  
**Date:** 2026-08-01

## 1. Goal

Turn hypothesis-scoped retrieved evidence (Part 1B/Part 2) into **deterministic candidate assessments** — support candidates, contradiction candidates, sufficiency levels, ranking scores, and top-N selection — **without** claiming proven root cause, remediations, verifiers, abstention, or final diagnosis.

## 2. Reuse inventory

### 2.1 Hypothesis retrieval domain (`backend/app/domain/hypothesis_retrieval/`)

| Asset | Reuse for Part 3 |
|-------|------------------|
| `HypothesisRetrievedItem` | Primary evidence unit — relation_candidate, scores, source_type, metadata |
| `RetrievalValidationResult` | Validation status / warnings influence assessment confidence and penalties |
| `HypothesisRetrievalSession` | Hypothesis-scoped container; `metrics` JSONB for per-hypothesis assessments |
| `HypothesisRetrievalRun` | Analysis-scoped run; `configuration_snapshot` JSONB for ranking / selection |
| `HypothesisRetrievalRelevanceAssessment` | Part 2 relevance score as ranking/support input (**not** causal proof) |
| `RetrievalItemRelation` | `SUPPORT_CANDIDATE` / `CONTRADICTION_CANDIDATE` / `CONTEXT` / `UNKNOWN` — already candidate language |
| `RetrievalCandidateFeatureVector` | Exact identifier overlap, authority, graph distance features |

### 2.2 Causal / graph / temporal (read-only inputs)

| Asset | Reuse |
|-------|-------|
| `CausalHypothesis` + critic decision | Prior score, claim, expected/falsifying observations, open-set / disagreement flags via retrieval context |
| Evidence graph (via session `context_snapshot`) | Graph completeness / inconsistency warnings |
| Temporal localisation (via context) | Temporal completeness signals |

Part 3 **does not** mutate causal hypothesis rows’ core claim/status fields. Optional summary may be mirrored into session metrics only.

### 2.3 Part 2 item metadata

Items already carry (when Part 2 enabled):

- `item_metadata.retrieval_relevance_score`
- `item_metadata.features` (feature vector)
- `item_metadata.relevance_assessment` / validation notes under session `metrics.intelligence`

Part 3 reads these when present; falls back to `retrieval_score` and `relation_candidate` when absent.

## 3. Persistence capacity — migration 016 **NOT required**

Existing JSONB columns are sufficient:

| Store | Key | Content |
|-------|-----|---------|
| `hypothesis_retrieval_sessions.metrics` | `evidence_assessment` | Per-item assessments, support, contradiction, sufficiency for that hypothesis |
| `hypothesis_retrieval_runs.configuration_snapshot` | `evidence_assessment` | Run-level versions, ranking result, candidate selection, config flags |
| `AnalysisContext.options` | `hypothesis_evidence_assessment` | Soft summary for analysis output (status, top candidate ids, warnings) |

**Decision:** Prefer **no Alembic migration 016**. No new tables/columns. Updates are in-place JSONB merges after retrieval completes.

Hard need for 016 would only arise if assessments must be queryable as first-class rows with indexes — deferred (MSc scope uses debug read APIs over JSONB).

## 4. Insertion point

```text
_maybe_run_phase6a4
→ _maybe_run_phase6a5_hypothesis_retrieval   # Parts 1B/2
→ _maybe_run_phase6a5_evidence_assessment    # Part 3 (NEW; soft-fail)
→ _persist_results
```

Master flag `HYPOTHESIS_EVIDENCE_ASSESSMENT_ENABLED=false` → no-op (Parts 1B/2 unchanged).

## 5. Language constraints (frozen)

Allowed assessment types only:

- `SUPPORT_CANDIDATE`
- `CONTRADICTION_CANDIDATE`
- `CONTEXT_ONLY`
- `INSUFFICIENT`
- `AMBIGUOUS`
- `UNRELATED`

**Forbidden:** PROVEN, VERIFIED, TRUE, FALSE, confirmed root cause, causal proof.

`RankingScore` ≠ `RootCauseConfidence`. Highest ranked ≠ verified root cause.

## 6. Soft-fail / isolation

- Soft-fail: exceptions become warnings; never fail the analysis run alone.
- Hypothesis-scoped assessment; org-scoped API reads.
- Do not overwrite `diagnosis`, `recommendations`, or baseline `retrieved_documents` / chunks.
- No LLM, remediations, verifiers, abstention, or final diagnosis in Part 3.

## 7. Package placement

New packages for clarity:

- `backend/app/domain/evidence_assessment/`
- `backend/app/ai/evidence_assessment/`

Reuse hypothesis_retrieval models as **inputs**; do not fork retrieved-item schemas.

## 8. Out of scope

- Migration 016 / new ORM tables
- Frontend / branding WIP
- Causal UI
- Module 10 multi-agent prompts
- Changing frozen taxonomy or org roles
