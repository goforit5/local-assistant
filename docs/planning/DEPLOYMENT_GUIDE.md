# Deployment Guide: Life Graph Integration
**Version**: 1.0.0
**Date**: 2025-11-06
**Author**: AI Development Team
**Status**: Planning Phase

---

## Table of Contents
1. [Overview](#overview)
2. [Infrastructure Requirements](#infrastructure-requirements)
3. [Environment Setup](#environment-setup)
4. [Development Deployment](#development-deployment)
5. [Staging Deployment](#staging-deployment)
6. [Production Deployment](#production-deployment)
7. [Database Management](#database-management)
8. [Monitoring & Observability](#monitoring--observability)
9. [Backup & Disaster Recovery](#backup--disaster-recovery)
10. [Scaling Strategy](#scaling-strategy)
11. [Troubleshooting](#troubleshooting)

---

## Overview

### Deployment Strategy

**Current (v1.0)**: Single-server deployment for personal use
**Future (v2.0+)**: Multi-server with load balancing and auto-scaling

### Deployment Environments

| Environment | Purpose | Update Frequency |
|-------------|---------|------------------|
| **Development** | Local development and testing | Continuous |
| **Staging** | Pre-production testing and QA | After PR merge to main |
| **Production** | Live user-facing environment | Weekly releases |

---

## Infrastructure Requirements

### Minimum Requirements (v1.0 - Personal Use)

**Hardware**:
- **CPU**: 2 cores (4 recommended)
- **RAM**: 4 GB (8 GB recommended)
- **Storage**: 50 GB SSD (for documents + database)
- **Network**: 10 Mbps upload/download

**Software**:
- **OS**: macOS 12+, Ubuntu 22.04+, or Windows 11 with WSL2
- **Python**: 3.11+
- **Node.js**: 20+
- **PostgreSQL**: 16+
- **Docker**: 24+ (optional, for containerized deployment)

### Recommended Production Requirements (v2.0+)

**Hardware** (per server):
- **CPU**: 4 cores (8 recommended)
- **RAM**: 16 GB (32 GB recommended)
- **Storage**: 500 GB SSD + S3/CDN for documents
- **Network**: 100 Mbps+

**Infrastructure**:
- **API Servers**: 2+ (load balanced)
- **Database**: PostgreSQL with read replicas
- **Cache**: Redis for session/query caching
- **CDN**: CloudFront or similar for document delivery
- **Load Balancer**: AWS ALB, Nginx, or Traefik

---

## Environment Setup

### Environment Variables

**File**: `.env` (never commit this file!)
```bash
# Application
APP_NAME=local_assistant
ENVIRONMENT=development  # development, staging, production
VERSION=1.0.0
DEBUG=true               # false in production

# API Server
API_HOST=0.0.0.0
API_PORT=8765
API_WORKERS=1            # 4+ in production

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5433/local_assistant
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_DEFAULT_MODEL=gpt-4o
OPENAI_MAX_TOKENS=4096

# Document Storage
DOCUMENT_STORAGE_PATH=/Users/andrew/Projects/AGENTS/local_assistant/storage/documents
DOCUMENT_MAX_SIZE_MB=10

# Security (JWT for future multi-user)
SECRET_KEY=your-secret-key-here-change-in-production
JWT_EXPIRATION_HOURS=24

# Monitoring
LOG_LEVEL=INFO           # DEBUG, INFO, WARNING, ERROR
SENTRY_DSN=              # Optional: error tracking
PROMETHEUS_PORT=9090     # Optional: metrics

# Feature Flags
ENABLE_DOCUMENT_DEDUPLICATION=true
ENABLE_FUZZY_MATCHING=true
ENABLE_PRIORITY_CALCULATION=true
```

**Template**: `.env.template` (commit this)
```bash
# Copy to .env and fill in values
APP_NAME=local_assistant
ENVIRONMENT=development
DATABASE_URL=postgresql://postgres:password@localhost:5433/local_assistant
OPENAI_API_KEY=sk-...
SECRET_KEY=change-me
```

### Configuration Files

**Directory Structure**:
```
config/
├── document_intelligence_config.yaml
├── entity_resolution_config.yaml
├── commitment_priority_config.yaml
├── storage_config.yaml
└── prompts/
    ├── entity-resolution/
    │   └── vendor_matching_v1.0.0.yaml
    ├── commitment-creation/
    │   └── invoice_to_commitment_v1.0.0.yaml
    └── validation/
        └── validate_vendor_v1.0.0.yaml
```

---

## Development Deployment

### Local Setup (macOS/Linux)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/local_assistant.git
cd local_assistant

# 2. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Testing tools

# 4. Install UI dependencies
cd ui
npm install
cd ..

# 5. Copy environment template
cp .env.template .env
vim .env  # Fill in OPENAI_API_KEY and other secrets

# 6. Start PostgreSQL (Docker)
docker run -d \
  --name local_assistant_postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=local_assistant \
  -p 5433:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:16

# 7. Run database migrations
alembic upgrade head

# 8. Seed test data (optional)
python scripts/seed_test_data.py

# 9. Start API server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8765

# 10. Start UI dev server (new terminal)
cd ui
npm run dev

# 11. Access application
# UI: http://localhost:5173
# API: http://localhost:8765/api
# API Docs: http://localhost:8765/api/docs
```

### Docker Compose (Alternative)

**File**: `docker-compose.dev.yml`
```yaml
version: '3.9'

services:
  postgres:
    image: postgres:16
    container_name: local_assistant_postgres
    environment:
      POSTGRES_DB: local_assistant
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: Dockerfile.dev
    container_name: local_assistant_api
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://postgres:password@postgres:5432/local_assistant
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8765:8765"
    volumes:
      - ./api:/app/api
      - ./config:/app/config
      - ./storage:/app/storage
    command: uvicorn api.main:app --reload --host 0.0.0.0 --port 8765

  ui:
    build:
      context: ./ui
      dockerfile: Dockerfile.dev
    container_name: local_assistant_ui
    depends_on:
      - api
    ports:
      - "5173:5173"
    volumes:
      - ./ui/src:/app/src
    command: npm run dev -- --host 0.0.0.0

volumes:
  postgres_data:
```

**Usage**:
```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Stop all services
docker-compose -f docker-compose.dev.yml down

# Rebuild after dependency changes
docker-compose -f docker-compose.dev.yml up -d --build
```

---

## Staging Deployment

### Staging Server Setup

**Server Requirements**:
- Ubuntu 22.04 LTS
- 4 GB RAM
- 50 GB SSD
- Nginx reverse proxy
- SSL certificate (Let's Encrypt)

### Automated Staging Deployment

**Script**: `scripts/deploy_staging.sh`
```bash
#!/bin/bash
set -e

echo "🚀 Deploying to staging..."

# Configuration
STAGING_HOST="staging.local-assistant.com"
STAGING_USER="deploy"
APP_DIR="/opt/local_assistant"

# 1. SSH into staging server
ssh $STAGING_USER@$STAGING_HOST << 'ENDSSH'
  cd /opt/local_assistant

  # 2. Pull latest code
  echo "📥 Pulling latest code..."
  git fetch origin
  git checkout main
  git pull origin main

  # 3. Activate virtual environment
  source venv/bin/activate

  # 4. Install dependencies
  echo "📦 Installing dependencies..."
  pip install -r requirements.txt

  # 5. Run database migrations
  echo "🔄 Running migrations..."
  alembic upgrade head

  # 6. Build UI
  echo "🏗️  Building UI..."
  cd ui
  npm install
  npm run build
  cd ..

  # 7. Restart services
  echo "♻️  Restarting services..."
  sudo systemctl restart local-assistant-api
  sudo systemctl restart nginx

  # 8. Health check
  echo "🏥 Running health check..."
  sleep 5
  curl -f http://localhost:8765/api/health || exit 1

  echo "✅ Staging deployment complete!"
ENDSSH

# 9. Run smoke tests against staging
echo "🧪 Running smoke tests..."
ENVIRONMENT=staging pytest -m smoke tests/

echo "✅ Staging validated!"
```

### Systemd Service Configuration

**File**: `/etc/systemd/system/local-assistant-api.service`
```ini
[Unit]
Description=Local Assistant API Service
After=network.target postgresql.service

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/opt/local_assistant
Environment="PATH=/opt/local_assistant/venv/bin"
EnvironmentFile=/opt/local_assistant/.env
ExecStart=/opt/local_assistant/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8765 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start**:
```bash
sudo systemctl enable local-assistant-api
sudo systemctl start local-assistant-api
sudo systemctl status local-assistant-api
```

### Nginx Reverse Proxy

**File**: `/etc/nginx/sites-available/local-assistant`
```nginx
upstream api_backend {
    server 127.0.0.1:8765;
}

server {
    listen 80;
    server_name staging.local-assistant.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name staging.local-assistant.com;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/staging.local-assistant.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/staging.local-assistant.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # API proxy
    location /api {
        proxy_pass http://api_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # UI static files
    location / {
        root /opt/local_assistant/ui/dist;
        try_files $uri $uri/ /index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Health check endpoint (no auth required)
    location = /api/health {
        proxy_pass http://api_backend;
        access_log off;
    }
}
```

**Enable and reload**:
```bash
sudo ln -s /etc/nginx/sites-available/local-assistant /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Production Deployment

### Production Checklist

**Before Deployment**:
- [ ] All tests pass (unit, integration, E2E)
- [ ] Security scan clean (bandit, safety)
- [ ] Performance benchmarks meet targets
- [ ] Database migrations tested (upgrade + downgrade)
- [ ] Rollback plan prepared
- [ ] Monitoring dashboards ready
- [ ] On-call engineer available
- [ ] Backup verified within last 24 hours
- [ ] Deployment window communicated to users

### Blue-Green Deployment

**Strategy**: Zero-downtime deployment with instant rollback capability

```mermaid
graph TD
    A[Blue - Current Production] --> B[Deploy Green - New Version]
    B --> C[Run smoke tests on Green]
    C --> D{Tests pass?}
    D -->|No| E[Destroy Green, Keep Blue]
    D -->|Yes| F[Switch load balancer to Green]
    F --> G[Monitor metrics]
    G --> H{Issues detected?}
    H -->|Yes| I[Switch back to Blue - Instant rollback]
    H -->|No| J[Success - Green becomes new Blue]
```

**Docker Compose** (Production):

**File**: `docker-compose.prod.yml`
```yaml
version: '3.9'

services:
  postgres:
    image: postgres:16
    container_name: local_assistant_postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: always

  api_blue:
    image: local-assistant-api:${BLUE_VERSION}
    container_name: local_assistant_api_blue
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ENVIRONMENT: production
      LOG_LEVEL: INFO
    ports:
      - "8765:8765"
    volumes:
      - ./config:/app/config:ro
      - ./storage:/app/storage
    command: uvicorn api.main:app --host 0.0.0.0 --port 8765 --workers 4
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8765/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  api_green:
    image: local-assistant-api:${GREEN_VERSION}
    container_name: local_assistant_api_green
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ENVIRONMENT: production
      LOG_LEVEL: INFO
    ports:
      - "8766:8765"  # Different external port
    volumes:
      - ./config:/app/config:ro
      - ./storage:/app/storage
    command: uvicorn api.main:app --host 0.0.0.0 --port 8765 --workers 4
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8765/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:latest
    container_name: local_assistant_nginx
    depends_on:
      - api_blue
      - api_green
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./ui/dist:/usr/share/nginx/html:ro
    restart: always

volumes:
  postgres_data:
```

### Production Deployment Script

**File**: `scripts/deploy_production.sh`
```bash
#!/bin/bash
set -e

# Configuration
VERSION=$1
BLUE_VERSION=$(cat .current_version)
GREEN_VERSION=$VERSION

if [ -z "$VERSION" ]; then
    echo "Usage: ./deploy_production.sh <version>"
    exit 1
fi

echo "🚀 Starting production deployment..."
echo "📦 Blue (current): $BLUE_VERSION"
echo "📦 Green (new): $GREEN_VERSION"

# 1. Pre-deployment checks
echo "🔍 Running pre-deployment checks..."
./scripts/pre_deploy_checks.sh || exit 1

# 2. Backup database
echo "💾 Creating database backup..."
docker exec local_assistant_postgres pg_dump -U postgres local_assistant > \
    backups/backup_$(date +%Y%m%d_%H%M%S).sql
echo "✅ Backup created"

# 3. Build new image
echo "🏗️  Building new Docker image..."
docker build -t local-assistant-api:$GREEN_VERSION .

# 4. Run database migrations (if any)
echo "🔄 Running database migrations..."
docker run --rm --network host \
    -e DATABASE_URL=$DATABASE_URL \
    local-assistant-api:$GREEN_VERSION \
    alembic upgrade head

# 5. Deploy Green
echo "🟢 Deploying Green environment..."
export GREEN_VERSION=$GREEN_VERSION
export BLUE_VERSION=$BLUE_VERSION
docker-compose -f docker-compose.prod.yml up -d api_green

# 6. Wait for Green to be healthy
echo "⏳ Waiting for Green to be healthy..."
sleep 10
for i in {1..30}; do
    if curl -f http://localhost:8766/api/health > /dev/null 2>&1; then
        echo "✅ Green is healthy"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# 7. Run smoke tests against Green
echo "🧪 Running smoke tests..."
ENVIRONMENT=production API_URL=http://localhost:8766 pytest -m smoke tests/
if [ $? -ne 0 ]; then
    echo "❌ Smoke tests failed! Rolling back..."
    docker-compose -f docker-compose.prod.yml stop api_green
    exit 1
fi

# 8. Switch traffic from Blue to Green
echo "🔄 Switching traffic from Blue to Green..."
sed -i.bak 's/api_blue:8765/api_green:8765/g' nginx/nginx.conf
docker exec local_assistant_nginx nginx -s reload

# 9. Monitor for 5 minutes
echo "👀 Monitoring Green for 5 minutes..."
for i in {1..30}; do
    if ! curl -f http://localhost/api/health > /dev/null 2>&1; then
        echo "❌ Health check failed! Rolling back..."
        sed -i.bak 's/api_green:8765/api_blue:8765/g' nginx/nginx.conf
        docker exec local_assistant_nginx nginx -s reload
        exit 1
    fi
    echo "Health check passed ($i/30)"
    sleep 10
done

# 10. Success - Stop Blue
echo "✅ Deployment successful!"
docker-compose -f docker-compose.prod.yml stop api_blue
echo $GREEN_VERSION > .current_version

echo "🎉 Production deployment complete!"
echo "📝 New version: $GREEN_VERSION"
echo "📝 Previous version (Blue): $BLUE_VERSION still available for rollback"
```

### Rollback Procedure

```bash
#!/bin/bash
# scripts/rollback_production.sh

set -e

PREVIOUS_VERSION=$(cat .previous_version)

echo "⏪ Rolling back to version: $PREVIOUS_VERSION"

# 1. Switch traffic back to Blue
sed -i.bak 's/api_green:8765/api_blue:8765/g' nginx/nginx.conf
docker exec local_assistant_nginx nginx -s reload

# 2. Start Blue (if stopped)
docker-compose -f docker-compose.prod.yml up -d api_blue

# 3. Wait for Blue to be healthy
sleep 10
curl -f http://localhost/api/health || exit 1

# 4. Stop Green
docker-compose -f docker-compose.prod.yml stop api_green

echo "✅ Rollback complete!"
```

---

## Database Management

### Backup Strategy

**Automated Daily Backups**:

**Cron Job** (`/etc/cron.d/local-assistant-backup`):
```bash
# Daily backup at 2 AM
0 2 * * * deploy /opt/local_assistant/scripts/backup_database.sh

# Weekly full backup (Sunday 3 AM)
0 3 * * 0 deploy /opt/local_assistant/scripts/backup_database_full.sh
```

**Backup Script** (`scripts/backup_database.sh`):
```bash
#!/bin/bash
set -e

BACKUP_DIR="/opt/local_assistant/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.sql"
DAYS_TO_KEEP=30

# 1. Create backup
echo "📦 Creating database backup..."
docker exec local_assistant_postgres pg_dump -U postgres -F c local_assistant > $BACKUP_FILE

# 2. Compress
echo "🗜️  Compressing backup..."
gzip $BACKUP_FILE

# 3. Upload to S3 (optional)
if [ ! -z "$AWS_S3_BACKUP_BUCKET" ]; then
    echo "☁️  Uploading to S3..."
    aws s3 cp $BACKUP_FILE.gz s3://$AWS_S3_BACKUP_BUCKET/backups/
fi

# 4. Clean up old backups
echo "🧹 Cleaning up backups older than $DAYS_TO_KEEP days..."
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +$DAYS_TO_KEEP -delete

echo "✅ Backup complete: $BACKUP_FILE.gz"
```

### Restore Procedure

```bash
#!/bin/bash
# scripts/restore_database.sh

set -e

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./restore_database.sh <backup_file.sql.gz>"
    exit 1
fi

echo "⚠️  WARNING: This will replace the current database!"
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# 1. Stop API servers
echo "🛑 Stopping API servers..."
docker-compose -f docker-compose.prod.yml stop api_blue api_green

# 2. Drop and recreate database
echo "🗑️  Dropping database..."
docker exec local_assistant_postgres psql -U postgres -c "DROP DATABASE IF EXISTS local_assistant;"
docker exec local_assistant_postgres psql -U postgres -c "CREATE DATABASE local_assistant;"

# 3. Restore backup
echo "📥 Restoring backup..."
gunzip -c $BACKUP_FILE | docker exec -i local_assistant_postgres psql -U postgres -d local_assistant

# 4. Run migrations (if needed)
echo "🔄 Running migrations..."
docker run --rm --network host \
    -e DATABASE_URL=$DATABASE_URL \
    local-assistant-api:latest \
    alembic upgrade head

# 5. Restart API servers
echo "♻️  Restarting API servers..."
docker-compose -f docker-compose.prod.yml up -d api_blue

echo "✅ Restore complete!"
```

---

## Monitoring & Observability

### Logging Configuration

**Structured Logging** (`api/core/logger.py`):
```python
"""Structured logging configuration."""

import logging
import json
from datetime import datetime
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['service'] = 'local-assistant-api'
        log_record['version'] = os.getenv('VERSION', 'unknown')


def setup_logger():
    """Configure structured logging."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
```

### Prometheus Metrics

**Metrics Endpoint** (`api/routes/metrics.py`):
```python
"""Prometheus metrics endpoint."""

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import APIRouter

router = APIRouter()

# Metrics
api_requests_total = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

api_request_duration_seconds = Histogram(
    'api_request_duration_seconds',
    'API request duration',
    ['method', 'endpoint']
)

extraction_cost_dollars_total = Counter(
    'extraction_cost_dollars_total',
    'Total extraction cost in dollars'
)

documents_uploaded_total = Counter(
    'documents_uploaded_total',
    'Total documents uploaded'
)

database_connections = Gauge(
    'database_connections',
    'Number of active database connections'
)


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

### Monitoring Dashboard

**Grafana Dashboard** (`monitoring/grafana_dashboard.json`):
```json
{
  "dashboard": {
    "title": "Local Assistant - Production",
    "panels": [
      {
        "title": "API Request Rate",
        "targets": [
          {
            "expr": "rate(api_requests_total[5m])"
          }
        ]
      },
      {
        "title": "API Latency (P95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, api_request_duration_seconds_bucket)"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(api_requests_total{status=~\"5..\"}[5m])"
          }
        ]
      },
      {
        "title": "Extraction Cost (Daily)",
        "targets": [
          {
            "expr": "increase(extraction_cost_dollars_total[24h])"
          }
        ]
      }
    ]
  }
}
```

### Alerting Rules

**Prometheus Alerts** (`monitoring/alerts.yml`):
```yaml
groups:
  - name: local_assistant_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(api_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} requests/sec"

      - alert: HighLatency
        expr: histogram_quantile(0.95, api_request_duration_seconds_bucket) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "API latency is high"
          description: "P95 latency is {{ $value }}s"

      - alert: DatabaseConnectionPoolExhausted
        expr: database_connections > 20
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool exhausted"

      - alert: HighExtractionCost
        expr: increase(extraction_cost_dollars_total[1h]) > 10
        labels:
          severity: warning
        annotations:
          summary: "High extraction cost"
          description: "Cost is ${{ $value }} in last hour"
```

---

## Backup & Disaster Recovery

### Backup Types

| Type | Frequency | Retention | Storage |
|------|-----------|-----------|---------|
| **Incremental** | Every 6 hours | 7 days | Local disk |
| **Daily Full** | Daily at 2 AM | 30 days | Local + S3 |
| **Weekly Full** | Sunday 3 AM | 90 days | S3 Glacier |

### Disaster Recovery Plan

**RTO (Recovery Time Objective)**: 4 hours
**RPO (Recovery Point Objective)**: 6 hours (incremental backup interval)

**Recovery Steps**:
```bash
# 1. Provision new server (if hardware failure)
# 2. Install dependencies
# 3. Restore latest backup
./scripts/restore_database.sh backups/backup_latest.sql.gz

# 4. Restore document storage
aws s3 sync s3://backup-bucket/storage/ ./storage/

# 5. Deploy application
./scripts/deploy_production.sh $(cat .current_version)

# 6. Verify
curl -f http://localhost/api/health
pytest -m smoke tests/
```

---

## Scaling Strategy

### Vertical Scaling (v1.0)

**Current**: Single server, increase resources as needed
- Upgrade RAM: 4GB → 8GB → 16GB
- Upgrade CPU: 2 cores → 4 cores → 8 cores
- Upgrade storage: Add SSD capacity

### Horizontal Scaling (v2.0+)

**Load Balanced Architecture**:
```
                     ┌─────────────┐
Internet ────────────┤ Load Balancer│
                     └──────┬───────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
       ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
       │ API #1  │     │ API #2  │     │ API #3  │
       └────┬────┘     └────┬────┘     └────┬────┘
            │               │               │
            └───────────────┼───────────────┘
                            │
                     ┌──────▼───────┐
                     │  PostgreSQL  │
                     │  (Primary)   │
                     └──────┬───────┘
                            │
                     ┌──────▼───────┐
                     │  PostgreSQL  │
                     │  (Replica)   │
                     └──────────────┘
```

---

## Troubleshooting

### Common Issues

#### Issue: API Returns 500 Errors

**Symptoms**:
- All API requests return 500
- Logs show database connection errors

**Diagnosis**:
```bash
# Check API logs
docker logs local_assistant_api_blue --tail=100

# Check database
docker exec local_assistant_postgres pg_isready -U postgres

# Check connections
docker exec local_assistant_postgres psql -U postgres -c \
    "SELECT count(*) FROM pg_stat_activity;"
```

**Solution**:
```bash
# Restart API with fresh connections
docker-compose -f docker-compose.prod.yml restart api_blue

# If connection pool exhausted, increase pool size in .env
DATABASE_POOL_SIZE=20  # Increase from 5
```

#### Issue: Slow Vision Extraction

**Symptoms**:
- Document upload takes > 10 seconds
- Timeout errors

**Diagnosis**:
```bash
# Check OpenAI API status
curl https://status.openai.com/api/v2/status.json

# Check logs for specific error
docker logs local_assistant_api_blue | grep "vision_extraction"

# Check rate limits
grep "rate_limit" logs/api.log
```

**Solution**:
- Reduce `detail_level` to `auto` or `low`
- Implement retry with exponential backoff
- Cache results for duplicate documents

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-06 | Initial deployment guide |

---

**Congratulations!** You now have complete planning documentation for the Life Graph Integration project. All 10 planning documents are complete and ready for the development team to begin implementation.
