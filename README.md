# Community Pharmacy Training SaaS Platform

A SaaS platform for community pharmacy education and professional development. Supports structured training content, interactive learning sessions, evidence-based content governance, multi-tenant organisations, and subscription billing.

**Status:** MVP / Beta-ready foundation — full backend test suite, TypeScript-clean frontend, production deployment docs.

---

## Who This Is For

- Community pharmacists building CPD portfolios
- Pharmacy students preparing for practice
- Pharmacy schools and training centres delivering structured curricula
- Healthcare institutions preparing pharmacists for real-world patient interactions

## Who This Is Not For

This platform is a **training and structured-learning tool**. It is not:
- A substitute for pharmacist clinical judgment
- A source of direct patient care decisions
- A replacement for local formulary, protocols, or regulatory requirements
- An emergency medical advice service

No AI clinical advice is currently enabled. All training content is administrator-governed and clinically reviewed before publication.

---

## Implemented Modules

| Module | Status |
|--------|--------|
| User authentication — register, login, JWT sessions (30 min access / 30-day refresh) | **Active** |
| Password reset and change password (token-based, no SMTP required for dev) | **Active** |
| RBAC — 6 system roles, permission-based dependency guards | **Active** |
| Multi-tenant organisations with per-org role assignments | **Active** |
| Evidence-based content governance — create, version, clinical review, publish | **Active** |
| Bulk CSV / ZIP content import pipeline with preview and commit | **Active** |
| Admin content governance UI — dashboard, import center, approval batches, evidence, region rules | **Active** |
| Learner training library — browse published content by region, type, difficulty | **Active** |
| Interactive training sessions — step-based flow, 8-dimension deterministic scoring, reveal | **Active** |
| Learner progress analytics — session counts, dimension breakdown, recommendations | **Active** |
| Subscription plans — Free / Pro / Institution / Enterprise with monthly session metering | **Active** |
| PayPal checkout and webhook foundation — subscription lifecycle, idempotent event handling | **Active** |
| Subscription lifecycle — pending activation, active, cancellation, period tracking | **Active** |
| Admin PayPal readiness panel — credential health, per-plan checkout status | **Active** |
| Security headers — X-Content-Type-Options, X-Frame-Options, Referrer-Policy | **Active** |
| Rate limiting — per-IP on all auth and billing endpoints | **Active** |
| Audit logging — immutable trail for all auth, org, and content actions | **Active** |
| OTC triage simulations | Roadmap |
| Prescription screening workflows | Roadmap |
| AI tutor (open-ended pharmacy Q&A) | Roadmap — safety-gated |
| OSCE station builder | Roadmap |
| Pharmacy games and flashcards | Roadmap |
| Email verification and SMTP integration | Roadmap |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend framework | FastAPI 0.104 (async) |
| Database ORM | SQLAlchemy 2.0 async |
| Migrations | Alembic (12 migrations, single head) |
| Database — production | PostgreSQL 15 |
| Database — tests | SQLite in-memory (aiosqlite) |
| Password hashing | PBKDF2-SHA256 (260 000 iterations, stdlib) |
| JWT | joserfc HS256 — access (30 min) + refresh (30 days) |
| Rate limiting | SlowAPI |
| AI provider | Anthropic Claude (content governance tooling; AI tutor not yet enabled) |
| Frontend framework | React 18 + TypeScript |
| Build tool | Vite 5 |
| Styling | Tailwind CSS 3 |
| State management | Zustand 4 |
| HTTP client | Axios 1.6 |
| Containerisation | Docker + Docker Compose |
| Reverse proxy / SPA server | Nginx |
| Payment provider | PayPal Subscriptions v1 + Webhooks |

---

## Quick Start (Docker Compose)

```bash
# 1. Clone
git clone https://github.com/tarigfm-cmd/mm.git && cd mm

# 2. Configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY, JWT_SECRET_KEY, DB_PASSWORD, ANTHROPIC_API_KEY
# (see DEPLOYMENT.md for required variables)

# 3. Start all services
docker-compose up

# Frontend   → http://localhost:5173
# Backend    → http://localhost:8000
# API docs   → http://localhost:8000/docs
```

### Run database migrations

```bash
cd backend
alembic upgrade head
```

### Seed development content (optional)

Creates one superuser and one published demo drill item:

```bash
python scripts/dev_seed_published_content.py
# Superuser: dev-admin@pharmlearn.dev / DevAdmin1!
```

---

## Local Development (without Docker)

See [DEVELOPMENT.md](DEVELOPMENT.md) for the full step-by-step guide including frontend dev server, backend virtualenv setup, and the full E2E admin + learner journey.

---

## Key URLs

| URL | Description |
|-----|-------------|
| `http://localhost:5173` | Frontend SPA |
| `http://localhost:5173/learn/content` | Learner training library |
| `http://localhost:5173/learn/progress` | Learner progress analytics |
| `http://localhost:5173/billing` | Subscription and billing page |
| `http://localhost:5173/profile` | User profile and password change |
| `http://localhost:5173/admin/governance` | Admin content governance (superusers only) |
| `http://localhost:5173/admin/billing/plans` | Admin PayPal plan configuration (superusers only) |
| `http://localhost:8000/docs` | Interactive API documentation |
| `http://localhost:8000/api/health` | Health check (database + Redis status) |

---

## API Routes

```
# Health
GET  /api/health

# Auth
POST  /api/auth/register
POST  /api/auth/login
POST  /api/auth/refresh
GET   /api/auth/me
PATCH /api/auth/me
POST  /api/auth/logout
POST  /api/auth/forgot-password
POST  /api/auth/reset-password
POST  /api/auth/change-password

# Learner training
GET  /api/learn/content
GET  /api/learn/content/{id}
GET  /api/learn/content/{id}/training-flow
POST /api/learn/content/{id}/sessions
POST /api/learn/sessions/{id}/submit
POST /api/learn/content/{id}/attempt
GET  /api/learn/progress

# Billing
GET  /api/billing/plans
GET  /api/billing/me/subscription
GET  /api/billing/me/usage
POST /api/billing/me/subscription/cancel
POST /api/billing/checkout/paypal
POST /api/billing/webhooks/paypal
POST /api/billing/admin/users/{user_id}/subscription
GET  /api/billing/admin/plans
PATCH /api/billing/admin/plans/{plan_code}
GET  /api/billing/admin/paypal/status

# Content governance (RBAC-gated)
GET/POST /api/content/items
GET/PATCH /api/content/items/{id}
POST /api/content/items/{id}/versions
POST /api/content/items/{id}/versions/{vid}/rollback
POST /api/content/items/{id}/reviews
POST/DELETE /api/content/items/{id}/publish/{region}
POST /api/content/import/preview
POST /api/content/import/commit
GET  /api/content/import/batches
GET  /api/content/governance-summary
GET/POST /api/content/region-rules
PATCH /api/content/region-rules/{id}

# Evidence sources
GET/POST /api/evidence
PATCH /api/evidence/{id}

# Organizations
POST /api/orgs
GET  /api/orgs
GET/PATCH /api/orgs/{slug}
GET/POST /api/orgs/{slug}/members
PATCH/DELETE /api/orgs/{slug}/members/{user_id}
GET  /api/roles
```

Full interactive docs: `http://localhost:8000/docs`

---

## Testing

```bash
# Backend — 414 tests, SQLite in-memory (no PostgreSQL required)
cd backend && pytest tests/ -v

# Frontend TypeScript check
cd frontend && npx tsc --noEmit

# Frontend production build
cd frontend && npm run build
```

All tests pass. Frontend TypeScript check: zero errors. Production build: succeeds.

---

## Payments

- **PayPal** is the primary checkout provider (Subscriptions v1 + Webhooks)
- **Shopify** is permanently excluded from this project
- **Stripe, Paddle, Lemon Squeezy** are not planned — future providers would follow the existing `PaymentProviderBase` abstraction in `backend/app/services/payment_providers/`
- PayPal checkout requires sandbox configuration before live use — see [DEVELOPMENT.md](DEVELOPMENT.md) → "PayPal Checkout & Webhooks" for the 10-step sandbox setup guide

---

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full production checklist:
- Required environment variables and security flags
- Migration command (`alembic upgrade head`)
- Docker Compose start sequence
- Health check, first admin creation, PayPal live setup
- Rate limit table and security headers documentation
- Deployment checklist summary

---

## Roadmap

### Next

- PayPal real sandbox end-to-end test run
- Production server deployment
- UI/UX design polish pass
- Real pharmacy content review and publishing workflow
- SMTP email integration for password reset

### Future

- AI tutor (open-ended pharmacy Q&A) — safety-gated, requires content governance review
- OTC triage simulations
- OSCE station builder and runner
- Pharmacy games, flashcards, dose calculator
- Advanced adaptive assessment engine
- Institution cohort analytics dashboard
- Team/institutional billing
- Mobile-responsive improvements
- GDPR-compliant data deletion

---

## Clinical Safety Note

This platform is designed for structured training and professional development. It does not:
- Generate or deliver clinical advice to patients
- Replace pharmacist judgment in dispensing or patient counselling
- Substitute for local formulary, BNF guidance, MHRA alerts, NICE guidelines, or employer protocols
- Provide real-time drug interaction checking for live patient cases

All training content is administrator-managed and subject to the clinical review workflow before publication. Platform administrators are responsible for ensuring that published content is appropriate for their jurisdiction and user group.

---

## Known Limitations

- Email verification flow is not implemented (users are marked unverified; no email is sent)
- Password reset requires SMTP integration for production; dev-only `EXPOSE_RESET_TOKEN_IN_DEV` flag provides the reset URL directly in the API response
- Expired refresh token cleanup runs per-user on login/refresh; no background sweep for inactive users
- AI tutor is not enabled; `ANTHROPIC_API_KEY` is used only for internal content tooling in the current build
