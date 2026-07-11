# DevGuard AI

**AI-Powered DevOps Intelligence Platform**

DevGuard AI analyses CI/CD pipeline failures, Infrastructure-as-Code files, and deployment configurations to identify root causes, extract evidence, and generate intelligent remediation recommendations.

## Current Module Status

| Module | Scope | Status |
|--------|-------|--------|
| **Module 1** | Project foundation (backend, frontend, Docker, health API, DB connection) | ✅ Complete |
| **Module 2** | Database schema and migrations | 🚧 In progress (Alembic initial migration) |
| Module 3+ | Auth, uploads, ML, RAG, LLM, dashboard | Planned |

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 (async) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Router |
| Database | PostgreSQL 16 |
| DevOps | Docker, Docker Compose |

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker Desktop (with Compose v2)
- Git

## Environment Setup

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Edit `.env` and set at minimum:

- `POSTGRES_PASSWORD` — change from `change_me`
- `DATABASE_URL` — must match postgres credentials

## Local Development (Without Docker)

### 1. PostgreSQL

Run PostgreSQL locally and ensure it matches your `.env` credentials.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

## Docker Compose Setup

From the project root:

```bash
cp .env.example .env
docker compose up --build
```

Services:

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| Frontend | http://localhost:5173 |
| Swagger UI | http://localhost:8000/docs |
| Health (liveness) | http://localhost:8000/api/v1/health |
| Health (readiness) | http://localhost:8000/api/v1/health/ready |

## Database Migrations (Alembic)

Migrations run from the `backend/` directory. With Docker Compose, use `docker compose exec backend`.

```bash
# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Show current revision
docker compose exec backend alembic current

# Show migration history
docker compose exec backend alembic history

# Roll back all migrations (removes all application tables and enum types)
docker compose exec backend alembic downgrade base
```

**Warning:** `alembic downgrade base` deletes all local development data in the application tables. Use only when you intentionally want to reset the schema.

For future schema changes after ORM model updates:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head
```

Without Docker, from `backend/` with your virtualenv active:

```bash
alembic upgrade head
alembic current
alembic history
alembic downgrade base
```

## Test Commands

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

## Lint Commands

```bash
cd backend
source .venv/bin/activate
ruff check .
```

```bash
cd frontend
npm run lint
```

## Troubleshooting — Apple Silicon Macs

**Docker builds are slow or fail**

- Ensure Docker Desktop is updated and uses the VirtioFS file sharing implementation.
- Do not set `platform: linux/amd64` — all images use multi-arch defaults (arm64 native on M-series Macs).

**PostgreSQL not ready when backend starts**

- Backend waits for `postgres` healthcheck via `depends_on: condition: service_healthy`.
- If readiness still fails, run `docker compose logs postgres` and verify credentials in `.env`.

**Frontend shows "Backend Offline"**

- Confirm backend is running: `curl http://localhost:8000/api/v1/health`
- Ensure `VITE_API_BASE_URL` in `.env` is `http://localhost:8000/api/v1` (browser accesses host machine, not Docker internal network).
- Check CORS: `BACKEND_CORS_ORIGINS` must include `http://localhost:5173`.

**Port already in use**

- Change `BACKEND_PORT` or `FRONTEND_PORT` in `.env`.

**Module import errors in backend tests**

- Run pytest from the `backend/` directory so `pythonpath = ["."]` resolves correctly.

## Project Structure

```
devguard_ai/
├── backend/           # FastAPI application
├── frontend/          # React + Vite application
├── docs/              # Architecture documentation
├── docker-compose.yml
├── .env.example
└── README.md
```

## License

Proprietary — MSc Advanced Software Engineering dissertation project.
