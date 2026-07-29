# Human approval instructions

1. Open `candidate_review.csv` (or per-query markdown under `by_query/`).
2. For each row, set `human_relevance` to 0–3 (or leave blank to keep proposed).
3. Set `accept` to `Y` for rows that should enter official gold.
4. Prefer at least one grade ≥2 per query when evidence exists.
5. Run:

```bash
backend/.venv/bin/python scripts/dataset/benchmark/promote_labels.py
```

6. Re-run evaluation against `gold_labels.csv` (default).

Academic note: dissertation claims of human-validated gold require this approval step.
