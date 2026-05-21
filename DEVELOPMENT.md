# Development Guide

## Prerequisites

- Python 3.9+
- Node.js 16+
- Docker & Docker Compose (optional but recommended)
- OpenAI API Key

## Quick Start with Docker

```bash
# 1. Clone and setup
git clone <repo>
cd mm
cp .env.example .env

# 2. Add your OpenAI API key to .env
OPENAI_API_KEY=sk-...

# 3. Start all services
docker-compose up

# 4. Access
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs
```

## Local Development (without Docker)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env in backend directory
cp ../.env.example .env

# Run migrations (when ready)
# alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## Project Structure

### Backend Architecture

```
app/
├── main.py              # FastAPI app entry
├── config.py            # Configuration
├── models/              # Pydantic models & DB schemas
│   ├── scenario.py
│   ├── material.py
│   └── user.py
├── routes/              # API endpoints
│   ├── materials.py
│   ├── scenarios.py
│   └── health.py
├── services/            # Business logic
│   ├── ai_generator.py
│   ├── material_processor.py
│   └── evaluator.py
└── utils/               # Utilities
    ├── document_parser.py
    └── validators.py
```

### Frontend Architecture

```
src/
├── components/          # Reusable UI components
│   ├── Navigation.tsx
│   ├── ScenarioCard.tsx
│   └── MessageBubble.tsx
├── pages/               # Page components
│   ├── Dashboard.tsx
│   ├── MaterialsUpload.tsx
│   └── ScenarioPage.tsx
├── services/            # API calls
│   └── api.ts
├── store/               # State management (Zustand)
│   └── scenarioStore.ts
├── types/               # TypeScript types
│   └── index.ts
├── App.tsx              # Root component
├── main.tsx             # Entry point
└── index.css            # Tailwind styles
```

## API Endpoints

### Materials
- `POST /api/materials/upload` - Upload clinical materials
- `GET /api/materials/list` - List uploaded materials

### Scenarios
- `POST /api/scenarios/generate` - Generate scenarios from materials
- `GET /api/scenarios` - List all scenarios
- `GET /api/scenarios/{id}` - Get specific scenario
- `POST /api/scenarios/{id}/answer` - Submit answer with AI feedback

## Environment Variables

```
# API
DEBUG=True
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4-turbo-preview

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/clinical_ai

# Features
ENABLE_S3=False
UPLOAD_DIR=./uploads
```

## Testing

### Backend Tests
```bash
cd backend
pytest tests/
pytest tests/ -v --cov=app
```

### Frontend Tests
```bash
cd frontend
npm test
```

## Next Steps: AI Integration

1. **Document Processing**
   - Extract text from PDFs/images using PyPDF2 or pytesseract
   - Store in vector database (Pinecone, Weaviate)

2. **Scenario Generation**
   - Use LangChain + OpenAI for context-aware generation
   - Implement prompt engineering for medical accuracy

3. **Interactive Learning**
   - WebSocket support for real-time feedback
   - Store conversation history
   - Analytics dashboard

## Troubleshooting

### Backend connection issues
```bash
# Check if backend is running
curl http://localhost:8000/api/health

# Check logs
docker logs clinical_ai_backend
```

### Database issues
```bash
# Reset database
docker-compose down -v
docker-compose up db
```

## Resources

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [React Docs](https://react.dev/)
- [OpenAI API](https://platform.openai.com/docs)
- [LangChain Docs](https://docs.langchain.com/)
