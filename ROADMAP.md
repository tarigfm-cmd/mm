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

## Known Debt Closure Gate (Complete)

Goal: Fix documented architectural debt before building new modules.

- [x] AuditLog written for all identity and org actions (register, login, logout, token refresh, org create/update, member add/update/remove)
- [x] `RoleRead.permissions` now loaded via eager join (was always `[]`)
- [x] `ScenarioResponse.interaction_count` accurate in `get_scenario` (was always `0`)
- [x] Organization PATCH uses `OrganizationUpdate` with all-optional fields (was requiring all fields)
- [x] Expired/revoked refresh tokens pruned per-user on login and token refresh

## Evidence-Based Content Governance Foundation (Complete)

Goal: Production-grade content lifecycle management before learner-facing features go live.

- [x] `ContentItem` model — unified parent for all educational content types (8 content types)
- [x] `ContentVersion` — immutable snapshot with SHA-256 content hash; circular FK via `use_alter=True`
- [x] `EvidenceSource` — tracked external clinical evidence with `next_review_due_at` scheduling
- [x] `ApprovalBatch` — bulk external-reviewer sign-off records with manifest hash
- [x] `ClinicalReview` — per-item pharmacist approval; `approved / approved_with_conditions / rejected / needs_revision`
- [x] `RegionPublishingRule` — per-region, per-content-type publishing requirements
- [x] `PublicationRecord` — tracks where/when content was published per region
- [x] `LearnerFailureAnalytics` — content-version-aware failure type tracking (6 failure dimensions)
- [x] Alembic migration 004 — all 8 governance tables
- [x] Full RBAC enforcement: learners see only published content; write operations require `is_superuser`
- [x] Publish gate: requires version + at least one approved clinical review
- [x] Rollback: creates new immutable version copied from target
- [x] Multi-region publishing: per-region publication records; `GET /api/content/published?region=UK`
- [x] 9 audit events for all governance writes
- [x] Analytics: failure hotspots, per-item failure summary, org weakness map
- [x] Bulk CSV/ZIP import pipeline: `ImportBatch` + `ImportRowError` models, Alembic migration 006
- [x] `POST /api/content/import/preview` — validate CSV/ZIP, detect duplicates, report errors without DB writes
- [x] `POST /api/content/import/commit` — create `ContentItem`, `ContentVersion`, `EvidenceSource`, `RegionPublishingRule`, `ImportBatch`
- [x] Security controls: path traversal rejection, nested ZIP rejection, 200 MB upload / 600 MB uncompressed limits, 10k row limit
- [x] RBAC: `content.import` for preview/commit; `content.approve` required to set `clinically_approved` status on import
- [x] Duplicate detection: within-upload (external_id + hash) and against DB; duplicates skipped, not errored
- [x] Never auto-publishes imported content; all items land in `pending_review` (or `clinically_approved` if reviewer and approved status)
- [x] Audit log writes only safe metadata — no clinical payload logged
- [x] 49 import pipeline tests (209 total, all passing)
- [x] `CONTENT_GOVERNANCE.md` — updated with full import API reference, validation rules, security constraints

## Admin and Reviewer Content Governance UI (Complete)

Goal: Internal admin interface for managing the community pharmacy content lifecycle — not a learner UI.

- [x] `AdminRoute` — superuser gate; non-superusers see "Insufficient permissions" screen
- [x] `GovernanceLayout` — horizontal tab nav inside main content area (no second sidebar)
- [x] `GovernanceDashboard` — single `GET /api/content/governance-summary` for all stat cards; by-content-type breakdown chips; 3-column panel (evidence due, approval batches, recent imports)
- [x] `ImportCenter` — 4-step wizard: upload → preview (blue) → optional approval batch → commit (amber); ConfirmActionDialog before commit; recent import history from `importBatchApi`
- [x] `ApprovalBatchesPage` — create and list pharmacist team sign-off batches with region toggles
- [x] `ContentLibraryPage` — paginated table (20/page) with status, type, domain, and search (title/external_id) filters; `external_id` column displayed
- [x] `ContentDetailPage` — metadata grid, version history with rollback, clinical review submission, per-region publish/unpublish; all destructive actions confirmed
- [x] `EvidenceManagementPage` — due-for-review amber alert, region/status filters, create form, inline edit
- [x] `RegionRulesPage` — live CRUD: create rules, toggle allowed statuses, inline edit, deactivate with ConfirmActionDialog; backed by `GET/POST/PATCH /api/content/region-rules`
- [x] Shared components: StatCard, StatusBadge, RegionBadge, ContentTypeBadge, EvidenceStatusBadge, ConfirmActionDialog, FileUploadPanel, ImportPreviewTable, CommitResultPanel
- [x] `governanceApi.ts` — 7 API objects: `importApi`, `approvalBatchApi`, `contentApi` (with `search`), `evidenceApi`, `governanceSummaryApi`, `importBatchApi`, `regionRulesApi`
- [x] `types/governance.ts` — full TypeScript schema mirroring all backend Pydantic models incl. 6 new types
- [x] Navigation updated — "Governance" link visible only to superusers (ShieldCheckIcon, amber active state)
- [x] `App.tsx` — all 7 governance pages registered as lazy routes under `/admin/governance`
- [x] TypeScript check: `npx tsc --noEmit` passes with zero errors
- [x] DEVELOPMENT.md + CONTENT_GOVERNANCE.md + ROADMAP.md updated

## Admin Governance UI Stabilization + Backend Contract Closure (Complete)

Goal: Close gaps discovered after the initial admin UI build — real data everywhere, no static placeholders.

- [x] `external_id` exposed in `ContentItemListItem` (was missing from list schema; table showed "—")
- [x] `GET /api/content/governance-summary` — single aggregate endpoint; replaces 5 chatty `GET /items?page=1&per_page=1&status=X` calls
- [x] `GET /api/content/import/batches` + `GET /api/content/import/batches/{id}` — safe import history; no clinical payloads, no raw error JSON
- [x] `GET/POST/PATCH /api/content/region-rules` — full CRUD with RBAC (`content.review` for GET; `content.publish` for POST/PATCH)
- [x] `search` param on `GET /api/content/items` — ILIKE on title and external_id (max 200 chars)
- [x] `GovernanceDashboard` updated to use `governanceSummaryApi` + `importBatchApi`
- [x] `ContentLibraryPage` updated with search input + real `external_id` display
- [x] `ImportCenter` updated with recent import history panel
- [x] `RegionRulesPage` rewritten from static placeholder to live CRUD
- [x] 26 new backend tests in `test_admin_ui_stabilization.py`; full suite 243/243 passing
- [x] TypeScript check: zero errors

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
- [x] CSV bulk content import for educators (implemented in Phase 1 milestone)
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
