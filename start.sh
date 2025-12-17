#!/bin/bash
set -e

# Start Local Assistant UI + API with UV

# Load shared config
source "$(dirname "$0")/scripts/config.sh"

echo "🦄 Starting Local Assistant..."

# Run checks
check_uv
check_env || exit 1
check_ports

# Sync dependencies with uv
echo "📦 Syncing dependencies with uv..."
uv sync

# Start FastAPI backend with uv
echo "🚀 Starting API server on :$API_PORT..."
cd "$(dirname "$0")"
uv run uvicorn api.main:app --host 0.0.0.0 --port $API_PORT --reload &
API_PID=$!

# Wait for API to be ready
echo "⏳ Waiting for API to be ready..."
sleep 3

# Start React UI
echo "🎨 Starting UI on :5173..."
cd ui
if [ ! -d "node_modules" ]; then
    echo "📦 Installing UI dependencies..."
    npm install
fi
npm run dev &
UI_PID=$!

# Trap Ctrl+C to cleanup
cleanup() {
    echo "\n🛑 Shutting down..."
    kill $API_PID $UI_PID 2>/dev/null
    exit 0
}
trap cleanup INT TERM

echo "✅ Local Assistant running!"
echo "   API:  http://localhost:$API_PORT"
echo "   UI:   http://localhost:$UI_PORT"
echo "   Docs: http://localhost:$API_PORT/docs"
echo ""
echo "Press Ctrl+C to stop"

# Wait for background processes
wait
