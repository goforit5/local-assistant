#!/usr/bin/env python3
"""
Device Code Authentication for Microsoft Graph

This uses device code flow which is perfect for CLI/headless scenarios.
No redirect URI or web server needed!
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import msal

def main():
    print("\n" + "="*70)
    print("Microsoft Graph - Device Code Authentication")
    print("="*70 + "\n")

    # Get config
    client_id = os.getenv("GRAPH_CLIENT_ID")
    tenant_id = os.getenv("GRAPH_TENANT_ID")

    if not all([client_id, tenant_id]):
        print("❌ Missing GRAPH_CLIENT_ID or GRAPH_TENANT_ID")
        return 1

    # Setup cache
    cache_dir = Path.home() / ".local" / "assistant" / "graph"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "token_cache.json"

    # Create MSAL app (Public client for device code flow)
    cache = msal.SerializableTokenCache()
    if cache_file.exists():
        cache.deserialize(cache_file.read_text())

    app = msal.PublicClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
    )

    scopes = [
        "https://graph.microsoft.com/Tasks.ReadWrite",
        "https://graph.microsoft.com/Group.Read.All",
        "https://graph.microsoft.com/User.Read",
    ]

    # Check for cached token first
    accounts = app.get_accounts()
    if accounts:
        print("✓ Found cached credentials!")
        result = app.acquire_token_silent(scopes, account=accounts[0])
        if result and "access_token" in result:
            print("✅ Authentication successful (using cached token)\n")
            print(f"Username: {accounts[0].get('username')}")
            print(f"Token length: {len(result['access_token'])} chars")
            print(f"\nCache file: {cache_file}")
            print("\nYour credentials are saved and will auto-refresh! ✓")
            return 0

    # No cached token, start device code flow
    print("No cached credentials found. Starting device code flow...\n")

    flow = app.initiate_device_flow(scopes=scopes)

    if "user_code" not in flow:
        print("❌ Failed to create device code flow")
        return 1

    # Display instructions
    print("="*70)
    print(flow["message"])
    print("="*70)
    print()
    print("⏳ Waiting for you to complete authentication...")
    print("   (This will automatically continue once you're done)")
    print()

    # Wait for user to complete auth
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        print(f"\n❌ Authentication failed: {result.get('error_description', 'Unknown error')}")
        return 1

    # Save cache
    if cache.has_state_changed:
        cache_file.write_text(cache.serialize())

    print("\n" + "="*70)
    print("✅ SUCCESS! Authentication complete")
    print("="*70)
    print(f"\n✓ Token saved to: {cache_file}")
    print(f"✓ Token length: {len(result['access_token'])} characters")

    # Show account info
    accounts = app.get_accounts()
    if accounts:
        print(f"✓ Authenticated as: {accounts[0].get('username')}")

    print("\n" + "="*70)
    print("Your credentials are now saved permanently!")
    print("="*70)
    print("\nThey will automatically refresh when needed.")
    print("You can now access Microsoft Planner and To Do!\n")

    print("Try these commands:")
    print("  python3 scripts/graph/list_planner_tasks.py")
    print("  python3 scripts/graph/list_todo_tasks.py")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
