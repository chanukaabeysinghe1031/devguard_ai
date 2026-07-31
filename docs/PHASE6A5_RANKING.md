# Phase 6A.5 — Hypothesis Ranking

Version: `hypothesis_ranking_v1`

Flag: `HYPOTHESIS_RANKING_ENABLED` (default OFF)

## RankingScore ≠ RootCauseConfidence

Outputs field `ranking_score` only. Highest ranked hypothesis is **not** a verified root cause.

## Weighted components (active-weight normalisation)

| Component | Role |
|-----------|------|
| support_score | From support analysis |
| sufficiency_score | Coverage / completeness |
| authority_score | Source authority mix |
| diversity_score | Source diversity (− duplicates) |
| retrieval_relevance | Mean item relevance |
| temporal / graph / docs / historical completeness | Sufficiency facets |
| parser_confidence | From parser evidence when present |
| generation_prior | Hypothesis generation prior |
| contradiction_penalty | Subtracted |

Deterministic for identical inputs (sort by score desc, then `hypothesis_id` asc).

## Tie signal

When top two scores differ by ≤ `RANKING_TIE_EPSILON` (default 0.02), ranking warnings include `top_scores_within_tie_epsilon`.
