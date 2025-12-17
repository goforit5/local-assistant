"""
Gmail OAuth 2.0 Manager with Token Encryption.

Handles OAuth flow, token storage with Fernet encryption, and automatic refresh.
Based on Superhuman's persistent auth strategy.
"""

import base64
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.models import EmailAccount


class GmailOAuthManager:
    """
    Manages Gmail OAuth 2.0 authentication with encrypted token storage.

    Features:
    - Fernet encryption for access/refresh tokens
    - Automatic token refresh (10 min before expiry)
    - Retry logic with max attempts
    - Account deactivation on repeated failures
    """

    def __init__(self):
        """Initialize OAuth manager with Google credentials and encryption."""
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

        # Setup Fernet encryption for tokens
        key = os.getenv("OAUTH_ENCRYPTION_KEY")
        if not key:
            raise ValueError("OAUTH_ENCRYPTION_KEY environment variable required")

        # Convert hex key to Fernet format
        key_bytes = bytes.fromhex(key)
        self.cipher = Fernet(base64.urlsafe_b64encode(key_bytes))

        # Gmail API scopes (read, modify, send, compose + Drive for attachments)
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.compose',
            'https://www.googleapis.com/auth/drive.readonly',
        ]

    def get_auth_url(self) -> str:
        """
        Generate OAuth authorization URL for user consent.

        Returns:
            Authorization URL for user to visit
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uris": [self.redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=self.scopes,
        )
        flow.redirect_uri = self.redirect_uri

        auth_url, _ = flow.authorization_url(
            access_type='offline',  # Get refresh token
            prompt='consent',  # Force consent to get refresh token
            include_granted_scopes='true',
        )
        return auth_url

    def exchange_code_for_tokens(self, code: str) -> dict:
        """
        Exchange authorization code for access/refresh tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Dict with access_token, refresh_token, expiry
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uris": [self.redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=self.scopes,
        )
        flow.redirect_uri = self.redirect_uri

        flow.fetch_token(code=code)
        creds = flow.credentials

        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "expiry": creds.expiry,
        }

    def encrypt_token(self, token: str) -> str:
        """Encrypt token using Fernet."""
        return self.cipher.encrypt(token.encode()).decode()

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt token using Fernet."""
        return self.cipher.decrypt(encrypted_token.encode()).decode()

    async def store_tokens(
        self,
        db: AsyncSession,
        email: str,
        tokens: dict,
    ) -> EmailAccount:
        """
        Store or update OAuth tokens for an email account.

        Args:
            db: Async database session
            email: Gmail email address
            tokens: Dict with access_token, refresh_token, expiry

        Returns:
            Updated EmailAccount instance
        """
        # Query for existing account
        result = await db.execute(
            select(EmailAccount).where(EmailAccount.email_address == email)
        )
        account = result.scalar_one_or_none()

        if not account:
            # Create new account
            account = EmailAccount(
                email_address=email,
                is_active=True,
            )
            db.add(account)

        # Encrypt and store tokens
        account.access_token = self.encrypt_token(tokens["access_token"])
        if tokens.get("refresh_token"):
            account.refresh_token = self.encrypt_token(tokens["refresh_token"])
        account.token_expiry = tokens.get("expiry")
        account.is_active = True
        account.consecutive_sync_failures = 0  # Reset on successful auth

        await db.commit()
        await db.refresh(account)
        return account

    async def get_credentials(
        self,
        db: AsyncSession,
        email: str,
    ) -> Optional[Credentials]:
        """
        Get Google Credentials for an email account with auto-refresh.

        Args:
            db: Async database session
            email: Gmail email address

        Returns:
            Google Credentials object or None if account not found/inactive
        """
        # Query for active account
        result = await db.execute(
            select(EmailAccount).where(
                EmailAccount.email_address == email,
                EmailAccount.is_active == 1,  # SQLite boolean
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            return None

        # Check if we've exceeded max refresh attempts
        if account.consecutive_sync_failures >= 5:
            print(f"Account {email} exceeded max failures, needs re-auth")
            account.is_active = False
            await db.commit()
            return None

        # Decrypt tokens
        access_token = self.decrypt_token(account.access_token)
        refresh_token = (
            self.decrypt_token(account.refresh_token)
            if account.refresh_token
            else None
        )

        # Create credentials object
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            expiry=account.token_expiry,
        )

        # Auto-refresh if needed (Superhuman-style: refresh 10 min before expiry)
        should_refresh = False
        if creds.expired:
            should_refresh = True
        elif creds.expiry:
            # Make expiry timezone-aware if it isn't
            expiry = creds.expiry
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)

            time_until_expiry = expiry - datetime.now(timezone.utc)
            if time_until_expiry.total_seconds() < 600:  # 10 minutes
                should_refresh = True

        if should_refresh and creds.refresh_token:
            try:
                print(f"Auto-refreshing token for {email}")
                creds.refresh(Request())

                # Update stored tokens
                account.access_token = self.encrypt_token(creds.token)
                account.token_expiry = creds.expiry
                account.consecutive_sync_failures = 0  # Reset on success

                await db.commit()
                print(f"Successfully refreshed token for {email}")
            except Exception as e:
                print(f"Token refresh failed for {email}: {e}")
                account.consecutive_sync_failures += 1
                await db.commit()

                if account.consecutive_sync_failures >= 5:
                    print(f"Max refresh attempts reached for {email}, deactivating")
                    account.is_active = False
                    await db.commit()
                    return None

        return creds

    async def list_active_accounts(self, db: AsyncSession) -> list[str]:
        """
        List all active email accounts.

        Args:
            db: Async database session

        Returns:
            List of email addresses
        """
        result = await db.execute(
            select(EmailAccount.email_address).where(EmailAccount.is_active == 1)
        )
        return [row[0] for row in result.all()]

    async def deactivate_account(self, db: AsyncSession, email: str) -> bool:
        """
        Deactivate an email account.

        Args:
            db: Async database session
            email: Email address to deactivate

        Returns:
            True if account was deactivated, False if not found
        """
        result = await db.execute(
            select(EmailAccount).where(EmailAccount.email_address == email)
        )
        account = result.scalar_one_or_none()

        if not account:
            return False

        account.is_active = False
        await db.commit()
        return True
