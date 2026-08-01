# Phase 6A.6 Part 2 — Deduplication

`RemediationCandidateDeduplicator` (`remediation_deduplicator_v1`) merges near-identical candidates while preserving distinct mechanisms (role vs permission vs resource-policy).

- Flag: `REMEDIATION_DEDUPLICATION_ENABLED` (default OFF)
- Diversity selector (`remediation_diversity_v1`) keeps mechanism variety under bounds
