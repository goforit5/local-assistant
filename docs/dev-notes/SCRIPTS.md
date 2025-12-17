# 🦄 Local Assistant - Scripts Guide

All scripts now use DRY principles with shared configuration in `scripts/config.sh`.

## Quick Start

### Development Mode (Recommended)
```bash
./dev.sh
```

Opens **tmux** with 3 organized panes:
- **Top**: API server logs (port 8765)
- **Bottom-left**: UI dev server (port 5173)
- **Bottom-right**: Commands & info

**Tmux Navigation:**
- `Ctrl+b →` - Switch panes
- `Ctrl+b ↑/↓` - Navigate panes
- `Ctrl+b d` - Detach (keeps running)
- `Ctrl+b [` - Scroll mode (q to exit)

**Re-attach:**
```bash
tmux attach -t local-assistant
```

### Stop Everything
```bash
./stop.sh
```

Cleanly stops:
- Tmux session
- API server (port 8765)
- UI server (port 5173)
- All related processes

### Simple Mode (No Tmux)
```bash
./start.sh
```

Runs both services in background. Use `./stop.sh` to clean up.

---

## Shared Configuration

All scripts source `scripts/config.sh` for DRY:

```bash
# Ports
API_PORT=8765
UI_PORT=5173

# Paths
PROJECT_DIR, UI_DIR, ENV_FILE

# Functions
check_uv()        # Install uv if missing
check_env()       # Validate .env file
check_ports()     # Kill port conflicts
kill_port()       # Kill specific port
```

### Update Ports (One Place)

Edit `scripts/config.sh`:
```bash
export API_PORT=9000
export UI_PORT=4000
```

All scripts automatically use new ports!

---

## Scripts Overview

| Script | Purpose | Mode |
|--------|---------|------|
| `dev.sh` | Development with tmux panes | Interactive |
| `start.sh` | Simple background start | Background |
| `stop.sh` | Stop all services | Cleanup |
| `scripts/config.sh` | Shared configuration | Library |

---

## Development Workflow

### 1. Start Development
```bash
./dev.sh
```

### 2. View Logs
All logs visible in tmux panes. Switch panes with `Ctrl+b →`

### 3. Run Commands
Use bottom-right pane:
```bash
make test
make lint
make format
```

### 4. Detach (Keep Running)
```bash
Ctrl+b d
```

### 5. Re-attach Later
```bash
tmux attach -t local-assistant
```

### 6. Stop When Done
```bash
./stop.sh
```

---

## Troubleshooting

### Port Already in Use
Scripts auto-kill conflicting processes. If issues persist:
```bash
lsof -ti:8765 | xargs kill -9  # API
lsof -ti:5173 | xargs kill -9  # UI
```

### Tmux Not Found
```bash
brew install tmux  # macOS
```

### UV Not Found
Scripts auto-install UV on first run.

### API Startup Errors
Check `.env` has valid API keys:
```bash
cat .env
```

---

## Advanced

### Custom Ports
Edit `scripts/config.sh`:
```bash
export API_PORT=YOUR_PORT
export UI_PORT=YOUR_PORT
```

### Custom Tmux Layout
Edit `dev.sh` and modify:
```bash
tmux split-window -v    # Horizontal split
tmux split-window -h    # Vertical split
tmux resize-pane -y 15  # Resize
```

### Run Individual Services
```bash
make api    # API only (port 8765)
make ui     # UI only (port 5173)
```

---

**All scripts follow DRY - one config, many uses!** 🎯
