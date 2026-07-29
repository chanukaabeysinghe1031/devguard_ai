# Official Documentation Corpus (Research)

**Corpus version:** `0.5.0-official-docs`  
**Collection:** `devguard_research_knowledge`  
**Does not modify:** product collection `devguard_knowledge`

## Architecture

Official vendor documentation is a **second research source** alongside the GitHub incident corpus.

```text
datasets/raw/docs/{vendor}/
  README.md
  manifest.json          # approved hosts + technology defaults
  source_list.json       # approved URLs only
  downloads/*.html       # raw HTML (gitignored)
  download_manifest.json # etag / hash / retrieved (gitignored)

        │ download_official_docs.py
        ▼
parse + mask_secrets + metadata
        │ run_official_docs_pipeline.py
        ▼
datasets/processed/docs/parsed/*.json
datasets/processed/docs/chunks/*.json
        │ SentenceTransformerEmbeddingProvider (MiniLM, 384-d, batch 16)
        ▼
Chroma upsert → devguard_research_knowledge
  metadata.source_type = official_documentation
```

Shared infrastructure (not duplicated):

| Concern | Reused component |
|---------|------------------|
| Chunking | `app.ai.rag.chunker.chunk_markdown` via `chunk_utils.chunk_official_document` |
| Embeddings | `SentenceTransformerEmbeddingProvider` |
| Vector store | `ChromaVectorStore` |
| Secret masking | `mask_secrets` |
| Research collection | `devguard_research_knowledge` |

## Downloader

```bash
backend/.venv/bin/python scripts/dataset/download_official_docs.py
backend/.venv/bin/python scripts/dataset/download_official_docs.py --vendor aws --vendor docker
```

Behaviour:

- Only hosts listed in each vendor `manifest.json` / `approved_hosts`
- Respects `robots.txt` when readable
- Retries transient failures
- Skips unchanged files via content hash and conditional `ETag` / `Last-Modified`
- Logs failures without aborting sibling downloads

## Metadata

Each parsed document records: `document_id`, `vendor`, `technology`, `category`, `version`, `url`, `section`, `heading_hierarchy`, `language`, `document_hash`, `source_type=official_documentation`.

Each chunk inherits vendor/technology/category/url/section/version and adds `chunk_hash`.

## Chunking

- Target size **600–1000** characters (default **900**)
- Default **100** character overlap on hard-splits only
- Heading-aware split; prefers not cutting mid-fence / mid-table when a section already fits
- **No second chunking algorithm** — always `chunk_markdown`

## Versioning

| Field | Value |
|-------|-------|
| Previous | `0.4.0-phases4-7` |
| Current | `0.5.0-official-docs` |
| Report | `datasets/reports/official_docs_report.json` |
| VERSION file | `datasets/VERSION` |

## Updating documents

1. Edit `source_list.json` (add/remove approved URLs).
2. Re-run the downloader (unchanged hashes are skipped).
3. Re-run `run_official_docs_pipeline.py` (upserts / skips duplicates; **does not recreate** the collection).

## Rebuilding embeddings

To rebuild **only** documentation vectors, re-run the official-docs pipeline (idempotent upsert).  
To rebuild the **entire** research collection including GitHub incidents, use the existing `run_knowledge_pipeline.py --recreate-collection` **then** re-run the official-docs pipeline. Never point either tool at `devguard_knowledge` for this work.

## Adding new vendors

1. Create `datasets/raw/docs/<vendor>/{README.md,manifest.json,source_list.json}`.
2. Restrict `approved_hosts` to official documentation domains.
3. Add the vendor directory name to `VENDOR_DIRS` in `download_official_docs.py`.
4. Download → pipeline → confirm retrieval mixes GitHub + docs for a smoke query.

## Approved vendors (this phase)

AWS, Docker, Terraform, GitHub Actions, Kubernetes, Python, OpenJDK / Maven / Gradle (under `java/`), Node.js / npm (under `node/`).

Forbidden: Medium, Stack Overflow, blogs, personal sites, unknown mirrors.
