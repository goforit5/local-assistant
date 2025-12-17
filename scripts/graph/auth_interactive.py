#!/usr/bin/env python3
"""
Interactive User Authentication for Microsoft Graph

This script performs the OAuth flow step-by-step and saves credentials.
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import msal

def main():
    print("\n" + "="*70)
    print("Microsoft Graph - Interactive Authentication")
    print("="*70 + "\n")

    # Get config
    client_id = os.getenv("GRAPH_CLIENT_ID")
    tenant_id = os.getenv("GRAPH_TENANT_ID")
    client_secret = os.getenv("GRAPH_CLIENT_SECRET")
    redirect_uri = "http://localhost:8000/auth/graph/callback"

    if not all([client_id, tenant_id]):
        print("❌ Missing GRAPH_CLIENT_ID or GRAPH_TENANT_ID")
        return 1

    # Setup cache
    cache_dir = Path.home() / ".local" / "assistant" / "graph"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "token_cache.json"

    # Create MSAL app
    cache = msal.SerializableTokenCache()
    if cache_file.exists():
        cache.deserialize(cache_file.read_text())

    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
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
        print("Found cached credentials!")
        result = app.acquire_token_silent(scopes, account=accounts[0])
        if result and "access_token" in result:
            print("✅ Authentication successful (using cached token)")
            print(f"\nUsername: {accounts[0].get('username')}")
            print(f"Token length: {len(result['access_token'])} chars")
            print(f"\nCache file: {cache_file}")
            return 0

    # No cached token, start interactive flow
    print("No cached credentials found. Starting authentication flow...\n")

    flow = app.initiate_auth_code_flow(
        scopes=scopes,
        redirect_uri=redirect_uri,
    )

    if "auth_uri" not in flow:
        print("❌ Failed to create auth flow")
        return 1

    print("="*70)
    print("STEP 1: Visit this URL in your browser:")
    print("="*70)
    print(f"\n{flow['auth_uri']}\n")
    print("="*70)
    print("STEP 2: Sign in with your Microsoft account")
    print("STEP 3: After signing in, copy the FULL redirect URL")
    print("        (It will look like: http://localhost:8000/auth/graph/callback?code=...)")
    print("="*70)
    print()

    # Get redirect URL from user
    redirect_response = input("Paste the full redirect URL here: ").strip()

    if not redirect_response:
        print("\n❌ No URL provided")
        return 1

    # Complete the flow
    print("\nCompleting authentication...")
    result = app.acquire_token_by_auth_code_flow(
        auth_code_flow=flow,
        auth_response=redirect_response,
    )

    if "access_token" not in result:
        print(f"\n❌ Authentication failed: {result.get('error_description', 'Unknown error')}")
        return 1

    # Save cache
    if cache.has_state_changed:
        cache_file.write_text(cache.serialize())

    print("\n" + "="*70)
    print("✅ SUCCESS! Authentication complete")
    print("="*70)
    print(f"\nToken saved to: {cache_file}")
    print(f"Token length: {len(result['access_token'])} characters")

    # Show account info
    accounts = app.get_accounts()
    if accounts:
        print(f"\nAuthenticated as: {accounts[0].get('username')}")

    print("\nYour credentials are saved and will auto-refresh.")
    print("You can now access Microsoft Graph APIs!\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
