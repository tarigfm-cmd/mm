# Clinical Scenario AI Generator

> An interactive AI-powered platform for generating and learning from clinical scenarios based on submitted medical materials.

## 🎯 Features

- 📄 **Multi-format Upload** - Support for PDF, images, DOCX, and text files
- 🤖 **AI-Powered Scenarios** - Automatic scenario generation using GPT-4
- 💬 **Interactive Learning** - Real-time Q&A with AI feedback
- 📊 **Performance Tracking** - Score and progress analytics
- 🎓 **Difficulty Levels** - Beginner, Intermediate, Advanced scenarios
- 🔒 **Secure** - API key protection, rate limiting, SSL/TLS
- 🚀 **Production Ready** - Docker, PostgreSQL, Redis, Nginx

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI API Key (get at [platform.openai.com](https://platform.openai.com))

### 1-Minute Setup

```bash
# Clone repository
git clone https://github.com/tarigfm-cmd/mm.git
cd mm

# Copy environment template
cp .env.example .env

# Add your OpenAI API key
nano .env

# Start everything
docker-compose up
```

Access your app:
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs

## 📁 Project Structure

```
mm/
├── backend/                 # FastAPI Python backend
│   ├── app/
│   │   ├── main.py         # FastAPI app entry
│   │   ├── models/         # Data models
│   │   ├── routes/         # API endpoints
│   │   ├── services/       # Business logic
│   │   └── utils/          # Utilities
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile
├── frontend/               # React TypeScript frontend
│   ├── src/
│   │   ├── components/    # Reusable components
│   │   ├── pages/         # Page components
│   │   ├── services/      # API calls
│   │   └── types/         # TypeScript types
│   ├── package.json       # NPM dependencies
│   └── Dockerfile
├── docker-compose.yml     # Local development
├── docker-compose.prod.yml # Production setup
├── nginx.conf             # Nginx configuration
├── .env.example           # Environment variables
├── DEVELOPMENT.md         # Development guide
├── ARCHITECTURE.md        # System design
├── DEPLOYMENT.md          # Production deployment
└── README.md             # This file
```

## 🔧 Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Relational database
- **Redis** - Caching & sessions
- **OpenAI GPT-4** - AI scenario generation
- **Pydantic** - Data validation

### Frontend
- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Axios** - HTTP client

### DevOps
- **Docker** - Containerization
- **Docker Compose** - Orchestration
- **Nginx** - Reverse proxy
- **GitHub Actions** - CI/CD

## 📚 API Endpoints

### Materials
- `POST /api/materials/upload` - Upload clinical materials
- `GET /api/materials` - List uploaded materials
- `GET /api/materials/{id}` - Get specific material

### Scenarios
- `POST /api/scenarios/generate` - Generate scenario from material
- `GET /api/scenarios` - List all scenarios
- `GET /api/scenarios/{id}` - Get specific scenario
- `POST /api/scenarios/{id}/answer` - Submit answer with AI feedback

### Health
- `GET /api/health` - Check backend health

## 📖 Documentation

- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Setup, testing, troubleshooting
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design, data flows, database schema
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment (Heroku, AWS, Digital Ocean, Railway)

## 🌐 Deployment

### One-Command Local Deployment
```bash
bash scripts/deploy.sh development
```

### Production Deployment (4 Options)

1. **Heroku** (5 minutes, $7/month)
   ```bash
   heroku create clinical-ai-backend
   heroku config:set OPENAI_API_KEY=sk-xxxxx
   git push heroku main
   ```

2. **AWS Free Tier** (15 minutes, free 1st year)
   - EC2 + RDS + Nginx + SSL

3. **Digital Ocean** (10 minutes, $5-15/month)
   - App Platform or Droplet

4. **Railway** (8 minutes, $5-20/month)
   - GitHub integration, auto-deploys

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

## 🛠️ Development

### Local Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### Testing

```bash
# Backend tests
cd backend
pytest tests/ -v

# Frontend tests
cd frontend
npm test
```

## 🔐 Security

- ✅ Environment variable secrets (no hardcoding)
- ✅ HTTPS/SSL encryption
- ✅ Rate limiting (100 req/min API, 10 req/s frontend)
- ✅ Input validation (Pydantic)
- ✅ CORS protection
- ✅ File upload validation (type & size)
- ✅ Database password encryption
- ✅ API rate limiting

## 📊 Monitoring

After deployment, setup monitoring:

1. **Error Tracking** - [Sentry](https://sentry.io) (free tier)
2. **Uptime Monitoring** - [UptimeRobot](https://uptimerobot.com) (free)
3. **Logs** - Check with: `docker-compose logs -f backend`
4. **Performance** - Monitor with: `docker stats`

## 🚦 Troubleshooting

### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Check database connection
docker-compose logs db

# Restart
docker-compose restart backend
```

### Frontend shows blank page
```bash
# Check if backend is reachable
curl http://localhost:8000/api/health

# Check frontend logs
docker-compose logs frontend

# Clear cache
docker-compose down -v
docker-compose up
```

### Database connection error
```bash
# Reset database
docker-compose down
docker volume rm mm_postgres_data
docker-compose up
```

## 📝 Environment Variables

Key variables to configure in `.env`:

```
OPENAI_API_KEY=sk-your-key          # Required for AI
DEBUG=False                          # Set to False in production
DB_PASSWORD=secure-password         # Change this!
SECRET_KEY=random-secret-key        # Change this!
VITE_API_URL=http://localhost:8000  # Frontend API endpoint
```

See `.env.example` for all available options.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see LICENSE file for details.

## 💡 Roadmap

- [ ] User authentication & authorization
- [ ] Progress analytics dashboard
- [ ] Scenario difficulty assessment
- [ ] Multi-language support
- [ ] Mobile app (React Native)
- [ ] Advanced search with embeddings
- [ ] Batch scenario generation
- [ ] Export to PDF/CSV

## 🆘 Support

### Common Issues

**Q: Where do I get an OpenAI API key?**  
A: Visit https://platform.openai.com/api-keys → Create new API key

**Q: Can I run this without Docker?**  
A: Yes, follow [DEVELOPMENT.md](DEVELOPMENT.md) for local setup

**Q: How much does this cost to run?**  
A: $0 to start (free tier), ~$50-100/month at scale

**Q: How do I deploy to production?**  
A: Follow [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step guides

## 📞 Contact

- **GitHub Issues** - Report bugs: https://github.com/tarigfm-cmd/mm/issues
- **Email** - tarigfm@gmail.com

## 🎉 Acknowledgments

Built with:
- FastAPI & React
- OpenAI GPT-4
- PostgreSQL & Redis
- Docker & Nginx
- Community support

---

**Ready to launch?** 🚀

```bash
docker-compose up
# Then go to http://localhost:5173
```

Happy learning! 📚
