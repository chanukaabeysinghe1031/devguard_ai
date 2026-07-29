# DevGuard AI — Datasets (Phase 1)

Research corpus assets for classification, RAG knowledge, and retrieval evaluation.

This tree follows `docs/MASTER_ARCHITECTURE.md` §9.2. It is **separate** from:

- runtime PostgreSQL incident tables
- the small curated markdown under `knowledge_base/` (enrichment only)

## Layout

```text
datasets/
├── VERSION
├── README.md
├── DATASET_CARD.md
├── ANNOTATION_GUIDE.md
├── schemas/
│   ├── incident.schema.json
│   ├── knowledge_chunk.schema.json
│   └── retrieval_query.schema.json
├── manifests/
│   └── collection_targets.json
├── raw/github/          # GitHub Issues API downloads
├── raw/docs/            # Official documentation (later phase)
├── sanitized/
├── labelled/
├── synthetic/
├── processed/
└── reports/
```

## Phase 1 scope

| Included | Excluded |
|----------|----------|
| Directory layout + schemas | Full knowledge-base product ingest |
| GitHub Issues API collector | HTML scraping |
| Provenance fields + secret masking on collect | Chroma indexing of the full corpus |
| Collection targets for ~300–600 curation | OpenAI / GPT reasoning |
| Incident JSON validator | Embedding generation at scale |

## Collect issues

Optional but recommended: set a GitHub token for higher API rate limits.

```bash
export GITHUB_TOKEN=ghp_your_token_here   # never commit

# Single repository (smoke)
python scripts/dataset/collect_github_issues.py \
  --repo actions/runner \
  --labels bug \
  --max-issues 5 \
  --technology github_actions \
  --failure-category configuration_failure

# Curated target list (bounded max_issues per repo)
python scripts/dataset/collect_github_issues.py --from-targets

# Open/unresolved evaluation set (separate folder; ~20 per repo)
python scripts/dataset/collect_github_issues.py --open-eval-set

# Dry run (no files written)
python scripts/dataset/collect_github_issues.py --repo actions/runner --max-issues 3 --dry-run
```

Validate:

```bash
python scripts/dataset/validate_incidents.py
```

Closed issues live under `datasets/raw/github/` (knowledge candidates).  
Open issues live under `datasets/raw/github_open/` (symptom / eval add-on).

## Phase 2 — Clean & normalise

```bash
python scripts/dataset/clean_incidents.py
# closed only:
python scripts/dataset/clean_incidents.py --skip-open

python scripts/dataset/validate_incidents.py datasets/sanitized
```

Outputs:

- `datasets/sanitized/github/` — cleaned closed candidates
- `datasets/sanitized/github_open/` — cleaned open eval set
- `datasets/reports/phase2_clean_report.json` — counts and reject reasons
- `datasets/reports/phase2_rejected.jsonl` — rejected raw paths (local)

Cleaning removes spam/+1 titles, short/empty text, weak failure signal (closed pool), near-duplicates, re-applies secret masking, and normalises whitespace/HTML comments/emoji noise.

## Phase 3 — Extract knowledge

```bash
python scripts/dataset/extract_knowledge.py
# closed pool only:
python scripts/dataset/extract_knowledge.py --skip-open
```

Outputs:

- `datasets/labelled/github/` — incidents with extracted `symptoms` / `root_cause` / `resolution`
- `datasets/labelled/github_open/` — open issues kept as `curation_candidate` only
- `datasets/processed/knowledge/curated/` — high-confidence knowledge records
- `datasets/processed/knowledge/candidates/` — medium/low candidates for review
- `datasets/reports/phase3_extract_report.json`

Extraction is **heuristic** (issue-template sections + cause/fix patterns). It does not call GPT. Human review can promote candidates before chunking.

## Phases 4–7 — Chunk, embed, evaluate, diagnose

Uses a **separate** Chroma collection: `devguard_research_knowledge` (does not replace product `devguard_knowledge`).

```bash
export CHROMA_HOST=localhost CHROMA_PORT=8001
export EMBEDDING_PROVIDER=sentence_transformers EMBEDDING_DEVICE=cpu

# Prefer backend venv (sentence-transformers installed there)
backend/.venv/bin/python scripts/dataset/run_knowledge_pipeline.py --include-candidates --recreate-collection

# Local grounded diagnosis (default)
backend/.venv/bin/python scripts/dataset/run_knowledge_pipeline.py --skip-index --skip-eval \
  --diagnose "AWS AccessDenied during deployment" --llm local

# Optional OpenAI (requires billing quota)
backend/.venv/bin/python scripts/dataset/run_knowledge_pipeline.py --skip-index --skip-eval \
  --diagnose "AWS AccessDenied during deployment" --llm openai
```

Outputs:

- `datasets/processed/chunks/` — chunk JSON (~600–900 chars)
- Chroma collection `devguard_research_knowledge`
- `datasets/reports/phases4_7_pipeline_report.json` — index + P@k/MRR/nDCG + diagnosis summary
- Eval queries: `datasets/manifests/retrieval_eval_queries.json`

## Official documentation enrichment (`0.5.0-official-docs`)

Adds authoritative vendor docs into the **same** research collection without touching product `devguard_knowledge`.

See `datasets/OFFICIAL_DOCUMENTATION_CORPUS.md`.

```bash
export CHROMA_HOST=localhost CHROMA_PORT=8001
export EMBEDDING_PROVIDER=sentence_transformers EMBEDDING_DEVICE=cpu EMBEDDING_BATCH_SIZE=16

backend/.venv/bin/python scripts/dataset/download_official_docs.py
backend/.venv/bin/python scripts/dataset/run_official_docs_pipeline.py
```

## Human gold retrieval benchmark (`1.0.0-human-gold`)

See `datasets/BENCHMARK_GUIDE.md` and `datasets/benchmark/README.md`.

```bash
backend/.venv/bin/python scripts/dataset/benchmark/generate_queries.py
backend/.venv/bin/python scripts/dataset/benchmark/retrieve_candidates.py --top-k 20
# Human review: edit datasets/benchmark/review/candidate_review.csv then:
backend/.venv/bin/python scripts/dataset/benchmark/promote_labels.py --reviewed-by your_name
cd backend && python -m app.cli.evaluate_benchmark --top-k 5 --save-json --save-markdown --save-charts
```

Official `gold_labels.csv` requires human approval. Candidate labels are for review only.

## Curation target

Aim for **300–600** high-quality **resolved** incidents with clear failure signal after Phase 2–3. Prefer issues where root cause / resolution can later be filled. Reject spam, +1 threads, and unclear failures (`datasets/ANNOTATION_GUIDE.md`).

## Authority

When this README conflicts with architecture docs, follow:

1. `docs/MASTER_ARCHITECTURE.md`
2. `docs/PROJECT_CONSTITUTION.md`
3. `docs/DATASET_SPECIFICATION.md`
