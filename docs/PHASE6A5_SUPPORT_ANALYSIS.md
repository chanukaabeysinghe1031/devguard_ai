# Phase 6A.5 — Support Analysis

Version: `support_analysis_v1`

## Scope

Aggregates `SUPPORT_CANDIDATE` item assessments into a per-hypothesis **support_score** ∈ [0, 1].

## Components (active-weight normalised)

- `support_candidate_strength`
- `authority_weighted_support`
- `exact_identifier_overlap`
- `relevance_mean`
- small count bonus for multiple independent support candidates

## Explicit limitations

- `support_score_is_not_root_cause_confidence`
- `support_candidates_are_not_causal_confirmation`

Support candidates are evidence that *may* align with the hypothesis claim — not verified confirmation.
