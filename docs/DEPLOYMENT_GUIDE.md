# Life Graph - Deployment Guide

**Version**: 1.0.0
**Last Updated**: November 2025
**Target Environment**: Production

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Variables](#environment-variables)
3. [Docker Compose Deployment](#docker-compose-deployment)
4. [Database Setup](#database-setup)
5. [Health Checks](#health-checks)
6. [Monitoring Setup](#monitoring-setup)
7. [Backup and Restore](#backup-and-restore)
8. [Troubleshooting](#troubleshooting)
9. [Performance Tuning](#performance-tuning)

---

## Prerequisites

### System Requirements

- **OS**: Ubuntu 22.04 LTS or later
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 20GB minimum, 100GB+ for production
- **CPU**: 2 cores minimum, 4+ cores recommended

### Software Requirements

- **Docker**: 20.10+ and Docker Compose v2
- **PostgreSQL**: 16+ (via Docker or standalone)
- **Python**: 3.11+ (if running outside Docker)
- **Node.js**: 18+ (for UI build)

---

## Environment Variables

### Required Variables

Create `.env` file in project root:

```env
# Database
DATABASE_URL=postgresql+asyncpg://assistant:assistant@postgres:5432/assistant

# API Keys (required)
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-proj-...
GOOGLE_API_KEY=AIza...

# Application Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
WORKERS=4

# Storage
DOCUMENT_STORAGE_PATH=/app/data/documents

# Monitoring
PROMETHEUS_ENABLED=true
GRAFANA_ADMIN_PASSWORD=secure_password_here
```

### Optional Variables

```env
# Performance
MAX_UPLOAD_SIZE_MB=50
EXTRACTION_TIMEOUT_SECONDS=30
POOL_SIZE=20
MAX_OVERFLOW=10

# Feature Flags
ENABLE_DEDUPLICATION=true
ENABLE_AUTO_COMMIT_CREATION=true
FUZZY_MATCH_THRESHOLD=0.85

# Observability
ENABLE_TRACING=false
JAEGER_ENDPOINT=http://jaeger:14268/api/traces
```

---

## Docker Compose Deployment

### Quick Start

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd local_assistant
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

3. **Start all services**
   ```bash
   docker-compose up -d
   ```

4. **Run migrations**
   ```bash
   docker-compose exec api alembic upgrade head
   ```

5. **Verify deployment**
   ```bash
   curl http://localhost:8000/health
   ```

### Production Deployment

```bash
# Build images
docker-compose build

# Start services in detached mode
docker-compose up -d

# View logs
docker-compose logs -f api

# Check service status
docker-compose ps
```

### Service Architecture

```yaml
services:
  postgres:     # Database (port 5432)
  api:          # FastAPI backend (port 8000)
  ui:           # React frontend (port 5173)
  prometheus:   # Metrics collection (port 9090)
  grafana:      # Dashboards (port 3000)
```

---

## Database Setup

### Initial Setup

```bash
# Create database (if not using Docker)
psql -U postgres
CREATE DATABASE assistant;
CREATE USER assistant WITH PASSWORD 'assistant';
GRANT ALL PRIVILEGES ON DATABASE assistant TO assistant;
\q

# Run migrations
alembic upgrade head

# Verify migrations
alembic current
```

### Migration Health Check

```bash
./scripts/check_migration_health.sh
```

Expected output:
```
✓ Database connection successful
✓ Alembic version table exists
✓ Current revision: 004_signals_links
✓ All migrations applied
✓ Extensions enabled: pgcrypto, pg_trgm, btree_gist
✓ All tables present (8 tables)
✓ Indexes created (30+ indexes)
```

---

## Health Checks

### API Health Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-11-09T10:30:00Z",
  "uptime_seconds": 3600,
  "services": {
    "database": {
      "available": true,
      "latency_ms": 12.45
    }
  }
}
```

### Docker Health Checks

Built into `docker-compose.yml`:
- **Postgres**: `pg_isready` every 10s
- **API**: HTTP check on `/health` every 30s
- **Grafana**: HTTP check every 30s

### Monitoring Health

```bash
# Check service health
docker-compose ps

# View health check logs
docker-compose logs api | grep health
```

---

## Monitoring Setup

### Prometheus

**Configuration**: `config/prometheus.yml`

```yaml
scrape_configs:
  - job_name: 'lifegraph-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

**Access**: `http://localhost:9090`

**Key Metrics**:
- `lifegraph_documents_processed_total`
- `lifegraph_extraction_duration_seconds`
- `lifegraph_vendor_deduplication_rate`
- `lifegraph_active_commitments_count`

### Grafana

**Access**: `http://localhost:3000`
**Credentials**: admin / (from `GRAFANA_ADMIN_PASSWORD`)

**Pre-configured Dashboard**:
- **Life Graph Dashboard**: Imported from `config/grafana/dashboards/lifegraph_dashboard.json`

**Key Panels**:
1. Documents Processed (Total)
2. Active Commitments
3. Vendor Deduplication Rate
4. Extraction Cost (Today)
5. Document Processing Throughput
6. Extraction Latency (P95)
7. Commitment Priority Distribution
8. Pipeline Errors

---

## Backup and Restore

### Database Backup

**Manual Backup**:
```bash
./scripts/backup_database.sh
```

Creates timestamped backup:
```
backups/backup_20251109_103045.dump
```

**Automated Backup (Cron)**:
```bash
# Add to crontab
0 2 * * * /path/to/local_assistant/scripts/backup_database.sh
```

### Restore Database

```bash
./scripts/restore_database.sh backups/backup_20251109_103045.dump
```

### Document Storage Backup

```bash
# Backup documents directory
tar -czf documents_backup_$(date +%Y%m%d).tar.gz data/documents/

# Restore documents
tar -xzf documents_backup_20251109.tar.gz -C data/
```

---

## Troubleshooting

### Problem: API not starting

**Check logs**:
```bash
docker-compose logs api
```

**Common causes**:
- Database not ready (wait 10 seconds, retry)
- Missing environment variables
- Port 8000 already in use

**Solutions**:
```bash
# Restart API service
docker-compose restart api

# Check database connection
docker-compose exec api python -c "from memory.database import test_connection; test_connection()"
```

### Problem: Migrations failing

**Check current revision**:
```bash
docker-compose exec api alembic current
```

**Rollback and retry**:
```bash
docker-compose exec api alembic downgrade -1
docker-compose exec api alembic upgrade head
```

### Problem: High memory usage

**Check resource usage**:
```bash
docker stats
```

**Solutions**:
- Increase Docker memory limit
- Reduce `POOL_SIZE` in `.env`
- Reduce `WORKERS` count

### Problem: Slow extraction

**Check Prometheus metrics**:
```bash
curl http://localhost:8000/metrics | grep extraction_duration
```

**Solutions**:
- Check Vision API rate limits
- Increase `EXTRACTION_TIMEOUT_SECONDS`
- Use faster model (gpt-4o-mini)

---

## Performance Tuning

### Database Optimization

**Connection Pooling**:
```env
POOL_SIZE=20
MAX_OVERFLOW=10
POOL_TIMEOUT=30
```

**Index Monitoring**:
```sql
-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;

-- Unused indexes (candidates for removal)
SELECT schemaname, tablename, indexname
FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND indexrelname NOT LIKE 'pg_%';
```

### API Performance

**Workers**:
```bash
# Development: 1 worker
uvicorn api.main:app --workers 1

# Production: CPU count * 2 + 1
uvicorn api.main:app --workers 9  # For 4 CPU cores
```

**Caching (Future)**:
```env
REDIS_ENABLED=true
REDIS_URL=redis://redis:6379/0
CACHE_TTL_SECONDS=3600
```

### Query Optimization

**Slow Query Log**:
```sql
-- Enable slow query log
ALTER SYSTEM SET log_min_duration_statement = 1000; -- 1 second
SELECT pg_reload_conf();

-- View slow queries
SELECT query, calls, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

---

## Security Checklist

- [ ] API keys stored in environment variables (not in code)
- [ ] Database credentials rotated regularly
- [ ] HTTPS enabled (reverse proxy)
- [ ] CORS configured for production domains only
- [ ] Rate limiting enabled
- [ ] Database backups automated
- [ ] Grafana admin password changed
- [ ] PostgreSQL not exposed to public internet
- [ ] Docker images scanned for vulnerabilities
- [ ] Logs sanitized (no sensitive data)

---

## Production Checklist

- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Health checks passing
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards loaded
- [ ] Backups automated
- [ ] Monitoring alerts configured
- [ ] Log aggregation setup
- [ ] SSL certificates installed
- [ ] Domain DNS configured
- [ ] Firewall rules applied
- [ ] Load testing completed
- [ ] Disaster recovery plan documented

---

## Support

For deployment issues:
- **GitHub Issues**: [Repository Issues](https://github.com/...)
- **Email**: devops@example.com
- **Slack**: #lifegraph-deployments

---

**Happy Deploying!** 🚀
