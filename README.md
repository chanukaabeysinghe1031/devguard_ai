# DevGuard AI

**AI-Powered DevOps Intelligence Platform**

DevGuard AI analyses CI/CD pipeline failures, Infrastructure-as-Code files, and deployment configurations to identify root causes, extract evidence, and generate intelligent remediation recommendations.

## Architecture

Clean Architecture with layered separation:

- **API** — FastAPI routers and Pydantic schemas
- **Services** — Business orchestration
- **Domain** — Entities, enums, provider interfaces
- **Infrastructure** — Database, ML, RAG, external integrations

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) for full design documentation.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0 (async) |
| Frontend | React, TypeScript, Tailwind CSS, Vite |
| Database | PostgreSQL 16 |
| Vector DB | ChromaDB |
| ML | scikit-learn, sentence-transformers |
| RAG/LLM | LangChain, OpenAI |

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Node.js 20+ (for frontend, Module 9)

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env — set APP_SECRET_KEY (min 32 chars) and OPENAI_API_KEY
```

### 2. Start infrastructure

```bash
docker compose up -d postgres chromadb
```

### 3. Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Verify

- API root: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## Project Structure

```
devguard_ai/
├── backend/
│   ├── app/
│   │   ├── api/              # REST endpoints
│   │   ├── core/             # Config, security, logging
│   │   ├── domain/           # Entities, enums, interfaces
│   │   ├── infrastructure/   # DB, repos, ML, RAG
│   │   ├── schemas/          # Pydantic DTOs
│   │   ├── services/         # Business logic
│   │   └── main.py
│   ├── alembic/              # Database migrations
│   ├── dataset/              # Training data
│   ├── tests/
│   └── requirements.txt
├── frontend/                 # React app (Module 9)
├── docs/architecture/
└── docker-compose.yml
```

## Implementation Roadmap

| Module | Status |
|--------|--------|
| 1. Foundation (structure, DB, Docker, health API) | ✅ Complete |
| 2. Auth, upload API, file validation | Planned |
| 3. Preprocessing & feature extraction | Planned |
| 4. ML classification | Planned |
| 5. Evidence extraction | Planned |
| 6. RAG ingestion & retrieval | Planned |
| 7. LLM reasoning & recommendations | Planned |
| 8. Analysis orchestration | Planned |
| 9. Frontend dashboard | Planned |
| 10. Dataset & evaluation | Planned |
| 11. Admin & feedback | Planned |

## License

Proprietary — MSc Advanced Software Engineering dissertation project.
