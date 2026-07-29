# DevGuard AI Phase 4 Performance Report

Date: 2026-07-29  
Environment: Local Docker Compose (backend + postgres + chroma)

## Measurement Scope

- Classification latency
- Retrieval latency (embedding + vector query)
- Reasoning latency (local/OpenAI depending on route)
- End-to-end analysis duration

## Baseline Observations

- Stage-level latencies are already persisted in `output_summary.stages`.
- Module 8 metadata includes budget, provider usage, and total latency metrics.
- Retrieval quality and selected route are persisted for post-hoc analysis.

## Current Measurements (Spot Checks)

- Federated retrieval query (`self-hosted runner is offline GitHub Actions`) returns runner KB top hits from new CI runner document with high similarity.
- Classifier regression suite executes quickly and deterministically in local test environment.

## Bottleneck Indicators

- First-time sentence-transformer model load can dominate startup latency.
- OpenAI latency is external-network dependent; previous implementation had no bounded retry/timeout controls.
- Background-task timing/transaction visibility can affect integration test stability if execution mode/config differs.

## Optimizations Applied in Phase 4 Pass

1. OpenAI request timeout + retry with exponential backoff.
2. Circuit-breaker behavior for repeated provider failures.
3. Provider token/latency usage captured and propagated into orchestration budget accounting.
4. Federated retrieval option to improve relevance without re-embedding duplication.

## Recommended Next Measurements

- Add automated benchmark command producing:
  - p50/p95/p99 for each stage (`classifying`, `retrieving_knowledge`, `reasoning`)
  - per-provider latency and token usage histograms
  - retrieval hit-rate by category
- Run with at least 30 deterministic scenarios and 3 repeats each.
