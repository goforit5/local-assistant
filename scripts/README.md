# Development Scripts

Automated startup and shutdown scripts for the Local AI Assistant development environment.

---

## 📜 Scripts

### `start-dev.sh`
**Purpose**: One-command startup of entire development environment

**What it does**:
1. ✅ Checks for `.env` file (creates from `.env.example` if missing)
2. ✅ Installs/verifies `uv` package manager
3. ✅ Creates virtual environment with `uv venv`
4. ✅ Installs all dependencies with `uv pip install`
5. ✅ Starts Docker services (postgres, redis, chroma, prometheus, grafana)
6. ✅ Opens 4 organized Terminal windows
7. ✅ Opens 3 browser tabs for monitoring

**Usage**:
```bash
./scripts/start-dev.sh
```

**Terminal Windows Opened**:
- **Window 1** (Top-left): Docker Logs - Auto-scrolling container logs
- **Window 2** (Top-right): CLI Ready - Your main work terminal
- **Window 3** (Bottom-left): Cost Monitor - Auto-refreshes every 10s
- **Window 4** (Bottom-right): System Monitor - Auto-refreshes every 15s

**Browser Tabs Opened**:
- http://localhost:3001 - Grafana (admin/admin)
- http://localhost:9091 - Prometheus
- http://localhost:8002 - ChromaDB

---

### `stop-dev.sh`
**Purpose**: Graceful shutdown of entire development environment

**What it does**:
1. ✅ Generates final cost report
2. ✅ Closes all 4 Terminal windows
3. ✅ Stops and removes Docker containers
4. ✅ Closes monitoring browser tabs
5. ✅ Cleans up temporary files

**Usage**:
```bash
./scripts/stop-dev.sh
```

**What's preserved**:
- Virtual environment (`.venv`)
- Cost tracking data
- Docker volumes (database data)
- Your code and configuration

---

## 🚀 Quick Start

### First Time Setup
```bash
# 1. Make scripts executable (already done)
chmod +x scripts/*.sh

# 2. Start everything
./scripts/start-dev.sh

# 3. If .env was missing, edit it:
nano .env
# Add your API keys, then restart:
./scripts/start-dev.sh
```

### Daily Usage
```bash
# Start your dev session
./scripts/start-dev.sh

# Work in Terminal Window 2 (CLI Ready)
# Use Window 3 to monitor costs in real-time
# Use Window 4 to monitor system health

# When done for the day
./scripts/stop-dev.sh
```

---

## 📊 Services Started

### Docker Services (5 containers)

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| **PostgreSQL** | 5433 | `localhost:5433` | Main database for conversations, messages, documents |
| **Redis** | 6380 | `localhost:6380` | Cache layer for documents, session storage |
| **ChromaDB** | 8002 | http://localhost:8002 | Vector database for embeddings |
| **Prometheus** | 9091 | http://localhost:9091 | Metrics collection and queries |
| **Grafana** | 3001 | http://localhost:3001 | Visualization dashboards |

**Note**: Ports are remapped to avoid conflicts with local services:
- Postgres: 5432 (internal) → 5433 (external)
- Redis: 6379 (internal) → 6380 (external)
- ChromaDB: 8000 (internal) → 8002 (external)
- Prometheus: 9090 (internal) → 9091 (external)
- Grafana: 3000 (internal) → 3001 (external)

### Terminal Windows (4 windows)

| Window | Title | Purpose | Auto-Refresh |
|--------|-------|---------|--------------|
| **1** | 🐳 Docker Logs | Live Docker container logs | Continuous |
| **2** | 💻 CLI Ready | Your main terminal for commands | Manual |
| **3** | 💰 Cost Monitor | Real-time cost tracking | Every 10s |
| **4** | 📊 System Monitor | Service health checks | Every 15s |

**Window Positioning**:
- Windows are automatically positioned in a 2x2 grid
- Top-left: Docker Logs
- Top-right: CLI Ready (your main work window)
- Bottom-left: Cost Monitor
- Bottom-right: System Monitor

### Browser Tabs (3 tabs)

| Tab | URL | Credentials | Purpose |
|-----|-----|-------------|---------|
| **Grafana** | http://localhost:3001 | admin/admin | Dashboards, metrics visualization |
| **Prometheus** | http://localhost:9091 | None | Raw metrics, queries, targets |
| **ChromaDB** | http://localhost:8002 | None | Vector database API, health check |

---

## 🎯 Using the Environment

### In Terminal Window 2 (CLI Ready)

Environment is automatically activated. Use these commands:

```bash
# Chat with AI
python3 -m cli.main chat "Hello!"

# Process documents
python3 -m cli.main vision extract invoice.pdf --type invoice

# Complex reasoning
python3 -m cli.main reason "Plan a web app architecture"

# Check costs
python3 -m cli.main costs

# System status
python3 -m cli.main status

# Help
python3 -m cli.main --help
```

### Monitoring Windows

**Window 3 (Cost Monitor)**:
- Auto-refreshes every 10 seconds
- Shows cost breakdown by provider
- Displays per-request, hourly, and daily totals
- No interaction needed - just watch it

**Window 4 (System Monitor)**:
- Auto-refreshes every 15 seconds
- Shows Docker service health
- Displays API key status
- Shows service URLs

**Window 1 (Docker Logs)**:
- Auto-scrolls as new logs appear
- Shows all container output
- Useful for debugging
- Can search with Cmd+F

---

## 🔧 Configuration

### Environment Variables
Edit `.env` for configuration:

```bash
# Required API keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AI...

# Database (auto-configured)
DATABASE_URL=postgresql://assistant:assistant@localhost:5433/assistant
REDIS_URL=redis://localhost:6380/0
CHROMA_HOST=localhost
CHROMA_PORT=8002

# Cost limits
COST_LIMIT_PER_REQUEST=1.00
COST_LIMIT_PER_HOUR=10.00
COST_LIMIT_PER_DAY=50.00
```

### Custom Window Layout
Edit `start-dev.sh` to change window positions:

```bash
# Line ~90 in start-dev.sh
set bounds to {x1, y1, x2, y2}
```

### Disable Browser Auto-Open
Comment out lines in `start-dev.sh`:

```bash
# Line ~145-150 in start-dev.sh
# open "http://localhost:3001" 2>/dev/null || true
```

---

## 🐛 Troubleshooting

### Script Won't Start
```bash
# Check if scripts are executable
ls -la scripts/*.sh

# Make executable if needed
chmod +x scripts/*.sh

# Check for errors
./scripts/start-dev.sh
```

### Port Conflicts
```bash
# Check what's using ports
lsof -i :5433 -i :6380 -i :8002 -i :9091 -i :3001

# Stop conflicting services or edit docker-compose.yml
```

### Docker Issues
```bash
# Manually stop containers
docker-compose down

# Clean everything
docker-compose down -v

# Restart
./scripts/start-dev.sh
```

### UV Not Found
```bash
# Install UV manually
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH
export PATH="$HOME/.cargo/bin:$PATH"
```

### Windows Not Opening
```bash
# Check Terminal permissions
# System Preferences → Security & Privacy → Automation
# Allow Terminal to control System Events

# Or open manually
osascript scripts/start-dev.sh
```

---

## 📝 Files Created

### Runtime Files
```
.dev/                          # Created during startup
├── terminal_windows.txt       # Track opened windows
└── (cleaned up on stop)
```

### Data Files (Persistent)
```
data/                          # Docker volumes
├── postgres/                  # Database files
├── redis/                     # Cache data
├── chroma/                    # Vector embeddings
├── prometheus/                # Metrics data
├── grafana/                   # Dashboard configs
├── screenshots/               # Computer use screenshots
└── documents/                 # Cached documents
```

---

## 🎓 Tips & Best Practices

### 1. Always Use Window 2 for Commands
Window 2 is your main terminal with the environment activated. Use it for all CLI commands.

### 2. Watch Window 3 for Costs
Keep an eye on the cost monitor to avoid surprises. It updates every 10 seconds.

### 3. Check Window 4 for Issues
If something's not working, Window 4 shows service health. Look for red ✗ marks.

### 4. Use Window 1 for Debugging
If a command fails, switch to Window 1 to see Docker logs.

### 5. Stop Properly
Always use `./scripts/stop-dev.sh` instead of Ctrl+C. It ensures clean shutdown.

### 6. UV for Everything
Scripts use `uv` for all Python operations. Never use `pip` directly.

### 7. Edit Code While Running
You can edit code in your IDE while the dev environment runs. Changes take effect on next command.

---

## 🔄 Daily Workflow

### Morning
```bash
./scripts/start-dev.sh
# Wait for all windows to open
# Check Window 4 for service health
# Ready to code!
```

### During Development
```bash
# Work in Window 2
# Monitor costs in Window 3
# Watch health in Window 4
# Debug with Window 1
```

### Evening
```bash
./scripts/stop-dev.sh
# Generates final cost report
# Closes everything cleanly
# Data is preserved
```

---

## 📚 Related Documentation

- **TESTING_GUIDE.md**: How to test features
- **DEV_LOG.md**: Complete development history
- **DEPLOYMENT_READY.md**: Production deployment guide
- **IMPLEMENTATION_COMPLETE.md**: Architecture details

---

**Created**: October 30, 2025
**Last Updated**: October 30, 2025
**Maintained By**: Development Team
