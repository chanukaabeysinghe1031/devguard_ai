# Retrieval Architecture Comparison

Primary: `devguard_research_knowledge`
Secondary: `devguard_product_minilm`
Queries: 130 (gold labels)

## Aggregate metrics

- Single: `{"precision@1": 0.7462, "precision@3": 0.7333, "precision@5": 0.7231, "recall@5": 0.3096, "recall@10": 0.5354, "mrr": 0.8276, "map": 0.4444, "ndcg@5": 0.7096, "ndcg@10": 0.7306, "hit_rate": 0.9615, "latency_ms": 33.153, "duplicate_rate": 0.0, "source_diversity": 1.7154, "official_documentation_coverage": 0.8231, "github_incident_coverage": 0.0, "product_knowledge_coverage": 0.0, "p50_latency_ms": 21.6239, "p95_latency_ms": 53.6169, "mean_latency_ms": 33.153}`
- Federated: `{"precision@1": 0.7, "precision@3": 0.6872, "precision@5": 0.6862, "recall@5": 0.2984, "recall@10": 0.5179, "mrr": 0.7979, "map": 0.417, "ndcg@5": 0.6729, "ndcg@10": 0.7007, "hit_rate": 0.9615, "latency_ms": 28.1052, "duplicate_rate": 0.5, "source_diversity": 1.9308, "official_documentation_coverage": 0.8231, "github_incident_coverage": 0.0, "product_knowledge_coverage": 0.0, "p50_latency_ms": 27.8495, "p95_latency_ms": 31.3791, "mean_latency_ms": 28.1052}`

## Decision

**Default mode:** `primary_only`

Keep primary collection as default. Federated mode is optional and should remain disabled unless secondary corpus value outweighs added latency.

## Trade-offs

- Federated merge increases latency (extra collection query + dedupe).
- Gold labels score research document IDs; product chunks rarely raise Precision/nDCG.
- Product secondary improves operational diagnosis grounding for live incidents.
- Server flag / env controls federation; clients cannot bypass.
