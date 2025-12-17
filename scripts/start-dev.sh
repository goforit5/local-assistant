#!/bin/bash
# Local AI Assistant - Development Environment Startup
# Uses UV for all Python operations and manages Terminal windows

set -e  # Exit on error

PROJECT_ROOT="/Users/andrew/Projects/AGENTS/local_assistant"
cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🦄 Local AI Assistant - Development Startup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found${NC}"
    echo "Creating from .env.example..."
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo -e "${YELLOW}⚠️  Please edit .env and add your API keys${NC}"
    exit 1
fi

# Check for uv
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}⚠️  UV not found. Installing...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Setup virtual environment with UV
echo -e "${GREEN}[1/7]${NC} Setting up Python environment with UV..."
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    uv venv "$PROJECT_ROOT/.venv"
fi

# Install dependencies with UV
echo -e "${GREEN}[2/7]${NC} Installing dependencies with UV..."
source "$PROJECT_ROOT/.venv/bin/activate"
uv pip install -r "$PROJECT_ROOT/requirements.txt" -q

# Start Docker services
echo -e "${GREEN}[3/7]${NC} Starting Docker infrastructure..."
docker-compose up -d

# Wait for services to be healthy
echo -e "${GREEN}[4/7]${NC} Waiting for services to be healthy..."
sleep 5

# Check Docker service health
echo -e "${GREEN}[5/7]${NC} Checking Docker service health..."
docker-compose ps

# Create PID file directory
mkdir -p "$PROJECT_ROOT/.dev"

# Function to open Terminal window with command
open_terminal_window() {
    local window_name=$1
    local command=$2
    local window_number=$3

    osascript <<EOF
tell application "Terminal"
    activate

    -- Create new window
    set newWindow to do script "cd '$PROJECT_ROOT' && clear && echo '═══════════════════════════════════════════════════' && echo '  $window_name' && echo '═══════════════════════════════════════════════════' && echo '' && $command"

    -- Set window title
    set custom title of newWindow to "$window_name"

    -- Position window based on number
    tell window 1
        set position to {$(( 50 + (window_number * 600) )), $(( 50 + (window_number * 50) ))}
        set bounds to {$(( 50 + (window_number * 600) )), $(( 50 + (window_number * 50) )), $(( 650 + (window_number * 600) )), $(( 450 + (window_number * 50) ))}
    end tell
end tell
EOF
}

# Store window PIDs
echo "" > "$PROJECT_ROOT/.dev/terminal_windows.txt"

echo -e "${GREEN}[6/7]${NC} Opening Terminal windows..."

# Window 1: Docker Logs
echo -e "  ${BLUE}→${NC} Terminal 1: Docker Logs"
open_terminal_window "🐳 Docker Logs" "docker-compose logs -f" 0
echo "docker_logs" >> "$PROJECT_ROOT/.dev/terminal_windows.txt"
sleep 1

# Window 2: CLI Ready (with UV activation)
echo -e "  ${BLUE}→${NC} Terminal 2: CLI Ready"
open_terminal_window "💻 CLI Ready" "source .venv/bin/activate && echo '✅ Environment activated. Try: .venv/bin/python3 -m cli.main status' && exec bash" 1
echo "cli_ready" >> "$PROJECT_ROOT/.dev/terminal_windows.txt"
sleep 1

# Window 3: Cost Monitor (auto-refresh every 10s)
echo -e "  ${BLUE}→${NC} Terminal 3: Cost Monitor"
open_terminal_window "💰 Cost Monitor" "source .venv/bin/activate && while true; do clear; date; echo ''; .venv/bin/python3 -m cli.main costs --breakdown 2>/dev/null || echo 'No costs yet'; sleep 10; done" 2
echo "cost_monitor" >> "$PROJECT_ROOT/.dev/terminal_windows.txt"
sleep 1

# Window 4: System Monitor
echo -e "  ${BLUE}→${NC} Terminal 4: System Monitor"
open_terminal_window "📊 System Monitor" "source .venv/bin/activate && while true; do clear; date; echo ''; .venv/bin/python3 -m cli.main status 2>/dev/null || docker-compose ps; sleep 15; done" 3
echo "system_monitor" >> "$PROJECT_ROOT/.dev/terminal_windows.txt"

echo ""
echo -e "${GREEN}[7/7]${NC} Opening browser windows..."

# Wait a bit before opening browsers
sleep 2

# Open monitoring dashboards
echo -e "  ${BLUE}→${NC} Grafana (http://localhost:3001)"
open "http://localhost:3001" 2>/dev/null || true

echo -e "  ${BLUE}→${NC} Prometheus (http://localhost:9091)"
open "http://localhost:9091" 2>/dev/null || true

echo -e "  ${BLUE}→${NC} ChromaDB (http://localhost:8002)"
open "http://localhost:8002" 2>/dev/null || true

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Development environment started!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}📍 Services Running:${NC}"
echo ""
echo "  🐳 Docker Infrastructure:"
echo "     • PostgreSQL:  localhost:5433"
echo "     • Redis:       localhost:6380"
echo "     • ChromaDB:    localhost:8002"
echo "     • Prometheus:  localhost:9091"
echo "     • Grafana:     localhost:3001"
echo ""
echo "  📟 Terminal Windows:"
echo "     • Window 1: Docker Logs (auto-scrolling)"
echo "     • Window 2: CLI Ready (use for commands)"
echo "     • Window 3: Cost Monitor (auto-refresh 10s)"
echo "     • Window 4: System Monitor (auto-refresh 15s)"
echo ""
echo "  🌐 Browser Tabs:"
echo "     • Grafana:     http://localhost:3001 (admin/admin)"
echo "     • Prometheus:  http://localhost:9091"
echo "     • ChromaDB:    http://localhost:8002"
echo ""
echo -e "${YELLOW}🎯 Quick Commands (use in Window 2):${NC}"
echo ""
echo "  .venv/bin/python3 -m cli.main chat \"Hello!\""
echo "  .venv/bin/python3 -m cli.main costs"
echo "  .venv/bin/python3 -m cli.main status"
echo "  .venv/bin/python3 -m cli.main vision extract file.pdf"
echo ""
echo -e "${YELLOW}🛑 To stop everything:${NC}"
echo ""
echo "  ./scripts/stop-dev.sh"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
