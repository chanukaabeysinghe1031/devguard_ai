# DevGuard AI

**AI-Powered DevOps Incident Intelligence Platform**

DevGuard AI analyses CI/CD pipeline failures and Infrastructure-as-Code artefacts to classify failures, extract evidence, retrieve documentation, and produce explainable remediation recommendations — centred on an **incident investigation** lifecycle.

> **Important:** Architecture is frozen in `docs/`. Modules 1–9 and Phase 3–5 diagnosis validation remain. **Phase 5A** builds the incident-management business UI around existing APIs — see `docs/PHASE5A_IMPLEMENTATION_AUDIT.md`.

---

## Current Project Status

| Area | Status |
|------|--------|
| **Module 1 — Foundation** | ✅ Complete |
| **Module 2 — Schema evolution** | ✅ Complete (Alembic `001`–`007`, ADR-012 Accepted) |
| **Module 3 — Authentication** | ✅ JWT auth, refresh rotation/revocation, RBAC deps (`008_refresh_tokens`) |
| **Module 4 — Core Business APIs** | ✅ Organizations, projects, pipeline runs, incidents, notes, resolutions, analysis initiation |
| **Module 5 — File Upload Pipeline** | ✅ Secure uploads, local storage, validation, secret masking, analysis file association |
| **Module 6 — AI Execution Pipeline** | ✅ Deterministic staged analysis (rules/hybrid); RAG/LLM optional and off by default |
| **Module 7 — Grounded RAG + LLM** | ✅ Retrieval + structured reasoning with grounding checks and deterministic fallback |
| **Module 8 — Confidence/Cost Routing** | ✅ Confidence-aware execution routing and baseline mode control |
| **Module 9 — Hybrid Retrieval** | ✅ Embedding baseline + hybrid static + org-safe historical retrieval |
| **Phase 6A.1 — Artifact Bundle** | ✅ Parsers + GitHub acquisition (flags OFF by default) |
| **Phase 6A.2 — Temporal + Evidence Graph** | ✅ Localisation + typed graph + consistency (flags OFF by default) |
| **Phase 6A.3 — Hierarchical Classification** | ✅ Hierarchy + open-set + disagreement (flags OFF by default) |
| **Phase 6A.4 — Causal Hypotheses** | ✅ Competing candidates only (flags OFF by default) |
| **Phase 6A.5 Part 1B — Hypothesis retrieval** | ✅ Infrastructure only (flag OFF; no causal ranking) |
| **Phase 6A.5 Part 2 — Adaptive retrieval** | ✅ Intelligence path (all Part 2 flags OFF by default; no migration 016) |
| **Phase 6A.5 Part 3 — Evidence assessment** | ✅ Sufficiency / contradiction / ranking / candidates (all flags OFF; no migration 016) |
| **Step 3–4 — Chroma + MiniLM** | ✅ Persistent Chroma + local sentence-transformer embeddings |
| **Phase 1 — Dataset corpus kit** | ✅ Schemas + GitHub Issues API collector (no full ingest / no GPT) |
| **Frozen target architecture** | Incident-centred, organization-ready model (28 tables at head) |
| **Frontend product screens** | ✅ Phase 5A AppShell + incident workflow (see `docs/PHASE5A_*`) |
| **Phase 4 — Production hardening** | ✅ Complete — `docs/PHASE4_PRODUCTION_HARDENING.md` / tag `v0.9.0-phase4` |
| **Phase 5 — Release candidate validation** | ✅ See `docs/PHASE5_RELEASE_CANDIDATE_VALIDATION.md` |
| **Phase 5A — Incident business application** | ✅ Core + Module 5A.10 — `docs/PHASE5A_PRODUCTION_READINESS.md` / `v1.0.0-rc2` |
| **Phase 5B — GitHub Actions ingestion** | ✅ Implemented — `docs/PHASE5B_*` / ADR-005 (real App smoke optional/manual) |
| **Phase 5C — Multi-tenant org completeness** | ✅ Invites, org profile, System nav — see Phase 5C docs |
| **Phase 5D — Branding & loading UX** | ✅ Brand marks, auth transitions, project bootstrap — `docs/PHASE5D_BRANDING_AND_LOADING_UX.md` |

### Phase 5A product UI

- Index: [`docs/PHASE5A_PRODUCTION_READINESS.md`](docs/PHASE5A_PRODUCTION_READINESS.md)
- Audit: [`docs/PHASE5A_IMPLEMENTATION_AUDIT.md`](docs/PHASE5A_IMPLEMENTATION_AUDIT.md)
- E2E: [`docs/PHASE5A_E2E_REPORT.md`](docs/PHASE5A_E2E_REPORT.md)
- User manual: [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md)
- Branding / loading UX: [`docs/PHASE5D_BRANDING_AND_LOADING_UX.md`](docs/PHASE5D_BRANDING_AND_LOADING_UX.md)

### Phase 4 hardening (index)

- Full-system audit, API/OpenAPI validation, security matrix, E2E regression (34 scenarios)
- Single vs federated retrieval comparison (default: **primary-only**)
- Performance p50/p95 stage report, configuration audit, clean-start procedure
- Entry point: [`docs/PHASE4_PRODUCTION_HARDENING.md`](docs/PHASE4_PRODUCTION_HARDENING.md)

### What Modules 1–8 delivered

- FastAPI application shell with structured logging and request IDs
- React + TypeScript + Vite + Tailwind application shell
- PostgreSQL 16 via Docker Compose + Alembic migrations through `008`
- Auth: register/login/refresh/logout/me/change-password, bcrypt passwords, short-lived access JWTs, rotating refresh tokens
- Business APIs: org/membership, projects, pipeline runs, full incident workflow, notes, resolutions, analysis-run queue
- Secure incident file uploads with local storage abstraction, validation, checksums, secret masking
- Analysis orchestration: classify → evidence → optional RAG → template/LLM recommendations → persist
- Grounded RAG from curated `knowledge_base/` docs; citation rows in `retrieved_documents`
- Local grounded reasoner by default; optional OpenAI / ChromaDB / sentence-transformers via interfaces
- Confidence-aware and cost-aware routing (`rules_only`, `rules_rag`, `llm_only`, `rag_llm`, `confidence_routed`)
- Two-stage routing (initial before retrieval; post-retrieval after RAG) with typed routes and versioned policy
- Heuristic confidence calibration, evidence-quality / uncertainty / retrieval-quality evaluators
- Decimal budget enforcement, null-safe external cost, latency stage tracking, controlled diagnosis fusion
- Safe orchestration summaries on analysis detail responses; Module 8 metadata in `output_summary` JSON (no schema migration)
- Hybrid retrieval modes: `embedding_only` (Module 7 baseline), `hybrid_static`, `hybrid_with_history` (org-scoped; off by default)
- Phase 6A.5 Part 1B hypothesis-directed retrieval (experimental): `HYPOTHESIS_DIRECTED_RAG_ENABLED` defaults **false**; when off, Modules 6–9 RAG/diagnosis are unchanged. Part 1B is infrastructure only — not causal ranking; `SUPPORT_CANDIDATE` ≠ proven support. See `docs/PHASE6A5_HYPOTHESIS_RETRIEVAL_CONTRACTS.md`.
- Phase 6A.5 Part 2 adaptive retrieval intelligence: `ADAPTIVE_HYPOTHESIS_RETRIEVAL_ENABLED` and related flags default **false** (Part 1B unchanged when off). No migration 016 — payloads live in existing JSONB. See `docs/PHASE6A5_ADAPTIVE_RETRIEVAL.md`.
- Phase 6A.5 Part 3 evidence assessment: `HYPOTHESIS_EVIDENCE_ASSESSMENT_ENABLED` and related flags default **false**. `RankingScore` ≠ root-cause confidence; candidates only. No migration 016. See `docs/PHASE6A5_EVIDENCE_ASSESSMENT.md`.
- Deterministic diagnostic signals, lexical exact-match, versioned hybrid weight profiles, dedupe/diversity reranking
- Organization membership resolution and role-based authorization dependencies
- Default organization + owner membership created on user registration
- Frozen roles: `platform_admin`, `organization_owner`, `organization_admin`, `engineer`, `viewer`

### What is deliberately not claimed

- Full SaaS multi-tenant product surface
- Mandatory live OpenAI or ChromaDB in default local mode (flags/providers optional)
- ZIP archive uploads (deferred ADR-011)
- Frontend product screens incomplete (Phase 5A core is in progress; Module 5A.10 gates remain)
- Complete API surface from `API_SPECIFICATION.md` (audit/models admin still deferred)

---

## Frozen Target Architecture (summary)

Authority documents live under `docs/`. Primary source of truth:

**`docs/MASTER_ARCHITECTURE.md`**

Target domain flow:

```text
Organization → Membership / User → Project → Pipeline Run → Incident
  → Uploaded Files → Analysis Run → Prediction → Evidence
  → Retrieved Documents → Recommendations → Resolution → Report
```

The **current 11-table database is a legacy flat ML schema**. New product features must **not** be built on it. Schema evolution is planned in:

- `docs/ARCHITECTURE_DECISION_LOG.md` (ADR-012 — Proposed)
- `docs/SCHEMA_EVOLUTION_PLAN.md`

---

## Current Refactoring Stage

**AI orchestration phase (approved):** Module 9 complete — hybrid retrieval over Module 7/8 baselines.

**Still blocked (separate approval required):**

- Frontend product screens
- ZIP archive uploads
- Production database changes
- Billing / webhooks / analytics dashboards

Audit / plan artefacts:

- `docs/IMPLEMENTATION_ALIGNMENT_AUDIT.md`
- `docs/IMPLEMENTATION_REFACTORING_PLAN.md`
- `docs/SCHEMA_EVOLUTION_PLAN.md`
- `docs/ARCHITECTURE_DECISION_LOG.md`

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Router |
| Database | PostgreSQL 16 |
| DevOps | Docker, Docker Compose |

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker Desktop (Compose v2)
- Git

---

## Safe Setup Instructions

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Edit `.env` and set at minimum:

- `POSTGRES_PASSWORD` — change from `change_me`
- `DATABASE_URL` — must match postgres credentials
- `JWT_SECRET_KEY` — at least 32 random characters (required for auth)

### Docker Compose (recommended)

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| Frontend | http://localhost:5173 |
| Chroma (host) | http://localhost:8001 |
| Swagger UI | http://localhost:8000/docs |
| Health (liveness) | http://localhost:8000/api/v1/health |
| Health (readiness) | http://localhost:8000/api/v1/health/ready |

### Chroma vector database (Docker)

Chroma runs as a Compose service with a named volume so indexed knowledge survives restarts.

| Context | Host | Port |
|---------|------|------|
| Inside backend container | `chroma` | `8000` |
| From your Mac / host tools | `localhost` | `8001` |

Start infrastructure (Postgres + Chroma):

```bash
docker compose up -d postgres chroma
docker compose ps
curl http://localhost:8001/api/v2/heartbeat
```

Backend Compose overrides set `CHROMA_HOST=chroma` and `CHROMA_PORT=8000`. For scripts on the host, use:

```bash
export CHROMA_HOST=localhost
export CHROMA_PORT=8001
```

Optional federated retrieval (product + research collections) can be enabled by setting:

```bash
CHROMA_COLLECTION_NAME=devguard_product_minilm
CHROMA_SECONDARY_COLLECTION_NAME=devguard_research_knowledge
```

Safe connectivity check from the backend container (no collection create/delete):

```bash
docker compose up -d backend
docker compose exec backend python -c "
import chromadb
c = chromadb.HttpClient(host='chroma', port=8000)
print(c.heartbeat())
"
```

View logs / restart Chroma without wiping data:

```bash
docker compose logs --tail=100 chroma
docker compose restart chroma
```

Ordinary shutdown (keeps volumes):

```bash
docker compose down
```

**Do not** use `docker compose down -v` for ordinary shutdown — `-v` deletes volumes including Chroma knowledge.

Explicit Chroma data removal (destructive):

```bash
docker compose down
docker volume rm devguard_ai_chroma_data
```

Confirm with `docker volume ls | grep chroma`. This permanently removes indexed knowledge.

### Local sentence-transformer embeddings

See [docs/EMBEDDING_SETUP.md](docs/EMBEDDING_SETUP.md) for full setup.

```bash
# In .env (do not commit secrets)
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
```

OpenAI production-hardening options:

```bash
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=3
OPENAI_RETRY_BASE_DELAY_MS=500
OPENAI_RETRY_MAX_DELAY_MS=8000
OPENAI_CIRCUIT_BREAKER_FAILURES=5
OPENAI_CIRCUIT_BREAKER_RESET_SECONDS=60
```

Token-pricing configuration (aliases supported):

```bash
OPENAI_INPUT_COST_PER_1M_TOKENS=
OPENAI_OUTPUT_COST_PER_1M_TOKENS=
# or:
LLM_INPUT_COST_USD_PER_MILLION_TOKENS=
LLM_OUTPUT_COST_USD_PER_MILLION_TOKENS=
```

```bash
docker compose build backend
docker compose up -d postgres chroma backend
docker compose exec backend python -m app.cli.warmup_embeddings
docker compose exec backend python -m app.cli.test_embeddings \
  --text "AWS AccessDenied during deployment" \
  --compare-text "IAM permission denied while deploying" \
  --with-chroma
```

Default remains `EMBEDDING_PROVIDER=hash` for deterministic tests. Compose mounts `model_cache` so Hugging Face downloads survive backend recreation. First model load can take several minutes.

### Research dataset corpus (Phase 1)

Real public DevOps incidents are collected via the GitHub Issues API into `datasets/` (separate from runtime DB and from the small `knowledge_base/` enrichment docs). See `datasets/README.md` and `datasets/DATASET_CARD.md`.

```bash
export GITHUB_TOKEN=...   # optional; never commit
python scripts/dataset/collect_github_issues.py --repo actions/runner --labels bug --max-issues 5
python scripts/dataset/validate_incidents.py
```

### Local backend (without full Compose)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Host-side: Postgres must be on localhost (Compose publishes POSTGRES_PORT).
# Do not use hostname `postgres` outside Docker — it will not resolve.
export POSTGRES_HOST=localhost
export DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-devguard}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB:-devguard}
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Prefer `docker compose exec backend alembic upgrade head` when the stack runs via Compose.

### Local frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Database Migrations

Alembic reads `settings.database_url` via `get_settings()` in `backend/alembic/env.py`
(not the placeholder URL in `alembic.ini`). Compose sets `DATABASE_URL` with hostname
`postgres`, which **only resolves inside the Docker network**.

### Recommended — run Alembic inside the backend container

```bash
docker compose up -d postgres backend
docker compose exec backend alembic current
docker compose exec backend alembic heads
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
```

Expected head after Phase 6A.5 Part 1B/Part 2/Part 3: `015_phase6a5_hyp_retrieval` (Part 2/Part 3 add **no** migration 016).

Safe settings diagnostic (masks nothing itself — print only non-secret parts):

```bash
docker compose exec backend python -c "
from urllib.parse import urlparse
from app.core.config import get_settings
u = urlparse(get_settings().database_url)
print(u.scheme, u.hostname, u.port, u.path)
"
```

There is **no** module-level `settings` export. Use `get_settings()` or `Settings()`.

### Host-side Alembic (alternative)

Only when PostgreSQL is reachable on the published host port (default `localhost:5432`).
Do **not** use hostname `postgres` from the Mac host.

```bash
cd backend
source .venv/bin/activate
export POSTGRES_HOST=localhost
export DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-devguard}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB:-devguard}
alembic current
alembic upgrade head
```

### Option B — recreate local development database

After pulling schema work, reset **local** Postgres only (destroys local data):

```bash
docker compose down
docker volume rm devguard_ai_postgres_data   # name may vary; check: docker volume ls | grep postgres
docker compose up -d postgres
# wait until healthy, then:
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend alembic current
docker compose run --rm backend alembic heads
```

### Seed (idempotent)

Failure categories always. Bootstrap org/owner only when enabled:

```bash
# .env — development only
BOOTSTRAP_ENABLED=true
BOOTSTRAP_OWNER_PASSWORD=choose_a_local_password

docker compose run --rm backend python -m app.infrastructure.database.seed
```

Do not log or commit bootstrap passwords. Do not enable bootstrap in production.

```bash
docker compose exec backend alembic history
# Destructive — deletes application table data:
# docker compose exec backend alembic downgrade base
```

**Warning:** `alembic downgrade base` deletes application table data.

---

## Repository Layer (legacy schema)

| Layer | Location |
|-------|----------|
| Domain interfaces | `app/domain/interfaces/repositories.py` |
| Domain entities | `app/domain/entities/` |
| Infrastructure | `app/infrastructure/repositories/` |

Implemented against the **legacy** tables: User, FailureCategory, PipelineRun.

Repositories flush; they do not own commits (future services will).

---

## Test Status

```bash
cd backend
source .venv/bin/activate
ruff check .
pytest tests/ -v
```

| Suite | Expectation |
|-------|-------------|
| Health tests | Should pass without Docker DB |
| Auth tests | Require PostgreSQL (`devguard_test`); cover login/refresh/logout/me/RBAC |
| Business API tests | Require PostgreSQL; cover projects, incidents, org isolation, analysis stub |
| Upload tests | Require PostgreSQL; cover validation, duplicates, masking, analysis file_ids |
| Repository + seed tests | Require PostgreSQL (`devguard_test`); skip if DB unavailable |
| Frontend tests | Not implemented yet |

Known limitation: DB integration tests skip when Docker/Postgres is not running.

---

## Known Limitations

1. Legacy 11-table schema ≠ frozen target schema  
2. No authentication or authorization  
3. No business APIs beyond health  
4. No AI pipeline  
5. Frontend is a Module 1 placeholder (single home page)  
6. Cursor / agents must not treat legacy schema as final  
7. `analysis_history` exists in legacy schema but is **not** recommended for MVP in DATABASE_ARCHITECTURE  

---

## Next Approved Work

After project-owner approval of:

1. ADR-012 (`docs/ARCHITECTURE_DECISION_LOG.md`)  
2. `docs/SCHEMA_EVOLUTION_PLAN.md`  

…implementation may proceed with **schema evolution only** (models + migrations), still without product feature expansion unless separately approved.

---

## Documentation Map

| Document | Role |
|----------|------|
| `docs/MASTER_ARCHITECTURE.md` | Single source of truth |
| `docs/PROJECT_CONSTITUTION.md` | Non-negotiable rules |
| `docs/DATABASE_ARCHITECTURE.md` | Target database design |
| `docs/ARCHITECTURE_DECISION_LOG.md` | Binding ADRs |
| `docs/SCHEMA_EVOLUTION_PLAN.md` | Legacy → target migration plan |
| `docs/IMPLEMENTATION_ALIGNMENT_AUDIT.md` | Latest audit |
| `docs/IMPLEMENTATION_REFACTORING_PLAN.md` | Refactor issue register |

---

## Lint Commands

```bash
cd backend && source .venv/bin/activate && ruff check .
cd frontend && npm run lint
```

---

## Troubleshooting — Apple Silicon Macs

**Docker builds are slow or fail**

- Ensure Docker Desktop uses VirtioFS; do not force `platform: linux/amd64`.

**PostgreSQL not ready when backend starts**

- Backend waits for postgres healthcheck. Check `docker compose logs postgres` and `.env` credentials.

**Frontend shows "Backend Offline"**

- `curl http://localhost:8000/api/v1/health`
- Ensure `VITE_API_BASE_URL=http://localhost:8000/api/v1`
- Ensure CORS includes `http://localhost:5173`

**Port already in use**

- Change `BACKEND_PORT` or `FRONTEND_PORT` in `.env`.

---

## Project Structure

```text
devguard_ai/
├── backend/           # FastAPI application
├── frontend/          # React + Vite application shell
├── docs/              # Frozen architecture + audit/planning docs
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## License

Proprietary — MSc Advanced Software Engineering dissertation project.
