#!/usr/bin/env python3
"""
Test Microsoft Graph Authentication

Tests authentication flow and token retrieval.
Usage: python3 scripts/graph/test_auth.py
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.microsoft_graph.auth import create_authenticator_from_env
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
)

logger = structlog.get_logger(__name__)


async def main():
    """Test authentication."""
    print("=" * 60)
    print("Microsoft Graph Authentication Test")
    print("=" * 60)
    print()

    try:
        # Create authenticator from environment
        print("Creating authenticator from environment variables...")
        authenticator = create_authenticator_from_env()
        print("✓ Authenticator created")
        print()

        # Get access token
        print("Acquiring access token...")
        print("(This may open a browser window for authentication)")
        print()

        token = authenticator.get_access_token()

        print("✓ Access token acquired successfully!")
        print()
        print(f"Token preview: {token[:20]}...{token[-20:]}")
        print(f"Token length: {len(token)} characters")
        print()

        # Get account info
        account_info = authenticator.get_account_info()
        if account_info:
            print("✓ Authenticated account:")
            print(f"  Username: {account_info['username']}")
            print(f"  Environment: {account_info['environment']}")
        print()

        print("=" * 60)
        print("Authentication test PASSED ✓")
        print("=" * 60)

        return 0

    except Exception as e:
        print()
        print("=" * 60)
        print(f"Authentication test FAILED ✗")
        print(f"Error: {e}")
        print("=" * 60)
        logger.error("auth_test_failed", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
