# PharmLearn AI — Community Pharmacy Training Platform

A SaaS platform for community pharmacy education and clinical training.
Built with FastAPI, React, PostgreSQL, and Claude AI.

## Platform Modules

| Module | Status |
|--------|--------|
| Clinical case scenarios | **Active** |
| User authentication & JWT sessions | **Active** |
| Multi-tenant organization management | **Active** |
| RBAC (6 system roles) | **Active** |
| Per-user progress analytics | **Active** |
| OTC triage simulations | Roadmap (Phase 2) |
| Prescription screening | Roadmap (Phase 2) |
| Drug interaction detection | Roadmap (Phase 2) |
| OSCE stations | Roadmap (Phase 3) |
| Pharmacy games & flashcards | Roadmap (Phase 3) |
| Adaptive assessments | Roadmap (Phase 3) |
| AI tutor | Roadmap (Phase 3) |
| Platform admin dashboard | Roadmap (Phase 4) |
| Subscriptions & billing | Roadmap (Phase 4) |
| Evidence-based content review | Roadmap (Phase 4) |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend framework | FastAPI 0.104 (async) |
| Database ORM | SQLAlchemy 2.0 async |
| Database (production) | PostgreSQL 15 |
| Database (tests) | SQLite in-memory (aiosqlite) |
| AI provider | Anthropic Claude (`claude-sonnet-4-6`) |
| Document parsing | pypdf, python-docx |
| Password hashing | PBKDF2-SHA256 (260 000 iterations, stdlib) |
| JWT | joserfc HS256, access (30 min) + refresh (30 days) |
| Frontend framework | React 18 + TypeScript |
| Build tool | Vite 5 |
| Styling | Tailwind CSS 3 |
| State management | Zustand 4 |
| HTTP client | Axios 1.6 |
| Containerisation | Docker + Docker Compose |
| Reverse proxy | Nginx |

## Quick Start (Docker)

```bash
# 1. Clone and enter
git clone https://github.com/tarigfm-cmd/mm.git && cd mm

# 2. Configure environment
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY and strong JWT secrets

# 3. Start all services
docker-compose up

# Frontend   → http://localhost:5173
# Backend    → http://localhost:8000
# API docs   → http://localhost:8000/docs
```

## Local Development (without Docker)

See [DEVELOPMENT.md](DEVELOPMENT.md) for step-by-step instructions.

## Project Structure

```
mm/
├── backend/
│   ├── alembic/versions/   # 001 initial, 002 identity/rbac, 003 interaction user_id
│   ├── app/
│   │   ├── core/
│   │   │   ├── security.py       # PBKDF2 hashing + joserfc JWT
│   │   │   └── dependencies.py   # get_current_user, get_optional_user, RBAC helpers
│   │   ├── domains/              # Bounded-context stubs (Phase 3+)
│   │   ├── models/
│   │   │   ├── content.py        # Material
│   │   │   ├── identity.py       # User, Organization, Role, Permission,
│   │   │   │                     # OrganizationMembership, RefreshToken, AuditLog
│   │   │   └── learning.py       # Scenario, Interaction (with optional user_id)
│   │   ├── routes/
│   │   │   ├── auth.py           # /api/auth/* (register, login, refresh, me, logout)
│   │   │   ├── health.py         # /api/health
│   │   │   ├── materials.py      # /api/materials/*
│   │   │   ├── organizations.py  # /api/orgs/* + /api/roles
│   │   │   ├── progress.py       # /api/progress
│   │   │   └── scenarios.py      # /api/scenarios/*
│   │   ├── schemas/
│   │   │   ├── content.py
│   │   │   ├── identity.py
│   │   │   ├── learning.py
│   │   │   └── platform.py
│   │   ├── services/
│   │   │   ├── ai_service.py         # Anthropic Claude integration
│   │   │   └── document_parser.py    # PDF/DOCX text extraction
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   └── tests/
│       ├── test_auth.py          # Auth endpoint integration tests
│       ├── test_health.py
│       ├── test_materials.py
│       ├── test_organizations.py
│       ├── test_progress.py      # Progress endpoint tests
│       ├── test_rbac.py          # Schema validation + role hierarchy
│       └── test_security.py      # Password hashing + JWT unit tests
├── frontend/src/
│   ├── components/
│   │   ├── Navigation.tsx        # Sidebar with auth-aware user section
│   │   ├── ProtectedRoute.tsx    # Auth guard + layout shell
│   │   └── ...
│   ├── hooks/useAuthInit.ts      # Session restore on app load
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   ├── Dashboard.tsx
│   │   ├── MaterialsUpload.tsx
│   │   ├── ScenariosPage.tsx
│   │   ├── ScenarioPage.tsx
│   │   ├── OrganizationsPage.tsx
│   │   ├── OrgDetailPage.tsx
│   │   └── ProgressPage.tsx
│   ├── services/api.ts           # Axios instances, silent refresh interceptor
│   ├── store/appStore.ts         # Zustand store (auth + content + learning state)
│   └── types/index.ts
├── docker-compose.yml
├── nginx.conf
├── ARCHITECTURE.md
├── DEVELOPMENT.md
└── ROADMAP.md
```

## API Endpoints

```
# Health
GET  /api/health

# Auth
POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me
PATCH /api/auth/me
POST /api/auth/logout

# Materials
POST /api/materials/upload
GET  /api/materials
GET  /api/materials/{id}
DEL  /api/materials/{id}

# Scenarios
POST /api/scenarios/generate
GET  /api/scenarios
GET  /api/scenarios/{id}
POST /api/scenarios/{id}/answer
GET  /api/scenarios/{id}/interactions

# Organizations
POST /api/orgs
GET  /api/orgs
GET  /api/orgs/{slug}
PATCH /api/orgs/{slug}
GET  /api/orgs/{slug}/members
POST /api/orgs/{slug}/members
PATCH /api/orgs/{slug}/members/{user_id}
DEL  /api/orgs/{slug}/members/{user_id}

# Roles
GET  /api/roles

# Progress (authenticated)
GET  /api/progress?days=30
```

Full interactive docs: `http://localhost:8000/docs`

## Testing

```bash
# Backend (79 tests)
cd backend && pytest tests/ -v

# Frontend TypeScript check
cd frontend && npx tsc --noEmit
```

## Known Limitations

- Email verification is not implemented (users are marked unverified; no email is sent)
- AuditLog table is created and migrated but nothing writes to it yet
- Progress analytics require authenticated scenario submissions to accumulate data
- Refresh token cleanup (expired token pruning) is not scheduled
