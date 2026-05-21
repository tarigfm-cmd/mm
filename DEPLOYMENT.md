# Deployment Guide - Going Live 🚀

## Quick Deployment Options

### **Option 1: Heroku (Fastest - 5 minutes)**

Perfect for MVP, single-click deploy.

```bash
# Install Heroku CLI
brew install heroku
heroku login

# Create apps
heroku create clinical-ai-backend
heroku create clinical-ai-frontend

# Set environment variables
heroku config:set OPENAI_API_KEY=sk-your-key --app clinical-ai-backend
heroku config:set DEBUG=False --app clinical-ai-backend

# Add database
heroku addons:create heroku-postgresql:hobby-dev --app clinical-ai-backend

# Deploy backend
git subtree push --prefix backend heroku/main

# Deploy frontend
# Go to https://vercel.com → Import from GitHub → Deploy
```

**Cost:** ~$7/month backend + ~$0 frontend = **$84/year**

---

### **Option 2: AWS Free Tier (Medium - 15 minutes)**

Best long-term option with 1 year free tier.

```bash
# 1. Create AWS account at aws.amazon.com
# 2. Launch EC2 (Ubuntu 22.04 LTS, t2.micro - Free!)

# SSH into instance
ssh -i your-key.pem ubuntu@your-ec2-public-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Clone and deploy
git clone https://github.com/tarigfm-cmd/mm.git
cd mm
cp .env.example .env
nano .env  # Add OpenAI key

# Run production setup
docker-compose -f docker-compose.prod.yml up -d

# Setup SSL with Certbot
sudo apt update && sudo apt install -y certbot python3-certbot-nginx
sudo certbot certonly --standalone -d your-domain.com
```

**Cost:** Free 12 months, then ~$25/month (EC2 + RDS) = **Free first year**

---

### **Option 3: Digital Ocean (Popular - 10 minutes)**

Simplest with excellent documentation.

```bash
# 1. Create account at digitalocean.com
# 2. Create App Platform project
# 3. Connect GitHub repository
# 4. Set environment variables:
#    - OPENAI_API_KEY
#    - DEBUG=False
#    - DATABASE_URL (auto-created)
# 5. Click "Deploy"
# 6. Wait 5 minutes
# 7. Done! ✅

# Or use Droplet (VPS):
# 1. Create Ubuntu 22.04 Droplet ($6/month)
# 2. SSH in and run commands from Option 2
```

**Cost:** $5-15/month = **$60-180/year**

---

### **Option 4: Railway (Modern - 8 minutes)**

Modern alternative with automatic deployments.

```bash
# 1. Go to railway.app
# 2. Login with GitHub
# 3. New Project → GitHub repo
# 4. Add PostgreSQL database (auto-linked)
# 5. Set OPENAI_API_KEY secret
# 6. Deploy ✅
```

**Cost:** $5-20/month = **$60-240/year**

---

## 🎯 Recommended Setup (Best Value)

### For MVP (Proof of Concept)
```
Backend:  Heroku ($7/month)
Frontend: Vercel (Free)
Domain:   Namecheap ($12/year)
Total:    ~$90/year
```

### For Production (Scalable)
```
Backend:  AWS EC2 + RDS ($20/month)
Frontend: CloudFront + S3 ($2/month)
Domain:   Route53 ($1/month)
SSL:      AWS Certificate Manager (Free)
Total:    ~$275/year
```

---

## 📋 Step-by-Step: Heroku (Easiest)

### Prerequisites
- GitHub account
- Heroku account (free)
- OpenAI API key

### Deploy Backend

```bash
# 1. Install Heroku CLI
brew install heroku  # macOS
# or https://devcenter.heroku.com/articles/heroku-cli

# 2. Login
heroku login

# 3. Create backend app
heroku create clinical-ai-backend

# 4. Set environment variables
heroku config:set OPENAI_API_KEY=sk-xxxxxxx --app clinical-ai-backend
heroku config:set DEBUG=False --app clinical-ai-backend

# 5. Add PostgreSQL database
heroku addons:create heroku-postgresql:hobby-dev --app clinical-ai-backend

# 6. Get database URL (auto-set as DATABASE_URL)
heroku config --app clinical-ai-backend | grep DATABASE_URL

# 7. Deploy
git push heroku main

# 8. Check logs
heroku logs --tail --app clinical-ai-backend

# 9. Run migrations (when ready)
heroku run "python -m alembic upgrade head" --app clinical-ai-backend

# Backend is live at: https://clinical-ai-backend.herokuapp.com
```

### Deploy Frontend

```bash
# Option A: Vercel (Recommended)
# 1. Go to vercel.com
# 2. Click "New Project"
# 3. Import your GitHub repo
# 4. Set environment: VITE_API_URL=https://clinical-ai-backend.herokuapp.com
# 5. Click Deploy ✅

# Option B: Netlify
# 1. Go to netlify.com
# 2. Connect GitHub
# 3. Build command: cd frontend && npm run build
# 4. Publish directory: frontend/dist
# 5. Set env: VITE_API_URL=https://clinical-ai-backend.herokuapp.com
# 6. Deploy ✅
```

---

## 🔐 Production Checklist

Before going live:

```
Security:
  ☐ DEBUG=False in production
  ☐ Strong database password (20+ characters)
  ☐ OPENAI_API_KEY in environment (not hardcoded)
  ☐ CORS configured for your domain only
  ☐ Rate limiting enabled
  ☐ HTTPS/SSL certificate enabled

Database:
  ☐ Daily backups enabled
  ☐ Connection pooling configured
  ☐ Database user has minimal permissions
  ☐ Migrations tested locally first

Monitoring:
  ☐ Error tracking (Sentry)
  ☐ Uptime monitoring (UptimeRobot)
  ☐ Application logs reviewed
  ☐ Database performance monitored

Performance:
  ☐ Frontend assets minified
  ☐ CDN configured (CloudFront/Cloudflare)
  ☐ Database queries optimized
  ☐ Caching strategy implemented

Testing:
  ☐ All endpoints tested
  ☐ File upload limits tested
  ☐ Error scenarios tested
  ☐ Load testing performed
```

---

## 🚨 Common Issues & Solutions

### Issue: 502 Bad Gateway

```bash
# Backend might be down
heroku logs --tail --app clinical-ai-backend

# Restart app
heroku restart --app clinical-ai-backend

# Check free dyno hours
heroku ps --app clinical-ai-backend
```

### Issue: Database Connection Error

```bash
# Check database URL
heroku config --app clinical-ai-backend | grep DATABASE_URL

# Verify database is running
heroku pg:info --app clinical-ai-backend

# Reset database
heroku pg:reset DATABASE --app clinical-ai-backend --confirm clinical-ai-backend
```

### Issue: OpenAI API Errors

```bash
# Verify API key is set
heroku config --app clinical-ai-backend | grep OPENAI_API_KEY

# Test connection
curl -X GET https://clinical-ai-backend.herokuapp.com/api/health
```

---

## 📊 Monitoring After Launch

### Setup Error Tracking

```bash
# Install Sentry (free tier: $0-29/month)
# 1. Create account at sentry.io
# 2. Create new project (select Python for backend)
# 3. Copy DSN key
# 4. Set in backend: heroku config:set SENTRY_DSN=<your-dsn>
```

### Setup Uptime Monitoring

```bash
# Use UptimeRobot (free)
# 1. Go to uptimerobot.com
# 2. Add monitor: https://clinical-ai-backend.herokuapp.com/api/health
# 3. Get alerts if service goes down
```

### View Logs

```bash
# Real-time logs
heroku logs --tail --app clinical-ai-backend

# Filter by error
heroku logs --grep error --app clinical-ai-backend

# Get last 100 lines
heroku logs --num 100 --app clinical-ai-backend
```

---

## 🔄 Continuous Deployment (CI/CD)

### Automatic Deploy on Push

```bash
# For Heroku + GitHub (Free!)
# 1. Go to Heroku dashboard
# 2. Open your app: clinical-ai-backend
# 3. Go to "Deploy" tab
# 4. Connect GitHub repository
# 5. Enable "Automatic deploys" from main branch
# 6. Every push to main = automatic deploy! 🚀
```

### GitHub Actions (Advanced)

Create `.github/workflows/deploy.yml` to:
- Run tests on every push
- Build Docker images
- Push to Docker Hub
- Deploy to your server
- Send Slack notifications

---

## 💰 Cost Optimization

### Reduce Costs
- Use free tier services first
- Implement caching (Redis)
- Compress assets
- Use CDN for static files
- Optimize database queries

### Scaling Strategy
```
Stage 1: MVP ($90/year)
  └─ Heroku Free/Eco + Vercel Free

Stage 2: Growth ($200/year)
  └─ Heroku Standard + Vercel Pro + CloudFlare

Stage 3: Production ($500-1000/year)
  └─ AWS + RDS + CloudFront + Route53
```

---

## 🎉 You're Live!

### After Deployment

```bash
# Test your app
curl https://your-domain.com              # Frontend
curl https://your-domain.com/api/health   # Backend health check

# View logs
heroku logs --tail --app clinical-ai-backend

# Scale if needed
heroku ps:scale web=2 --app clinical-ai-backend  # 2 dynos
```

**Congratulations! Your Clinical Scenario AI Generator is live! 🎊**

Next steps:
- Monitor error logs daily
- Collect user feedback
- Optimize performance based on metrics
- Plan scaling as you grow
