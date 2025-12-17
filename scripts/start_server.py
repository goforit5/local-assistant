#!/usr/bin/env python3.11
"""
Start uvicorn server with .env file loaded.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Verify OAuth env vars are loaded
required_vars = ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'OAUTH_ENCRYPTION_KEY']
missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    print(f"ERROR: Missing environment variables: {missing}")
    sys.exit(1)

print(f"✓ Loaded OAuth env vars from {env_path}")
print(f"  - GOOGLE_CLIENT_ID: {os.getenv('GOOGLE_CLIENT_ID')[:20]}...")
print(f"  - GOOGLE_CLIENT_SECRET: {os.getenv('GOOGLE_CLIENT_SECRET')[:20]}...")
print(f"  - OAUTH_ENCRYPTION_KEY: {os.getenv('OAUTH_ENCRYPTION_KEY')[:20]}...")

# Start uvicorn
import uvicorn
uvicorn.run(
    "api.main:app",
    host="0.0.0.0",
    port=8000,
    reload=True,
)
