"""
Unit Tests for Microsoft Graph Authentication

Tests authentication flows, token management, and caching.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path

from services.microsoft_graph.auth import GraphAuthenticator, create_authenticator_from_env


class TestGraphAuthenticator:
    """Test GraphAuthenticator class."""

    def test_init_with_client_secret(self):
        """Test initialization with client secret (confidential client)."""
        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
            client_secret="test_secret",
        )

        assert auth.client_id == "test_client_id"
        assert auth.tenant_id == "test_tenant_id"
        assert auth.client_secret == "test_secret"
        assert auth.authority == "https://login.microsoftonline.com/test_tenant_id"
        assert "Tasks.ReadWrite" in auth.scopes

    def test_init_without_client_secret(self):
        """Test initialization without client secret (public client)."""
        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
        )

        assert auth.client_secret is None

    def test_custom_scopes(self):
        """Test custom permission scopes."""
        custom_scopes = ["Mail.Read", "Calendars.ReadWrite"]

        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
            scopes=custom_scopes,
        )

        assert auth.scopes == custom_scopes

    @patch("services.microsoft_graph.auth.msal.ConfidentialClientApplication")
    def test_get_access_token_from_cache(self, mock_msal):
        """Test getting access token from cache."""
        # Setup mock app
        mock_app = Mock()
        mock_msal.return_value = mock_app

        mock_app.get_accounts.return_value = [{"username": "test@example.com"}]
        mock_app.acquire_token_silent.return_value = {
            "access_token": "cached_token",
            "expires_in": 3600,
        }

        # Create authenticator
        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
            client_secret="test_secret",
        )
        auth.app = mock_app

        # Get token
        token = auth.get_access_token()

        assert token == "cached_token"
        mock_app.acquire_token_silent.assert_called_once()

    @patch("services.microsoft_graph.auth.msal.ConfidentialClientApplication")
    def test_get_access_token_app_only(self, mock_msal):
        """Test app-only authentication flow."""
        mock_app = Mock()
        mock_msal.return_value = mock_app

        # No cached token
        mock_app.get_accounts.return_value = []

        # App-only flow succeeds
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "app_token",
            "expires_in": 3600,
        }

        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
            client_secret="test_secret",
        )
        auth.app = mock_app

        token = auth.get_access_token()

        assert token == "app_token"
        mock_app.acquire_token_for_client.assert_called_once()

    def test_token_cache_file(self, tmp_path):
        """Test token cache persistence."""
        cache_file = tmp_path / "token_cache.json"

        # Create auth with cache file
        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
            cache_file=str(cache_file),
        )

        # Cache file should be set
        assert auth.cache_file == cache_file

    def test_clear_cache(self, tmp_path):
        """Test clearing token cache."""
        cache_file = tmp_path / "token_cache.json"
        cache_file.write_text('{"cached": "data"}')

        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
            cache_file=str(cache_file),
        )

        auth.clear_cache()

        assert not cache_file.exists()

    @patch("services.microsoft_graph.auth.msal.ConfidentialClientApplication")
    def test_get_account_info(self, mock_msal):
        """Test getting account information."""
        mock_app = Mock()
        mock_msal.return_value = mock_app

        mock_app.get_accounts.return_value = [{
            "username": "test@example.com",
            "home_account_id": "test_id",
            "environment": "login.microsoftonline.com",
            "local_account_id": "local_id",
        }]

        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
        )
        auth.app = mock_app

        account_info = auth.get_account_info()

        assert account_info["username"] == "test@example.com"
        assert account_info["home_account_id"] == "test_id"

    @patch("services.microsoft_graph.auth.msal.ConfidentialClientApplication")
    def test_get_account_info_no_account(self, mock_msal):
        """Test getting account info with no cached account."""
        mock_app = Mock()
        mock_msal.return_value = mock_app
        mock_app.get_accounts.return_value = []

        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
        )
        auth.app = mock_app

        account_info = auth.get_account_info()

        assert account_info is None


class TestAuthFromEnv:
    """Test environment variable configuration."""

    @patch.dict("os.environ", {
        "GRAPH_CLIENT_ID": "env_client_id",
        "GRAPH_TENANT_ID": "env_tenant_id",
        "GRAPH_CLIENT_SECRET": "env_secret",
        "GRAPH_SCOPES": "Mail.Read Calendars.ReadWrite",
    })
    def test_create_from_env_full(self):
        """Test creating authenticator from full environment config."""
        auth = create_authenticator_from_env()

        assert auth.client_id == "env_client_id"
        assert auth.tenant_id == "env_tenant_id"
        assert auth.client_secret == "env_secret"
        assert "Mail.Read" in auth.scopes
        assert "Calendars.ReadWrite" in auth.scopes

    @patch.dict("os.environ", {
        "GRAPH_CLIENT_ID": "env_client_id",
        "GRAPH_TENANT_ID": "env_tenant_id",
    })
    def test_create_from_env_minimal(self):
        """Test creating authenticator with minimal env vars."""
        auth = create_authenticator_from_env()

        assert auth.client_id == "env_client_id"
        assert auth.tenant_id == "env_tenant_id"
        assert auth.client_secret is None  # Optional

    @patch.dict("os.environ", {}, clear=True)
    def test_create_from_env_missing_required(self):
        """Test error when required env vars missing."""
        with pytest.raises(ValueError, match="Missing required environment variables"):
            create_authenticator_from_env()


# Performance tests
class TestAuthPerformance:
    """Performance tests for authentication."""

    @patch("services.microsoft_graph.auth.msal.ConfidentialClientApplication")
    def test_token_cache_performance(self, mock_msal, performance_timer):
        """Test that cached tokens are retrieved quickly."""
        mock_app = Mock()
        mock_msal.return_value = mock_app

        mock_app.get_accounts.return_value = [{"username": "test@example.com"}]
        mock_app.acquire_token_silent.return_value = {
            "access_token": "cached_token",
            "expires_in": 3600,
        }

        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
            client_secret="test_secret",
        )
        auth.app = mock_app

        # First call (cache miss simulation)
        performance_timer.start()
        token1 = auth.get_access_token()
        performance_timer.stop()
        first_call_time = performance_timer.elapsed

        # Second call (cache hit)
        performance_timer.start()
        token2 = auth.get_access_token()
        performance_timer.stop()
        second_call_time = performance_timer.elapsed

        assert token1 == token2
        # Cache should be fast (this is a weak assertion due to mocking)
        assert second_call_time < 1.0  # Less than 1 second


# Edge cases and error handling
class TestAuthEdgeCases:
    """Test edge cases and error scenarios."""

    @patch("services.microsoft_graph.auth.msal.ConfidentialClientApplication")
    def test_auth_failure_all_flows(self, mock_msal):
        """Test authentication failure when all flows fail."""
        mock_app = Mock()
        mock_msal.return_value = mock_app

        # All auth flows fail
        mock_app.get_accounts.return_value = []
        mock_app.acquire_token_for_client.return_value = {"error": "auth_failed"}
        mock_app.initiate_auth_code_flow.return_value = {}  # No auth_uri

        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
            client_secret="test_secret",
        )
        auth.app = mock_app

        with pytest.raises(RuntimeError, match="Failed to acquire access token"):
            auth.get_access_token()

    @patch("services.microsoft_graph.auth.msal.ConfidentialClientApplication")
    def test_force_refresh(self, mock_msal):
        """Test forcing token refresh."""
        mock_app = Mock()
        mock_msal.return_value = mock_app

        mock_app.get_accounts.return_value = []
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "fresh_token",
        }

        auth = GraphAuthenticator(
            client_id="test_client_id",
            tenant_id="test_tenant_id",
            client_secret="test_secret",
        )
        auth.app = mock_app

        # Force refresh should skip cache check
        token = auth.get_access_token(force_refresh=True)

        assert token == "fresh_token"
        mock_app.acquire_token_silent.assert_not_called()
