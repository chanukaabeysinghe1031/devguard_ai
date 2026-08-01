# Phase 6A.6 Part 2 — Prioritisation

`RemediationCandidatePrioritiser` orders unverified candidates for later verification.

- Version: `remediation_candidate_prioritiser_v1`
- Flag: `REMEDIATION_RANKING_ENABLED` (default OFF)
- Score name: `candidate_priority_score` — never verification/causal/success confidence
- Prefers wrong-role corrections over policy broadening; penalises wildcards/high blast radius
- Statuses: PRIORITY / ALTERNATIVE / HIGH_RISK / INCOMPLETE / REJECTED / NO_SAFE_CANDIDATE
