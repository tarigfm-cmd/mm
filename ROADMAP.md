# PharmLearn AI — Product Roadmap

## Phase 1 — Foundation (Current)

Goal: Working platform with content ingestion, AI case generation, and interactive feedback.

- [x] FastAPI async backend with PostgreSQL + Redis
- [x] Material upload (PDF, DOCX, TXT, images with OCR)
- [x] Background text extraction
- [x] Claude AI clinical scenario generation
- [x] Interactive case practice with scored AI feedback
- [x] React frontend: dashboard, upload, scenario browser, case chat
- [x] Docker Compose dev environment
- [x] Domain stub packages for all Phase 2+ modules
- [x] Backend model/schema split by domain

## Identity Milestone — Core RBAC & Multi-Tenancy (Current)

Goal: Secure identity foundation before any user-facing features.

- [x] User model (PBKDF2-SHA256 passwords, is_superuser platform-admin flag)
- [x] Organization model (6 org types: university, pharmacy_chain, hospital, training_center, enterprise, individual_workspace)
- [x] OrganizationMembership — one user → many orgs, each with one Role
- [x] Role + Permission + RolePermission models (6 system roles seeded)
- [x] RefreshToken model (hashed, rotated on use)
- [x] AuditLog model
- [x] JWT auth (joserfc HS256) — access (30 min) + refresh (30 day) tokens
- [x] Auth routes: register, login, refresh, me, logout
- [x] RBAC FastAPI dependencies: get_current_user, require_superuser, require_org_role, has_permission
- [x] Alembic migration 002 for all 8 identity tables
- [x] 44 tests passing (password hashing, JWT, schema validation, role/permission logic)
- [ ] Email verification flow
- [ ] Profile update endpoint
- [ ] Frontend auth integration (login/register pages, token storage)

## Phase 2 — Users & Auth (continued)

Goal: Full user-facing auth and profile features.

- [ ] Email verification with token link
- [ ] Password reset flow
- [ ] Profile pages & progress history
- [ ] Session replacement: auth tokens instead of anonymous UUIDs
- [ ] Frontend login / register pages
- [ ] Protected frontend routes

Domain packages: `domains/users/`, `domains/organizations/`

## Phase 3 — Extended Learning Modes

Goal: Move beyond single-case chat to a full training ecosystem.

- [ ] OTC triage simulations (symptom → triage decision tree)
- [ ] Prescription screening workflows
- [ ] Drug interaction detection engine
- [ ] Red flag identification exercises
- [ ] Patient counselling scripts (scored roleplay)
- [ ] OSCE station builder & runner
- [ ] Pharmacy games: flashcards, drag-and-drop label matching, dose calculator
- [ ] Adaptive assessment engine (item difficulty calibration)
- [ ] AI tutor chat (open-ended pharmacy Q&A)

Domain packages: `domains/assessments/`, `domains/osce/`, `domains/games/`

## Phase 4 — Content Management & Evidence

Goal: Institutional-grade content quality and governance.

- [ ] Evidence-based content review workflow
- [ ] Content versioning with reviewer approval gates
- [ ] CSV bulk content import for educators
- [ ] Medical content tagging (BNF chapter, NICE guideline, MHRA alert)
- [ ] Evidence source linking (PubMed, NICE, BNF)
- [ ] Educator content studio (create custom cases)

Domain packages: `domains/content_review/`

## Phase 5 — Analytics & Monetisation

Goal: Institutional reporting and sustainable revenue.

- [ ] Learner progress dashboard (scores over time, weak areas)
- [ ] Cohort analytics for educators and institutions
- [ ] Subscription plans (Free / Pro / Institution)
- [ ] Stripe billing integration
- [ ] Usage-based plan limits (AI calls, storage)
- [ ] Admin dashboard (users, content, revenue)
- [ ] Export to PDF/CSV (certificates, progress reports)

Domain packages: `domains/analytics/`, `domains/subscriptions/`

## Phase 6 — Scale & Polish

Goal: Production hardening and reach.

- [ ] Redis caching for generated scenarios
- [ ] Vector search for related materials (pgvector or Pinecone)
- [ ] WebSocket real-time feedback (replace polling)
- [ ] Internationalisation (i18n) — Arabic, Spanish priority
- [ ] Mobile-responsive improvements
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Kubernetes deployment manifests
- [ ] GDPR-compliant data deletion

---

*Phases are indicative. Scope within each phase may shift based on user feedback.*
