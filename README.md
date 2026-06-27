# PharmLearn AI — Community Pharmacy Training Platform

A world-class, production-grade SaaS platform for community pharmacy education and clinical training.
Built with FastAPI, React, PostgreSQL, Redis, and Claude AI.

## Platform Vision

PharmLearn AI trains community pharmacists across the full scope of practice:

| Module | Status |
|--------|--------|
| Clinical case scenarios | Active (Phase 1) |
| OTC triage simulations | Roadmap (Phase 2) |
| Prescription screening | Roadmap (Phase 2) |
| Drug interaction detection | Roadmap (Phase 2) |
| Red flag identification | Roadmap (Phase 2) |
| Patient counselling practice | Roadmap (Phase 2) |
| OSCE stations | Roadmap (Phase 3) |
| Pharmacy games & flashcards | Roadmap (Phase 3) |
| Adaptive assessments | Roadmap (Phase 3) |
| AI tutor | Roadmap (Phase 3) |
| Evidence-based content review | Roadmap (Phase 4) |
| Admin dashboard | Roadmap (Phase 4) |
| Institution accounts | Roadmap (Phase 4) |
| Subscriptions & billing | Roadmap (Phase 4) |
| CSV bulk content import | Roadmap (Phase 4) |
| Content versioning & approvals | Roadmap (Phase 4) |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend framework | FastAPI 0.104 (async) |
| Database ORM | SQLAlchemy 2.0 async |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| AI provider | Anthropic Claude (`claude-sonnet-4-6`) |
| Document parsing | pypdf, python-docx, pytesseract |
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
# Edit .env and set ANTHROPIC_API_KEY

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
│   ├── app/
│   │   ├── core/           # Security, auth dependencies (Phase 2+)
│   │   ├── domains/        # Future bounded-context packages
│   │   │   ├── users/
│   │   │   ├── organizations/
│   │   │   ├── assessments/
│   │   │   ├── osce/
│   │   │   ├── games/
│   │   │   ├── analytics/
│   │   │   ├── subscriptions/
│   │   │   └── content_review/
│   │   ├── models/
│   │   │   ├── content.py   # Material
│   │   │   └── learning.py  # Scenario, Interaction
│   │   ├── routes/
│   │   │   ├── health.py
│   │   │   ├── materials.py
│   │   │   └── scenarios.py
│   │   ├── schemas/
│   │   │   ├── platform.py  # HealthResponse, PaginatedResponse
│   │   │   ├── content.py   # Material schemas
│   │   │   └── learning.py  # Scenario & Interaction schemas
│   │   ├── services/
│   │   │   ├── ai_service.py      # Anthropic Claude integration
│   │   │   └── document_parser.py # PDF/DOCX/image text extraction
│   │   ├── utils/
│   │   │   └── validators.py
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── alembic/             # Database migrations
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── services/api.ts
│       ├── store/appStore.ts
│       └── types/index.ts
├── docker-compose.yml
├── nginx.conf
├── ARCHITECTURE.md
├── DEVELOPMENT.md
└── ROADMAP.md
```

## Documentation

| Document | Purpose |
|----------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, data flow, module boundaries |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local setup, testing, environment variables |
| [ROADMAP.md](ROADMAP.md) | Phased feature delivery plan |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment guides |

## API Endpoints (Phase 1)

```
GET  /api/health
POST /api/materials/upload
GET  /api/materials
GET  /api/materials/{id}
DEL  /api/materials/{id}
POST /api/scenarios/generate
GET  /api/scenarios
GET  /api/scenarios/{id}
POST /api/scenarios/{id}/answer
GET  /api/scenarios/{id}/interactions
```

Full interactive docs: `http://localhost:8000/docs`

## Testing

```bash
# Backend
cd backend && pytest tests/ -v

# Frontend TypeScript check
cd frontend && npx tsc --noEmit
```

## Contributing

See [DEVELOPMENT.md](DEVELOPMENT.md).
