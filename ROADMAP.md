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

## Interactive Training Engine — Phase 2 (Complete)

Goal: Make training feel like real community pharmacy practice — step-based flow, multi-dimensional scoring, dimension feedback, post-submission reveal, and richer progress analytics.

- [x] `LearnerTrainingSession` model — tracks guided sessions per user/content/region; statuses: started, completed, abandoned
- [x] Alembic migration 007 — `learner_training_sessions` table
- [x] `training_engine.py` service — deterministic 8-dimension scoring; no AI; no invented clinical content; `not_assessable` for unscored dimensions
- [x] `GET /api/learn/content/{id}/training-flow?region_code=` — returns structured pre-submission step blueprint per content type; hidden fields never included
- [x] `POST /api/learn/content/{id}/sessions` — creates session; verifies published; stores current version
- [x] `POST /api/learn/sessions/{id}/submit` — user-scoped; idempotency gate; deterministic scoring; creates LearnerFailureAnalytics; returns dimension_feedback + reveal_summary
- [x] `GET /api/learn/progress` — upgraded: completed_sessions, average_score_percent, strongest/weakest dimension, dimension_breakdown, recent_sessions, recommended_next_content_type/domain
- [x] Scoring dimensions: red_flag_recognition, triage_or_referral_decision, medication_safety, counseling_quality, documentation_quality, calculation_accuracy, interaction_detection, communication_safety
- [x] Hidden/reveal security: 7 answer keys never appear before submission; reveal_summary only in submit response
- [x] TrainingDetailPage upgraded — flow fetch → session start → step-by-step cards → submit → result with dimension feedback + reveal
- [x] TrainingProgressPage upgraded — 4 stat cards, strongest/weakest dim, recommendation CTA, recent sessions table
- [x] New components: TrainingStepCard, TrainingProgressIndicator, DimensionScoreCard, TrainingResultPanel, ConfidenceSelector, RedFlagSelector, ActionResponseInput
- [x] `learnApi.ts` — added getTrainingFlow, startSession, submitSession
- [x] `types/learn.ts` — full TypeScript types for all Phase 2 schemas
- [x] 25 new backend tests in `test_training_engine.py`; full suite 293/293 passing
- [x] TypeScript check: zero errors
- [x] CONTENT_GOVERNANCE.md, DEVELOPMENT.md, ROADMAP.md updated

## Interactive Training Engine Stabilization Gate (Complete)

Goal: Harden engine correctness, close REVEAL_KEYS drift risk, add boundary tests.

- [x] `learn.py` imports `REVEAL_KEYS` directly from `training_engine.py` — single source of truth
- [x] `_DIM_TO_TYPE` dict covers all 8 dimensions for `recommended_next_content_type` (was missing 3)
- [x] `strongest_dimension` computed from full `dimension_breakdown`, not just dimensions with failures (was returning None when all fail-rates were 0)
- [x] 5 new edge-case tests: invalid region code 422, empty progress state, simulation flow + scoring, pinned-version submit
- [x] 298/298 backend tests passing
- [x] TypeScript check: zero errors
- [x] CONTENT_GOVERNANCE.md updated with pinned-version behaviour + known limitations

## Auth UX Completion + Account Experience (Complete)

Goal: Complete, secure, user-friendly authentication flow. Any new learner or admin can register, log in, view/update their profile, and be redirected correctly throughout the app.

- [x] `LoginPage` — inline error banner (401 suppressed by response interceptor — shown explicitly here), clears on field edit, forgot-password note
- [x] `LoginPage` — post-login redirect to `location.state.from` or `/learn/content`; already-authed users redirect to `/learn/content`
- [x] `RegisterPage` — confirm-password field with match validation; inline submit-error banner for server failures
- [x] `RegisterPage` — post-register auto-login + redirect to `/learn/content`
- [x] `ProtectedRoute` — preserves attempted URL as `state={{ from: location.pathname + location.search }}` on redirect to `/login`
- [x] `ProfilePage` (`/profile`) — avatar, user info (email, username, full_name, account status, member since), edit form (full_name + username), logout button
- [x] `authApi.updateMe(data)` — `PATCH /api/auth/me`; updates Zustand `currentUser` on success
- [x] `UserUpdate` interface added to `types/index.ts`
- [x] Navigation user section — clicking user name/avatar navigates to `/profile`; logout button moved below as labelled row
- [x] `/profile` lazy route added to `App.tsx` under `ProtectedRoute`
- [x] No backend changes required (all endpoints already existed)
- [x] TypeScript check: zero errors
- [x] DEVELOPMENT.md updated with auth flow reference table

## Learner-Facing Published Content Experience — Phase 1 (Complete)

Goal: Close the loop from published content to learner training and tracked progress.

- [x] `GET /api/learn/content` — browse published content for a region; filters: content_type, domain, difficulty, search; pagination; includes version_id and published_at
- [x] `GET /api/learn/content/{id}?region_code=UK` — detail with `safe_payload` (answer keys stripped); 404 for unpublished/wrong-region; `requires_local_disclaimer` and `requires_protocol_note` flags from RegionPublishingRule
- [x] `POST /api/learn/content/{id}/attempt` — deterministic scoring; creates LearnerFailureAnalytics record; returns score, feedback, failed_dimensions, recommended_next_step; no AI, no invented clinical feedback
- [x] `GET /api/learn/progress` — aggregates LearnerFailureAnalytics by user_id: total_attempts, average_score, attempts_by_content_type, weakness_breakdown (dimension fail rates), recent_attempts
- [x] Answer key security: `correct_answer_or_expected_response`, `expected_decision`, `expected_pharmacist_action`, `hidden_risk`, `failure_mode`, `critical_fail`, `scoring_rubric` never returned to learners
- [x] `TrainingLibraryPage` (`/learn/content`) — region selector, filters, content cards (not table), empty state with admin guidance
- [x] `TrainingDetailPage` (`/learn/content/:id`) — metadata header, safe payload viewer, attempt form, result panel; region-aware
- [x] `TrainingProgressPage` (`/learn/progress`) — stats cards, weakness bar chart, attempts-by-type chips, recent attempts list
- [x] Navigation updated — "Training Library" (BookOpenIcon) and "Training Progress" (TrophyIcon) added for all authenticated users
- [x] `learnApi.ts` — separate Axios instance with JWT refresh; `browse`, `getDetail`, `submitAttempt`, `getProgress`
- [x] `types/learn.ts` — full TypeScript types for all learner schemas
- [x] App.tsx — three new lazy routes under `/learn/`
- [x] 25 new backend tests in `test_learner_experience.py`; full suite 268/268 passing
- [x] TypeScript check: zero errors
- [x] CONTENT_GOVERNANCE.md, DEVELOPMENT.md, ROADMAP.md updated

## End-to-End Product Readiness Gate — Pre-Subscription / Pre-AI (Complete)

Goal: Audit and harden the full product flow before building subscriptions, payments, or AI tutor. No new features — only correctness and completeness.

- [x] Auth journey verified: register → auto-login → /learn/content; login preserves return URL; page reload restores auth from refresh token; logout revokes server-side token; protected routes redirect with return URL; admin governance routes block non-admin users; profile update works; no tokens in logs or URL
- [x] Admin governance journey verified: dashboard uses real summary data; import center gates commit behind zero-error preview; region rules page uses live backend data; content library supports search and external_id display; governance 403 errors are displayed with permission hint; all governance writes require explicit confirmation
- [x] Learner journey verified: training library handles empty state; training detail handles loading/404/flow-failure/start-failure/submit-failure/score-null/all-not_assessable; progress page handles zero sessions and null scores; profile edit handles validation errors
- [x] **Fixed:** `TrainingLibraryPage` now reads `?content_type` URL param on mount — "Train now" CTA from progress page now correctly pre-filters the library
- [x] `scripts/dev_seed_published_content.py` — idempotent dev seed script; creates one non-clinical demonstration drill item, published to UK; creates superuser if missing; refuses to run against production hosts; safe to run multiple times
- [x] `DEVELOPMENT.md` — full local E2E journey guide (seed script, admin steps, learner steps, manual publish alternative)
- [x] TypeScript check: zero errors
- [x] Backend tests: 298/298 passing (no backend changes required)

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
