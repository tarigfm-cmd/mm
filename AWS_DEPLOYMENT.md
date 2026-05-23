# 🚀 AWS Deployment Guide - Complete Step-by-Step

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Step 1-5: AWS Setup](#step-1-5-aws-setup)
3. [Step 6-8: Server Setup](#step-6-8-server-setup)
4. [Step 9-11: Application Deployment](#step-9-11-application-deployment)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)
7. [Maintenance](#maintenance)

---

## Prerequisites

Before starting, have these ready:

- [ ] AWS Account (free tier) - https://aws.amazon.com/free
- [ ] Domain name ($12-15/year) - Namecheap or GoDaddy
- [ ] OpenAI API Key - https://platform.openai.com/api-keys
- [ ] SSH client (built-in on Mac/Linux, PuTTY on Windows)
- [ ] Your GitHub repository URL

---

## Step 1-5: AWS Setup

### Step 1: Create AWS Account (5 minutes)

1. Go to https://aws.amazon.com/free
2. Click "Create a free account"
3. Fill in your email and password
4. Verify your identity (credit card required but won't be charged for free tier)
5. Choose your AWS region (pick one closest to you, e.g., us-east-1)

**✅ Done! You now have AWS access.**

---

### Step 2: Create Security Group (3 minutes)

Security Groups are like firewalls. We'll create one for our server.

1. Go to **AWS Console** → Search "EC2"
2. In left menu: **Security Groups**
3. Click **Create security group**
   - Name: `clinical-ai-sg`
   - Description: `Security group for Clinical AI`
4. Add inbound rules:

| Type | Protocol | Port | Source |
|------|----------|------|--------|
| SSH | TCP | 22 | 0.0.0.0/0 (Your IP better) |
| HTTP | TCP | 80 | 0.0.0.0/0 |
| HTTPS | TCP | 443 | 0.0.0.0/0 |

5. Click **Create security group**

**✅ Done! Your firewall is ready.**

---

### Step 3: Launch EC2 Instance (5 minutes)

EC2 is your server.

1. Go to **EC2 Dashboard** → Click **Launch instance**
2. Fill in:
   - **Name:** `clinical-ai-server`
   - **OS Image:** Ubuntu 22.04 LTS (Free Tier eligible)
   - **Instance type:** t2.micro (Free Tier eligible)
   - **Key pair:** 
     - Click "Create new key pair"
     - Name: `clinical-ai-key`
     - Format: `.pem` (for Mac/Linux) or `.ppk` (for Windows)
     - Click "Create key pair" (saves to your Downloads)
   - **Network settings:** 
     - Security group: Select `clinical-ai-sg` (created above)
   - **Storage:** 30 GB (Free Tier allows 30 GB)

3. Click **Launch instance**
4. Wait 2-3 minutes for instance to start
5. See green checkmark when ready

**✅ Done! Your server is running.**

---

### Step 4: Get Elastic IP (2 minutes)

Elastic IP keeps your server address stable (important for your domain).

1. Go to **EC2 Dashboard** → **Elastic IPs** (left menu)
2. Click **Allocate Elastic IP address**
3. Select your region
4. Click **Allocate**
5. In the list, find the new IP
6. Click it, then click **Associate Elastic IP address**
7. Select your `clinical-ai-server` instance
8. Click **Associate**

**✅ Done! You now have a static IP. Save it! Format: `54.123.45.67`**

---

### Step 5: Create RDS PostgreSQL Database (5 minutes)

RDS is AWS's managed database.

1. Go to **RDS Dashboard** → Click **Create database**
2. Fill in:
   - **Engine:** PostgreSQL
   - **Version:** Latest (15.x)
   - **Templates:** Free tier (make sure it shows "eligible for free tier")
   - **DB instance identifier:** `clinical-ai-db`
   - **Master username:** `postgres`
   - **Master password:** Create strong password (20+ chars)
     - Example: `P@ssw0rd!Clinical2024#Secure`
     - **SAVE THIS PASSWORD!**
   - **Allocated storage:** 20 GB (Free Tier)
   - **Storage type:** gp2
   - **VPC & Security:** 
     - VPC Security group: Create new → Name: `clinical-ai-rds-sg`
     - Publicly accessible: Yes
   - **Initial database name:** `clinical_ai`
   - **Backup retention:** 7 days
   - **Encryption:** Disabled (optional for free tier)

3. Click **Create database**
4. Wait 5-10 minutes for database to be ready
5. When green checkmark appears, click the database
6. Find **Endpoint** (looks like: `clinical-ai-db.xxxxx.us-east-1.rds.amazonaws.com`)
7. **SAVE THIS ENDPOINT!**

**✅ Done! Your database is ready.**

---

## Step 6-8: Server Setup

### Step 6: SSH Into Your Server (3 minutes)

SSH lets you control your server from your computer.

**On Mac/Linux:**
```bash
# Open terminal and change to Downloads folder
cd ~/Downloads

# Fix key permissions
chmod 400 clinical-ai-key.pem

# Connect to your server
# Replace 54.123.45.67 with your Elastic IP from Step 4
ssh -i clinical-ai-key.pem ubuntu@54.123.45.67

# Type 'yes' when asked about fingerprint
# You should see: ubuntu@ip-xxx:~$
```

**On Windows:**
1. Download PuTTY: https://www.putty.org/
2. Convert key: PuTTYgen → Load `.pem` → Save as `.ppk`
3. Open PuTTY → Host: `54.123.45.67` → Auth → Select `.ppk` file → Open

**✅ Done! You're now inside your server.**

---

### Step 7: Install Docker & Clone Project (5 minutes)

Run these commands on your server:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone your repository
cd /home/ubuntu
git clone https://github.com/tarigfm-cmd/mm.git
cd mm

# Copy environment file
cp .env.example .env

# Edit environment file
sudo nano .env
```

In the editor:
1. Set your environment variables:
   ```
   DEBUG=False
   OPENAI_API_KEY=sk-your-openai-key-here
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@YOUR_RDS_ENDPOINT:5432/clinical_ai
   SECRET_KEY=generate-random-secret-key-here-at-least-50-characters
   ALLOWED_HOSTS=your-domain.com,54.123.45.67
   ```

2. Save: Press `Ctrl+O` → `Enter` → `Ctrl+X`

**✅ Done! Your server is ready.**

---

### Step 8: Start Docker Services (5 minutes)

```bash
# Still in /home/ubuntu/mm directory

# Start services in production mode
sudo docker-compose -f docker-compose.prod.yml up -d

# Watch the logs (wait 30 seconds)
sudo docker-compose -f docker-compose.prod.yml logs -f

# You should see:
# - Backend running on port 8000
# - Frontend running on port 5173
# - PostgreSQL connection successful
# - Nginx running on port 80/443

# Stop watching logs: Press Ctrl+C
```

Test if backend is running:
```bash
curl http://localhost:8000/api/health

# Should return: {"status":"ok"}
```

**✅ Done! Your services are running.**

---

## Step 9-11: Application Deployment

### Step 9: Setup SSL Certificate with Let's Encrypt (3 minutes)

SSL makes your site secure (HTTPS).

```bash
# Install Certbot (Let's Encrypt tool)
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
# Replace your-domain.com with your actual domain
sudo certbot certonly --standalone \
  -d your-domain.com \
  -d www.your-domain.com \
  --agree-tos \
  --email your-email@example.com

# You'll see success message with certificate location
# Certificates are at: /etc/letsencrypt/live/your-domain.com/

# Setup auto-renewal (runs automatically)
sudo certbot renew --dry-run
```

**✅ Done! You have a free SSL certificate.**

---

### Step 10: Configure Nginx (2 minutes)

Update your nginx.conf file with your domain:

```bash
sudo nano /etc/nginx/nginx.conf
```

Find and update:
```
server_name your-domain.com www.your-domain.com;
ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
```

Reload Nginx:
```bash
sudo nginx -t  # Test config
sudo systemctl reload nginx
```

**✅ Done! Nginx is configured.**

---

### Step 11: Point Domain to Your Server (3 minutes)

This makes your domain point to your server.

1. Go to your domain registrar (Namecheap, GoDaddy, etc.)
2. Go to **DNS Settings**
3. Find **A Record** or **Name Server**
4. Create/Edit:
   - **Name:** @ (or leave blank)
   - **Type:** A
   - **Value:** Your Elastic IP (e.g., `54.123.45.67`)
   - **TTL:** 3600
5. Click Save
6. Wait 15-30 minutes for DNS propagation

Test DNS:
```bash
# On your computer
nslookup your-domain.com

# Should show your Elastic IP
```

**✅ Done! Your domain is configured.**

---

## Verification

### Test Everything Works

```bash
# From your computer, test:

# 1. Frontend (should show your app)
curl https://your-domain.com

# 2. Backend API (should return JSON)
curl https://your-domain.com/api/health

# 3. API Documentation
# Visit: https://your-domain.com/api/docs in browser
```

### Access Your App

Open these in your browser:
- 🌐 **Frontend:** https://your-domain.com
- 🔌 **Backend API:** https://your-domain.com/api
- 📚 **API Docs:** https://your-domain.com/api/docs
- ✅ **Health Check:** https://your-domain.com/api/health

---

## Troubleshooting

### Issue: Can't SSH to Server

```bash
# Check security group allows port 22
# Check key file permissions: chmod 400 clinical-ai-key.pem
# Try explicit region: ssh -i key.pem -o ConnectTimeout=10 ubuntu@IP
```

### Issue: Docker Services Won't Start

```bash
# Check logs
sudo docker-compose -f docker-compose.prod.yml logs

# Check disk space
df -h

# Restart Docker
sudo systemctl restart docker
sudo docker-compose -f docker-compose.prod.yml up -d
```

### Issue: Certificate Renewal Fails

```bash
# Manual renew
sudo certbot renew --force-renewal

# Check certificate expiration
sudo certbot certificates
```

### Issue: 502 Bad Gateway

```bash
# Backend might be down
sudo docker-compose -f docker-compose.prod.yml logs backend

# Restart services
sudo docker-compose -f docker-compose.prod.yml restart backend
```

### Issue: Database Connection Error

```bash
# Check RDS endpoint is correct in .env
cat .env | grep DATABASE_URL

# Test connection from server
psql -h YOUR_RDS_ENDPOINT -U postgres -d clinical_ai

# Verify security group allows port 5432
```

---

## Maintenance

### Update Your Application

```bash
# SSH to your server
ssh -i clinical-ai-key.pem ubuntu@YOUR_ELASTIC_IP

# Pull latest changes
cd /home/ubuntu/mm
git pull origin main

# Rebuild and restart
sudo docker-compose -f docker-compose.prod.yml up -d --build

# Check logs
sudo docker-compose -f docker-compose.prod.yml logs -f
```

### View Logs

```bash
# Real-time logs
sudo docker-compose -f docker-compose.prod.yml logs -f

# Backend only
sudo docker-compose -f docker-compose.prod.yml logs -f backend

# Filter by keyword
sudo docker-compose -f docker-compose.prod.yml logs | grep error
```

### Restart Services

```bash
# Restart all
sudo docker-compose -f docker-compose.prod.yml restart

# Restart specific service
sudo docker-compose -f docker-compose.prod.yml restart backend
sudo docker-compose -f docker-compose.prod.yml restart frontend
```

### Check Server Health

```bash
# Disk usage
df -h

# Memory usage
free -h

# CPU usage
top

# Docker status
docker ps -a

# Nginx status
sudo systemctl status nginx
```

### Auto-Renew SSL Certificate

```bash
# Check renewal works
sudo certbot renew --dry-run

# Add to crontab (runs at 2 AM daily)
sudo crontab -e

# Add this line:
0 2 * * * /usr/bin/certbot renew
```

---

## Cost Tracking

Monitor your costs in AWS Console:

1. Go to **Billing Dashboard**
2. Check monthly estimate
3. Set **Budget Alerts** to be notified if you exceed $10

Free Tier limits:
- EC2: 750 hours/month (runs 24/7 all month)
- RDS: 750 hours/month
- Data transfer: 1 GB/month

After free tier expires (~$30-50/month total).

---

## 🎉 You're Live!

Your Clinical Scenario AI Generator is now running on production AWS! 

```
✅ Secure HTTPS connection
✅ Production-grade database
✅ Auto-renewing SSL certificate
✅ Nginx reverse proxy
✅ Docker containerization
✅ Easy updates via git pull
✅ Automatic backups (RDS)
✅ Monitoring and logs
```

### Next Steps

1. ✅ Monitor application for errors
2. ✅ Collect user feedback
3. ✅ Track performance metrics
4. ✅ Plan scaling as you grow

---

## Support

- AWS Docs: https://docs.aws.amazon.com/
- Docker Docs: https://docs.docker.com/
- FastAPI Docs: https://fastapi.tiangolo.com/
- Let's Encrypt: https://letsencrypt.org/

**Congratulations! 🚀**
