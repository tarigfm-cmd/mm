# Production Deployment Checklist

Use this document before every production deployment. Work through each section top-to-bottom.

---

## 1. Pre-flight — Environment Variables

Copy `.env.example` to `.env` and set every variable below. The app **refuses to start** in production (`DEBUG=False`) if any unsafe default secret is detected.

### Required (app will not start without these)

| Variable | Notes |
|----------|-------|
| `SECRET_KEY` | 50+ char random hex. `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_SECRET_KEY` | 32+ char random hex. Same command as above. |
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | PostgreSQL host (Docker service name or external host) |
| `DB_PORT` | PostgreSQL port (default `5432`) |
| `DB_NAME` | Database name |
| `REDIS_URL` | Full Redis URL, e.g. `redis://redis:6379/0` |

### Security flags (must remain False in production)

| Variable | Default | Notes |
|----------|---------|-------|
| `DEBUG` | `False` | **Never True in production.** Enables `Base.metadata.create_all` and bypasses secret validation. |
| `EXPOSE_RESET_TOKEN_IN_DEV` | `False` | **Never True in production.** Exposes raw password-reset URL in API response. |
| `PAYPAL_SKIP_WEBHOOK_VERIFY` | `False` | **Never True in production.** Disables PayPal webhook signature verification. |

### Recommended production settings

```env
DEBUG=False
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-domain.example.com
APP_PUBLIC_URL=https://your-domain.example.com

JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=60

MAX_UPLOAD_SIZE=52428800
UPLOAD_DIR=./uploads
ALLOWED_EXTENSIONS=pdf,png,jpg,jpeg,txt,docx

PAYPAL_ENV=live
VITE_API_URL=
```

`VITE_API_URL` must be **empty** — a relative path so SPA API calls go through the nginx proxy, not directly to the backend.

### AI

```env
ANTHROPIC_API_KEY=sk-ant-...
AI_MODEL=claude-sonnet-4-6
```

### PayPal (leave blank to disable checkout gracefully — returns HTTP 503)

```env
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_WEBHOOK_ID=
PAYPAL_ENV=live
```

---

## 2. Database Migrations

Run migrations **before** starting the application. Never rely on `Base.metadata.create_all` — that is only active when `DEBUG=True`.

```bash
cd backend
alembic upgrade head
```

Verify the migration chain has a single head:

```bash
alembic heads
# Expected output: one revision ID — 012...
```

Current chain: `001 → 002 → 003 → 004 → 005 → 006 → 007 → 008 → 009 → 010 → 011 → 012`

If you see multiple heads, **stop the deployment** and resolve the branch before proceeding.

---

## 3. Build

### Frontend

```bash
cd frontend
npm ci
npm run build
```

Output lands in `frontend/dist/`. The Docker build copies this into the nginx image.

TypeScript check (run before building):

```bash
npx tsc --noEmit
```

### Backend

No build step required. Docker builds install requirements from `requirements.txt`.

---

## 4. Docker Compose Production Start

```bash
docker-compose up -d
```

Services:
- **db** — PostgreSQL 15
- **redis** — Redis 7
- **backend** — FastAPI on port 8000 (internal only)
- **frontend** — nginx serving SPA + proxying `/api/` to backend on port 80

The nginx config (`frontend/nginx-frontend.conf`) proxies all `/api/` requests to `http://backend:8000`. Because `VITE_API_URL` is empty (relative paths), all SPA API calls go through nginx — the backend port is never exposed directly.

---

## 5. Health Check

```bash
curl https://your-domain.example.com/api/health
```

Expected response:

```json
{"status": "ok", "database": "ok", "redis": "ok"}
```

If `"database": "error"` or `"redis": "error"`, check service connectivity before proceeding.

---

## 6. First Admin User

On a fresh database, create the first platform administrator directly:

```bash
# 1. Register
curl -X POST https://your-domain.example.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","username":"admin","password":"StrongPass1!","full_name":"Platform Admin"}'

# 2. Promote to superuser — direct DB access required for the first admin only
psql -U $DB_USER -d $DB_NAME \
  -c "UPDATE users SET is_superuser = true WHERE email = 'admin@example.com';"

# 3. Verify
curl -X POST https://your-domain.example.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"StrongPass1!"}'
```

After the first admin exists, all subsequent admin promotions can be done via the Swagger UI at `/docs`.

---

## 7. PayPal Setup (if using checkout)

See `DEVELOPMENT.md` → "PayPal sandbox setup sequence" for the full 10-step guide. Production differences:

- Set `PAYPAL_ENV=live` (not `sandbox`)
- Use live credentials from `https://developer.paypal.com`
- `PAYPAL_SKIP_WEBHOOK_VERIFY=False` (default — never override in production)
- Register the webhook URL: `{APP_PUBLIC_URL}/api/billing/webhooks/paypal`

Verify readiness at `/admin/billing/plans` (sign in as superuser).

---

## 8. Password Reset Limitation

**There is no SMTP server.** Password reset tokens are generated and stored, but the reset email is not sent automatically.

**Beta workaround options:**

1. **Dev flag (dev/staging only)** — set `EXPOSE_RESET_TOKEN_IN_DEV=True` to get the raw reset URL back from the `POST /api/auth/forgot-password` response. The `/forgot-password` page displays it. Never use this in production.
2. **Direct token lookup** — query `password_reset_tokens` table for the user, construct URL as `{APP_PUBLIC_URL}/reset-password?token={raw_token}`. Note: only the SHA-256 hash is stored; for this approach use the dev flag.
3. **SMTP integration** — wire an email provider (SendGrid, SES, Mailgun) into `POST /api/auth/forgot-password`. Planned future milestone.

---

## 9. Rate Limiting

Rate limits are applied on all sensitive endpoints:

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

Clients that exceed the limit receive HTTP 429. Rate limiting is implemented via SlowAPI and is always enabled in production (the test fixture that disables it only runs during pytest).

---

## 10. Security Headers

All responses include:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
```

Applied via ASGI middleware in `backend/app/main.py` — cannot be stripped by individual routes.

---

## 11. Backup Recommendation

Before any migration or deployment:

```bash
pg_dump -U $DB_USER -d $DB_NAME -F c -f backup_$(date +%Y%m%d_%H%M%S).dump
```

Restore:

```bash
pg_restore -U $DB_USER -d $DB_NAME -F c backup_YYYYMMDD_HHMMSS.dump
```

---

## 12. Monitoring

Set `SENTRY_DSN` to enable Sentry error tracking. Leave blank to disable.

---

## Deployment Checklist Summary

- [ ] `.env` copied from `.env.example`; all required variables set
- [ ] `SECRET_KEY` is a unique random value (not the example default)
- [ ] `JWT_SECRET_KEY` is a unique random value (not the example default)
- [ ] `DEBUG=False`
- [ ] `EXPOSE_RESET_TOKEN_IN_DEV=False`
- [ ] `PAYPAL_SKIP_WEBHOOK_VERIFY=False`
- [ ] `CORS_ORIGINS` set to the real domain (not `*`)
- [ ] `APP_PUBLIC_URL` set to the real public URL
- [ ] `VITE_API_URL` is empty (nginx proxies `/api/`)
- [ ] Database backup taken
- [ ] `alembic upgrade head` run and completed without errors
- [ ] `alembic heads` shows exactly one head
- [ ] `npm run build` succeeded (or Docker build passed)
- [ ] `docker-compose up -d` started all services
- [ ] `GET /api/health` returns `{"status":"ok","database":"ok","redis":"ok"}`
- [ ] First admin user created and verified
- [ ] PayPal credentials configured and readiness check passes (if using checkout)
