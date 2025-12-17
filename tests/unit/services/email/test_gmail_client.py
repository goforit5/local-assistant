"""
Unit tests for GmailClient.

Tests Gmail API usage following Google best practices:
- Partial response optimization (50-70% bandwidth reduction)
- format=metadata usage (2 units vs 5 units)
- Proper error handling (429 rate limiting, 401 auth)
- Quota-efficient API calls
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from memory.models import Email, EmailAccount
from services.email.gmail_client import GmailClient


@pytest.fixture
def gmail_client():
    """Create Gmail client instance."""
    with patch.dict(os.environ, {
        'GOOGLE_CLIENT_ID': 'test-client-id',
        'GOOGLE_CLIENT_SECRET': 'test-client-secret',
        'GOOGLE_REDIRECT_URI': 'http://localhost:8000/callback',
        'OAUTH_ENCRYPTION_KEY': '96da028c8903caff90a61435c9e9c55796e0556d0ddca238730582e5df6b3199',
    }):
        return GmailClient()


@pytest.fixture
def mock_db():
    """Create mock async database session."""
    return AsyncMock()


@pytest.fixture
def mock_gmail_service():
    """Create mock Gmail API service."""
    service = MagicMock()
    # Setup nested mock structure for Gmail API
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        'messages': [],
        'resultSizeEstimate': 0
    }
    return service


class TestGmailClientInitialization:
    """Test Gmail client initialization."""

    def test_initialization(self, gmail_client):
        """Test Gmail client initializes with correct settings."""
        assert gmail_client.batch_size == 50
        assert gmail_client.use_partial_response == True  # Always use optimization
        assert gmail_client.push_enabled in [True, False]  # Based on env

    def test_redis_url_from_env(self):
        """Test Redis URL comes from environment."""
        with patch.dict('os.environ', {'REDIS_URL': 'redis://custom:6380/1'}):
            client = GmailClient()
            assert client.redis_url == 'redis://custom:6380/1'


class TestPartialResponseOptimization:
    """Test partial response optimization (Google best practice)."""

    @pytest.mark.asyncio
    async def test_initial_sync_uses_partial_response(self, gmail_client, mock_db):
        """Test initial sync uses fields parameter for 50-70% bandwidth reduction."""
        mock_service = MagicMock()

        # Mock OAuth credentials
        with patch.object(gmail_client, 'get_gmail_service', return_value=mock_service):
            # Mock Redis
            with patch('services.email.gmail_client.redis_from_url') as mock_redis:
                mock_redis_instance = AsyncMock()
                mock_redis.return_value = mock_redis_instance

                # Mock messages.list response
                mock_request = MagicMock()
                mock_request.uri = 'https://gmail.googleapis.com/gmail/v1/users/me/messages'
                mock_request.execute.return_value = {
                    'messages': [
                        {'id': 'msg1', 'threadId': 'thread1', 'historyId': '12345'},
                        {'id': 'msg2', 'threadId': 'thread2', 'historyId': '12346'},
                    ],
                    'resultSizeEstimate': 2
                }
                mock_service.users().messages().list.return_value = mock_request

                # Mock account query
                mock_account = EmailAccount(email_address='test@gmail.com')
                mock_db.execute.return_value.scalar_one_or_none.return_value = mock_account

                count = await gmail_client.initial_sync(mock_db, 'test@gmail.com', max_results=500)

                # Verify partial response fields added to URI
                assert 'fields=' in mock_request.uri
                expected_fields = 'messages(id,threadId,historyId),nextPageToken,resultSizeEstimate'
                assert expected_fields in mock_request.uri

                assert count == 2

    @pytest.mark.asyncio
    async def test_fetch_message_uses_metadata_format(self, gmail_client, mock_db):
        """Test fetch_message_details uses format=metadata (2 units vs 5 units)."""
        mock_service = MagicMock()

        with patch.object(gmail_client, 'get_gmail_service', return_value=mock_service):
            # Mock message.get response
            mock_request = MagicMock()
            mock_request.uri = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/msg123'
            mock_request.execute.return_value = {
                'id': 'msg123',
                'threadId': 'thread1',
                'labelIds': ['INBOX', 'UNREAD'],
                'snippet': 'Test email snippet',
                'payload': {
                    'headers': [
                        {'name': 'From', 'value': 'sender@example.com'},
                        {'name': 'To', 'value': 'recipient@gmail.com'},
                        {'name': 'Subject', 'value': 'Test Subject'},
                        {'name': 'Date', 'value': 'Mon, 27 Nov 2025 10:00:00 +0000'},
                    ]
                },
                'historyId': '12345',
            }
            mock_service.users().messages().get.return_value = mock_request

            email_data = await gmail_client.fetch_message_details(mock_db, 'test@gmail.com', 'msg123')

            # Verify format=metadata used
            call_args = mock_service.users().messages().get.call_args
            assert call_args[1]['format'] == 'metadata'

            # Verify specific headers requested (optimization)
            assert 'metadataHeaders' in call_args[1]
            assert 'From' in call_args[1]['metadataHeaders']

            # Verify fields parameter added
            assert 'fields=' in mock_request.uri

            # Verify email data parsed correctly
            assert email_data['id'] == 'msg123'
            assert email_data['sender'] == 'sender@example.com'
            assert email_data['subject'] == 'Test Subject'
            assert email_data['is_read'] == False  # UNREAD in labels


class TestEmailStorage:
    """Test email storage in database."""

    @pytest.mark.asyncio
    async def test_store_email_creates_new_record(self, gmail_client, mock_db):
        """Test storing new email creates database record."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        email_data = {
            'id': 'new-msg-id',
            'thread_id': 'thread-123',
            'account_email': 'user@gmail.com',
            'subject': 'Test Email',
            'sender': 'sender@example.com',
            'recipient': 'user@gmail.com',
            'snippet': 'Test snippet',
            'date_received': datetime.now(timezone.utc),
            'labels': json.dumps(['INBOX']),
            'is_read': False,
        }

        email = await gmail_client.store_email(mock_db, email_data)

        # Verify new email added
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_email_updates_existing_record(self, gmail_client, mock_db):
        """Test storing existing email updates record (not creates duplicate)."""
        existing_email = Email(
            id='existing-msg-id',
            thread_id='thread-123',
            account_email='user@gmail.com',
            subject='Old Subject',
            sender='sender@example.com',
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = existing_email

        email_data = {
            'id': 'existing-msg-id',
            'subject': 'Updated Subject',
            'is_read': True,
        }

        email = await gmail_client.store_email(mock_db, email_data)

        # Verify no new email added (update only)
        mock_db.add.assert_not_called()
        mock_db.commit.assert_called_once()

        # Verify fields updated
        assert existing_email.subject == 'Updated Subject'
        assert existing_email.is_read == True


class TestAccountManagement:
    """Test account management operations."""

    @pytest.mark.asyncio
    async def test_list_active_accounts(self, gmail_client, mock_db):
        """Test listing active accounts."""
        mock_oauth = AsyncMock()
        mock_oauth.list_active_accounts.return_value = ['user1@gmail.com', 'user2@gmail.com']

        with patch.object(gmail_client, 'oauth_manager', mock_oauth):
            accounts = await gmail_client.list_active_accounts(mock_db)

            assert len(accounts) == 2
            assert 'user1@gmail.com' in accounts


class TestErrorHandling:
    """Test error handling for various Gmail API errors."""

    @pytest.mark.asyncio
    async def test_initial_sync_handles_api_error(self, gmail_client, mock_db):
        """Test initial sync handles Gmail API HttpError."""
        mock_service = MagicMock()

        with patch.object(gmail_client, 'get_gmail_service', return_value=mock_service):
            # Simulate API error
            http_error = HttpError(
                resp=MagicMock(status=429),  # Rate limit
                content=b'Rate limit exceeded'
            )
            mock_service.users().messages().list.return_value.execute.side_effect = http_error

            with pytest.raises(HttpError) as exc_info:
                await gmail_client.initial_sync(mock_db, 'test@gmail.com')

            assert exc_info.value.resp.status == 429

    @pytest.mark.asyncio
    async def test_fetch_message_returns_none_on_error(self, gmail_client, mock_db):
        """Test fetch_message_details returns None on error (not crash)."""
        mock_service = MagicMock()

        with patch.object(gmail_client, 'get_gmail_service', return_value=mock_service):
            # Simulate 404 error (message not found)
            http_error = HttpError(
                resp=MagicMock(status=404),
                content=b'Message not found'
            )
            mock_service.users().messages().get.return_value.execute.side_effect = http_error

            result = await gmail_client.fetch_message_details(mock_db, 'test@gmail.com', 'nonexistent')

            assert result is None  # Graceful error handling


class TestMessageBodyFetching:
    """Test fetching full message body (text + HTML)."""

    @pytest.mark.asyncio
    async def test_fetch_message_body_decodes_base64(self, gmail_client, mock_db):
        """Test message body decoding from base64url format."""
        import base64

        mock_service = MagicMock()

        with patch.object(gmail_client, 'get_gmail_service', return_value=mock_service):
            # Create base64url encoded body
            text_body = "This is plain text email body"
            html_body = "<p>This is HTML email body</p>"
            encoded_text = base64.urlsafe_b64encode(text_body.encode()).decode()
            encoded_html = base64.urlsafe_b64encode(html_body.encode()).decode()

            # Mock full message response
            mock_service.users().messages().get.return_value.execute.return_value = {
                'id': 'msg123',
                'payload': {
                    'parts': [
                        {
                            'mimeType': 'text/plain',
                            'body': {'data': encoded_text}
                        },
                        {
                            'mimeType': 'text/html',
                            'body': {'data': encoded_html}
                        }
                    ]
                }
            }

            body = await gmail_client.fetch_message_body(mock_db, 'test@gmail.com', 'msg123')

            assert body['body_text'] == text_body
            assert body['body_html'] == html_body

    @pytest.mark.asyncio
    async def test_fetch_message_body_handles_single_part(self, gmail_client, mock_db):
        """Test fetching body for single-part (non-multipart) message."""
        import base64

        mock_service = MagicMock()

        with patch.object(gmail_client, 'get_gmail_service', return_value=mock_service):
            text_body = "Simple text email"
            encoded_text = base64.urlsafe_b64encode(text_body.encode()).decode()

            # Single-part message (no parts array)
            mock_service.users().messages().get.return_value.execute.return_value = {
                'id': 'msg123',
                'payload': {
                    'mimeType': 'text/plain',
                    'body': {'data': encoded_text}
                }
            }

            body = await gmail_client.fetch_message_body(mock_db, 'test@gmail.com', 'msg123')

            assert body['body_text'] == text_body
            assert body['body_html'] is None


class TestPushNotificationIntegration:
    """Test push notification integration."""

    @pytest.mark.asyncio
    async def test_enable_push_notifications_when_enabled(self, gmail_client, mock_db):
        """Test enabling push notifications when feature enabled."""
        gmail_client.push_enabled = True

        with patch('services.email.gmail_client.GmailPushNotifications') as mock_push_class:
            mock_push = AsyncMock()
            mock_push.watch_mailbox.return_value = True
            mock_push_class.return_value = mock_push

            result = await gmail_client.enable_push_notifications(mock_db, 'test@gmail.com')

            assert result == True
            mock_push.watch_mailbox.assert_called_once_with(mock_db, 'test@gmail.com')

    @pytest.mark.asyncio
    async def test_enable_push_notifications_when_disabled(self, gmail_client, mock_db):
        """Test enabling push notifications returns False when feature disabled."""
        gmail_client.push_enabled = False

        result = await gmail_client.enable_push_notifications(mock_db, 'test@gmail.com')

        assert result == False
