#!/bin/bash
# Development mode with organized terminal windows

set -e

# Load shared config
source "$(dirname "$0")/scripts/config.sh"

echo "🦄 Starting Local Assistant in Development Mode..."

# Run checks
check_uv
check_env || exit 1
check_ports

# Check for tmux
if ! command -v tmux &> /dev/null; then
    echo "⚠️  tmux not found. Installing with brew..."
    if command -v brew &> /dev/null; then
        brew install tmux
    else
        echo "❌ brew not found. Install tmux manually:"
        echo "   brew install tmux"
        exit 1
    fi
fi

# Sync dependencies
echo "📦 Syncing dependencies..."
cd "$PROJECT_DIR"
uv sync --quiet

# Create session name
SESSION="local-assistant"

# Kill existing tmux session if it exists
tmux kill-session -t $SESSION 2>/dev/null || true

# Start new tmux session
echo "🚀 Starting tmux session: $SESSION"

# Create tmux session with 3 panes
tmux new-session -d -s $SESSION -n "assistant" -c "$PROJECT_DIR"

# Split horizontally (API on top, UI on bottom)
tmux split-window -v -t $SESSION:0 -c "$PROJECT_DIR"

# Split bottom pane vertically (UI left, Logs right)
tmux split-window -h -t $SESSION:0.1 -c "$PROJECT_DIR"

# Pane 0 (top): API Server
tmux send-keys -t $SESSION:0.0 "
echo '${GREEN}🚀 API Server (Port $API_PORT)${NC}'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
uv run uvicorn api.main:app --host 0.0.0.0 --port $API_PORT --reload
" C-m

# Pane 1 (bottom-left): UI Dev Server
tmux send-keys -t $SESSION:0.1 "
sleep 2
echo '${BLUE}🎨 UI Dev Server (Port $UI_PORT)${NC}'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
cd ui
npm run dev
" C-m

# Pane 2 (bottom-right): Logs & Commands
tmux send-keys -t $SESSION:0.2 "
sleep 3
clear
echo '${GREEN}✅ Local Assistant Running!${NC}'
echo ''
echo '  API:  http://localhost:$API_PORT'
echo '  UI:   http://localhost:$UI_PORT'
echo '  Docs: http://localhost:$API_PORT/docs'
echo ''
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo ''
echo 'Quick Commands:'
echo '  make test    - Run tests'
echo '  make lint    - Lint code'
echo '  make format  - Format code'
echo '  ./stop.sh    - Stop all services'
echo ''
echo 'Tmux Commands:'
echo '  Ctrl+b →     - Switch to next pane'
echo '  Ctrl+b ↑/↓   - Navigate panes'
echo '  Ctrl+b d     - Detach session'
echo '  Ctrl+b [     - Scroll mode (q to exit)'
echo ''
" C-m

# Adjust pane sizes (API gets 40% height, UI/Logs split remaining 60%)
tmux resize-pane -t $SESSION:0.0 -y 15

# Attach to session
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Development environment ready!"
echo ""
echo "   Attaching to tmux session: $SESSION"
echo "   Press Ctrl+b then d to detach"
echo "   Run './stop.sh' to stop all services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sleep 2
tmux attach-session -t $SESSION
