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

# Auth / JWT (generate with: python3 -c "import secrets; print(secrets.token_hex(32))")
JWT_SECRET_KEY=change-me-jwt-secret-key-min-32-chars-00000000000
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
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

#### Import pipeline tests

```bash
# Run only the import pipeline test suite
pytest tests/test_import_pipeline.py -v

# Run a specific test
pytest tests/test_import_pipeline.py::test_preview_single_csv_success -v
```

The import tests use small synthetic CSV data generated in-memory. The real content bank ZIP is never required. Each test gets a fully isolated in-memory database via the `fresh_engine` fixture.

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
│   │   ├── core/
│   │   │   ├── security.py      # PBKDF2 hashing + joserfc JWT
│   │   │   └── dependencies.py  # FastAPI auth/RBAC dependencies
│   │   ├── domains/             # Bounded-context stubs (Phase 3+)
│   │   ├── models/
│   │   │   ├── content.py       # Material ORM model
│   │   │   ├── learning.py      # Scenario, Interaction ORM models
│   │   │   └── identity.py      # User, Org, Role, Permission, etc.
│   │   ├── routes/              # FastAPI routers
│   │   │   ├── health.py
│   │   │   ├── auth.py          # /api/auth endpoints
│   │   │   ├── materials.py
│   │   │   └── scenarios.py
│   │   ├── schemas/
│   │   │   ├── platform.py      # HealthResponse, PaginatedResponse
│   │   │   ├── content.py       # Material schemas
│   │   │   ├── learning.py      # Scenario & Interaction schemas
│   │   │   └── identity.py      # User, Org, Auth schemas
│   │   ├── services/
│   │   │   ├── ai_service.py    # Anthropic Claude integration
│   │   │   └── document_parser.py
│   │   └── utils/validators.py
│   ├── alembic/
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       └── 002_identity_rbac.py
│   ├── tests/
│   │   ├── conftest.py          # SQLite async test fixtures
│   │   ├── test_health.py
│   │   ├── test_materials.py
│   │   ├── test_security.py     # Password + JWT tests
│   │   └── test_rbac.py         # Schema + role/permission tests
│   └── requirements.txt
└── frontend/
    └── src/
        ├── store/appStore.ts    # Zustand platform store
        ├── services/api.ts      # Typed API client
        └── types/index.ts       # TypeScript interfaces
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

## Admin Governance UI

The content governance section lives at `/admin/governance` and is guarded by `is_superuser`.

### Route map

| URL | Page |
|-----|------|
| `/admin/governance` | GovernanceDashboard (stats + quick links) |
| `/admin/governance/import` | ImportCenter (CSV/ZIP preview → commit wizard) |
| `/admin/governance/approval-batches` | ApprovalBatchesPage (team sign-off records) |
| `/admin/governance/content` | ContentLibraryPage (paginated table with filters) |
| `/admin/governance/content/:id` | ContentDetailPage (item detail, versions, reviews, publish) |
| `/admin/governance/evidence` | EvidenceManagementPage (evidence sources, due-for-review alert) |
| `/admin/governance/regions` | RegionRulesPage (live CRUD for RegionPublishingRule records) |

### Access control

The `AdminRoute` component (rendered before `GovernanceLayout`) checks `currentUser.is_superuser`.
Non-superusers see an "Insufficient permissions" screen instead of the governance UI.
Backend RBAC enforces the same constraint on every API call — the frontend gate is presentational only.

### Governance API client

`frontend/src/services/governanceApi.ts` — separate Axios instance with the same JWT refresh interceptor pattern as `api.ts`. All import endpoints are multipart/form-data with extended timeouts (preview 300 s, commit 600 s).

API objects exported:
- `importApi` — preview and commit multipart uploads
- `approvalBatchApi` — list and create approval batches
- `contentApi` — list (with `search`, `status`, `content_type`, `domain` filters), get, create, versions, reviews, publish, unpublish
- `evidenceApi` — list, create, update, dueForReview
- `governanceSummaryApi` — single aggregate call for the dashboard stat cards
- `importBatchApi` — list and get import batch metadata (no clinical payloads)
- `regionRulesApi` — list, create, update region publishing rules

### Import rules (enforced in UI + backend)

- Only CSV or ZIP content packages may be uploaded. The Excel dashboard must NOT be uploaded here.
- Always run Preview before committing — the "Commit Import" button is disabled until preview shows zero errors.
- All committed items land in `pending_review`; nothing is auto-published.
- Commit requires explicit confirmation via `ConfirmActionDialog`.
- Publish and Unpublish actions each require explicit per-region confirmation.

## Learner Training UI

The learner training section is accessible to any authenticated user at `/learn/`.

### Route map

| URL | Page |
|-----|------|
| `/learn/content` | TrainingLibraryPage — browse published content with region/type/difficulty/search filters |
| `/learn/content/:id?region=UK` | TrainingDetailPage — step-based guided training: flow → session → steps → submit → result |
| `/learn/progress` | TrainingProgressPage — sessions, scores, dimension breakdown, recommendation |

### Learner API client

`frontend/src/services/learnApi.ts` — separate Axios instance with the same JWT refresh interceptor pattern. Exports `learnApi` with:
- `browse` — list published content
- `getDetail` — fetch safe content detail
- `getTrainingFlow` — fetch step blueprint per content type (no hidden fields)
- `startSession` — create `LearnerTrainingSession`
- `submitSession` — submit all responses; returns dimension feedback + reveal summary
- `submitAttempt` — Phase-1 single-attempt endpoint (kept for compatibility)
- `getProgress` — comprehensive progress summary

### Training engine routes

```bash
GET  /api/learn/content/{id}/training-flow?region_code=UK   # step blueprint
POST /api/learn/content/{id}/sessions                        # start session
POST /api/learn/sessions/{session_id}/submit                 # submit all responses
```

Run engine tests:

```bash
cd backend
pytest tests/test_training_engine.py -v
```

### Key learner UX constraints

- Region selector defaults to `UK`. Changing region reloads the library.
- Empty library state explicitly tells users that an admin must publish content first.
- Answer/scoring keys are never returned by the detail or flow endpoints — only in the submit response as `reveal_summary`.
- Sessions are user-scoped. Users cannot submit another user's session (403).
- Completed sessions cannot be re-submitted (409).
- Progress page shows session-level data (completed_sessions, average_score_percent) plus attempt-level dimension breakdown.
- Progress page uses `LearnerFailureAnalytics` + `LearnerTrainingSession` — separate from the Scenario progress page.

### Frontend TypeScript checks

Run after any frontend change:

```bash
cd frontend
npx tsc --noEmit
```

All governance pages and API client are fully typed. `ContentItemListItem` includes `external_id: string | null`. New types (`GovernanceSummary`, `ImportBatchRead`, `ImportBatchListResponse`, `RegionPublishingRuleRead/Create/Update`) are defined in `frontend/src/types/governance.ts`.
