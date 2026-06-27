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

## Phase 2 — Users & Auth

Goal: Real accounts, multi-role access, institution support.

- [ ] User registration & email verification
- [ ] JWT authentication (python-jose, passlib bcrypt)
- [ ] Role-based access control: learner | educator | admin
- [ ] Institution (organization) accounts
- [ ] Learner-to-institution linking
- [ ] Profile pages & progress history
- [ ] Session replacement: auth tokens instead of anonymous UUIDs

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
