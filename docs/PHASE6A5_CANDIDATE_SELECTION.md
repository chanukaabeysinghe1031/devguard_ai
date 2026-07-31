# Phase 6A.5 — Candidate Selection

Version: `candidate_selection_v1`

Flag: `CANDIDATE_SELECTION_ENABLED` (default OFF)

## Statuses

| Status | Meaning |
|--------|---------|
| `TOP_CANDIDATE` | Single clear winner |
| `TOP_N` | Clear winner + up to `MAX_CANDIDATE_HYPOTHESES` listed |
| `TIE` | Top scores within `RANKING_TIE_EPSILON` — no single top id |
| `WEAK_EVIDENCE` | Top `ranking_score` < `MIN_RANKING_SCORE_FOR_TOP_CANDIDATE` |
| `UNKNOWN` | No ranked hypotheses |

## Explicit limitations

- Selected candidates are **not** verified root causes
- Candidate selection is **not** final diagnosis
- No abstention / remediations / verifiers in this stage

## Bounds

- `MAX_CANDIDATE_HYPOTHESES=5`
- `MIN_RANKING_SCORE_FOR_TOP_CANDIDATE=0.40`
- `RANKING_TIE_EPSILON=0.02`
