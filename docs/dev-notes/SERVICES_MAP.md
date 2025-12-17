# Services Map - Complete Reference

## 🗺️ All Services Running in Development Environment

---

## 📊 Service Overview

### Total Services: 5 Docker + 4 Terminal Windows + 3 Browser Tabs = **12 Active Components**

---

## 🐳 Docker Infrastructure Services

### 1. PostgreSQL - Main Database
**Container**: `assistant-postgres`
**Image**: `postgres:16-alpine`
**Ports**: `5433:5432` (external:internal)
**Status**: Health-checked every 10s

**Access**:
```bash
# From host
psql -h localhost -p 5433 -U assistant -d assistant

# From Python
DATABASE_URL=postgresql://assistant:assistant@localhost:5433/assistant
```

**Purpose**: Stores all structured data
- Conversations and chat history
- Message content with tokens/costs
- Document metadata and cache
- Cost tracking entries

**Data Location**: `/Users/andrew/Projects/AGENTS/local_assistant/data/postgres/`
**Volume Mount**: `./data/postgres:/var/lib/postgresql/data`

**Health Check**: `pg_isready -U assistant`

---

### 2. Redis - Cache Layer
**Container**: `assistant-redis`
**Image**: `redis:7-alpine`
**Ports**: `6380:6379` (external:internal)
**Status**: Health-checked every 10s

**Access**:
```bash
# From host
redis-cli -p 6380

# From Python
REDIS_URL=redis://localhost:6380/0
```

**Purpose**: High-speed caching and sessions
- L1 cache for documents (hot data)
- Session storage for conversations
- Rate limit tracking
- Temporary result storage

**Data Location**: `/Users/andrew/Projects/AGENTS/local_assistant/data/redis/`
**Volume Mount**: `./data/redis:/data`
**Persistence**: AOF (Append-Only File)

**Health Check**: `redis-cli ping`

---

### 3. ChromaDB - Vector Database
**Container**: `assistant-chroma`
**Image**: `chromadb/chroma:latest`
**Ports**: `8002:8000` (external:internal)
**Status**: Health-checked every 30s
**UI**: http://localhost:8002

**Access**:
```bash
# From browser
open http://localhost:8002

# From Python
CHROMA_HOST=localhost
CHROMA_PORT=8002
```

**Purpose**: Vector embeddings and similarity search
- Document embeddings for semantic search
- Conversation context retrieval
- Similar document finding
- RAG (Retrieval Augmented Generation) support

**Data Location**: `/Users/andrew/Projects/AGENTS/local_assistant/data/chroma/`
**Volume Mount**: `./data/chroma:/chroma/chroma`

**API Endpoints**:
- Health: `GET http://localhost:8002/api/v1/heartbeat`
- Collections: `GET http://localhost:8002/api/v1/collections`

**Health Check**: `curl -f http://localhost:8000/api/v1/heartbeat`

---

### 4. Prometheus - Metrics Collection
**Container**: `assistant-prometheus`
**Image**: `prom/prometheus:latest`
**Ports**: `9091:9090` (external:internal)
**UI**: http://localhost:9091

**Access**:
```bash
# From browser
open http://localhost:9091

# Query API
curl http://localhost:9091/api/v1/query?query=up
```

**Purpose**: Time-series metrics database
- Request counts by provider/model
- Latency distributions (histograms)
- Token usage tracking
- Cost metrics by window
- Error rates by type

**Data Location**: `/Users/andrew/Projects/AGENTS/local_assistant/data/prometheus/`
**Volume Mount**: `./data/prometheus:/prometheus`

**Config**: `/Users/andrew/Projects/AGENTS/local_assistant/config/prometheus.yml`

**Key Endpoints**:
- UI: http://localhost:9091
- Metrics: http://localhost:9091/metrics
- Targets: http://localhost:9091/targets
- Query: http://localhost:9091/api/v1/query

**Scrape Targets**:
- App metrics: `localhost:8000/metrics` (when app exports)

---

### 5. Grafana - Visualization Dashboards
**Container**: `assistant-grafana`
**Image**: `grafana/grafana:latest`
**Ports**: `3001:3000` (external:internal)
**UI**: http://localhost:3001
**Credentials**: `admin/admin`

**Access**:
```bash
# From browser
open http://localhost:3001

# Login with:
Username: admin
Password: admin
```

**Purpose**: Metrics visualization and dashboards
- Real-time cost tracking dashboards
- Request performance graphs
- Service health monitoring
- Custom alert rules

**Data Location**: `/Users/andrew/Projects/AGENTS/local_assistant/data/grafana/`
**Config Location**: `/Users/andrew/Projects/AGENTS/local_assistant/config/grafana/`

**Provisioning**:
- Datasources: `./config/grafana/provisioning/datasources/`
- Dashboards: `./config/grafana/provisioning/dashboards/`
- Pre-built: `./config/grafana/dashboards/`

**Pre-configured Datasources**:
- Prometheus: http://prometheus:9090 (internal Docker network)

**Key URLs**:
- Home: http://localhost:3001
- Datasources: http://localhost:3001/datasources
- Dashboards: http://localhost:3001/dashboards
- Explore: http://localhost:3001/explore

---

## 💻 Terminal Windows

### Window 1: 🐳 Docker Logs
**Title**: "🐳 Docker Logs"
**Position**: Top-left (50, 50, 650, 450)
**Auto-refresh**: Continuous (live tail)

**Command**:
```bash
docker-compose logs -f
```

**Purpose**:
- Real-time container logs
- Debug Docker issues
- Monitor service startup
- Track errors

**What to watch**:
- Container startup messages
- Error logs (red text)
- API requests (if verbose)
- Health check results

**When to use**: When something's not working, check this window first.

---

### Window 2: 💻 CLI Ready
**Title**: "💻 CLI Ready"
**Position**: Top-right (650, 100, 1250, 500)
**Auto-refresh**: Manual (your main terminal)

**Command**:
```bash
source .venv/bin/activate && bash -l
```

**Purpose**:
- Your main work terminal
- Run all CLI commands here
- Environment pre-activated
- Ready to use immediately

**Common commands**:
```bash
# Chat
python3 -m cli.main chat "Hello"

# Vision
python3 -m cli.main vision extract file.pdf

# Costs
python3 -m cli.main costs

# Status
python3 -m cli.main status

# Help
python3 -m cli.main --help
```

**When to use**: For all your CLI commands and testing.

---

### Window 3: 💰 Cost Monitor
**Title**: "💰 Cost Monitor"
**Position**: Bottom-left (1300, 150, 1900, 550)
**Auto-refresh**: Every 10 seconds

**Command**:
```bash
source .venv/bin/activate && \
while true; do \
  clear; date; echo ''; \
  python3 -m cli.main costs --breakdown 2>/dev/null || echo 'No costs yet'; \
  sleep 10; \
done
```

**Purpose**:
- Real-time cost tracking
- Automatic refresh every 10s
- Breakdown by provider
- Monitor spend limits

**What you'll see**:
```
Current Request:  $0.0000  / $1.00
Current Hour:     $0.0125  / $10.00
Today:            $0.0325  / $50.00

Provider Breakdown:
anthropic: $0.0200
openai:    $0.0125
google:    $0.0000
```

**When to use**: Keep this visible to monitor costs in real-time.

---

### Window 4: 📊 System Monitor
**Title**: "📊 System Monitor"
**Position**: Bottom-right (1950, 200, 2550, 600)
**Auto-refresh**: Every 15 seconds

**Command**:
```bash
source .venv/bin/activate && \
while true; do \
  clear; date; echo ''; \
  python3 -m cli.main status 2>/dev/null || docker-compose ps; \
  sleep 15; \
done
```

**Purpose**:
- Docker service health
- API key validation
- Service URL reference
- System status overview

**What you'll see**:
```
✓ ANTHROPIC_API_KEY: sk-ant-xxx...
✓ OPENAI_API_KEY: sk-xxx...
✓ GOOGLE_API_KEY: AI...

Service URLs:
📊 Grafana: http://localhost:3001
📈 Prometheus: http://localhost:9091
💾 ChromaDB: http://localhost:8002
```

**When to use**: Quick health check, verify services are up.

---

## 🌐 Browser Tabs

### Tab 1: Grafana Dashboard
**URL**: http://localhost:3001
**Credentials**: admin/admin (first login prompts to change)
**Purpose**: Primary monitoring dashboard

**Features**:
- Pre-configured Prometheus datasource
- Real-time metrics visualization
- Custom dashboard creation
- Alert configuration
- Time-series graphs

**Default Dashboards** (to be created):
- Agent Performance (request rate, latency, errors)
- Cost Tracking (hourly/daily spend, breakdown)
- Computer Use (action success rate, safety triggers)
- System Health (Docker services, resources)

**Key Navigation**:
- Home: Browse dashboards
- Explore: Query Prometheus directly
- Alerting: Configure alerts
- Configuration: Datasources, plugins

**First-time Setup**:
1. Login with admin/admin
2. (Optional) Change password
3. Add datasource (already configured)
4. Import/create dashboards

---

### Tab 2: Prometheus UI
**URL**: http://localhost:9091
**Credentials**: None required
**Purpose**: Raw metrics and queries

**Features**:
- PromQL query interface
- Target status monitoring
- Alert rule viewing
- Service discovery
- Time-series exploration

**Key Pages**:
- **Graph** (http://localhost:9091/graph):
  - Execute PromQL queries
  - Visualize time-series
  - Example: `rate(requests_total[5m])`

- **Targets** (http://localhost:9091/targets):
  - Scrape target health
  - Last scrape time
  - Target discovery

- **Alerts** (http://localhost:9091/alerts):
  - Active alerts
  - Alert rules
  - Firing alerts

- **Config** (http://localhost:9091/config):
  - View current config
  - Scrape intervals
  - Target jobs

**Example Queries**:
```promql
# Total requests
requests_total

# Request rate (5m)
rate(requests_total[5m])

# Latency p95
histogram_quantile(0.95, latency_seconds)

# Cost by provider
sum(cost_dollars) by (provider)
```

---

### Tab 3: ChromaDB API
**URL**: http://localhost:8002
**Credentials**: None required
**Purpose**: Vector database health and API

**Features**:
- Heartbeat health check
- API documentation
- Collection listing
- Direct API access

**Key Endpoints**:
- **Heartbeat**: `GET /api/v1/heartbeat`
  ```bash
  curl http://localhost:8002/api/v1/heartbeat
  # Returns: {"nanosecond heartbeat": 123456789}
  ```

- **Version**: `GET /api/v1/version`
  ```bash
  curl http://localhost:8002/api/v1/version
  # Returns: {"version": "0.4.x"}
  ```

- **Collections**: `GET /api/v1/collections`
  ```bash
  curl http://localhost:8002/api/v1/collections
  # Returns: [{"name": "documents", "metadata": {...}}]
  ```

- **Count**: `POST /api/v1/collections/{collection}/count`
  ```bash
  curl -X POST http://localhost:8002/api/v1/collections/documents/count
  # Returns: {"count": 42}
  ```

**When to use**:
- Verify ChromaDB is running
- Check collection health
- Inspect stored embeddings
- API testing

---

## 🔗 Service Dependencies

```
┌─────────────────────────────────────────────┐
│          CLI Application Layer              │
│  (Window 2 - Your commands)                 │
└─────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌──────────────┐        ┌──────────────┐
│   Services   │        │  Providers   │
│   Layer      │        │  (AI APIs)   │
└──────────────┘        └──────────────┘
        │
        ├────────────────────────────┐
        ▼                            ▼
┌──────────────┐            ┌──────────────┐
│   Memory     │            │ Observability│
│   Layer      │            │   Layer      │
└──────────────┘            └──────────────┘
        │                            │
        ├────────┬──────────┬────────┤
        ▼        ▼          ▼        ▼
    ┌─────┐  ┌─────┐  ┌────────┐ ┌────────┐
    │ PG  │  │Redis│  │ Prom   │ │Grafana │
    │5433 │  │6380 │  │ 9091   │ │ 3001   │
    └─────┘  └─────┘  └────────┘ └────────┘
        │
        ▼
    ┌─────┐
    │Chroma│
    │8002 │
    └─────┘
```

**Dependency Flow**:
1. CLI → Services → Providers (AI APIs)
2. Services → Memory (Postgres, Redis, Chroma)
3. Services → Observability (Prometheus, Grafana)
4. All layers → Docker Network (assistant-network)

---

## 🔌 Network Configuration

### Docker Network: `local_assistant_assistant-network`
**Type**: Bridge
**Subnet**: Auto-assigned by Docker

**Internal Service Communication** (container-to-container):
- postgres:5432
- redis:6379
- chroma:8000
- prometheus:9090
- grafana:3000

**External Host Access** (from macOS host):
- localhost:5433 → postgres:5432
- localhost:6380 → redis:6379
- localhost:8002 → chroma:8000
- localhost:9091 → prometheus:9090
- localhost:3001 → grafana:3000

---

## 📍 File Locations

### Configuration Files
```
/Users/andrew/Projects/AGENTS/local_assistant/
├── .env                           # Environment variables
├── config/
│   ├── models_registry.yaml       # AI model configs
│   ├── vision_config.yaml         # Vision service settings
│   ├── computer_use.yaml          # Computer use settings
│   ├── prometheus.yml             # Prometheus config
│   └── grafana/
│       ├── provisioning/          # Auto-provisioning
│       └── dashboards/            # Dashboard definitions
└── docker-compose.yml             # Container orchestration
```

### Data Directories (Persistent)
```
/Users/andrew/Projects/AGENTS/local_assistant/data/
├── postgres/                      # PostgreSQL data files
├── redis/                         # Redis AOF/RDB files
├── chroma/                        # ChromaDB embeddings
├── prometheus/                    # Time-series metrics
├── grafana/                       # Dashboard configs
├── screenshots/                   # Computer use screenshots
├── documents/                     # Cached documents
└── logs/                          # Application logs
```

### Development Files (Temporary)
```
/Users/andrew/Projects/AGENTS/local_assistant/
├── .venv/                         # Virtual environment (uv)
├── .dev/
│   └── terminal_windows.txt       # Active window tracking
└── __pycache__/                   # Python bytecode
```

---

## 🎛️ Port Reference

| Service | Internal | External | Protocol | Purpose |
|---------|----------|----------|----------|---------|
| PostgreSQL | 5432 | 5433 | TCP | Database queries |
| Redis | 6379 | 6380 | TCP | Cache operations |
| ChromaDB | 8000 | 8002 | HTTP | Vector API |
| Prometheus | 9090 | 9091 | HTTP | Metrics queries |
| Grafana | 3000 | 3001 | HTTP | Dashboard UI |

**Why Non-Standard External Ports?**
- Avoid conflicts with existing local services
- Your machine already has services on standard ports
- Docker containers use standard ports internally
- Port mapping allows coexistence

---

## 🚦 Service Status Indicators

### Health Status
- 🟢 **Healthy**: Service is up and passing health checks
- 🟡 **Starting**: Service is initializing (health: starting)
- 🔴 **Unhealthy**: Service failed health checks
- ⚫ **Stopped**: Service is not running

### Where to Check
1. **Window 4** (System Monitor): Real-time status every 15s
2. **Docker Command**: `docker-compose ps`
3. **Individual Health**: `docker inspect assistant-<service>`

---

## 📈 Monitoring Metrics

### Available Metrics (Prometheus)

**Request Metrics**:
- `request_count` - Total requests by model/provider/status
- `request_duration_seconds` - Latency histogram
- `request_errors_total` - Error count by type

**Token Metrics**:
- `token_usage_input` - Input tokens by model
- `token_usage_output` - Output tokens by model
- `token_usage_total` - Total tokens by model

**Cost Metrics**:
- `cost_dollars_request` - Per-request cost
- `cost_dollars_hourly` - Hourly spend
- `cost_dollars_daily` - Daily spend
- `cost_dollars_by_provider` - Provider breakdown

**System Metrics**:
- `up` - Service availability (0=down, 1=up)
- `process_cpu_seconds_total` - CPU usage
- `process_resident_memory_bytes` - Memory usage

---

## 🎯 Quick Reference Commands

### Check All Services
```bash
# Docker services
docker-compose ps

# CLI status
python3 -m cli.main status

# Individual service
docker inspect assistant-postgres | grep Status
```

### View Logs
```bash
# All logs
docker-compose logs -f

# Specific service
docker-compose logs -f postgres

# Recent errors
docker-compose logs --tail=50 | grep -i error
```

### Restart Services
```bash
# All services
docker-compose restart

# Specific service
docker-compose restart postgres

# Full restart
./scripts/stop-dev.sh && ./scripts/start-dev.sh
```

### Access Services
```bash
# PostgreSQL
psql -h localhost -p 5433 -U assistant -d assistant

# Redis
redis-cli -p 6380

# ChromaDB
curl http://localhost:8002/api/v1/heartbeat

# Prometheus
open http://localhost:9091

# Grafana
open http://localhost:3001
```

---

**Last Updated**: October 30, 2025
**Maintained By**: Development Team
**Version**: 1.0.0
