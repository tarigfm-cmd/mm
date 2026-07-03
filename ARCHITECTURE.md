# Community Pharmacy Training SaaS Platform — Architecture

## System Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Frontend (React 18 + TypeScript + Vite)                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Login / Register / Forgot+Reset Password                           │   │
│  │  Training Library · Training Detail · Training Progress             │   │
│  │  Billing · Profile                                                  │   │
│  │  Admin: Governance Dashboard · Import Center · Content Library      │   │
│  │         Evidence · Region Rules · Approval Batches                  │   │
│  │         Billing Plans (PayPal config)                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
                            │ HTTPS / REST (JSON)
                            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  Reverse Proxy (Nginx — SPA serving, /api/ proxy to backend)               │
└────────────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI — async Python 3.11)                                     │
│                                                                            │
│  Active routes                                                             │
│  ├── /api/health                  # DB + Redis liveness                   │
│  ├── /api/auth/*                  # register, login, refresh, me, logout  │
│  │                                  forgot-password, reset-password,       │
│  │                                  change-password                        │
│  ├── /api/learn/*                 # training library, sessions, progress  │
│  ├── /api/billing/*               # plans, subscription, checkout,        │
│  │                                  webhooks, admin config                 │
│  ├── /api/content/*               # governance: items, versions,          │
│  │                                  reviews, publish, import, evidence     │
│  ├── /api/evidence/*              # evidence sources                      │
│  ├── /api/orgs/*                  # organisations + membership            │
│  ├── /api/roles                   # system roles                          │
│  ├── /api/scenarios/*             # Phase-1 scenario practice             │
│  ├── /api/materials/*             # Phase-1 document upload               │
│  ├── /api/progress                # Phase-1 scenario progress             │
│  └── /api/analytics/*             # learner failure analytics             │
│                                                                            │
│  Core services                                                             │
│  ├── core/security.py             # PBKDF2-SHA256, joserfc JWT            │
│  ├── core/limiter.py              # shared SlowAPI limiter                │
│  ├── core/dependencies.py         # get_current_user, RBAC guards         │
│  ├── services/entitlements.py     # plan limits, usage metering           │
│  ├── services/audit.py            # immutable audit log writer            │
│  ├── services/billing_status.py   # PayPal config health helper           │
│  ├── services/training_engine.py  # 8-dimension deterministic scoring     │
│  ├── services/payment_providers/  # PaymentProviderBase ABC + PayPal impl │
│  ├── services/ai_service.py       # Anthropic Claude (content tooling)    │
│  └── services/document_parser.py  # PDF/DOCX text extraction              │
│                                                                            │
│  Infrastructure                                                            │
│  ├── database.py                  # SQLAlchemy 2.0 async, asyncpg prod    │
│  ├── config.py                    # pydantic-settings, lru_cache          │
│  └── main.py                      # lifespan, secret validation, headers  │
└────────────────────────────────────────────────────────────────────────────┘
          │                   │                    │
          ▼                   ▼                    ▼
   ┌────────────┐     ┌─────────────┐     ┌──────────────┐
   │ PostgreSQL │     │    Redis    │     │ Anthropic    │
   │     15     │     │      7      │     │ Claude API   │
   └────────────┘     └─────────────┘     └──────────────┘
```

## Database Migrations

| ID | Name | Key tables |
|----|------|------------|
| 001 | initial_schema | materials, scenarios, interactions |
| 002 | identity_rbac | users, organisations, roles, permissions, role_permissions, organisation_memberships, refresh_tokens, audit_logs |
| 003 | interaction_user_id | adds `user_id` FK to interactions |
| 004 | content_governance | content_items, content_versions, evidence_sources, approval_batches, clinical_reviews, region_publishing_rules, publication_records, learner_failure_analytics |
| 005 | governance_permissions | seeds 10 governance permissions; assigns to educator / content_reviewer / institution_admin / platform_admin |
| 006 | import_pipeline | import_batches, import_row_errors |
| 007 | learner_training_sessions | learner_training_sessions |
| 008 | billing | subscription_plans, user_subscriptions, usage_events |
| 009 | payment_webhook_events | payment_webhook_events |
| 010 | paypal_plan_id | adds `external_paypal_plan_id` to subscription_plans |
| 011 | payment_checkout_sessions | payment_checkout_sessions |
| 012 | password_reset_tokens | password_reset_tokens |

**Important:** Migrations target PostgreSQL (`postgresql.UUID`, `postgresql.JSON`). Application models use `sqlalchemy.Uuid` (cross-DB) so tests run on SQLite in-memory via `Base.metadata.create_all`. Never use `Base.metadata.create_all` in production — always run Alembic.

## Data Model Summary

```
users
├── id (UUID PK)
├── email (unique) / username (unique) / full_name
├── hashed_password  (PBKDF2-SHA256, 260k iterations)
├── is_active / is_verified / is_superuser
└── created_at / updated_at

organisations
├── id / name / slug (unique) / org_type (6 types)
└── is_active / settings (JSON)

organisation_memberships         (user ↔ org, unique per pair)
├── user_id → users.id
├── organisation_id → organisations.id
├── role_id → roles.id
└── is_active / joined_at

roles (seeded by migration 002)
└── student | pharmacist | educator | content_reviewer | institution_admin | platform_admin

permissions / role_permissions   (10 governance permissions, seeded migration 005)

refresh_tokens
├── token_hash (SHA-256, unique)
└── expires_at / is_revoked / device_info

password_reset_tokens
├── token_hash (SHA-256, unique)
└── expires_at / used_at / request_ip / user_agent

audit_logs (immutable — all identity, org, and governance actions)

content_items / content_versions / evidence_sources
approval_batches / clinical_reviews / region_publishing_rules
publication_records / learner_failure_analytics
import_batches / import_row_errors

learner_training_sessions
subscription_plans / user_subscriptions / usage_events
payment_webhook_events / payment_checkout_sessions
```

## Authentication Flow

```
Register  → POST /api/auth/register       → User created (is_verified=False)
Login     → POST /api/auth/login          → access_token (JWT, 30 min, in-memory)
                                          → refresh_token (JWT, 30 days, localStorage)
                                          → RefreshToken row (hashed) stored in DB

Silent    ← 401 on any protected request
refresh   → POST /api/auth/refresh        → old RT revoked, new AT+RT issued (rotation)

Logout    → POST /api/auth/logout         → RT marked is_revoked=True in DB

Reset PW  → POST /api/auth/forgot-password  → token row created (SHA-256 hash stored)
          → POST /api/auth/reset-password   → hash lookup, mark used, revoke all RTs

Change PW → POST /api/auth/change-password  → verify current, enforce rules, revoke all RTs
```

**Token security:**
- Access tokens: Zustand memory only — never in localStorage or cookies
- Refresh tokens: `localStorage` (`pharmlearn_rt`) — rotated on every use
- All tokens stored as SHA-256 hashes in DB (never raw values)
- `jti` UUID claim per token prevents hash collisions under rapid login
- `type` claim (`access` | `refresh`) prevents cross-type use

## RBAC Model

Six system roles (seeded migration 002):

| Role | Notes |
|------|-------|
| `student` | Learner — practice training sessions |
| `pharmacist` | Qualified professional — CPD use |
| `educator` | Creates/curates content |
| `content_reviewer` | Reviews evidence-based content |
| `institution_admin` | Manages org members and settings |
| `platform_admin` | Full platform access |

`is_superuser=True` on a User bypasses **all** org-membership and permission checks. Used for platform operators.

Ten governance permissions (seeded migration 005): `content.import`, `content.review`, `content.approve`, `content.publish`, `content.unpublish`, `content.version.create`, `content.rollback`, `evidence.manage`, `analytics.view`, `analytics.view_org`.

**RBAC dependency factories in `core/dependencies.py`:**
- `require_content_permission(perm)` — platform-scoped: user holds `perm` in *any* active org membership
- `has_permission(perm)` — org-scoped: checks `perm` in the specific org from the path parameter

## Security Hardening

**Security headers (all responses):**
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
```
Applied via ASGI middleware in `main.py` — cannot be stripped by individual routes.

**Rate limits (SlowAPI, `core/limiter.py`):**
| Endpoint | Limit |
|----------|-------|
| `POST /api/auth/register` | 5/minute per IP |
| `POST /api/auth/login` | 10/minute per IP |
| `POST /api/auth/refresh` | 20/minute per IP |
| `POST /api/auth/forgot-password` | 3/minute per IP |
| `POST /api/auth/reset-password` | 5/minute per IP |
| `POST /api/auth/change-password` | 5/minute per IP |
| `POST /api/billing/checkout/paypal` | 10/minute per IP |
| `POST /api/billing/webhooks/paypal` | 120/minute per IP |

**Production secret validation (`main.py` lifespan):** Raises `RuntimeError` at startup if `SECRET_KEY` or `JWT_SECRET_KEY` hold default placeholder values, and warns on `EXPOSE_RESET_TOKEN_IN_DEV=True` or `PAYPAL_SKIP_WEBHOOK_VERIFY=True`. Bypassed only when `DEBUG=True`.

## Frontend Architecture

```
src/
├── App.tsx                 # Router, lazy routes, Toaster
├── components/
│   ├── Navigation.tsx      # Sidebar — auth-aware, superuser admin section
│   ├── ProtectedRoute.tsx  # Auth guard + layout shell
│   ├── AdminRoute.tsx      # Superuser guard
│   ├── governance/         # StatCard, StatusBadge, ConfirmActionDialog, etc.
│   └── learn/              # TrainingStepCard, TrainingResultPanel, etc.
├── hooks/
│   └── useAuthInit.ts      # Session restore from localStorage refresh token
├── pages/
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── ForgotPasswordPage.tsx
│   ├── ResetPasswordPage.tsx
│   ├── ProfilePage.tsx
│   ├── BillingPage.tsx
│   ├── PayPalSuccessPage.tsx
│   ├── PayPalCancelPage.tsx
│   ├── learn/
│   │   ├── TrainingLibraryPage.tsx
│   │   ├── TrainingDetailPage.tsx
│   │   └── TrainingProgressPage.tsx
│   ├── governance/
│   │   ├── GovernanceDashboard.tsx
│   │   ├── ImportCenter.tsx
│   │   ├── ApprovalBatchesPage.tsx
│   │   ├── ContentLibraryPage.tsx
│   │   ├── ContentDetailPage.tsx
│   │   ├── EvidenceManagementPage.tsx
│   │   └── RegionRulesPage.tsx
│   └── admin/
│       └── AdminBillingPlansPage.tsx
├── services/
│   ├── api.ts              # authApi + Axios with silent-refresh interceptor
│   ├── billingApi.ts       # billingApi — plans, subscription, checkout, admin
│   ├── governanceApi.ts    # importApi, contentApi, evidenceApi, etc.
│   └── learnApi.ts         # learnApi — browse, sessions, submit, progress
├── store/
│   └── appStore.ts         # Zustand — auth state (currentUser, authInitialized)
└── types/
    ├── index.ts            # User, Org, Auth schemas
    ├── billing.ts          # Plan, subscription, PayPal types
    ├── governance.ts       # Content, evidence, import types
    └── learn.ts            # Training flow, session, progress types
```

**Auth session restore (on app mount):**
```
useAuthInit
  └─ localStorage has refresh token?
      ├─ No  → authInitialized=True, user=null → ProtectedRoute → /login
      └─ Yes → POST /api/auth/refresh (no interceptors)
                ├─ OK   → store AT in memory, new RT in localStorage
                │         GET /api/auth/me → setCurrentUser → authInitialized=True
                └─ Fail → clearStoredRefreshToken() → authInitialized=True → /login

http interceptor (401 on non-auth endpoint):
  └─ Silent refresh → retry original request
     └─ Refresh fails → clearAuth() + redirect /login
```

## Payment Provider Abstraction

```
backend/app/services/payment_providers/
├── base.py      # PaymentProviderBase ABC, CheckoutResult, WebhookVerifyResult
├── paypal.py    # PayPalProvider — httpx async; create_subscription, verify_webhook,
│               #                  cancel_subscription, extract_paypal_period_dates
└── registry.py  # get_paypal_provider() factory (lru_cached, reads from Settings)
```

The abstraction is designed so an additional provider can be plugged in without touching the billing route layer. Shopify, Stripe, Paddle, and Lemon Squeezy are excluded from this project.

## Audit Logging

`services/audit.py` — `log_action(db, *, action, ...)` appends an immutable `AuditLog` row. Caller owns the commit boundary.

**Actions logged:** `user.register`, `user.login`, `user.logout`, `auth.token_refresh`, `org.create`, `org.update`, `org.member_added`, `org.member_role_updated`, `org.member_removed`, `content.item_created`, `content.version_created`, `content.version_rollback`, `content.review_created`, `content.published`, `content.unpublished`, `content.approval_batch_created`, `content.evidence_source_created`, `content.evidence_source_updated`.

Refresh token pruning runs in the same DB transaction as login and refresh: expired and revoked tokens for the user are deleted before commit.

## Known Limitations

1. **Email verification:** Column and `is_verified` flag exist; no verification email is sent.
2. **SMTP:** Password reset tokens are stored; the reset URL must be delivered manually in production until SMTP is integrated (see `DEPLOYMENT.md` § 8).
3. **Background token sweep:** Expired refresh tokens are pruned per-user on login/refresh; no scheduled job removes tokens for inactive users.
4. **AI tutor:** `ANTHROPIC_API_KEY` is currently used only for internal content tooling. The learner-facing AI tutor is not yet enabled.
