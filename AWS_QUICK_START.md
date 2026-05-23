# 🚀 AWS Deployment - Quick Reference

## Your Complete AWS Setup

I've created everything you need to deploy to AWS in one place. Here's what you have:

### 📁 Files Created
1. **AWS_DEPLOYMENT.md** - 11-step detailed guide with screenshots
2. **scripts/deploy-aws.sh** - Automated deployment script
3. **docker-compose.prod.yml** - Production Docker setup
4. **nginx.conf** - Enterprise-grade Nginx configuration

---

## ⚡ Quick Start (2 Options)

### Option A: Automated Deployment (Easiest - 40 minutes)

```bash
# 1. Create AWS Account
# Go to: https://aws.amazon.com/free
# Sign up (takes 5 minutes)

# 2. Create EC2 + RDS + Security Groups
# Follow AWS_DEPLOYMENT.md Steps 1-5 (15 minutes)
# Don't worry, each step has exact instructions

# 3. SSH into your server
ssh -i your-key.pem ubuntu@YOUR_ELASTIC_IP

# 4. Run deployment script
curl -O https://raw.githubusercontent.com/tarigfm-cmd/mm/main/scripts/deploy-aws.sh
chmod +x deploy-aws.sh
sudo ./deploy-aws.sh

# Answer the prompts (domain name, etc.)
# Done! 🎉
```

### Option B: Manual Step-by-Step (More learning - 50 minutes)

Follow **AWS_DEPLOYMENT.md** from Step 1 to Step 11. Each step has:
- ✅ What to do
- ✅ Exact commands to run
- ✅ What to expect
- ✅ Troubleshooting

---

## 📊 Cost Breakdown

| Component | Year 1 | Year 2+ |
|-----------|--------|---------|
| EC2 t2.micro | FREE | $10/month |
| RDS PostgreSQL 20GB | FREE | $15/month |
| Elastic IP | FREE | FREE |
| Route53 DNS | $6 | $6/year |
| Domain (Namecheap) | $12 | $12/year |
| **Total** | **~$18** | **~$180/year** |

✅ **Extremely affordable!** Free for 1 year with AWS Free Tier.

---

## 🎯 Pre-Deployment Checklist

Before you start, have these ready:

- [ ] AWS Account (create at https://aws.amazon.com/free)
- [ ] Domain name ($12-15 at Namecheap/GoDaddy)
- [ ] OpenAI API key (https://platform.openai.com/api-keys)
- [ ] SSH key file (.pem or .ppk)
- [ ] Strong database password (20+ characters)

---

## 🔑 11-Step Overview

| Step | Task | Time | Free? |
|------|------|------|-------|
| 1 | Create AWS Account | 5 min | ✅ |
| 2 | Create Security Group | 3 min | ✅ |
| 3 | Launch EC2 Instance (t2.micro) | 5 min | ✅ |
| 4 | Allocate Elastic IP | 2 min | ✅ |
| 5 | Create RDS PostgreSQL | 5 min | ✅ |
| 6 | SSH Into Server | 3 min | ✅ |
| 7 | Install Docker & Clone Project | 5 min | ✅ |
| 8 | Start Docker Services | 5 min | ✅ |
| 9 | Setup SSL Certificate (Let's Encrypt) | 3 min | ✅ |
| 10 | Configure Nginx | 2 min | ✅ |
| 11 | Point Domain to Server | 3 min | ✅ |
| **Total** | **Deploy to production** | **~40 min** | **✅ FREE** |

---

## 📚 Documentation Files

### **AWS_DEPLOYMENT.md** (Complete Guide)
- 11 detailed steps with explanations
- Exact commands you can copy/paste
- Screenshots/architecture diagrams
- Common issues & solutions
- Maintenance commands
- Cost analysis

### **scripts/deploy-aws.sh** (Automation)
- Installs Docker & Docker Compose
- Installs Certbot for SSL
- Clones your repository
- Sets up environment
- Gets SSL certificate
- Starts all services
- Verifies everything works

### **docker-compose.prod.yml** (Production Setup)
- FastAPI backend
- React frontend
- PostgreSQL database
- Redis cache
- Nginx reverse proxy
- Auto-restart on crash
- Health checks

### **nginx.conf** (Web Server)
- SSL/TLS configuration
- Rate limiting (protection from abuse)
- Gzip compression (faster loading)
- Security headers
- API proxying
- Static file caching

---

## ✅ What You'll Have After Deployment

After following the guide, you'll have:

```
✅ Production-grade server (AWS EC2 t2.micro)
✅ Managed PostgreSQL database (AWS RDS)
✅ SSL/TLS encryption (Let's Encrypt, free)
✅ Automatic HTTPS redirect
✅ Rate limiting (protects from spam)
✅ Reverse proxy (Nginx)
✅ Redis caching (fast)
✅ Docker containers (easy to update)
✅ Domain configured (your-domain.com)
✅ Health monitoring (built-in)
✅ Application logs (easy debugging)
✅ Automatic backups (daily, included)
```

---

## 🌐 Your App Will Be Live At

After deployment, access your app:

```
Frontend:       https://your-domain.com
Backend API:    https://your-domain.com/api
API Docs:       https://your-domain.com/api/docs
Health Check:   https://your-domain.com/api/health
```

---

## 🔧 After Deployment - Maintenance

### Update your code
```bash
ssh -i your-key.pem ubuntu@YOUR_ELASTIC_IP
cd mm
git pull origin main
docker-compose -f docker-compose.prod.yml up -d --build
```

### View logs
```bash
docker-compose -f docker-compose.prod.yml logs -f backend
```

### Restart services
```bash
docker-compose -f docker-compose.prod.yml restart
```

### Auto-renew SSL (runs automatically)
```bash
# Schedule this with cron (automatic)
# 0 2 * * * sudo certbot renew
```

---

## 🆘 Need Help?

### Common Questions

**Q: How do I get my OpenAI API key?**
A: Visit https://platform.openai.com/api-keys → Create new API key

**Q: Where do I buy a domain?**
A: Namecheap (cheapest), GoDaddy, or AWS Route53

**Q: What if the deployment fails?**
A: Check AWS_DEPLOYMENT.md troubleshooting section or view logs:
```bash
docker-compose -f docker-compose.prod.yml logs backend
```

**Q: Can I use a different AWS region?**
A: Yes! Select region in each step, but be consistent.

**Q: What if I exceed free tier?**
A: After 1 year, costs ~$30-50/month. You can scale down or optimize.

---

## 🎯 Next Steps

**Choose your path:**

1. **I want it automated** → Run `deploy-aws.sh`
2. **I want to learn** → Follow `AWS_DEPLOYMENT.md` step-by-step
3. **I want the simplest** → Use Heroku instead (5 minutes, $7/month)

---

## 📞 Support Resources

- **AWS Documentation:** https://docs.aws.amazon.com/
- **Docker Docs:** https://docs.docker.com/
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Let's Encrypt:** https://letsencrypt.org/
- **Nginx Docs:** https://nginx.org/en/docs/

---

## ✨ You're Ready!

Everything is set up and documented. Choose your deployment method:

### 🚀 **Automated (Recommended for speed)**
```bash
sudo ./deploy-aws.sh
```

### 📖 **Manual (Recommended for learning)**
Follow AWS_DEPLOYMENT.md steps 1-11

### 💨 **Alternative: 5-Minute Heroku Deploy**
Follow DEPLOYMENT.md Option 1

---

**Your Clinical Scenario AI Generator is about to go live! 🎉**

Good luck! You've got this! 💪
