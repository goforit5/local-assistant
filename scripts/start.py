#!/usr/bin/env python3
"""Start Local Assistant API and UI with UV."""

import os
import sys
import time
import subprocess
import signal
import shutil
from pathlib import Path

# Unique ports to avoid conflicts
API_PORT = 8765
UI_PORT = 5173

processes = []


def cleanup(signum=None, frame=None):
    """Kill all child processes."""
    print("\n🛑 Shutting down...")
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()
    sys.exit(0)


def check_uv():
    """Check if uv is installed, install if not."""
    if not shutil.which("uv"):
        print("❌ uv not found. Installing...")
        install = subprocess.run(
            ["curl", "-LsSf", "https://astral.sh/uv/install.sh"],
            capture_output=True
        )
        if install.returncode == 0:
            subprocess.run(["sh"], input=install.stdout)
            print("✅ uv installed successfully")
        else:
            print("❌ Failed to install uv. Please install manually:")
            print("   curl -LsSf https://astral.sh/uv/install.sh | sh")
            sys.exit(1)


def main():
    # Register cleanup handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    root = Path(__file__).parent

    # Check for uv
    check_uv()

    # Check .env
    env_file = root / ".env"
    if not env_file.exists():
        print("⚠️  No .env file found. Creating from .env.example...")
        example = root / ".env.example"
        if example.exists():
            env_file.write_text(example.read_text())
            print("⚠️  Please edit .env with your API keys")
            sys.exit(1)

    print("🦄 Starting Local Assistant...")

    # Check and kill existing processes on our ports
    print("🔍 Checking for port conflicts...")
    for port in [API_PORT, UI_PORT]:
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                print(f"⚠️  Port {port} in use. Killing existing process...")
                subprocess.run(["kill", "-9"] + result.stdout.strip().split())
                time.sleep(1)
        except:
            pass

    # Sync dependencies with uv
    print("📦 Syncing dependencies with uv...")
    sync = subprocess.run(["uv", "sync"], cwd=root)
    if sync.returncode != 0:
        print("❌ Failed to sync dependencies")
        sys.exit(1)

    # Start API with uv run
    print(f"🚀 Starting API server on :{API_PORT}...")
    api_proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "api.main:app",
         "--host", "0.0.0.0", "--port", str(API_PORT), "--reload"],
        cwd=root
    )
    processes.append(api_proc)

    # Wait for API
    print("⏳ Waiting for API to be ready...")
    time.sleep(3)

    # Check if node_modules exists
    ui_dir = root / "ui"
    node_modules = ui_dir / "node_modules"
    if not node_modules.exists():
        print("📦 Installing UI dependencies...")
        npm_install = subprocess.run(["npm", "install"], cwd=ui_dir)
        if npm_install.returncode != 0:
            print("❌ Failed to install UI dependencies")
            cleanup()

    # Start UI
    print(f"🎨 Starting UI on :{UI_PORT}...")
    ui_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=ui_dir
    )
    processes.append(ui_proc)

    print("\n✅ Local Assistant running!")
    print(f"   API:  http://localhost:{API_PORT}")
    print(f"   UI:   http://localhost:{UI_PORT}")
    print(f"   Docs: http://localhost:{API_PORT}/docs")
    print("\nPress Ctrl+C to stop\n")

    # Wait for processes
    try:
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
