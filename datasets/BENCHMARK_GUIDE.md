# BENCHMARK_GUIDE — Human Gold Retrieval Benchmark

## Purpose

Provide a reusable, academically defensible retrieval evaluation set for DevGuard AI.  
This replaces heuristic Phase-6 category matching with graded human relevance labels.

## Benchmark structure

| Asset | Description |
|-------|-------------|
| `queries.csv` | ~130 realistic engineer questions with metadata |
| `gold_labels.csv` | Human-approved graded relevance (0–3) |
| `gold_labels.candidates.csv` | Auto-proposed labels pending review |
| `categories.csv` | Category group catalogue |
| `benchmark_metadata.json` | Benchmark/corpus versioning |
| `evaluation_config.json` | Metrics + retriever defaults |
| `review/` | Human review worksheets |
| `results/` | Per-run JSON/CSV/Markdown/charts |

## Queries

Each query includes:

- `technology`, `failure_category`, `pipeline_stage`
- `expected_technologies`, `expected_vendors`
- `difficulty` ∈ {easy, medium, hard}
- `category_group` for reporting slices

## Gold labels

Graded relevance:

| Grade | Meaning |
|------:|---------|
| 3 | Highly relevant |
| 2 | Relevant |
| 1 | Partially relevant |
| 0 | Not relevant |

Binary metrics (P/R/MRR/Hit/MAP) treat grade **≥ 2** as relevant.  
nDCG uses the full 0–3 scale.

### Human approval workflow

1. `retrieve_candidates.py` retrieves top-20 hits and proposes grades.
2. Reviewer edits `review/candidate_review.csv`.
3. `promote_labels.py` writes approved rows into `gold_labels.csv`.
4. Evaluation defaults to official gold only.

## Metrics

Implemented in `scripts/dataset/benchmark/metrics.py` and aggregated by `evaluate_benchmark.py`:

- Precision@1, @3, @5
- Recall@5, @10
- MRR, MAP
- nDCG@5, @10
- Hit rate
- Latency (mean / p50)
- Category accuracy
- Vendor coverage

## Evaluation process

```bash
export CHROMA_HOST=localhost CHROMA_PORT=8001
export EMBEDDING_PROVIDER=sentence_transformers EMBEDDING_DEVICE=cpu

cd backend
python -m app.cli.evaluate_benchmark \
  --top-k 5 \
  --save-json \
  --save-markdown \
  --save-charts
```

Outputs land under `datasets/benchmark/results/run_<timestamp>_<labels>/`.

## Versioning

Each run records:

- Benchmark version
- Corpus version
- Embedding model + dimension
- Retriever version
- Evaluation date
- Labels mode (`gold` | `candidates`)

## Adding new queries

1. Append rows to `queries.csv` (unique `query_id`).
2. Re-run `retrieve_candidates.py` (or retrieve only new IDs manually).
3. Human-label and promote.
4. Bump `benchmark_version` in `benchmark_metadata.json` when the gold set changes meaningfully.

## Evaluating future corpus versions

1. Rebuild/index the research collection as usual.
2. Keep the same `queries.csv` + `gold_labels.csv`.
3. Re-run `python -m app.cli.evaluate_benchmark`.
4. Compare `results/` runs; do not mutate gold labels for convenience.

## What must never happen

- Do not write AI-only grades into `gold_labels.csv` without human accept.
- Do not evaluate against product collection `devguard_knowledge`.
- Do not modify Modules 1–9 APIs for this benchmark.
