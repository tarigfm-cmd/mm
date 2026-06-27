# Development Guide

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 20+ |
| Docker + Docker Compose | any recent |
| Anthropic API key | from console.anthropic.com |

## Environment Setup

```bash
cp .env.example .env
```

Key variables to set in `.env`:

```env
# Required for AI features
ANTHROPIC_API_KEY=sk-ant-...

# Keep defaults for local Docker dev
DB_PASSWORD=postgres
SECRET_KEY=change-me-in-production-min-50-chars-000000000000
```

## Option A — Docker Compose (recommended)

```bash
docker-compose up
```

Services started:
- **PostgreSQL 15** on port 5432
- **Redis 7** on port 6379
- **Backend** (hot-reload) on port 8000
- **Frontend** (Vite dev) on port 5173

Access:
- App: http://localhost:5173
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

## Option B — Local (no Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# You need a running PostgreSQL and Redis, then:
cp ../.env.example .env
# Edit .env with your local DB/Redis URLs

uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

For local dev without Docker, the Vite proxy falls back to `http://localhost:8000`
(configurable via `BACKEND_URL` env var if your backend runs elsewhere).

## Running Tests

### Backend

```bash
cd backend

# All tests with coverage
pytest tests/ -v --cov=app

# Fast (no coverage)
pytest tests/ -v
```

Tests use an in-memory SQLite database — no PostgreSQL or Redis required.

### Frontend TypeScript check

```bash
cd frontend
npx tsc --noEmit
```

## Project Structure

```
mm/
├── backend/
│   ├── app/
│   │   ├── core/           # Security stubs (JWT/RBAC Phase 2)
│   │   ├── domains/        # Future bounded-context packages
│   │   ├── models/
│   │   │   ├── content.py  # Material ORM model
│   │   │   └── learning.py # Scenario, Interaction ORM models
│   │   ├── routes/         # FastAPI routers
│   │   ├── schemas/
│   │   │   ├── platform.py # HealthResponse, PaginatedResponse
│   │   │   ├── content.py  # Material schemas
│   │   │   └── learning.py # Scenario & Interaction schemas
│   │   ├── services/
│   │   │   ├── ai_service.py       # Anthropic Claude integration
│   │   │   └── document_parser.py  # Text extraction
│   │   └── utils/validators.py
│   ├── alembic/            # Database migrations
│   ├── tests/
│   │   ├── conftest.py     # SQLite async test fixtures
│   │   ├── test_health.py
│   │   └── test_materials.py
│   └── requirements.txt
└── frontend/
    └── src/
        ├── store/appStore.ts   # Zustand platform store
        ├── services/api.ts     # Typed API client
        └── types/index.ts      # TypeScript interfaces
```

## Key Design Decisions

**UUIDs everywhere** — All primary keys use `sqlalchemy.Uuid` (not `postgresql.UUID`) for cross-database compatibility between SQLite (tests) and PostgreSQL (production).

**Background text extraction** — File upload returns immediately; text extraction runs as a FastAPI `BackgroundTask`. The frontend polls `GET /api/materials/{id}` until `has_content: true`.

**Anonymous sessions** — No auth in Phase 1. Browser generates a UUID stored in `localStorage` and sends it as `X-Session-Id` header so interactions can be associated across requests.

**AI service** — `app/services/ai_service.py` handles both scenario generation and answer evaluation via the Anthropic Python SDK. The AI model is configured via `AI_MODEL` env var (default: `claude-sonnet-4-6`).

## Database Migrations

Migrations use Alembic with psycopg2 (sync) while the app uses asyncpg.

```bash
# Run migrations against running PostgreSQL
cd backend
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

In development the app auto-creates tables via `Base.metadata.create_all` on startup (lifespan event). Use Alembic for production.

## Adding a New Domain Module

1. Add a package under `backend/app/domains/<name>/`
2. Create `models.py`, `schemas.py`, `router.py`, `service.py`
3. Register the router in `backend/app/main.py`
4. Create an Alembic migration for new tables
5. Add TypeScript types in `frontend/src/types/index.ts`
6. Add API methods in `frontend/src/services/api.ts`

See [ARCHITECTURE.md](ARCHITECTURE.md) for module boundary conventions.
