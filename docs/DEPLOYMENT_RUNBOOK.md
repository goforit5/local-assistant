# Production Deployment Runbook

**Version:** 1.0
**Last Updated:** 2025-11-26
**Maintainer:** DevOps Team

---

## Table of Contents

1. [Overview](#overview)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Deployment Steps](#deployment-steps)
4. [Health Check Verification](#health-check-verification)
5. [Rollback Procedures](#rollback-procedures)
6. [Troubleshooting Guide](#troubleshooting-guide)
7. [Monitoring and Alerting](#monitoring-and-alerting)
8. [Post-Deployment Tasks](#post-deployment-tasks)

---

## Overview

### System Architecture

The Local Assistant application consists of 6 primary Docker services:

| Service | Container Name | Port | Purpose |
|---------|---------------|------|---------|
| PostgreSQL | assistant-postgres | 5433:5432 | Primary database |
| Redis | assistant-redis | 6380:6379 | Caching & sessions |
| ChromaDB | assistant-chroma | 8002:8000 | Vector embeddings |
| Prometheus | assistant-prometheus | 9091:9090 | Metrics collection |
| Grafana | assistant-grafana | 3001:3000 | Observability dashboards |
| Jaeger | assistant-jaeger | 16686 | Distributed tracing (optional) |

### Prerequisites

- Docker 24.0+ and Docker Compose 2.20+
- Minimum 4GB RAM, 10GB disk space
- Network access to AI provider APIs
- Valid SSL certificates (production)

---

## Pre-Deployment Checklist

### 1. Environment Configuration

**Verify all required environment variables are set:**

```bash
# Required API Keys
✓ ANTHROPIC_API_KEY
✓ OPENAI_API_KEY
✓ GOOGLE_API_KEY

# Database Configuration
✓ DATABASE_URL=postgresql://assistant:assistant@postgres:5432/assistant
✓ REDIS_URL=redis://redis:6379/0
✓ CHROMA_HOST=chroma
✓ CHROMA_PORT=8000

# Observability
✓ PROMETHEUS_PORT=9090
✓ GRAFANA_PORT=3000
✓ OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
✓ OTEL_SERVICE_NAME=local-assistant

# Security & Limits
✓ COST_LIMIT_PER_REQUEST=1.00
✓ COST_LIMIT_PER_HOUR=10.00
✓ COST_LIMIT_PER_DAY=50.00
✓ COMPUTER_USE_SANDBOX=true
✓ REQUIRE_CONFIRMATION_FOR_SENSITIVE=true

# Application Settings
✓ ENVIRONMENT=production
✓ LOG_LEVEL=INFO
✓ SESSION_TIMEOUT=3600
```

**Validate configuration:**

```bash
# Copy example and edit
cp .env.example .env
vim .env

# Validate configuration
python3 scripts/validate_config.py

# Expected output:
# ✓ All required environment variables present
# ✓ API keys format valid
# ✓ Database URL parseable
# ✓ Port configurations valid
```

### 2. Secrets Management

**Ensure secrets are properly secured:**

```bash
# DO NOT commit .env to version control
grep -q "^\.env$" .gitignore || echo ".env" >> .gitignore

# Set proper permissions
chmod 600 .env

# For production, use secrets manager (AWS Secrets Manager, Vault, etc.)
# Example with AWS Secrets Manager:
aws secretsmanager get-secret-value \
  --secret-id local-assistant/prod/api-keys \
  --query SecretString --output text > .env
```

### 3. Database Preparation

**Create backup before deployment:**

```bash
# Backup existing database
./scripts/backup_database.sh

# Expected output:
# [2025-11-26 10:00:00] Creating backup directory: ./data/backups
# [2025-11-26 10:00:01] Backing up database to: assistant_20251126_100001.sql.gz
# [2025-11-26 10:00:05] Backup completed: 2.3 MB
# [2025-11-26 10:00:05] Cleaning up old backups (retention: 30 days)
```

**Verify migration scripts:**

```bash
# Check pending migrations
alembic current
alembic history

# Expected output:
# Current revision: abc123def456
# Pending migrations: 2
```

### 4. Infrastructure Readiness

**Verify Docker resources:**

```bash
# Check Docker daemon
docker info | grep -E "Server Version|CPUs|Total Memory"

# Expected output:
# Server Version: 24.0.7
# CPUs: 4
# Total Memory: 8 GiB

# Check disk space
df -h ./data

# Expected output:
# Filesystem      Size  Used Avail Use% Mounted on
# /dev/sda1       50G   15G   35G  30% /
```

**Create required directories:**

```bash
# Create data directories with proper permissions
mkdir -p data/{postgres,redis,chroma,prometheus,grafana,logs,backups,screenshots,documents}
chmod 755 data
chmod 700 data/postgres data/redis data/chroma
```

### 5. Configuration Files

**Verify monitoring configurations:**

```bash
# Check Prometheus configuration
cat config/prometheus.yml

# Check Grafana provisioning
ls -la config/grafana/provisioning/
ls -la config/grafana/dashboards/

# Expected files:
# config/prometheus.yml
# config/grafana/provisioning/datasources/
# config/grafana/dashboards/
```

---

## Deployment Steps

### Step 1: Stop Existing Services (if applicable)

```bash
# Gracefully stop running services
docker-compose down

# Expected output:
# Stopping assistant-grafana     ... done
# Stopping assistant-prometheus  ... done
# Stopping assistant-chroma      ... done
# Stopping assistant-redis       ... done
# Stopping assistant-postgres    ... done
# Removing assistant-grafana     ... done
# Removing network local_assistant_assistant-network
```

**For zero-downtime deployment, see [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)**

### Step 2: Pull Latest Images

```bash
# Pull all required Docker images
docker-compose pull

# Expected output:
# Pulling postgres     ... done
# Pulling redis        ... done
# Pulling chroma       ... done
# Pulling prometheus   ... done
# Pulling grafana      ... done
# Pulling jaeger       ... done
```

### Step 3: Build Custom Images (if applicable)

```bash
# If you have custom Dockerfiles
docker-compose build --no-cache

# Verify images
docker images | grep assistant

# Expected output:
# local-assistant-api    latest   abc123def456   2 minutes ago   500MB
```

### Step 4: Start Infrastructure Services

**Start services in dependency order:**

```bash
# Step 4a: Start database and cache
docker-compose up -d postgres redis

# Wait for health checks
sleep 15

# Verify services are healthy
docker-compose ps

# Expected output:
# NAME                   STATUS                   PORTS
# assistant-postgres     Up (healthy)            5433:5432
# assistant-redis        Up (healthy)            6380:6379
```

### Step 5: Run Database Migrations

```bash
# Run Alembic migrations
alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO  [alembic.runtime.migration] Will assume transactional DDL.
# INFO  [alembic.runtime.migration] Running upgrade abc123 -> def456, add_user_sessions
# INFO  [alembic.runtime.migration] Running upgrade def456 -> ghi789, add_vector_indexes

# Verify current revision
alembic current

# Expected output:
# ghi789 (head)
```

**If migrations fail, see [Rollback Procedures](#rollback-procedures)**

### Step 6: Start Application Services

```bash
# Start vector database
docker-compose up -d chroma

# Wait for health check
sleep 10

# Start observability stack
docker-compose up -d prometheus grafana

# Optional: Start tracing (if needed)
docker-compose --profile tracing up -d jaeger

# Verify all services
docker-compose ps

# Expected output:
# NAME                   STATUS                   PORTS
# assistant-postgres     Up (healthy)            5433:5432
# assistant-redis        Up (healthy)            6380:6379
# assistant-chroma       Up (healthy)            8002:8000
# assistant-prometheus   Up                      9091:9090
# assistant-grafana      Up                      3001:3000
```

### Step 7: Start Application

```bash
# Start the main application
./start.sh

# Or manually:
python3 start.py

# Expected output:
# [2025-11-26 10:05:00] INFO: Starting Local Assistant
# [2025-11-26 10:05:01] INFO: Initializing providers...
# [2025-11-26 10:05:02] INFO: Connecting to PostgreSQL at localhost:5433
# [2025-11-26 10:05:03] INFO: Connecting to Redis at localhost:6380
# [2025-11-26 10:05:04] INFO: Connecting to ChromaDB at localhost:8002
# [2025-11-26 10:05:05] INFO: Application started successfully
```

---

## Health Check Verification

### Automated Health Check

```bash
# Run comprehensive health check script
./scripts/health_check.sh

# Expected output:
# ================================
# Local Assistant Health Check
# ================================
# [2025-11-26 10:06:00] Checking Docker services...
# ✓ PostgreSQL is healthy (response time: 12ms)
# ✓ Redis is healthy (response time: 8ms)
# ✓ ChromaDB is healthy (response time: 45ms)
# ✓ Prometheus is healthy (response time: 23ms)
# ✓ Grafana is healthy (response time: 156ms)
#
# [2025-11-26 10:06:05] Checking database connectivity...
# ✓ Database connection successful
# ✓ Can execute queries (3 tables found)
#
# [2025-11-26 10:06:06] Checking API endpoints...
# ✓ Health endpoint: HTTP 200
# ✓ API version: v1.0
#
# [2025-11-26 10:06:07] All checks passed!
# Exit code: 0
```

### Manual Health Checks

**PostgreSQL:**

```bash
# Check connection
docker exec assistant-postgres pg_isready -U assistant

# Expected: assistant-postgres:5432 - accepting connections

# Query database
docker exec assistant-postgres psql -U assistant -c "SELECT version();"

# Expected: PostgreSQL 16.x on x86_64-pc-linux-musl
```

**Redis:**

```bash
# Check connection
docker exec assistant-redis redis-cli ping

# Expected: PONG

# Check memory usage
docker exec assistant-redis redis-cli INFO memory | grep used_memory_human

# Expected: used_memory_human:2.34M
```

**ChromaDB:**

```bash
# Check heartbeat
curl -f http://localhost:8002/api/v1/heartbeat

# Expected: {"nanosecond heartbeat":1732635600000000000}

# List collections
curl http://localhost:8002/api/v1/collections

# Expected: []
```

**Prometheus:**

```bash
# Check metrics endpoint
curl http://localhost:9091/api/v1/query?query=up

# Expected: {"status":"success","data":{"resultType":"vector","result":[...]}}

# Check targets
curl http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Expected:
# {"job":"prometheus","health":"up"}
# {"job":"local-assistant","health":"up"}
```

**Grafana:**

```bash
# Check health
curl http://localhost:3001/api/health

# Expected: {"database":"ok","version":"10.x.x"}

# List datasources
curl -u admin:admin http://localhost:3001/api/datasources | jq '.[].name'

# Expected: "Prometheus"
```

---

## Rollback Procedures

### Scenario 1: Migration Failure

**If database migration fails during deployment:**

```bash
# Step 1: Check current migration status
alembic current

# Output: def456 (failed at ghi789)

# Step 2: Rollback to previous revision
alembic downgrade -1

# Expected output:
# INFO  [alembic.runtime.migration] Running downgrade ghi789 -> def456

# Step 3: Verify rollback
alembic current

# Expected: def456

# Step 4: Restore from backup if needed
./scripts/restore_database.sh data/backups/assistant_20251126_100001.sql.gz
```

### Scenario 2: Service Failures

**If services fail health checks:**

```bash
# Step 1: Stop all services
docker-compose down

# Step 2: Restore previous configuration
git checkout HEAD~1 docker-compose.yml
git checkout HEAD~1 .env

# Step 3: Restart with previous version
docker-compose up -d

# Step 4: Verify services
./scripts/health_check.sh
```

### Scenario 3: Data Corruption

**If data integrity issues detected:**

```bash
# Step 1: Stop application immediately
./stop.sh
docker-compose down

# Step 2: Restore database from backup
./scripts/restore_database.sh data/backups/assistant_20251126_100001.sql.gz

# Expected output:
# [2025-11-26 10:15:00] Stopping existing containers...
# [2025-11-26 10:15:05] Restoring from backup: assistant_20251126_100001.sql.gz
# [2025-11-26 10:15:20] Database restored successfully
# [2025-11-26 10:15:21] Restarting services...

# Step 3: Verify data integrity
psql postgresql://assistant:assistant@localhost:5433/assistant -c "SELECT COUNT(*) FROM alembic_version;"

# Step 4: Restart services
docker-compose up -d
./start.sh
```

### Scenario 4: Complete Environment Rollback

**Full rollback to previous known-good state:**

```bash
# Step 1: Document current state
docker-compose ps > rollback_state.txt
alembic current >> rollback_state.txt

# Step 2: Stop everything
./stop.sh
docker-compose down -v  # WARNING: Removes volumes!

# Step 3: Restore from backup
./scripts/restore_database.sh data/backups/assistant_20251126_100001.sql.gz

# Step 4: Checkout previous version
git log --oneline -n 5
git checkout <previous-commit>

# Step 5: Redeploy
docker-compose up -d
alembic current
./start.sh

# Step 6: Verify
./scripts/health_check.sh
```

---

## Troubleshooting Guide

### Common Issues

#### Issue 1: PostgreSQL Connection Refused

**Symptoms:**

```
psycopg2.OperationalError: could not connect to server: Connection refused
```

**Diagnosis:**

```bash
# Check if container is running
docker ps | grep postgres

# Check logs
docker logs assistant-postgres --tail 50

# Check port binding
netstat -an | grep 5433
```

**Solutions:**

1. **Port conflict:**
   ```bash
   # Check what's using port 5433
   lsof -i :5433

   # Change port in docker-compose.yml
   sed -i 's/5433:5432/5434:5432/' docker-compose.yml
   docker-compose up -d postgres
   ```

2. **Container not healthy:**
   ```bash
   # Restart container
   docker-compose restart postgres

   # Check health
   docker exec assistant-postgres pg_isready -U assistant
   ```

3. **Data directory permissions:**
   ```bash
   # Fix permissions
   sudo chown -R 999:999 data/postgres
   docker-compose restart postgres
   ```

#### Issue 2: Redis Memory Issues

**Symptoms:**

```
redis.exceptions.ConnectionError: Error while reading from socket: ('Connection closed by server.',)
```

**Diagnosis:**

```bash
# Check Redis memory usage
docker exec assistant-redis redis-cli INFO memory

# Check container resources
docker stats assistant-redis --no-stream
```

**Solutions:**

1. **Increase memory limit:**
   ```bash
   # Edit docker-compose.yml
   vim docker-compose.yml

   # Add to redis service:
   deploy:
     resources:
       limits:
         memory: 512M

   docker-compose up -d redis
   ```

2. **Clear cache:**
   ```bash
   docker exec assistant-redis redis-cli FLUSHDB
   ```

#### Issue 3: ChromaDB Embedding Failures

**Symptoms:**

```
requests.exceptions.HTTPError: 500 Server Error: Internal Server Error
```

**Diagnosis:**

```bash
# Check ChromaDB logs
docker logs assistant-chroma --tail 100

# Test connection
curl http://localhost:8002/api/v1/heartbeat

# Check disk space
df -h ./data/chroma
```

**Solutions:**

1. **Restart ChromaDB:**
   ```bash
   docker-compose restart chroma
   sleep 10
   curl http://localhost:8002/api/v1/heartbeat
   ```

2. **Clear corrupt collections:**
   ```bash
   # Backup first
   cp -r data/chroma data/chroma.backup.$(date +%Y%m%d_%H%M%S)

   # Reset ChromaDB
   docker-compose down
   rm -rf data/chroma/*
   docker-compose up -d chroma
   ```

#### Issue 4: Migration Conflicts

**Symptoms:**

```
alembic.util.exc.CommandError: Target database is not up to date.
```

**Diagnosis:**

```bash
# Check current revision
alembic current

# Check expected revision
alembic heads

# Check migration history
alembic history
```

**Solutions:**

1. **Stamp database:**
   ```bash
   # If database is ahead
   alembic stamp head

   # If database is behind
   alembic upgrade head
   ```

2. **Resolve conflicts:**
   ```bash
   # Check for branch conflicts
   alembic branches

   # Merge branches
   alembic merge -m "merge branches" <rev1> <rev2>
   alembic upgrade head
   ```

#### Issue 5: Prometheus Scraping Failures

**Symptoms:**

```
No data found in Grafana dashboards
```

**Diagnosis:**

```bash
# Check Prometheus targets
curl http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Check Prometheus logs
docker logs assistant-prometheus --tail 50
```

**Solutions:**

1. **Fix configuration:**
   ```bash
   # Validate prometheus.yml
   docker exec assistant-prometheus promtool check config /etc/prometheus/prometheus.yml

   # Reload config
   curl -X POST http://localhost:9091/-/reload
   ```

2. **Check network connectivity:**
   ```bash
   # Test from Prometheus container
   docker exec assistant-prometheus wget -O- http://host.docker.internal:8080/metrics
   ```

#### Issue 6: Disk Space Exhaustion

**Symptoms:**

```
OSError: [Errno 28] No space left on device
```

**Diagnosis:**

```bash
# Check disk usage
df -h
du -sh data/*

# Check Docker disk usage
docker system df
```

**Solutions:**

1. **Clean up logs:**
   ```bash
   # Rotate logs
   find data/logs -name "*.log" -mtime +7 -delete

   # Truncate large logs
   truncate -s 0 data/logs/assistant.log
   ```

2. **Clean Docker resources:**
   ```bash
   # Remove unused images
   docker image prune -a

   # Remove unused volumes
   docker volume prune

   # Clean build cache
   docker builder prune
   ```

3. **Clean old backups:**
   ```bash
   # Remove backups older than 30 days
   find data/backups -name "*.sql.gz" -mtime +30 -delete
   ```

---

## Monitoring and Alerting

### Prometheus Metrics

**Key metrics to monitor:**

```promql
# Service availability
up{job="local-assistant"}

# Request rate
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Request latency (p95)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Database connections
postgres_active_connections

# Redis memory usage
redis_memory_used_bytes

# ChromaDB collection size
chroma_collection_documents_total
```

### Grafana Dashboards

**Access Grafana:**

```bash
# Open in browser
open http://localhost:3001

# Default credentials
# Username: admin
# Password: admin
```

**Key dashboards:**

1. **System Overview**: CPU, memory, disk usage
2. **API Performance**: Request rates, latency, errors
3. **Database Health**: Connection pool, query performance
4. **Cache Efficiency**: Redis hit/miss ratio
5. **Cost Tracking**: API usage and costs per provider

### Alert Configuration

**Configure alerts in `config/prometheus.yml`:**

```yaml
rule_files:
  - 'alerts.yml'

# Example alerts.yml
groups:
  - name: local_assistant_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/sec"

      - alert: DatabaseConnectionsHigh
        expr: postgres_active_connections > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Database connection pool nearly exhausted"

      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes > 400000000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Redis memory usage above 400MB"

      - alert: ServiceDown
        expr: up{job="local-assistant"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Local Assistant service is down"
```

### Log Aggregation

**Centralize logs for analysis:**

```bash
# View all container logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f chroma

# Export logs for analysis
docker-compose logs --no-color > deployment_logs_$(date +%Y%m%d_%H%M%S).log

# Application logs location
tail -f data/logs/assistant.log
```

---

## Post-Deployment Tasks

### 1. Verify Production Readiness

```bash
# Run health check
./scripts/health_check.sh

# Check migration health
./scripts/check_migration_health.sh

# Validate configuration
python3 scripts/validate_config.py
```

### 2. Performance Baseline

```bash
# Capture initial metrics
curl http://localhost:9091/api/v1/query?query=up > metrics_baseline.json

# Document response times
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8080/health

# Create curl-format.txt:
cat > curl-format.txt << 'EOF'
time_namelookup:  %{time_namelookup}\n
time_connect:     %{time_connect}\n
time_appconnect:  %{time_appconnect}\n
time_pretransfer: %{time_pretransfer}\n
time_redirect:    %{time_redirect}\n
time_starttransfer: %{time_starttransfer}\n
time_total:       %{time_total}\n
EOF
```

### 3. Documentation

```bash
# Document deployment
cat > deployment_report_$(date +%Y%m%d).md << EOF
# Deployment Report - $(date +%Y-%m-%d)

## Services Deployed
- PostgreSQL: $(docker exec assistant-postgres psql -U assistant -c "SELECT version();" | grep PostgreSQL)
- Redis: $(docker exec assistant-redis redis-cli INFO server | grep redis_version)
- ChromaDB: Running on port 8002

## Migration Status
$(alembic current)

## Health Check Results
$(./scripts/health_check.sh)

## Issues Encountered
- None

## Rollback Plan
- Backup location: data/backups/assistant_$(date +%Y%m%d)*.sql.gz
- Restore command: ./scripts/restore_database.sh <backup_file>
EOF
```

### 4. Security Audit

```bash
# Check file permissions
ls -la .env
# Expected: -rw------- (600)

# Verify no secrets in logs
grep -i "api.key\|password\|secret" data/logs/assistant.log

# Check exposed ports
netstat -tuln | grep -E "5433|6380|8002|9091|3001"

# Verify firewall rules (production)
# Only allow necessary ports externally
```

### 5. Backup Verification

```bash
# Test restore procedure
./scripts/restore_database.sh data/backups/assistant_$(date +%Y%m%d)*.sql.gz

# Verify restored data
docker exec assistant-postgres psql -U assistant -c "SELECT COUNT(*) FROM alembic_version;"
```

---

## Appendix

### A. Service Dependency Graph

```
┌─────────────────┐
│   Application   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼───┐
│ Redis │ │ Chroma│
└───────┘ └──────┘
    │
┌───▼────────┐
│ PostgreSQL │
└────────────┘
```

### B. Port Reference

| Service | Internal Port | External Port | Protocol |
|---------|--------------|---------------|----------|
| PostgreSQL | 5432 | 5433 | TCP |
| Redis | 6379 | 6380 | TCP |
| ChromaDB | 8000 | 8002 | HTTP |
| Prometheus | 9090 | 9091 | HTTP |
| Grafana | 3000 | 3001 | HTTP |
| Jaeger UI | 16686 | 16686 | HTTP |
| Jaeger Collector | 14268 | 14268 | HTTP |

### C. Contact Information

| Role | Contact | Availability |
|------|---------|-------------|
| DevOps Team | devops@example.com | 24/7 |
| Database Admin | dba@example.com | Business hours |
| Security Team | security@example.com | 24/7 |

### D. Related Documentation

- [Migration Guide](./MIGRATION_GUIDE.md) - Zero-downtime deployment strategies
- [Developer Guide](./DEVELOPER_GUIDE.md) - Development environment setup
- [User Guide](./USER_GUIDE.md) - End-user documentation
- [API Documentation](./api/README.md) - API reference

---

**End of Runbook**
