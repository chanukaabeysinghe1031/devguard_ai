# Phase 6A.5 — Relevance Scoring

Version: `hypothesis_retrieval_relevance_v1`

Score field name: **`retrieval_relevance_score` only**.

Uses active-weight normalization over non-null feature components. Exact-identifier boost is optional (`HYPOTHESIS_EXACT_IDENTIFIER_BOOST_ENABLED`).

Limitations documented on each assessment: relevance ≠ causal support; exact matches can mislead.
