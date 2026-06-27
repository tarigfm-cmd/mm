# PharmLearn AI — Architecture

## System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│  Frontend (React 18 + TypeScript + Vite)                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Login / Register │ Dashboard │ Scenarios │ Organizations   │   │
│  │  Materials Upload │ Progress                                │   │
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
│  Active routes                     Domain stubs (Phase 3+)         │
│  ├── /api/health                   ├── assessments/                │
│  ├── /api/auth/*                   ├── osce/                       │
│  ├── /api/materials/*              ├── games/                      │
│  ├── /api/scenarios/*              ├── analytics/                  │
│  ├── /api/orgs/*                   ├── subscriptions/              │
│  ├── /api/roles                    └── content_review/             │
│  └── /api/progress                                                 │
│                                                                    │
│  Services                                                          │
│  ├── ai_service.py (Claude — scenario gen + answer eval)           │
│  └── document_parser.py (PDF/DOCX text extraction)                 │
│                                                                    │
│  Infrastructure                                                    │
│  ├── database.py (SQLAlchemy 2.0 async, asyncpg in prod)          │
│  ├── config.py (pydantic-settings)                                 │
│  └── core/security.py (PBKDF2 + joserfc JWT)                      │
└────────────────────────────────────────────────────────────────────┘
          │                   │                    │
          ▼                   ▼                    ▼
   ┌────────────┐     ┌─────────────┐     ┌──────────────┐
   │ PostgreSQL │     │    Redis    │     │ Anthropic    │
   │     15     │     │      7      │     │ Claude API   │
   └────────────┘     └─────────────┘     └──────────────┘
```

## Data Model

```
users
├── id (UUID PK)
├── email (unique)
├── username (unique)
├── hashed_password  (PBKDF2-SHA256, 260k iterations)
├── full_name
├── is_active / is_verified / is_superuser
└── created_at / updated_at

organizations
├── id (UUID PK)
├── name / slug (unique) / org_type
├── is_active / settings (JSON)
└── created_at / updated_at

organization_memberships         (user ↔ org, unique per pair)
├── user_id → users.id
├── organization_id → organizations.id
├── role_id → roles.id
├── is_active
└── joined_at

roles                            (seeded by migration 002)
├── student / pharmacist / educator
├── content_reviewer / institution_admin / platform_admin
└── is_system_role = True

permissions / role_permissions   (defined, not yet populated)

refresh_tokens
├── user_id → users.id
├── token_hash (SHA-256 of JWT, unique)
├── expires_at / is_revoked
└── device_info

audit_logs                       (table exists; not yet written to)
├── user_id / organization_id
├── action / resource_type / resource_id
└── extra_data / ip_address

materials
├── title / file_name / file_path / file_type / file_size
├── content_text (extracted)
└── created_at / updated_at

scenarios
├── material_id → materials.id (nullable, SET NULL on delete)
├── title / clinical_case / difficulty_level / specialty
├── key_concepts (JSON) / expected_answer
└── created_at / updated_at

interactions
├── scenario_id → scenarios.id (CASCADE delete)
├── user_id → users.id (nullable, SET NULL; populated when authenticated)
├── session_id (anonymous sessions)
├── user_answer / ai_feedback
├── score (0–1 float) / key_findings / next_steps / strengths / areas_for_improvement (JSON)
└── created_at
```

## Authentication Flow

```
Register  →  POST /api/auth/register  →  User created (is_verified=False)
Login     →  POST /api/auth/login     →  access_token (JWT, 30 min, in-memory)
                                     →  refresh_token (JWT, 30 days, localStorage)
                                     →  RefreshToken row (hashed) stored in DB

Silent    ←  401 on any protected request
refresh   →  POST /api/auth/refresh  →  old RT revoked, new AT+RT issued (rotation)

Logout    →  POST /api/auth/logout   →  RT marked is_revoked=True in DB
```

**Token security:**
- Access tokens stored in Zustand (memory only) — not in localStorage or cookies
- Refresh tokens stored in localStorage (`pharmlearn_rt`) — JWTs, verified server-side
- All refresh tokens stored as SHA-256 hashes in DB (never raw)
- Each token includes a `jti` (UUID) claim to prevent hash collisions under rapid login
- Token type claim (`"type": "access"` | `"type": "refresh"`) prevents cross-use

## RBAC Model

Six system roles (seeded by migration 002):

| Role | Scope | Notes |
|------|-------|-------|
| `student` | Org | Can practice scenarios |
| `pharmacist` | Org | Qualified professional building CPD |
| `educator` | Org | Creates and curates content |
| `content_reviewer` | Org | Reviews evidence-based content |
| `institution_admin` | Org | Manages org members and settings |
| `platform_admin` | Org | Full platform access |

`is_superuser=True` on a User record bypasses **all** org membership and permission checks. This is the operator/Anthropic-staff escape hatch.

Admin operations within an org require `institution_admin` or `platform_admin` membership (`ADMIN_ROLES` set in organizations.py).

## Migrations

| ID | Name | Tables |
|----|------|--------|
| 001 | initial_schema | materials, scenarios, interactions |
| 002 | identity_rbac | users, organizations, roles, permissions, role_permissions, organization_memberships, refresh_tokens, audit_logs |
| 003 | interaction_user_id | adds `user_id` FK column to interactions |

**Important**: Migrations use `postgresql.UUID` and `postgresql.JSON` — they target PostgreSQL only. Application models use `sqlalchemy.Uuid(as_uuid=True, native_uuid=True)` (cross-DB) so tests can run on SQLite in-memory databases via `Base.metadata.create_all`.

## Frontend Auth Architecture

```
useAuthInit (runs once on app mount)
  └─ localStorage has refresh token?
      ├─ No  →  authInitialized=True, user=null  →  ProtectedRoute redirects /login
      └─ Yes →  POST /api/auth/refresh (authHttp — no interceptors)
                ├─ OK  →  store access token in memory, store new RT in localStorage
                │         GET /api/auth/me → setCurrentUser → authInitialized=True
                └─ Fail → clearStoredRefreshToken() → authInitialized=True → /login

http interceptor (on 401 from any non-auth endpoint):
  └─ Silent refresh → retry original request with new access token
     └─ Refresh fails → clearAuth() + redirect /login
```

## Audit Logging

`app/services/audit.py` provides a single `log_action(db, *, action, ...)` coroutine that appends an immutable `AuditLog` row to the current session. The caller owns the commit boundary — `log_action` does not flush or commit.

**Actions logged:**

| Action | Trigger |
|--------|---------|
| `user.register` | New user created |
| `user.login` | Successful password authentication |
| `user.logout` | Refresh token revoked via logout endpoint |
| `auth.token_refresh` | Refresh token rotated |
| `org.create` | Organization created |
| `org.update` | Organization name / slug / type changed |
| `org.member_added` | Member added (or re-activated) |
| `org.member_role_updated` | Member's role changed |
| `org.member_removed` | Member deactivated |

**Fields stored:** `user_id` (actor), `organization_id` (where relevant), `action`, `resource_type`, `resource_id`, `extra_data` (safe metadata — never passwords or raw token values), `ip_address`, `created_at`.

Refresh token pruning runs inside the same DB transaction as `login` and `refresh_tokens`: any row for the user where `is_revoked=True` OR `expires_at < now` is deleted before the commit.

## Known Limitations & Technical Debt

1. **Email verification**: Column and `is_verified` flag exist; no verification flow is implemented.
2. **Expired refresh token background sweep**: Pruning runs per-user on login/refresh; no scheduled job removes tokens for inactive users.
3. **`RoleRead.permissions`**: Always returns `[]` in tests because no permissions are seeded. The query is correct (eager-loads via `role_permissions → permission`); permissions will appear once they are inserted.
4. **Progress tracking requires authenticated submissions**: Anonymous scenario attempts (no Bearer token) are not attributed to users and do not appear in progress analytics.
