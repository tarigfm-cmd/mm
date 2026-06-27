# PharmLearn AI — Architecture

## System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│  Frontend (React 18 + TypeScript + Vite)                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Dashboard │ Content Library │ Case Practice │ Assessments  │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
                          │ HTTPS / REST (JSON)
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│  API Gateway (Nginx — rate limiting, TLS termination)              │
└────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI — async Python 3.11)                             │
│                                                                    │
│  Routes (Phase 1 active)           Planned domains                 │
│  ├── /api/health                   ├── users/                      │
│  ├── /api/materials/*              ├── organizations/              │
│  └── /api/scenarios/*             ├── assessments/                │
│                                    ├── osce/                       │
│  Services                          ├── games/                      │
│  ├── ai_service.py (Claude)        ├── analytics/                  │
│  └── document_parser.py           ├── subscriptions/              │
│                                    └── content_review/             │
│  Infrastructure                                                    │
│  ├── database.py (SQLAlchemy 2.0 async)                           │
│  ├── config.py (pydantic-settings)                                │
│  └── core/security.py (Phase 2 — JWT + RBAC)                     │
└────────────────────────────────────────────────────────────────────┘
          │                   │                    │
          ▼                   ▼                    ▼
   ┌────────────┐     ┌─────────────┐     ┌──────────────┐
   │ PostgreSQL │     │    Redis    │     │ Anthropic    │
   │     15     │     │      7      │     │ Claude API   │
   └────────────┘     └─────────────┘     └──────────────┘
```

## Backend Layer Structure

### Current (Phase 1)

```
app/
├── core/                    # Cross-cutting infrastructure
│   └── security.py          # Stub — JWT/RBAC in Phase 2
│
├── domains/                 # Bounded-context packages (stubs for Phase 2+)
│   ├── users/
│   ├── organizations/
│   ├── assessments/
│   ├── osce/
│   ├── games/
│   ├── analytics/
│   ├── subscriptions/
│   └── content_review/
│
├── models/                  # SQLAlchemy ORM models
│   ├── content.py           # Material
│   └── learning.py          # Scenario, Interaction
│
├── routes/                  # FastAPI routers (active endpoints)
│   ├── health.py
│   ├── materials.py
│   └── scenarios.py
│
├── schemas/                 # Pydantic I/O schemas
│   ├── platform.py          # HealthResponse, PaginatedResponse
│   ├── content.py           # Material*
│   └── learning.py          # Scenario*, Interaction*, ScenarioGenerate*
│
├── services/                # Domain-agnostic application services
│   ├── ai_service.py        # Claude scenario generation + answer evaluation
│   └── document_parser.py   # PDF/DOCX/TXT/image text extraction
│
├── utils/
│   └── validators.py        # File validation, upload path helpers
│
├── config.py                # pydantic-settings — all env vars
├── database.py              # Async engine, session factory, Base
└── main.py                  # App factory, middleware, lifespan
```

## Database Schema (Phase 1)

All primary keys use UUID v4 (cross-database compatible via `sqlalchemy.Uuid`).

```
materials
  id            UUID PK
  title         VARCHAR(255)
  description   TEXT nullable
  file_name     VARCHAR(255)
  file_path     VARCHAR(500)
  file_size     BIGINT
  file_type     VARCHAR(50)      -- pdf | docx | txt | png | jpg | jpeg
  content_text  TEXT nullable    -- populated by background task
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ

scenarios
  id              UUID PK
  material_id     UUID FK → materials.id ON DELETE SET NULL nullable
  title           VARCHAR(255)
  clinical_case   TEXT
  difficulty_level VARCHAR(50)   -- beginner | intermediate | advanced
  specialty       VARCHAR(100) nullable
  key_concepts    JSON nullable
  expected_answer TEXT nullable
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ

interactions
  id                   UUID PK
  scenario_id          UUID FK → scenarios.id ON DELETE CASCADE
  session_id           VARCHAR(255) nullable  -- anonymous browser session
  user_answer          TEXT
  ai_feedback          TEXT
  score                FLOAT nullable         -- 0.0–1.0
  key_findings         JSON nullable
  next_steps           JSON nullable
  strengths            JSON nullable
  areas_for_improvement JSON nullable
  created_at           TIMESTAMPTZ
```

Planned Phase 2 tables: `users`, `roles`, `user_roles`, `organizations`, `memberships`, `subscriptions`.

## Data Flow

### Upload Material → Generate Scenario

```
1. POST /api/materials/upload (multipart)
2. Validate file type & size
3. Write bytes to disk (UUID-prefixed filename)
4. INSERT materials row (content_text = NULL)
5. BackgroundTask: extract_text() → UPDATE content_text
6. Client polls GET /api/materials/{id} until has_content = true
7. POST /api/scenarios/generate
8. ai_service.generate_scenario(content_text, difficulty_level)
9. Claude returns structured JSON → INSERT scenarios row
10. Return ScenarioResponse
```

### Student Answer → AI Feedback

```
1. POST /api/scenarios/{id}/answer
2. Fetch scenario (clinical_case + expected_answer)
3. ai_service.evaluate_answer(case, expected, student_answer)
4. Claude returns score + structured feedback JSON
5. INSERT interactions row
6. Return InteractionResponse
```

## AI Service

`app/services/ai_service.py` wraps the Anthropic Python SDK.

- **Model:** configured via `AI_MODEL` (default `claude-sonnet-4-6`)
- **generate_scenario():** produces a pharmacy clinical case from document text
- **evaluate_answer():** scores a student's response 0–1 with structured feedback
- Both functions expect and return plain Python dicts; routes own serialisation.
- JSON fence stripping handles models that wrap output in markdown code blocks.

## Frontend Architecture

```
src/
├── store/
│   └── appStore.ts        # Zustand platform store (content + learning state)
├── services/
│   └── api.ts             # Axios instance, interceptors, typed API methods
├── types/
│   └── index.ts           # TypeScript interfaces mirroring backend schemas
├── components/            # Reusable UI primitives
│   ├── Navigation.tsx
│   ├── DifficultyBadge.tsx
│   ├── ScenarioCard.tsx
│   ├── MessageBubble.tsx
│   ├── UploadDropzone.tsx
│   └── LoadingSpinner.tsx
└── pages/
    ├── Dashboard.tsx
    ├── MaterialsUpload.tsx
    ├── ScenariosPage.tsx
    └── ScenarioPage.tsx
```

**Session management:** Anonymous learner sessions use a UUID stored in `localStorage` (key: `pharmacy_ai_session_id`). Each API request carries this as `X-Session-Id` header.

## Security (Phase 1)

- File upload: extension whitelist, 50 MB size cap, UUID-prefixed storage names
- Rate limiting: SlowAPI (30 req/min general, 5 req/min upload)
- CORS: origins configured via `CORS_ORIGINS` env var
- No authentication yet — all endpoints are public in Phase 1

## Caching (Phase 2 planned)

Redis is provisioned but not yet used for application caching.
Planned uses: generated scenario cache, rate limit state, session data.

## Module Boundaries (Future)

Each domain package in `app/domains/` will own:
```
domains/<name>/
  ├── models.py    # SQLAlchemy ORM models
  ├── schemas.py   # Pydantic I/O schemas
  ├── router.py    # FastAPI APIRouter
  ├── service.py   # Business logic
  └── __init__.py
```

Routes registered in `main.py` via `app.include_router(domain.router.router)`.
