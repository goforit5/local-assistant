#!/bin/bash
# Stop all Local Assistant services

set -e

# Load shared config
source "$(dirname "$0")/scripts/config.sh"

echo "🛑 Stopping Local Assistant..."

# Kill tmux session
if tmux has-session -t $SESSION 2>/dev/null; then
    echo "  ✓ Killing tmux session: $SESSION"
    tmux kill-session -t $SESSION
fi

# Kill processes on ports
kill_port $API_PORT
kill_port $UI_PORT

# Kill any uvicorn processes
pkill -f "uvicorn api.main:app" 2>/dev/null || true

# Kill any vite dev server
pkill -f "vite" 2>/dev/null || true

echo ""
echo "✅ All services stopped!"
echo ""
