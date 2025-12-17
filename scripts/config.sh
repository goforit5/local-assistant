#!/bin/bash
# Shared configuration for all scripts

# Ports
export API_PORT=8765
export UI_PORT=5173

# Paths
export PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UI_DIR="$PROJECT_DIR/ui"
export ENV_FILE="$PROJECT_DIR/.env"
export ENV_EXAMPLE="$PROJECT_DIR/.env.example"

# Tmux
export SESSION="local-assistant"

# Colors
export GREEN='\033[0;32m'
export BLUE='\033[0;34m'
export YELLOW='\033[1;33m'
export RED='\033[0;31m'
export NC='\033[0m'

# Functions
check_uv() {
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}❌ uv not found.${NC} Installing..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.cargo/bin:$PATH"
    fi
}

check_env() {
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}⚠️  No .env file found.${NC}"
        if [ -f "$ENV_EXAMPLE" ]; then
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            echo "  ✓ Created .env from .env.example"
            echo -e "${RED}⚠️  Please edit .env with your API keys${NC}"
            return 1
        fi
    fi
    return 0
}

kill_port() {
    local port=$1
    if lsof -ti:$port &>/dev/null; then
        echo "  ✓ Killing process on port $port"
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
        sleep 0.5
    fi
}

check_ports() {
    echo "🔍 Checking for port conflicts..."
    kill_port $API_PORT
    kill_port $UI_PORT
}
