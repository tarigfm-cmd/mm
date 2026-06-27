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

### Current (Phase 1 + Identity milestone)

```
app/
├── core/                    # Cross-cutting infrastructure
│   ├── security.py          # PBKDF2 password hashing + joserfc JWT
│   └── dependencies.py      # FastAPI auth dependencies (get_current_user, RBAC helpers)
│
├── domains/                 # Bounded-context packages (stubs for Phase 3+)
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
│   ├── learning.py          # Scenario, Interaction
│   └── identity.py          # User, Organization, OrganizationMembership,
│                            # Role, Permission, RolePermission,
│                            # RefreshToken, AuditLog
│
├── routes/                  # FastAPI routers (active endpoints)
│   ├── health.py
│   ├── auth.py              # /api/auth — register, login, refresh, me, logout
│   ├── materials.py
│   └── scenarios.py
│
├── schemas/                 # Pydantic I/O schemas
│   ├── platform.py          # HealthResponse, PaginatedResponse
│   ├── content.py           # Material*
│   ├── learning.py          # Scenario*, Interaction*, ScenarioGenerate*
│   └── identity.py          # User*, Organization*, Role*, Permission*,
│                            # LoginRequest, TokenResponse, RefreshRequest
│
├── services/                # Domain-agnostic application services
│   ├── ai_service.py        # Claude scenario generation + answer evaluation
│   └── document_parser.py   # PDF/DOCX/TXT/image text extraction
│
├── utils/
│   └── validators.py        # File validation, upload path helpers
│
├── config.py                # pydantic-settings — all env vars (incl. JWT)
├── database.py              # Async engine, session factory, Base
└── main.py                  # App factory, middleware, lifespan
```

## Identity & RBAC Architecture

### User Identity

- One `User` row per person; holds hashed password (PBKDF2-SHA256, 260 000 iterations).
- `is_superuser = True` grants platform-admin bypass on all permission checks.
- `is_active` / `is_verified` flags control login access.

### Multi-Tenancy

- `Organization` rows represent tenants (university, pharmacy_chain, hospital,
  training_center, enterprise, individual_workspace).
- A `User` may belong to many organizations via `OrganizationMembership`.
- Each membership carries exactly **one** `Role` within that org.

### Roles (system-seeded)

| Name | Display | Typical scope |
|------|---------|---------------|
| `student` | Student | Enrolled learners |
| `pharmacist` | Pharmacist | CPD pharmacists |
| `educator` | Educator | Content creators |
| `content_reviewer` | Content Reviewer | Evidence workflow |
| `institution_admin` | Institution Admin | Org management |
| `platform_admin` | Platform Admin | Full platform access |

### Permissions

Fine-grained `Permission` rows (`resource` + `action`) are attached to roles via
`RolePermission`. Platform admins bypass all permission checks.

### Auth Flow

```
POST /api/auth/register  →  create User (hashed password)
POST /api/auth/login     →  verify password → issue access + refresh JWTs
                             store hashed refresh token in refresh_tokens
POST /api/auth/refresh   →  verify refresh JWT + DB record → rotate tokens
GET  /api/auth/me        →  decode Bearer token → return UserRead
POST /api/auth/logout    →  revoke refresh token in DB
```

Access tokens: HS256 JWT, 30-minute TTL (configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`).
Refresh tokens: HS256 JWT, 30-day TTL (configurable via `JWT_REFRESH_TOKEN_EXPIRE_DAYS`).
Refresh tokens are stored as SHA-256 hashes in the DB and rotated on every use.

### RBAC FastAPI Dependencies

| Dependency | Purpose |
|-----------|---------|
| `get_current_user` | Decode Bearer JWT → load User |
| `require_superuser` | Enforce `is_superuser = True` |
| `require_org_role(role_name)` | Enforce specific role within org |
| `get_user_org_membership` | Load membership for org-scoped routes |
| `has_permission(perm_name)` | Check named permission within org |

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

Identity tables (Migration 002): `users`, `organizations`, `roles`, `permissions`, `role_permissions`, `organization_memberships`, `refresh_tokens`, `audit_logs`.

Planned Phase 3+ tables: `subscriptions`, `osce_stations`, `assessments`, `game_sessions`.

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

## Security

- File upload: extension whitelist, 50 MB size cap, UUID-prefixed storage names
- Rate limiting: SlowAPI (30 req/min general, 5 req/min upload)
- CORS: origins configured via `CORS_ORIGINS` env var
- **Auth (Identity milestone):** JWT Bearer tokens via `joserfc` (HS256); passwords hashed
  with PBKDF2-SHA256 (260 000 iterations, stdlib `hashlib`). Refresh tokens stored as
  SHA-256 hashes and rotated on every use.
- Public endpoints (Phase 1 routes) remain unauthenticated; new protected routes use
  `Depends(get_current_user)` from `app/core/dependencies.py`.

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
