#!/bin/bash

# 🚀 Clinical AI Generator - AWS Automated Deployment Script
# This script handles all deployment steps automatically
# Usage: sudo ./deploy-aws.sh

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions for colored output
print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root. Use: sudo ./deploy-aws.sh"
fi

# Check if we're on Ubuntu
if ! grep -qi ubuntu /etc/os-release; then
    print_error "This script is designed for Ubuntu. Please run on Ubuntu 22.04 LTS"
fi

print_header "🚀 Clinical AI Generator - AWS Deployment"

# ============================================
# Step 1: Gather Information
# ============================================
print_header "Step 1: Configuration"

echo -e "${YELLOW}Please provide the following information:${NC}\n"

read -p "Enter your domain name (e.g., clinicalai.com): " DOMAIN
if [ -z "$DOMAIN" ]; then
    print_error "Domain name is required"
fi

read -p "Enter your OpenAI API Key (sk-...): " OPENAI_KEY
if [ -z "$OPENAI_KEY" ]; then
    print_error "OpenAI API Key is required"
fi

read -p "Enter your RDS Database Endpoint (xxx.rds.amazonaws.com): " DB_ENDPOINT
if [ -z "$DB_ENDPOINT" ]; then
    print_error "Database endpoint is required"
fi

read -p "Enter your RDS Database Password: " -s DB_PASSWORD
echo ""
if [ -z "$DB_PASSWORD" ]; then
    print_error "Database password is required"
fi

read -p "Enter your Email (for Let's Encrypt): " EMAIL
if [ -z "$EMAIL" ]; then
    print_error "Email is required"
fi

print_success "Configuration received"

# ============================================
# Step 2: Update System
# ============================================
print_header "Step 2: Updating System Packages"

apt update
apt upgrade -y
apt install -y curl wget git htop vim

print_success "System packages updated"

# ============================================
# Step 3: Install Docker
# ============================================
print_header "Step 3: Installing Docker & Docker Compose"

# Remove old docker installations
apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Add ubuntu user to docker group
usermod -aG docker ubuntu

# Install Docker Compose
DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d'"' -f4)
curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

print_success "Docker and Docker Compose installed"

# ============================================
# Step 4: Clone Repository
# ============================================
print_header "Step 4: Cloning Repository"

cd /home/ubuntu
if [ ! -d "mm" ]; then
    sudo -u ubuntu git clone https://github.com/tarigfm-cmd/mm.git
    print_success "Repository cloned"
else
    print_warning "Repository already exists, updating..."
    cd mm
    sudo -u ubuntu git pull origin main
    cd ..
fi

cd mm

print_success "Repository ready"

# ============================================
# Step 5: Configure Environment Variables
# ============================================
print_header "Step 5: Configuring Environment Variables"

# Generate SECRET_KEY
SECRET_KEY=$(openssl rand -hex 32)

# Create .env file
cat > .env <<EOF
# Application
DEBUG=False
SECRET_KEY=$SECRET_KEY

# OpenAI
OPENAI_API_KEY=$OPENAI_KEY
OPENAI_MODEL=gpt-4-turbo-preview

# Database
DB_USER=postgres
DB_PASSWORD=$DB_PASSWORD
DB_NAME=clinical_ai
DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@${DB_ENDPOINT}:5432/clinical_ai

# Redis
REDIS_URL=redis://redis:6379/0

# Server
HOST=0.0.0.0
PORT=8000
ALLOWED_HOSTS=localhost,127.0.0.1,$DOMAIN,www.$DOMAIN

# Frontend
VITE_API_URL=https://$DOMAIN
VITE_APP_NAME=Clinical AI Generator

# File Upload
MAX_UPLOAD_SIZE=52428800
UPLOAD_DIR=./uploads
ALLOWED_EXTENSIONS=pdf,png,jpg,jpeg,txt,docx

# Monitoring
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=https://$DOMAIN,https://www.$DOMAIN

# Features
ENABLE_REGISTRATION=True
ENABLE_FILE_UPLOAD=True
ENABLE_S3_STORAGE=False
EOF

print_success "Environment variables configured"

# ============================================
# Step 6: Install Certbot for SSL
# ============================================
print_header "Step 6: Installing Certbot (Let's Encrypt)"

apt install -y certbot python3-certbot-nginx

print_success "Certbot installed"

# ============================================
# Step 7: Start Docker Services
# ============================================
print_header "Step 7: Starting Docker Services"

docker-compose -f docker-compose.prod.yml down 2>/dev/null || true
docker-compose -f docker-compose.prod.yml up -d --build

print_success "Docker services started"

# Wait for services to start
print_warning "Waiting 30 seconds for services to initialize..."
sleep 30

# Check if services are running
if docker ps | grep -q clinical-ai-backend; then
    print_success "Backend is running"
else
    print_error "Backend failed to start. Check logs with: docker-compose logs backend"
fi

if docker ps | grep -q clinical-ai-frontend; then
    print_success "Frontend is running"
else
    print_error "Frontend failed to start. Check logs with: docker-compose logs frontend"
fi

# ============================================
# Step 8: Test Backend Health
# ============================================
print_header "Step 8: Testing Backend Health"

# Wait for backend to be ready
for i in {1..30}; do
    if curl -f http://localhost:8000/api/health > /dev/null 2>&1; then
        print_success "Backend health check passed"
        break
    fi
    if [ $i -eq 30 ]; then
        print_warning "Backend health check failed, but continuing..."
    fi
    sleep 1
done

# ============================================
# Step 9: Get SSL Certificate
# ============================================
print_header "Step 9: Getting SSL Certificate (Let's Encrypt)"

# Stop any services using port 80
docker-compose -f docker-compose.prod.yml down 2>/dev/null || true

# Get certificate
certbot certonly --standalone \
    -d $DOMAIN \
    -d www.$DOMAIN \
    --agree-tos \
    --email $EMAIL \
    --non-interactive \
    --preferred-challenges http

if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    print_success "SSL certificate obtained"
else
    print_error "Failed to obtain SSL certificate"
fi

# ============================================
# Step 10: Configure Nginx
# ============================================
print_header "Step 10: Configuring Nginx"

# Update nginx.conf with domain
cat > nginx.conf <<'NGINXEOF'
user www-data;
worker_processes auto;
pid /run/nginx.pid;

events {
    worker_connections 768;
}

http {
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 50M;

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript application/xml+rss 
               application/rss+xml font/truetype font/opentype 
               application/vnd.ms-fontobject image/svg+xml;

    upstream backend {
        server backend:8000;
    }

    upstream frontend {
        server frontend:80;
    }

    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name DOMAIN_PLACEHOLDER www.DOMAIN_PLACEHOLDER;

        ssl_certificate /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/privkey.pem;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;

        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        root /var/www/html;
        index index.html;
    }
}
NGINXEOF

# Replace placeholder with actual domain
sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" nginx.conf

print_success "Nginx configured"

# ============================================
# Step 11: Restart Services with Nginx
# ============================================
print_header "Step 11: Restarting Services"

docker-compose -f docker-compose.prod.yml up -d

# Wait for services
sleep 10

print_success "All services restarted"

# ============================================
# Step 12: Setup SSL Auto-Renewal
# ============================================
print_header "Step 12: Setting Up SSL Auto-Renewal"

# Add certbot renewal to crontab
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/bin/certbot renew --quiet") | crontab -

print_success "SSL auto-renewal configured"

# ============================================
# Verification
# ============================================
print_header "Deployment Complete! 🎉"

echo -e "${GREEN}Your Clinical Scenario AI Generator is now deployed!${NC}\n"

echo -e "${BLUE}📊 Access Your Application:${NC}"
echo -e "  🌐 Frontend:     https://$DOMAIN"
echo -e "  🔌 Backend API:  https://$DOMAIN/api"
echo -e "  📚 API Docs:     https://$DOMAIN/api/docs"
echo -e "  ✅ Health Check: https://$DOMAIN/api/health\n"

echo -e "${BLUE}📝 Useful Commands:${NC}"
echo -e "  View logs:       docker-compose -f docker-compose.prod.yml logs -f"
echo -e "  Check services:  docker-compose -f docker-compose.prod.yml ps"
echo -e "  Restart all:     docker-compose -f docker-compose.prod.yml restart"
echo -e "  Update code:     git pull && docker-compose -f docker-compose.prod.yml up -d --build\n"

echo -e "${BLUE}⚠️  Don't Forget:${NC}"
echo -e "  1. Point your domain to this server's IP"
echo -e "  2. Wait 15-30 minutes for DNS propagation"
echo -e "  3. Monitor logs for any issues"
echo -e "  4. Setup monitoring (Sentry, UptimeRobot)\n"

echo -e "${GREEN}Deployment script completed successfully! 🚀${NC}\n"

# Show status
print_header "Service Status"
docker-compose -f docker-compose.prod.yml ps
