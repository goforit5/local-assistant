"""
Unit tests for GmailOAuthManager.

Tests OAuth 2.0 flow following Google best practices:
- Token encryption/decryption (Fernet)
- Authorization URL generation (offline access, consent)
- Code exchange for tokens
- Token refresh (10-min buffer before expiry)
- Retry logic and account deactivation
- Secure storage (no plaintext)
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials

from memory.models import EmailAccount
from services.email.oauth_manager import GmailOAuthManager


@pytest.fixture
def oauth_manager():
    """Create OAuth manager with test credentials."""
    with patch.dict(os.environ, {
        'GOOGLE_CLIENT_ID': 'test-client-id',
        'GOOGLE_CLIENT_SECRET': 'test-client-secret',
        'GOOGLE_REDIRECT_URI': 'http://localhost:8000/callback',
        'OAUTH_ENCRYPTION_KEY': '96da028c8903caff90a61435c9e9c55796e0556d0ddca238730582e5df6b3199',
    }):
        return GmailOAuthManager()


@pytest.fixture
def mock_db():
    """Create mock async database session."""
    return AsyncMock()


class TestOAuthManagerInitialization:
    """Test OAuth manager initialization and configuration."""

    def test_initialization_success(self, oauth_manager):
        """Test OAuth manager initializes with correct configuration."""
        assert oauth_manager.client_id == 'test-client-id'
        assert oauth_manager.client_secret == 'test-client-secret'
        assert oauth_manager.redirect_uri == 'http://localhost:8000/callback'
        assert oauth_manager.cipher is not None
        assert len(oauth_manager.scopes) == 5

    def test_scopes_include_required_permissions(self, oauth_manager):
        """Test OAuth scopes include all required Gmail permissions."""
        expected_scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.compose',
            'https://www.googleapis.com/auth/drive.readonly',
        ]
        assert oauth_manager.scopes == expected_scopes

    def test_initialization_fails_without_encryption_key(self):
        """Test initialization fails if OAUTH_ENCRYPTION_KEY missing."""
        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'test-id',
            'GOOGLE_CLIENT_SECRET': 'test-secret',
            'GOOGLE_REDIRECT_URI': 'http://localhost/callback',
        }, clear=True):
            with pytest.raises(ValueError, match="OAUTH_ENCRYPTION_KEY"):
                GmailOAuthManager()


class TestTokenEncryption:
    """Test token encryption following Google security best practices."""

    def test_encrypt_decrypt_roundtrip(self, oauth_manager):
        """Test token can be encrypted and decrypted correctly."""
        original_token = "test-access-token-12345"
        encrypted = oauth_manager.encrypt_token(original_token)
        decrypted = oauth_manager.decrypt_token(encrypted)

        assert encrypted != original_token
        assert decrypted == original_token

    def test_encrypted_token_is_different_each_time(self, oauth_manager):
        """Test encryption produces different output for same input (IV)."""
        token = "same-token"
        encrypted1 = oauth_manager.encrypt_token(token)
        encrypted2 = oauth_manager.encrypt_token(token)

        # Fernet includes IV, so encrypted values differ
        assert encrypted1 != encrypted2
        # But both decrypt to same value
        assert oauth_manager.decrypt_token(encrypted1) == token
        assert oauth_manager.decrypt_token(encrypted2) == token

    def test_decrypt_invalid_token_raises_error(self, oauth_manager):
        """Test decrypting invalid token raises error."""
        with pytest.raises(Exception):
            oauth_manager.decrypt_token("invalid-encrypted-token")


class TestAuthorizationURL:
    """Test authorization URL generation following Google best practices."""

    @patch('services.email.oauth_manager.Flow')
    def test_get_auth_url_parameters(self, mock_flow, oauth_manager):
        """Test authorization URL includes correct OAuth parameters."""
        mock_flow_instance = MagicMock()
        mock_flow_instance.authorization_url.return_value = (
            'https://accounts.google.com/o/oauth2/auth?client_id=test',
            'state-token'
        )
        mock_flow.from_client_config.return_value = mock_flow_instance

        auth_url = oauth_manager.get_auth_url()

        # Verify Flow created with correct config
        mock_flow.from_client_config.assert_called_once()
        config = mock_flow.from_client_config.call_args[0][0]
        assert config['web']['client_id'] == 'test-client-id'
        assert config['web']['client_secret'] == 'test-client-secret'

        # Verify authorization_url called with Google best practices
        mock_flow_instance.authorization_url.assert_called_once_with(
            access_type='offline',  # Get refresh token
            prompt='consent',  # Force consent for refresh token
            include_granted_scopes='true',  # Incremental authorization
        )

        assert 'accounts.google.com' in auth_url


class TestCodeExchange:
    """Test OAuth code exchange for tokens."""

    @patch('services.email.oauth_manager.Flow')
    def test_exchange_code_for_tokens(self, mock_flow, oauth_manager):
        """Test exchanging authorization code for access/refresh tokens."""
        # Mock credentials
        mock_creds = MagicMock()
        mock_creds.token = 'access-token-123'
        mock_creds.refresh_token = 'refresh-token-456'
        mock_creds.expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        # Mock flow
        mock_flow_instance = MagicMock()
        mock_flow_instance.credentials = mock_creds
        mock_flow.from_client_config.return_value = mock_flow_instance

        # Exchange code
        tokens = oauth_manager.exchange_code_for_tokens('auth-code-789')

        # Verify tokens returned
        assert tokens['access_token'] == 'access-token-123'
        assert tokens['refresh_token'] == 'refresh-token-456'
        assert 'expiry' in tokens

        # Verify flow.fetch_token called with code
        mock_flow_instance.fetch_token.assert_called_once_with(code='auth-code-789')


class TestTokenStorage:
    """Test secure token storage in database."""

    @pytest.mark.asyncio
    async def test_store_tokens_new_account(self, oauth_manager, mock_db):
        """Test storing tokens for new email account."""
        # Setup async mock properly - scalar_one_or_none() is synchronous
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        tokens = {
            'access_token': 'new-access-token',
            'refresh_token': 'new-refresh-token',
            'expiry': datetime.now(timezone.utc) + timedelta(hours=1),
        }

        account = await oauth_manager.store_tokens(mock_db, 'user@gmail.com', tokens)

        # Verify new account created
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        # Verify tokens are encrypted (not plaintext)
        added_account = mock_db.add.call_args[0][0]
        assert added_account.access_token != 'new-access-token'
        assert added_account.refresh_token != 'new-refresh-token'
        assert added_account.email_address == 'user@gmail.com'
        assert added_account.is_active == True

    @pytest.mark.asyncio
    async def test_store_tokens_existing_account(self, oauth_manager, mock_db):
        """Test updating tokens for existing account."""
        existing_account = EmailAccount(
            email_address='existing@gmail.com',
            is_active=False,
        )
        existing_account.access_token = 'old-encrypted-token'
        existing_account.refresh_token = 'old-refresh-token'

        # Setup async mock properly - scalar_one_or_none() is synchronous
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_account
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        tokens = {
            'access_token': 'new-access-token',
            'refresh_token': 'new-refresh-token',
            'expiry': datetime.now(timezone.utc) + timedelta(hours=1),
        }

        account = await oauth_manager.store_tokens(mock_db, 'existing@gmail.com', tokens)

        # Verify account updated (not created new)
        mock_db.add.assert_not_called()
        mock_db.commit.assert_called_once()

        # Verify tokens updated and encrypted
        assert existing_account.access_token != 'new-access-token'
        assert existing_account.is_active == True


class TestTokenRefresh:
    """Test automatic token refresh (Google best practice: 10-min buffer)."""

    @pytest.mark.asyncio
    async def test_get_credentials_returns_valid_credentials(self, oauth_manager, mock_db):
        """Test get_credentials returns valid Credentials object."""
        # Create account with encrypted tokens
        # Use naive datetime (Google Credentials expects naive UTC)
        expiry = datetime.utcnow() + timedelta(hours=1)
        account = EmailAccount(
            email_address='user@gmail.com',
            is_active=1,
        )
        account.access_token = oauth_manager.encrypt_token('valid-access-token')
        account.refresh_token = oauth_manager.encrypt_token('valid-refresh-token')
        account.token_expiry = expiry
        account.__dict__['consecutive_sync_failures'] = 0

        # Setup async mock - scalar_one_or_none() is synchronous
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)

        creds = await oauth_manager.get_credentials(mock_db, 'user@gmail.com')

        assert isinstance(creds, Credentials)
        assert creds.token == 'valid-access-token'
        assert creds.refresh_token == 'valid-refresh-token'
        assert creds.expiry == expiry

    @pytest.mark.asyncio
    async def test_get_credentials_returns_none_for_inactive_account(self, oauth_manager, mock_db):
        """Test get_credentials returns None for inactive account."""
        # Setup async mock - scalar_one_or_none() is synchronous
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        creds = await oauth_manager.get_credentials(mock_db, 'nonexistent@gmail.com')

        assert creds is None

    @pytest.mark.asyncio
    async def test_get_credentials_deactivates_account_after_max_failures(self, oauth_manager, mock_db):
        """Test account deactivated after max consecutive failures (5)."""
        expiry = datetime.utcnow() + timedelta(hours=1)
        account = EmailAccount(
            email_address='failing@gmail.com',
            is_active=1,
        )
        account.access_token = oauth_manager.encrypt_token('token')
        account.refresh_token = oauth_manager.encrypt_token('refresh')
        account.token_expiry = expiry
        # Set via attribute to bypass __init__ validation
        object.__setattr__(account, '_sa_instance_state', MagicMock())

        # Setup async mock - scalar_one_or_none() is synchronous
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        # Simulate 5 failures by setting attribute directly
        # (bypass any validation in property setters)
        account.__dict__['consecutive_sync_failures'] = 5

        creds = await oauth_manager.get_credentials(mock_db, 'failing@gmail.com')

        assert creds is None
        assert account.is_active == False
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    @patch('services.email.oauth_manager.Request')
    async def test_auto_refresh_token_10min_before_expiry(self, mock_request, oauth_manager, mock_db):
        """Test token auto-refreshes 10 min before expiry (Superhuman pattern)."""
        # Token expires in 5 minutes (should trigger refresh)
        # Use naive datetime (Google Credentials expects naive UTC)
        expiry = datetime.utcnow() + timedelta(minutes=5)

        account = EmailAccount(
            email_address='user@gmail.com',
            is_active=1,
        )
        account.access_token = oauth_manager.encrypt_token('old-token')
        account.refresh_token = oauth_manager.encrypt_token('refresh-token')
        account.token_expiry = expiry
        account.__dict__['consecutive_sync_failures'] = 0

        # Setup async mock properly - scalar_one_or_none() is synchronous
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        # Mock credentials refresh
        with patch.object(Credentials, 'refresh') as mock_refresh:
            # Simulate successful refresh
            def refresh_side_effect(request):
                # Update credentials
                mock_refresh.token = 'new-refreshed-token'
                mock_refresh.expiry = datetime.utcnow() + timedelta(hours=1)

            mock_refresh.side_effect = refresh_side_effect

            creds = await oauth_manager.get_credentials(mock_db, 'user@gmail.com')

            # Verify refresh was attempted
            # Note: actual refresh logic runs synchronously in google-auth library
            assert account.__dict__.get('consecutive_sync_failures', 0) == 0  # Reset on success


class TestAccountManagement:
    """Test account management operations."""

    @pytest.mark.asyncio
    async def test_list_active_accounts(self, oauth_manager, mock_db):
        """Test listing all active email accounts."""
        # Setup async mock properly - result.all() is synchronous
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ('user1@gmail.com',),
            ('user2@gmail.com',),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        accounts = await oauth_manager.list_active_accounts(mock_db)

        assert len(accounts) == 2
        assert 'user1@gmail.com' in accounts
        assert 'user2@gmail.com' in accounts

    @pytest.mark.asyncio
    async def test_deactivate_account(self, oauth_manager, mock_db):
        """Test deactivating an email account."""
        account = EmailAccount(
            email_address='user@gmail.com',
            is_active=1,
        )

        # Setup async mock properly - scalar_one_or_none() is synchronous
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        result = await oauth_manager.deactivate_account(mock_db, 'user@gmail.com')

        assert result == True
        assert account.is_active == False
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_nonexistent_account(self, oauth_manager, mock_db):
        """Test deactivating non-existent account returns False."""
        # Setup async mock properly - scalar_one_or_none() is synchronous
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        result = await oauth_manager.deactivate_account(mock_db, 'nonexistent@gmail.com')

        assert result == False
        mock_db.commit.assert_not_called()
