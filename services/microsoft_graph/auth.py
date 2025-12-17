"""
Microsoft Graph Authentication Module

Handles OAuth 2.0 authentication using MSAL (Microsoft Authentication Library).
Supports both delegated (user context) and application (daemon) permissions.

Best Practices:
- Token cache for performance (reduces auth requests)
- Automatic token refresh before expiration
- Secure credential storage
- Support for multiple auth flows (interactive, device code, client credentials)
"""

import os
import msal
import structlog
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

logger = structlog.get_logger(__name__)


class GraphAuthenticator:
    """
    Microsoft Graph authenticator using MSAL.

    Supports:
    - Interactive browser flow (delegated permissions)
    - Device code flow (headless scenarios)
    - Client credentials flow (application permissions)
    """

    def __init__(
        self,
        client_id: str,
        tenant_id: str,
        client_secret: Optional[str] = None,
        redirect_uri: str = "http://localhost:8000/auth/graph/callback",
        scopes: Optional[list[str]] = None,
        cache_file: Optional[str] = None,
    ):
        """
        Initialize Graph authenticator.

        Args:
            client_id: Azure AD application (client) ID
            tenant_id: Azure AD tenant ID
            client_secret: Client secret (for application permissions)
            redirect_uri: OAuth redirect URI
            scopes: List of permission scopes
            cache_file: Path to token cache file (optional)
        """
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or [
            "Tasks.ReadWrite",
            "Tasks.ReadWrite.All",
            "Group.Read.All",
            "User.Read",
            "offline_access",  # For refresh tokens
        ]

        # Authority URL
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"

        # Token cache
        self.cache = msal.SerializableTokenCache()
        if cache_file:
            self.cache_file = Path(cache_file)
            if self.cache_file.exists():
                self.cache.deserialize(self.cache_file.read_text())
        else:
            self.cache_file = None

        # Initialize MSAL app
        if client_secret:
            # Confidential client (has secret, can use app-only or delegated)
            self.app = msal.ConfidentialClientApplication(
                client_id=client_id,
                client_credential=client_secret,
                authority=self.authority,
                token_cache=self.cache,
            )
        else:
            # Public client (no secret, delegated only)
            self.app = msal.PublicClientApplication(
                client_id=client_id,
                authority=self.authority,
                token_cache=self.cache,
            )

        logger.info(
            "graph_auth_initialized",
            client_id=client_id[:8] + "...",
            tenant_id=tenant_id[:8] + "...",
            has_secret=bool(client_secret),
            scopes=self.scopes,
        )

    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Get access token, refreshing if needed.

        This is the main entry point for getting tokens. It will:
        1. Check cache for valid token
        2. Try to refresh using refresh token
        3. Fall back to interactive auth if needed

        Args:
            force_refresh: Force a new token even if cached one is valid

        Returns:
            Access token string

        Raises:
            RuntimeError: If authentication fails
        """
        # Try to get token from cache
        if not force_refresh:
            accounts = self.app.get_accounts()
            if accounts:
                result = self.app.acquire_token_silent(
                    scopes=self.scopes,
                    account=accounts[0]
                )
                if result and "access_token" in result:
                    logger.debug("token_from_cache")
                    self._save_cache()
                    return result["access_token"]

        # No cached token, need to authenticate
        logger.info("no_cached_token_available")

        # Try different flows based on client type
        if self.client_secret:
            # Try application flow first (works without user)
            result = self._acquire_token_app_only()
            if result and "access_token" in result:
                self._save_cache()
                return result["access_token"]

        # Fall back to interactive flow
        result = self._acquire_token_interactive()
        if result and "access_token" in result:
            self._save_cache()
            return result["access_token"]

        # All flows failed
        error_msg = result.get("error_description", "Unknown error") if result else "No result"
        logger.error("auth_failed", error=error_msg)
        raise RuntimeError(f"Failed to acquire access token: {error_msg}")

    def _acquire_token_interactive(self) -> Dict[str, Any]:
        """
        Acquire token using interactive browser flow.

        This will:
        1. Open browser for user login
        2. User consents to permissions
        3. Token returned via redirect URI
        """
        logger.info("starting_interactive_auth")

        # Get authorization URL
        flow = self.app.initiate_auth_code_flow(
            scopes=self.scopes,
            redirect_uri=self.redirect_uri,
        )

        if "auth_uri" not in flow:
            logger.error("failed_to_create_auth_flow")
            return {}

        print("\n" + "="*60)
        print("Microsoft Graph Authentication Required")
        print("="*60)
        print(f"\nPlease visit this URL to authenticate:\n\n{flow['auth_uri']}\n")
        print("After authentication, you'll be redirected to localhost.")
        print("Copy the FULL redirect URL from your browser and paste it here.\n")

        # Wait for user to paste redirect URL
        redirect_response = input("Paste the full redirect URL here: ").strip()

        # Extract authorization code and complete flow
        result = self.app.acquire_token_by_auth_code_flow(
            auth_code_flow=flow,
            auth_response=redirect_response,
        )

        if "access_token" in result:
            logger.info("interactive_auth_successful")
        else:
            logger.error("interactive_auth_failed", error=result.get("error"))

        return result

    def _acquire_token_device_code(self) -> Dict[str, Any]:
        """
        Acquire token using device code flow (for headless scenarios).

        This is useful for:
        - SSH sessions
        - Docker containers
        - CI/CD pipelines
        """
        logger.info("starting_device_code_auth")

        flow = self.app.initiate_device_flow(scopes=self.scopes)

        if "user_code" not in flow:
            logger.error("failed_to_create_device_flow")
            return {}

        # Display device code instructions
        print("\n" + "="*60)
        print("Device Code Authentication")
        print("="*60)
        print(flow["message"])
        print("="*60 + "\n")

        # Wait for user to complete auth on another device
        result = self.app.acquire_token_by_device_flow(flow)

        if "access_token" in result:
            logger.info("device_code_auth_successful")
        else:
            logger.error("device_code_auth_failed", error=result.get("error"))

        return result

    def _acquire_token_app_only(self) -> Dict[str, Any]:
        """
        Acquire token using client credentials flow (application permissions).

        This requires:
        - Client secret configured
        - Application permissions granted
        - Admin consent

        No user interaction required (daemon scenario).
        """
        if not self.client_secret:
            logger.warning("app_only_requires_client_secret")
            return {}

        logger.info("starting_app_only_auth")

        # App-only flow uses /.default scope
        result = self.app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )

        if "access_token" in result:
            logger.info("app_only_auth_successful")
        else:
            logger.error("app_only_auth_failed", error=result.get("error"))

        return result

    def _save_cache(self) -> None:
        """Save token cache to file if configured."""
        if self.cache_file and self.cache.has_state_changed:
            self.cache_file.write_text(self.cache.serialize())
            logger.debug("token_cache_saved", path=str(self.cache_file))

    def clear_cache(self) -> None:
        """Clear token cache (forces re-authentication)."""
        if self.cache_file and self.cache_file.exists():
            self.cache_file.unlink()
        self.cache = msal.SerializableTokenCache()
        logger.info("token_cache_cleared")

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently authenticated account."""
        accounts = self.app.get_accounts()
        if accounts:
            account = accounts[0]
            return {
                "username": account.get("username"),
                "home_account_id": account.get("home_account_id"),
                "environment": account.get("environment"),
                "local_account_id": account.get("local_account_id"),
            }
        return None


def create_authenticator_from_env() -> GraphAuthenticator:
    """
    Create authenticator from environment variables.

    Expected environment variables:
    - GRAPH_CLIENT_ID
    - GRAPH_TENANT_ID
    - GRAPH_CLIENT_SECRET (optional, for app-only)
    - GRAPH_REDIRECT_URI (optional)
    - GRAPH_SCOPES (optional, space-separated)

    Returns:
        GraphAuthenticator instance

    Raises:
        ValueError: If required environment variables are missing
    """
    client_id = os.getenv("GRAPH_CLIENT_ID")
    tenant_id = os.getenv("GRAPH_TENANT_ID")

    if not client_id or not tenant_id:
        raise ValueError(
            "Missing required environment variables: GRAPH_CLIENT_ID, GRAPH_TENANT_ID"
        )

    client_secret = os.getenv("GRAPH_CLIENT_SECRET")
    redirect_uri = os.getenv("GRAPH_REDIRECT_URI", "http://localhost:8000/auth/graph/callback")
    scopes_str = os.getenv("GRAPH_SCOPES", "")
    scopes = scopes_str.split() if scopes_str else None

    # Token cache in user's home directory
    cache_dir = Path.home() / ".local" / "assistant" / "graph"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "token_cache.json"

    return GraphAuthenticator(
        client_id=client_id,
        tenant_id=tenant_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
        cache_file=str(cache_file),
    )
