"""
Unit tests for Email API Routes.

Tests API endpoints following Google OAuth best practices:
- OAuth flow (login, callback)
- Push notification webhook handling
- Email operations (list, sync, search)
- Error handling and validation
"""

import base64
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from memory.models import Email, EmailAccount


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return AsyncMock()


class TestOAuthFlow:
    """Test OAuth authentication flow."""

    @patch('api.routes.email.oauth_manager')
    def test_gmail_login_returns_auth_url(self, mock_oauth, client):
        """Test /auth/gmail/login returns Google authorization URL."""
        mock_oauth.get_auth_url.return_value = 'https://accounts.google.com/o/oauth2/auth?client_id=test'

        response = client.get('/api/email/auth/gmail/login')

        assert response.status_code == 200
        data = response.json()
        assert 'auth_url' in data
        assert 'accounts.google.com' in data['auth_url']
        mock_oauth.get_auth_url.assert_called_once()

    @patch('api.routes.email.oauth_manager')
    def test_gmail_callback_exchanges_code_for_tokens(self, mock_oauth, client):
        """Test OAuth callback exchanges authorization code for tokens."""
        # Mock token exchange
        mock_oauth.exchange_code_for_tokens.return_value = {
            'access_token': 'test-access-token',
            'refresh_token': 'test-refresh-token',
            'expiry': datetime.now(timezone.utc),
        }

        # Mock JWT decode to get email
        with patch('api.routes.email.jwt.decode') as mock_jwt:
            mock_jwt.return_value = {'email': 'test@gmail.com'}

            # Mock store_tokens
            mock_oauth.store_tokens = AsyncMock()

            response = client.post(
                '/api/email/auth/gmail/callback',
                json={'code': 'auth-code-123'}
            )

            assert response.status_code == 200
            data = response.json()
            assert data['success'] == True
            assert data['email'] == 'test@gmail.com'

    @patch('api.routes.email.oauth_manager')
    def test_gmail_callback_handles_invalid_code(self, mock_oauth, client):
        """Test OAuth callback handles invalid authorization code."""
        mock_oauth.exchange_code_for_tokens.side_effect = Exception('Invalid code')

        response = client.post(
            '/api/email/auth/gmail/callback',
            json={'code': 'invalid-code'}
        )

        assert response.status_code == 500
        assert 'Invalid code' in response.json()['detail']


class TestWebhookEndpoint:
    """Test push notification webhook endpoint."""

    @patch('api.routes.email.push_notifications')
    def test_gmail_webhook_receives_pubsub_message(self, mock_push, client):
        """Test webhook receives and decodes Pub/Sub message."""
        # Create mock Pub/Sub message
        notification_data = {
            'emailAddress': 'test@gmail.com',
            'historyId': '12345'
        }
        encoded_data = base64.b64encode(json.dumps(notification_data).encode()).decode()

        pubsub_message = {
            'message': {
                'data': encoded_data,
                'messageId': 'msg-123',
                'publishTime': '2025-11-27T10:00:00Z'
            },
            'subscription': 'projects/test/subscriptions/gmail-notifications-sub'
        }

        mock_push.handle_notification = AsyncMock(return_value={'success': True})

        response = client.post(
            '/api/email/webhooks/gmail',
            json=pubsub_message
        )

        # Webhook must return 200 OK quickly (Pub/Sub requirement)
        assert response.status_code == 200
        assert response.json()['success'] == True

    def test_gmail_webhook_returns_200_on_error(self, client):
        """Test webhook returns 200 even on error (prevents Pub/Sub retry)."""
        # Invalid message format
        response = client.post(
            '/api/email/webhooks/gmail',
            json={'invalid': 'message'}
        )

        # Must still return 200 to prevent retries
        assert response.status_code == 200


class TestEmailListingEndpoints:
    """Test email listing and filtering endpoints."""

    def test_list_accounts(self, client):
        """Test listing connected email accounts."""
        with patch('api.routes.email.get_db') as mock_get_db:
            mock_db = AsyncMock()
            mock_account = EmailAccount(
                email_address='test@gmail.com',
                total_messages=100,
                last_successful_sync=datetime.now(timezone.utc),
                watch_active=1,
                watch_expiry=datetime.now(timezone.utc),
            )
            mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_account]
            mock_get_db.return_value = mock_db

            response = client.get('/api/email/accounts')

            assert response.status_code == 200
            data = response.json()
            assert len(data['accounts']) == 1
            assert data['accounts'][0]['email'] == 'test@gmail.com'
            assert data['accounts'][0]['total_messages'] == 100

    def test_list_emails_with_filters(self, client):
        """Test listing emails with pagination and filters."""
        with patch('api.routes.email.get_db') as mock_get_db:
            mock_db = AsyncMock()
            mock_email = Email(
                id='msg123',
                subject='Test Email',
                sender='sender@example.com',
                snippet='Email snippet',
                date_received=datetime.now(timezone.utc),
                is_read=0,
                fast_category='work',
                fast_priority='high',
            )
            mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_email]
            mock_get_db.return_value = mock_db

            response = client.get('/api/email/emails?limit=50&unread_only=true&account=test@gmail.com')

            assert response.status_code == 200
            data = response.json()
            assert len(data['emails']) == 1
            assert data['emails'][0]['subject'] == 'Test Email'
            assert data['limit'] == 50

    def test_get_email_details(self, client):
        """Test getting full email details with attachments."""
        with patch('api.routes.email.get_db') as mock_get_db:
            mock_db = AsyncMock()

            # Mock email
            mock_email = Email(
                id='msg123',
                thread_id='thread1',
                subject='Test Email',
                sender='sender@example.com',
                recipient='recipient@gmail.com',
                date_received=datetime.now(timezone.utc),
                body_text='Email body text',
                body_html='<p>Email body</p>',
                labels='["INBOX", "UNREAD"]',
                is_read=0,
                fast_category='work',
                fast_priority='high',
            )

            # Mock attachments
            mock_db.execute.side_effect = [
                # First call: get email
                AsyncMock(scalar_one_or_none=AsyncMock(return_value=mock_email)),
                # Second call: get attachments
                AsyncMock(scalars=AsyncMock(return_value=AsyncMock(all=AsyncMock(return_value=[])))),
            ]
            mock_get_db.return_value = mock_db

            response = client.get('/api/email/emails/msg123')

            assert response.status_code == 200
            data = response.json()
            assert data['id'] == 'msg123'
            assert data['subject'] == 'Test Email'
            assert data['body_text'] == 'Email body text'
            assert len(data['labels']) == 2
            assert 'INBOX' in data['labels']

    def test_get_email_not_found(self, client):
        """Test getting non-existent email returns 404."""
        with patch('api.routes.email.get_db') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.execute.return_value.scalar_one_or_none.return_value = None
            mock_get_db.return_value = mock_db

            response = client.get('/api/email/emails/nonexistent')

            assert response.status_code == 404
            assert 'not found' in response.json()['detail']


class TestSyncEndpoints:
    """Test email sync endpoints."""

    @patch('api.routes.email.gmail_client')
    def test_trigger_full_sync(self, mock_client, client):
        """Test triggering full sync for account."""
        mock_client.initial_sync = AsyncMock()

        response = client.post(
            '/api/email/sync',
            json={'email': 'test@gmail.com', 'full_sync': True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] == True
        assert data['sync_type'] == 'full'
        assert data['status'] == 'started'

    @patch('api.routes.email.history_sync')
    def test_trigger_incremental_sync(self, mock_history, client):
        """Test triggering incremental sync returns results."""
        mock_history.sync_incremental = AsyncMock(return_value={
            'success': True,
            'sync_type': 'incremental',
            'emails_added': 5,
            'emails_deleted': 1,
            'labels_updated': 3,
        })

        response = client.post(
            '/api/email/sync',
            json={'email': 'test@gmail.com', 'full_sync': False}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] == True
        assert data['sync_type'] == 'incremental'
        assert data['emails_added'] == 5


class TestPushNotificationManagement:
    """Test push notification management endpoints."""

    @patch('api.routes.email.push_notifications')
    def test_enable_push_notifications(self, mock_push, client):
        """Test enabling push notifications for account."""
        mock_push.setup_pubsub_topic = AsyncMock()
        mock_push.watch_mailbox = AsyncMock(return_value=True)

        response = client.post('/api/email/push/enable/test@gmail.com')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] == True
        assert data['email'] == 'test@gmail.com'
        assert 'enabled' in data['message']

    @patch('api.routes.email.push_notifications')
    def test_enable_push_notifications_failure(self, mock_push, client):
        """Test enabling push notifications handles failure."""
        mock_push.setup_pubsub_topic = AsyncMock()
        mock_push.watch_mailbox = AsyncMock(return_value=False)

        response = client.post('/api/email/push/enable/test@gmail.com')

        assert response.status_code == 500

    @patch('api.routes.email.push_notifications')
    def test_disable_push_notifications(self, mock_push, client):
        """Test disabling push notifications."""
        mock_push.stop_watch = AsyncMock(return_value=True)

        response = client.post('/api/email/push/disable/test@gmail.com')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] == True

    def test_get_push_notification_status(self, client):
        """Test getting push notification status for all accounts."""
        with patch('api.routes.email.get_db') as mock_get_db:
            mock_db = AsyncMock()
            mock_account = EmailAccount(
                email_address='test@gmail.com',
                watch_active=1,
                watch_expiry=datetime.now(timezone.utc),
                watch_error=None,
                watch_last_renewed=datetime.now(timezone.utc),
            )
            mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_account]
            mock_get_db.return_value = mock_db

            response = client.get('/api/email/push/status')

            assert response.status_code == 200
            data = response.json()
            assert len(data['accounts']) == 1
            assert data['accounts'][0]['email'] == 'test@gmail.com'
            assert data['accounts'][0]['watch_active'] == True


class TestAttachmentProcessing:
    """Test attachment processing endpoints."""

    @patch('api.routes.email.document_processor')
    def test_process_email_attachments(self, mock_processor, client):
        """Test triggering attachment processing for email."""
        mock_processor.process_email_with_attachments = AsyncMock()

        response = client.post('/api/email/emails/msg123/process-attachments')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] == True
        assert data['email_id'] == 'msg123'
        assert 'started' in data['message']
