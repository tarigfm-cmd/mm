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

## Full Local E2E Journey

This section describes how to exercise both the admin and learner journeys end-to-end in a local development environment.

### Prerequisites

1. Start the stack: `docker-compose up`
2. Verify the API is up: `curl http://localhost:8000/api/health`
3. App should be at `http://localhost:5173`

### Step 1 — Seed published content (dev only)

A fresh database has no published content. Without published content, the learner Training Library is empty.

```bash
# From repo root — requires the Docker Compose backend to be running:
python scripts/dev_seed_published_content.py
```

This creates:
- One superuser: `dev-admin@pharmlearn.dev` / `DevAdmin1!`
- One drill content item (non-clinical dose conversion framework question) published to UK

The script is **idempotent** — safe to run multiple times. It refuses to run against production database hosts.

### Step 2 — Admin journey

1. Open `http://localhost:5173/login`
2. Sign in as `dev-admin@pharmlearn.dev` / `DevAdmin1!`
3. Click **Governance** (shown only to superusers)
4. **Dashboard** — stat cards show total/pending/approved/published counts
5. **Import Package** — upload a CSV or ZIP preview → commit → see import history
6. **Approval Batches** — create a batch, set team name and regions
7. **Content Library** — search by title/external ID, filter by status/type
8. **Content Detail** — view versions, submit clinical review, publish/unpublish per region
9. **Evidence Sources** — add and update evidence records; overdue items appear in amber alert
10. **Region Rules** — CRUD for publishing requirements per region

To publish imported content:
1. Import Center → preview CSV/ZIP → commit → content lands in `pending_review`
2. Content Library → open item → submit clinical review (decision: Approved)
3. Content Detail → publish for UK
4. Content now appears in learner Training Library

### Step 3 — Learner journey

1. Open `http://localhost:5173/register` to create a new account (or sign in if already registered)
2. After login you land at `http://localhost:5173/learn/content`
3. Region selector defaults to UK — change to see other regions
4. Click **Start training** on any item
5. Step through the guided training flow (briefing → red flags → decision → counseling)
6. Submit — see score, dimension feedback, and expert answer reveal
7. Visit `http://localhost:5173/learn/progress` to see cumulative stats
8. Click **Profile** in the sidebar to update your name/username

### Manual content publish (without seed script)

If you prefer to publish via the UI rather than the seed script:

```
Register as admin → Governance → Import Package
→ upload sample CSV (see CONTENT_GOVERNANCE.md for format)
→ Preview → Commit
→ Content Library → open item → Clinical Review (Approved)
→ Publish for UK
```

Alternatively, use `scripts/preview_content_package.py` to validate a package before importing.

## Auth Flow

### Frontend auth pages

| URL | Page |
|-----|------|
| `/login` | LoginPage — email + password, inline error, return-URL redirect |
| `/register` | RegisterPage — email, username, full name, password + confirm-password |
| `/profile` | ProfilePage — view/edit full name + username, account status, logout |

### Token storage

| Token | Storage | Notes |
|-------|---------|-------|
| Access token | Zustand memory store | Never written to localStorage or cookies |
| Refresh token | localStorage `pharmlearn_rt` | Rotated on every use; revoked on logout |

### Key behaviours

- After login or register, users land on `/learn/content` (or the originally requested URL for guarded pages).
- `ProtectedRoute` preserves the attempted URL as `state.from` and `LoginPage` reads it after sign-in.
- 401 responses from non-auth endpoints silently trigger a background token refresh; if refresh fails, the user is redirected to `/login`.
- Login errors (wrong credentials → 401) are shown as inline form errors — not toasts — because the response interceptor suppresses 401 toasts.
- Logout calls `POST /api/auth/logout` (best-effort) to revoke the server-side refresh token, then clears Zustand and localStorage.

### Auth API methods (`authApi` in `api.ts`)

| Method | Endpoint | Notes |
|--------|----------|-------|
| `login(credentials)` | `POST /api/auth/login` | Stores both tokens |
| `register(data)` | `POST /api/auth/register` | Returns `UserRead`; auto-login in UI |
| `me()` | `GET /api/auth/me` | Returns current `UserRead` |
| `updateMe(data)` | `PATCH /api/auth/me` | `{full_name?, username?}` |
| `logout()` | `POST /api/auth/logout` | Best-effort server revoke |
| `refresh(rt)` | `POST /api/auth/refresh` | Used by `useAuthInit` hook |

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

## Subscription & Billing

Plans, entitlements, and usage metering — no live payment processor connected (beta).

### Plans

| Code | Price | Sessions/month | OSCE | Games | Institution | Admin |
|------|-------|----------------|------|-------|-------------|-------|
| `free` | Free | 20 | No | No | No | No |
| `pro` | £19.99/mo | 1,000 | Yes | Yes | No | No |
| `institution` | £99/mo | 100,000 | Yes | Yes | Yes | No |
| `enterprise` | £499/mo | Unlimited | Yes | Yes | Yes | Yes |

Plans are seeded idempotently on startup via `_seed_subscription_plans()` in `main.py`.

### Default plan

All registered users get the **free** plan entitlement by default (no `UserSubscription` row required — entitlement service falls back to `free`).

Only a platform admin (`is_superuser=True`) can assign a plan to a user.

### Entitlement service

`backend/app/services/entitlements.py`:

| Function | Purpose |
|----------|---------|
| `get_user_current_subscription(db, user_id)` | Active subscription or `None` |
| `get_effective_plan(db, user_id)` | Plan from subscription, else free plan |
| `can_start_training_session(db, user_id, is_superuser)` | `(bool, reason)` — admins bypass |
| `record_usage_event(db, user_id, event_type, ...)` | Insert `UsageEvent`; caller commits |
| `count_monthly_usage(db, user_id, event_type)` | Count events in current calendar month |

### Billing API routes

| Method | Endpoint | Auth |
|--------|----------|------|
| `GET` | `/api/billing/plans` | Any authenticated user |
| `GET` | `/api/billing/me/subscription` | Any authenticated user |
| `GET` | `/api/billing/me/usage` | Any authenticated user |
| `POST` | `/api/billing/admin/users/{user_id}/subscription` | Superuser only |
| `GET` | `/api/billing/admin/plans` | Superuser only |
| `PATCH` | `/api/billing/admin/plans/{plan_code}` | Superuser only |

### Training session entitlement

`POST /api/learn/content/{id}/sessions` now:
1. Calls `can_start_training_session()` before creating the session
2. Returns **HTTP 402** with `"Training session limit reached for your current plan."` if the monthly limit is exceeded
3. Records `training_session_started` usage event on success

`POST /api/learn/sessions/{session_id}/submit` records `training_session_completed` on commit.

### Frontend billing pages

| URL | Page |
|-----|------|
| `/billing` | BillingPage — current plan, session usage bar, all 4 plan cards, upgrade CTA |
| `/admin/billing/plans` | AdminBillingPlansPage — plan table with PayPal Plan ID editor (superuser only) |

The **Billing** link appears in `Navigation` for all authenticated users.

When `startSession` returns 402, `TrainingDetailPage` shows a paywall card with a link to `/billing`.

`ProfilePage` shows the user's plan name as a badge (fetched from `GET /api/billing/me/subscription`).

### Upgrading during beta

Online checkout is not connected. To upgrade a user:

```bash
# Via API (requires superuser JWT)
curl -X POST http://localhost:8000/api/billing/admin/users/{user_id}/subscription \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan_code": "pro"}'
```

Or use the admin assignment endpoint from the Swagger docs at `http://localhost:8000/docs`.

### Running billing tests

```bash
cd backend
pytest tests/test_billing.py -v
```

22 tests covering: plan listing, free-tier fallback, subscription assignment, entitlement service (limit enforcement, superuser bypass, unlimited plans).

## PayPal Checkout & Webhooks

### Environment variables

```env
# PayPal credentials (leave blank to disable checkout; returns HTTP 503 gracefully)
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_WEBHOOK_ID=
PAYPAL_ENV=sandbox          # "sandbox" or "live"
PAYPAL_SKIP_WEBHOOK_VERIFY=false  # Set "true" in dev/test only. NEVER true in production.

# Public URL for PayPal return/cancel redirects
APP_PUBLIC_URL=http://localhost:5173
```

### Plan mapping — external_paypal_plan_id

Each paid plan has an `external_paypal_plan_id` column in `subscription_plans`. This stores
the PayPal billing plan ID (e.g. `P-XXXXXXXXXXXXXXXXXX`) created in the PayPal dashboard
or Catalog API.

**If a paid plan has no `external_paypal_plan_id`, checkout returns HTTP 422** —
"PayPal checkout is not configured for this plan yet." The plan button on the billing page
also shows "Checkout not configured for this plan yet." in place of the PayPal button.

To set the PayPal plan ID for a plan, use the admin UI or API:

**Admin UI (recommended):**
1. Sign in as a superuser
2. Navigate to `/admin/billing/plans`
3. Click **Edit** next to the plan, paste the `P-XXXXXXXXXXXXXXXXXX` ID, click **Save**

**API (superuser JWT required):**
```bash
curl -X PATCH http://localhost:8000/api/billing/admin/plans/pro \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"external_paypal_plan_id": "P-XXXXXXXXXXXXXXXXXX"}'
```

**Direct DB (if API is unavailable):**
```sql
UPDATE subscription_plans SET external_paypal_plan_id = 'P-XXXXXXXXXXXXXXXXXX'
WHERE code = 'pro';
```

The internal `plan_code` (e.g. "pro") is **never sent to PayPal** — only `external_paypal_plan_id`
is used in the PayPal subscription creation request.

### PayPal sandbox setup

1. Create a sandbox app at https://developer.paypal.com/developer/applications
2. Copy `Client ID` and `Secret` to `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET`
3. Create billing plans in the PayPal Catalog API (see PayPal docs) — note the `P-...` plan ID
4. Set `external_paypal_plan_id` on each paid plan in the database (see above)
5. Set up a webhook listener via `ngrok`: `ngrok http 8000`
6. Register `https://<ngrok-id>.ngrok.io/api/billing/webhooks/paypal` in PayPal developer portal
7. Copy the Webhook ID to `PAYPAL_WEBHOOK_ID`

### Sandbox test checklist

- [ ] `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` set from sandbox app
- [ ] `PAYPAL_ENV=sandbox`
- [ ] `PAYPAL_WEBHOOK_ID` set from PayPal developer webhook registration
- [ ] `external_paypal_plan_id` set on at least one plan (e.g. Pro)
- [ ] `APP_PUBLIC_URL` points to a reachable URL (e.g. ngrok tunnel for local dev)
- [ ] `GET /api/billing/plans` returns the plan with `external_paypal_plan_id` populated
- [ ] `POST /api/billing/checkout/paypal { plan_code: "pro" }` returns `checkout_url`
- [ ] Browser redirect to `checkout_url` shows PayPal subscription approval page
- [ ] After approval, PayPal redirects to `{APP_PUBLIC_URL}/billing/success`
- [ ] PayPal sends `BILLING.SUBSCRIPTION.ACTIVATED` webhook to `POST /api/billing/webhooks/paypal`
- [ ] `payment_webhook_events` table has a processed row; `user_subscriptions` row updated to `active`

### Checkout flow

```
POST /api/billing/checkout/paypal   { plan_code: "pro" }
  → validates: PayPal configured, plan active, plan paid, external_paypal_plan_id set
  → calls PayPal /v1/billing/subscriptions with external_paypal_plan_id (not plan code)
  → returns { checkout_url, external_subscription_id, status, provider }
  → records billing_checkout_started usage event (only on success)
  → Frontend redirects user to checkout_url (PayPal approval page)
  → User approves → PayPal redirects to {APP_PUBLIC_URL}/billing/success
  → PayPal POSTs BILLING.SUBSCRIPTION.ACTIVATED webhook (source of truth)
  → Webhook activates UserSubscription — never the return URL
```

Missing credentials → HTTP 503 "PayPal checkout is not configured yet."
Missing `external_paypal_plan_id` → HTTP 422 "PayPal checkout is not configured for this plan yet."

### Success and cancel pages

| URL | Behaviour |
|-----|-----------|
| `/billing/success` | Shows "Payment received by PayPal. Subscription activates once confirmed." Fetches current subscription status. Does NOT activate the plan itself. |
| `/billing/cancel` | Shows "Checkout cancelled. No payment taken." Links back to `/billing`. |

### Webhook endpoint

```
POST /api/billing/webhooks/paypal   (no auth required — verified by PayPal signature)
```

- Verifies signature via `/v1/notifications/verify-webhook-signature` (unless `PAYPAL_SKIP_WEBHOOK_VERIFY=true`)
- `PAYPAL_SKIP_WEBHOOK_VERIFY` must only be `true` in dev/test. Production rejects without valid signature.
- Missing `PAYPAL_WEBHOOK_ID` → rejected (fail-closed)
- Idempotent: duplicate events return `{ status: "already_processed" }`
- Resolves subscription via `external_subscription_id`, then falls back to `custom_id` (user UUID set at checkout)
- Unresolvable events stored with `processed_status="unresolved"` — no crash
- Raw webhook body is never stored; only a safe `payload_summary` is persisted

| PayPal event | Subscription status |
|---|---|
| `BILLING.SUBSCRIPTION.ACTIVATED` | `active` |
| `BILLING.SUBSCRIPTION.CANCELLED` | `canceled` |
| `BILLING.SUBSCRIPTION.SUSPENDED` | `past_due` |
| `BILLING.SUBSCRIPTION.EXPIRED` | `expired` |
| `BILLING.SUBSCRIPTION.PAYMENT.FAILED` | `past_due` |

### Provider abstraction

`backend/app/services/payment_providers/`:
- `base.py` — `PaymentProviderBase` ABC, `CheckoutResult`, `WebhookVerifyResult`
- `paypal.py` — `PayPalProvider` (httpx-based, async); `create_subscription` requires explicit `paypal_plan_id`
- `registry.py` — `get_paypal_provider()` factory (lru_cached, reads from Settings)

### Running PayPal tests

```bash
cd backend
pytest tests/test_paypal.py -v
```

42 tests — no real PayPal credentials required. All HTTP calls are mocked.

### Payment integrations excluded

Stripe, Paddle, Lemon Squeezy, and Shopify are **permanently excluded** from this project.
