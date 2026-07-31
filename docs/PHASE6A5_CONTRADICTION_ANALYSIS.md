# Phase 6A.5 — Contradiction Analysis

Version: `contradiction_analysis_v1`

Flag: `CONTRADICTION_ANALYSIS_ENABLED` (default OFF)

## Scope

Identifies `CONTRADICTION_CANDIDATE` assessments and derives a **contradiction_penalty** ∈ [0, 1] used only as a ranking subtractor.

## Explicit limitations

- `contradiction_candidates_are_not_disproof`
- `contradiction_penalty_is_not_falsification`

A contradiction candidate does **not** falsify a hypothesis. Empty contradiction set does not prove the claim.
