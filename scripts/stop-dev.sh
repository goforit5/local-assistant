#!/bin/bash
# Local AI Assistant - Development Environment Shutdown
# Gracefully stops all services and closes Terminal windows

set -e  # Exit on error

PROJECT_ROOT="/Users/andrew/Projects/AGENTS/local_assistant"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}  🛑 Local AI Assistant - Development Shutdown${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Final cost report
echo -e "${YELLOW}[1/5]${NC} Generating final cost report..."
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
    python3 -m cli.main costs --breakdown 2>/dev/null || echo "  No cost data available"
else
    echo "  Virtual environment not found"
fi
echo ""

# Close Terminal windows
echo -e "${YELLOW}[2/5]${NC} Closing Terminal windows..."
if [ -f "$PROJECT_ROOT/.dev/terminal_windows.txt" ]; then
    # Get list of Terminal windows with our titles
    osascript <<EOF
tell application "Terminal"
    set windowTitles to {"🐳 Docker Logs", "💻 CLI Ready", "💰 Cost Monitor", "📊 System Monitor"}

    repeat with windowTitle in windowTitles
        set windowFound to false
        repeat with w in windows
            try
                if custom title of w is windowTitle then
                    close w
                    set windowFound to true
                    exit repeat
                end if
            end try
        end repeat
    end repeat
end tell
EOF

    echo "  ✓ Closed 4 Terminal windows"
    rm -f "$PROJECT_ROOT/.dev/terminal_windows.txt"
else
    echo "  No Terminal window tracking file found"
fi

# Stop Docker services
echo -e "${YELLOW}[3/5]${NC} Stopping Docker services..."
docker-compose down
echo "  ✓ All Docker containers stopped"

# Close browser tabs (optional - comment out if you want to keep them)
echo -e "${YELLOW}[4/5]${NC} Closing browser tabs..."
osascript <<EOF 2>/dev/null || true
tell application "Safari"
    set tabsToClose to {"localhost:3001", "localhost:9091", "localhost:8002"}

    repeat with w in windows
        set tabList to tabs of w
        repeat with t in tabList
            set tabURL to URL of t
            repeat with urlPattern in tabsToClose
                if tabURL contains urlPattern then
                    close t
                end if
            end repeat
        end repeat
    end repeat
end tell
EOF

# Chrome version (uncomment if using Chrome)
osascript <<EOF 2>/dev/null || true
tell application "Google Chrome"
    set tabsToClose to {"localhost:3001", "localhost:9091", "localhost:8002"}

    repeat with w in windows
        set tabList to tabs of w
        repeat with t in tabList
            set tabURL to URL of t
            repeat with urlPattern in tabsToClose
                if tabURL contains urlPattern then
                    close t
                end if
            end repeat
        end repeat
    end repeat
end tell
EOF

echo "  ✓ Browser tabs closed"

# Clean up development files
echo -e "${YELLOW}[5/5]${NC} Cleaning up..."
rm -rf "$PROJECT_ROOT/.dev"
echo "  ✓ Cleanup complete"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Development environment stopped${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}📊 Session Summary:${NC}"
echo ""
echo "  All services have been stopped:"
echo "    • Docker containers: stopped and removed"
echo "    • Terminal windows: closed (4 windows)"
echo "    • Browser tabs: closed (3 tabs)"
echo "    • Virtual environment: preserved"
echo ""
echo -e "${YELLOW}🔄 To restart:${NC}"
echo ""
echo "  ./scripts/start-dev.sh"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
