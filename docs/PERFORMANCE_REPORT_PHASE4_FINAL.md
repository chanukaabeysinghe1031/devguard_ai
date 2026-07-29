# Performance Report — Phase 4 Final

## Environment

| Item | Value |
|------|-------|
| Host | Apple M1, 8 GB RAM (darwin) |
| Runtime | Host venv + live Chroma (`localhost:8001`) / Docker stack healthy |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` (CPU) |
| Primary collection | `devguard_product_minilm` |
| Secondary collection | `devguard_research_knowledge` (federated stages) |
| OpenAI | Not called (local fallback only) |
| Corpus | Existing Chroma volumes (not wiped for this run) |
| Machine-readable | `reports/performance/phase4/stage_latency.json` |

Retrieval note: primary=devguard_product_minilm; secondary=devguard_research_knowledge

| Stage | n | mean ms | p50 ms | p95 ms | stdev |
|-------|---|---------|--------|--------|-------|
| classification_small_cold | 5 | 0.081 | 0.067 | 0.134 | 0.027 |
| classification_small_warm | 40 | 0.056 | 0.056 | 0.058 | 0.001 |
| classification_large_warm | 15 | 30.329 | 30.246 | 30.618 | 0.353 |
| secret_masking_medium | 40 | 0.051 | 0.050 | 0.052 | 0.001 |
| signals_and_query_construction | 30 | 0.264 | 0.261 | 0.280 | 0.007 |
| embedding_query_warm | 15 | 5.872 | 5.731 | 6.156 | 0.550 |
| primary_retrieval_warm | 10 | 10.711 | 9.680 | 16.758 | 2.124 |
| secondary_retrieval_warm | 10 | 10.758 | 10.462 | 12.647 | 0.841 |
| federated_merge_dedupe_warm | 10 | 13.880 | 14.021 | 16.791 | 1.287 |
| local_fallback_reasoning | 20 | 0.149 | 0.141 | 0.170 | 0.018 |

## Limitations

- OpenAI reasoning latency is not measured in the default suite (avoids paid calls).
- Cold sentence-transformers model download is excluded; first embed may still warm caches.
- Database persistence and full HTTP request duration require the optional live harness.
- Federated stages run only when `CHROMA_SECONDARY_COLLECTION_NAME` is set.
