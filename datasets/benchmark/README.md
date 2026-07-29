# DevGuard AI — Human Gold Retrieval Benchmark

**Benchmark version:** `1.0.0-human-gold`  
**Target corpus:** `0.5.0-official-docs`  
**Collection:** `devguard_research_knowledge` (never `devguard_knowledge`)

## Academic integrity (read first)

Official gold labels in `gold_labels.csv` must be **human-approved**.

| File | Role |
|------|------|
| `gold_labels.candidates.csv` | Retrieval-assisted **proposals** only |
| `review/candidate_review.csv` | Human review worksheet |
| `gold_labels.csv` | Official gold after promotion |

Do **not** claim AI-proposed grades as human ground truth in the dissertation.

## Layout

```text
datasets/benchmark/
├── queries.csv
├── gold_labels.csv
├── gold_labels.candidates.csv
├── categories.csv
├── benchmark_metadata.json
├── evaluation_config.json
├── README.md
├── review/
│   ├── APPROVAL_INSTRUCTIONS.md
│   ├── candidate_review.csv
│   └── by_query/
└── results/
```

## Quick start

```bash
# 1) Materialise query set / metadata
backend/.venv/bin/python scripts/dataset/benchmark/generate_queries.py

# 2) Retrieve top-20 + propose candidate grades
export CHROMA_HOST=localhost CHROMA_PORT=8001
export EMBEDDING_PROVIDER=sentence_transformers EMBEDDING_DEVICE=cpu
backend/.venv/bin/python scripts/dataset/benchmark/retrieve_candidates.py --top-k 20

# 3) Human review: edit review/candidate_review.csv (accept=Y, human_relevance=0..3)
backend/.venv/bin/python scripts/dataset/benchmark/promote_labels.py --reviewed-by your_name

# 4) Evaluate official gold
cd backend
python -m app.cli.evaluate_benchmark --top-k 5 --save-json --save-markdown --save-charts
```

Candidate-only smoke (not dissertation gold):

```bash
python -m app.cli.evaluate_benchmark --labels candidates --top-k 5 --save-json --save-markdown
```

## Metrics

Precision@1/3/5 · Recall@5/10 · MRR · MAP · nDCG@5/10 · Hit Rate · Latency · Category accuracy · Vendor coverage

## Regression reuse

Keep `queries.csv` + approved `gold_labels.csv` fixed. Re-run evaluation when corpus/embeddings/retriever change; record versions in each results run.
