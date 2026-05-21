# Clinical Scenario AI Generator - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Dashboard │ Upload │ Scenario │ Interactive Chat    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                         HTTP/REST
                              │
┌─────────────────────────────────────────────────────────────┐
│                 Backend (FastAPI)                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Routes: Materials │ Scenarios │ Health │ WebSocket   │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Services: AI Generator │ Document Parser │ Evaluator │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Database: PostgreSQL │ Cache: Redis                  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
    ┌──────────┐          ┌─────────┐          ┌──────────┐
    │ OpenAI   │          │Database │          │ Storage  │
    │  API     │          │ (Postgres)         │ (S3/Local)
    │ (GPT-4)  │          └─────────┘          └──────────┘
    └──────────┘
```

## Component Architecture

### Backend Services

```python
app/
├── main.py (FastAPI App)
├── config.py (Settings)
├── models/
│   ├── schemas.py (Pydantic models)
│   └── database.py (SQLAlchemy models - TODO)
├── routes/
│   ├── materials.py (Material upload/list)
│   ├── scenarios.py (Scenario generation/interaction)
│   └── health.py (Health check)
├── services/
│   ├── ai_generator.py (OpenAI integration)
│   ├── document_parser.py (File processing - TODO)
│   ├── evaluator.py (Answer evaluation - TODO)
│   └── vector_store.py (Embedding storage - TODO)
└── utils/
    ├── validators.py (Input validation)
    └── helpers.py (Utility functions)
```

### Frontend Components

```tsx
App.tsx
├── Navigation.tsx
├── pages/
│   ├── Dashboard.tsx
│   ├── MaterialsUpload.tsx
│   └── ScenarioPage.tsx
├── components/
│   ├── ScenarioCard.tsx
│   ├── MessageBubble.tsx
│   └── UploadDropzone.tsx
├── services/
│   └── api.ts
└── types/
    └── index.ts
```

## Data Flow

### Upload Material → Generate Scenario

```
1. User uploads file
2. File validation (type, size)
3. Save to disk/S3
4. Create material record
5. Extract text content
6. Generate embedding
7. Create scenario from context
8. Return scenario to user
```

### Student Answer → AI Feedback

```
1. User submits answer
2. Fetch scenario context
3. Call OpenAI evaluation
4. Generate feedback
5. Calculate score
6. Store interaction
7. Return feedback to user
8. Update user progress
```

## Database Schema (Planned)

```sql
-- Materials table
CREATE TABLE materials (
  id SERIAL PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  file_path VARCHAR(500),
  file_size INTEGER,
  file_type VARCHAR(50),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Scenarios table
CREATE TABLE scenarios (
  id SERIAL PRIMARY KEY,
  material_id INTEGER REFERENCES materials(id),
  title VARCHAR(255),
  clinical_case TEXT,
  difficulty_level VARCHAR(50),
  diagnosis TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Interactions table
CREATE TABLE interactions (
  id SERIAL PRIMARY KEY,
  scenario_id INTEGER REFERENCES scenarios(id),
  user_answer TEXT,
  ai_feedback TEXT,
  score FLOAT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

## API Request/Response Cycle

### Generate Scenario

```
POST /api/scenarios/generate
{
  "material_id": 1,
  "difficulty_level": "Intermediate",
  "title": "MI Case",
  "clinical_case": ""
}

Response:
{
  "id": 1,
  "material_id": 1,
  "title": "Acute MI Case",
  "clinical_case": "45-year-old male...",
  "difficulty_level": "Intermediate",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Submit Answer

```
POST /api/scenarios/1/answer
{
  "content": "Acute myocardial infarction with...",
  "scenario_id": 1
}

Response:
{
  "feedback": "Excellent diagnosis...",
  "score": 0.92,
  "key_findings": ["ST elevation", "Troponin elevation"],
  "next_steps": ["Discuss treatment options"]
}
```

## Error Handling Strategy

```
Error Type           HTTP Code  Response
─────────────────────────────────────────────────────
Validation Error     400       {"detail": "validation error"}
Authentication       401       {"detail": "unauthorized"}
Not Found            404       {"detail": "resource not found"}
Conflict             409       {"detail": "resource exists"}
Rate Limited         429       {"detail": "too many requests"}
Server Error         500       {"detail": "internal error"}
Service Unavailable  503       {"detail": "service unavailable"}
```

## Caching Strategy

```
Cache Layer (Redis)
├── Material embeddings (TTL: 7 days)
├── Scenario metadata (TTL: 1 day)
├── User sessions (TTL: 24 hours)
└── API responses (TTL: 1 hour)
```

## Security Considerations

1. **Input Validation** - All user inputs validated via Pydantic
2. **File Upload** - Size limits, type whitelist, virus scan (optional)
3. **API Rate Limiting** - 100 requests/minute per IP
4. **CORS** - Configure for production domains only
5. **API Keys** - OpenAI key stored in environment variables
6. **Database** - Use connection pooling, prepared statements

## Deployment Architecture

```
┌─────────────────────────────────────────┐
│         Docker Compose / K8s            │
├─────────────────────────────────────────┤
│ Frontend │ Backend │ PostgreSQL │ Redis │
├─────────────────────────────────────────┤
│        Nginx / Traefik (Reverse Proxy)  │
├─────────────────────────────────────────┤
│              SSL/TLS Certificate        │
└─────────────────────────────────────────┘
```

## Performance Optimization

### Backend
- Connection pooling (PostgreSQL)
- Redis caching for frequent queries
- Async/await for I/O operations
- Query optimization with indexes
- Background task processing

### Frontend
- Code splitting with React.lazy
- Image optimization
- Lazy component loading
- Debounced API calls
- Local caching with localStorage

## Monitoring & Logging

```
┌──────────────────────────────────────┐
│        Application Logs              │
│ - Request/Response logs              │
│ - Error tracking                     │
│ - Performance metrics                │
└──────────────────────────────────────┘
        │
        ├─→ ELK Stack / CloudWatch
        ├─→ Sentry (Error tracking)
        └─→ DataDog (APM)
```

## Next Steps for Implementation

1. **Implement Database Models** - SQLAlchemy models and migrations
2. **Add Document Processing** - PDF/image text extraction
3. **WebSocket Support** - Real-time chat updates
4. **Authentication** - User accounts and authorization
5. **Vector Database** - Semantic search with embeddings
6. **Monitoring** - Logs, metrics, alerts
7. **Testing** - Unit and integration tests
8. **CI/CD Pipeline** - GitHub Actions workflow
