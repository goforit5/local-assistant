#!/usr/bin/env python3
"""
Setup User Authentication for Microsoft Graph

This script performs interactive authentication to get user consent
and saves the refresh token for persistent access.

Usage: python3 scripts/graph/setup_user_auth.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.microsoft_graph.auth import GraphAuthenticator

def main():
    print("=" * 60)
    print("Microsoft Graph User Authentication Setup")
    print("=" * 60)
    print()

    # Get credentials from environment
    client_id = os.getenv("GRAPH_CLIENT_ID")
    tenant_id = os.getenv("GRAPH_TENANT_ID")
    client_secret = os.getenv("GRAPH_CLIENT_SECRET")
    redirect_uri = os.getenv("GRAPH_REDIRECT_URI", "http://localhost:8000/auth/graph/callback")

    if not client_id or not tenant_id:
        print("❌ Error: Missing GRAPH_CLIENT_ID or GRAPH_TENANT_ID")
        print("Please set environment variables first.")
        return 1

    print(f"Client ID: {client_id}")
    print(f"Tenant ID: {tenant_id}")
    print(f"Redirect URI: {redirect_uri}")
    print()

    # Create cache directory
    cache_dir = Path.home() / ".local" / "assistant" / "graph"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "token_cache.json"

    print(f"Token cache: {cache_file}")
    print()

    # Create authenticator with delegated permissions
    print("Creating authenticator...")
    auth = GraphAuthenticator(
        client_id=client_id,
        tenant_id=tenant_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=[
            "Tasks.ReadWrite",
            "Tasks.ReadWrite.All",
            "Group.Read.All",
            "User.Read",
            "offline_access",  # This gives us refresh token
        ],
        cache_file=str(cache_file),
    )

    print("✓ Authenticator created")
    print()

    # Get access token (will trigger interactive flow)
    print("=" * 60)
    print("IMPORTANT: Interactive authentication required")
    print("=" * 60)
    print()
    print("A browser window will open for you to sign in.")
    print("After signing in, you'll be redirected to:")
    print(f"  {redirect_uri}")
    print()
    print("Copy the FULL URL from your browser (including the code)")
    print("and paste it when prompted.")
    print()
    input("Press Enter to continue...")
    print()

    try:
        # This will trigger interactive authentication
        token = auth.get_access_token()

        print()
        print("=" * 60)
        print("✅ SUCCESS! Authentication complete")
        print("=" * 60)
        print()
        print(f"Token preview: {token[:30]}...{token[-30:]}")
        print(f"Token length: {len(token)} characters")
        print()

        # Verify account info
        account_info = auth.get_account_info()
        if account_info:
            print("Authenticated as:")
            print(f"  Username: {account_info['username']}")
            print(f"  Account ID: {account_info['home_account_id']}")
        print()

        # Verify cache was saved
        if cache_file.exists():
            print(f"✓ Credentials saved to: {cache_file}")
            print()
            print("Your credentials are now saved and will be automatically")
            print("refreshed. You won't need to sign in again!")
        else:
            print("⚠ Warning: Token cache file not found")

        print()
        print("=" * 60)
        print("Setup Complete!")
        print("=" * 60)
        print()
        print("You can now run:")
        print("  python3 scripts/graph/list_planner_tasks.py")
        print("  python3 scripts/graph/list_todo_tasks.py")
        print()

        return 0

    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Authentication failed")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
