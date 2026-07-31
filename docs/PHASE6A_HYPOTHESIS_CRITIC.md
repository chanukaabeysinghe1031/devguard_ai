# Phase 6A — Hypothesis Critic

`CausalHypothesisCritic` (`critic_v1`) reviews candidates for:

- downstream symptoms vs earliest meaningful cause
- missing / contradicting evidence
- graph path conflicts
- over-specific claims without evidence
- open-set UNKNOWN forcing known categories

Decisions: `ACCEPT_FOR_RANKING`, `ACCEPT_WITH_WARNINGS`, `INCOMPLETE`, `CONTRADICTED`, `REJECT`.

The critic does **not** create verifier results.
