# Embedding setup — local sentence-transformers (Step 4)

DevGuard AI supports two embedding providers:

| Provider | Purpose |
|----------|---------|
| `hash` | Deterministic offline / unit-test baseline (default) |
| `sentence_transformers` | Real local semantic embeddings via Sentence Transformers |

Hash embeddings are **not** a production semantic model. They remain for tests, minimal installs, and offline development.

Sentence-transformer embeddings run **locally** on CPU by default. There is **no external embedding API charge**. Local execution still uses CPU, memory, and time.

## Default model

- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Typical dimension: **384** (read from the model at load time — not hard-coded as the only permitted size)
- Default device: **cpu** (stability over speed; MPS/CUDA available when explicitly configured)

## Configuration

```bash
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
EMBEDDING_BATCH_SIZE=16
EMBEDDING_NORMALIZE=true
EMBEDDING_MAX_INPUT_CHARACTERS=12000
EMBEDDING_STRICT_STARTUP_VALIDATION=false
```

Approved devices: `cpu`, `mps`, `cuda`, `auto`.

- Explicit `mps` / `cuda` fail clearly when unavailable (no silent device swap).
- `auto` prefers cuda → mps → cpu.

Keep Chroma settings from Step 3:

```bash
RAG_BACKEND=chroma
CHROMA_HOST=chroma          # inside Compose
CHROMA_PORT=8000
# Host scripts: CHROMA_HOST=localhost CHROMA_PORT=8001
CHROMA_COLLECTION_NAME=devguard_knowledge
```

## Install

Backend image / local venv:

```bash
pip install -r requirements.txt
# or: pip install -e ".[ai]"
```

`sentence-transformers` pulls a CPU-compatible PyTorch stack. Do not install CUDA wheels in the Mac development container unless you intentionally need them.

## Model download and cache

The first load downloads the model from Hugging Face (network required once).

Docker Compose mounts a named volume `model_cache` at `/root/.cache` so recreation of the backend container does not re-download the model. This volume is separate from `chroma_data` and `postgres_data`.

First start / warm-up can take several minutes depending on network and disk.

## Warm-up

```bash
docker compose exec backend python -m app.cli.warmup_embeddings
```

Expected summary fields: Provider, Model, Device, Dimension, Normalised, Status.

Does **not** write to Chroma.

## Smoke test (embeddings + temporary Chroma)

```bash
docker compose exec backend \
  python -m app.cli.test_embeddings \
  --text "AWS AccessDenied during deployment" \
  --compare-text "IAM permission denied while deploying" \
  --with-chroma
```

Uses temporary collection `devguard_embedding_smoke_test` only — never modifies `devguard_knowledge` during the smoke test. The temporary collection is deleted afterwards.

## How Chroma uses vectors

1. Documents are sanitised (secret masking) then embedded with `embed_documents`.
2. Queries use `embed_query` with the same model/device/normalisation.
3. Collection metadata stores a safe embedding identity (provider, model, dimension, normalised, config hash).
4. Upsertting into a non-empty collection with a mismatched identity raises a clear compatibility error — collections are **never** auto-deleted. Rebuild later with an explicit `--recreate` ingestion path when approved.

## Character vs token limits

`EMBEDDING_MAX_INPUT_CHARACTERS` is an application-level defensive bound. It is **not** equivalent to the model’s token limit. Prefer chunked knowledge documents from the ingestion pipeline for long content.

## Switch back to hash

```bash
EMBEDDING_PROVIDER=hash
```

Unit tests and offline CI should keep `hash` as the default.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Import / optional dependency error | Install `sentence-transformers` (requirements / `[ai]`) |
| Device configuration error | Use `EMBEDDING_DEVICE=cpu` |
| Model load failure | Network for first download; valid `EMBEDDING_MODEL` |
| Collection identity mismatch | Do not mix hash and MiniLM vectors in one collection; recreate explicitly |
| Slow first request | Run `warmup_embeddings`; confirm `model_cache` volume |

## Honest limitations

- First model load may be slow.
- CPU inference is slower than GPU.
- Character limits approximate token limits.
- Semantic retrieval quality still requires evaluation against DevOps incidents.
- Local compute is not “free” in resource terms — only external API cost is `not_applicable`.
