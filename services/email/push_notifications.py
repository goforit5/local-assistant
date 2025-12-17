"""
Gmail Push Notifications via Google Cloud Pub/Sub.

Enables Superhuman-grade instant email delivery (1-2 seconds vs 30s polling).
Watches expire after 7 days and must be renewed.

Reference: https://developers.google.com/gmail/api/guides/push
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.cloud import pubsub_v1
from google.iam.v1 import policy_pb2
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.models import EmailAccount
from services.email.gmail_client import GmailClient
from services.email.history_sync import GmailHistorySync

logger = logging.getLogger(__name__)


class GmailPushNotifications:
    """
    Manages Gmail push notifications for instant email delivery.

    Features:
    - Google Cloud Pub/Sub integration
    - Automatic watch setup with Gmail API
    - Watch renewal (7 day expiry)
    - Instant incremental sync on notification
    """

    def __init__(self):
        """Initialize push notifications with Pub/Sub client."""
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        self.topic_name = os.getenv("PUBSUB_TOPIC_NAME", "gmail-notifications")
        self.subscription_name = os.getenv("PUBSUB_SUBSCRIPTION_NAME", "gmail-notifications-sub")
        self.webhook_url = os.getenv("WEBHOOK_URL")

        self.gmail_client = GmailClient()
        self.history_sync = GmailHistorySync()

        # Watch settings
        self.watch_duration_days = 7  # Gmail maximum
        self.renewal_hours_before_expiry = int(
            os.getenv("WATCH_RENEWAL_HOURS_BEFORE_EXPIRY", "24")
        )

        # Initialize Pub/Sub publisher
        try:
            self.publisher = pubsub_v1.PublisherClient()
            self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)
        except Exception as e:
            logger.warning(f"Could not initialize Pub/Sub client: {e}")
            self.publisher = None

    async def setup_pubsub_topic(self) -> bool:
        """
        Create Pub/Sub topic and grant Gmail API permissions.

        Returns:
            True if topic exists or was created
        """
        if not self.publisher:
            logger.error("Pub/Sub publisher not initialized")
            return False

        try:
            # Check if topic exists
            try:
                self.publisher.get_topic(topic=self.topic_path)
                logger.info(f"Pub/Sub topic exists: {self.topic_path}")
                return True
            except Exception:
                # Create topic
                logger.info(f"Creating Pub/Sub topic: {self.topic_path}")
                self.publisher.create_topic(request={"name": self.topic_path})

                # Grant publish permission to Gmail service account
                policy = self.publisher.get_iam_policy(request={"resource": self.topic_path})
                binding = policy_pb2.Binding(
                    role="roles/pubsub.publisher",
                    members=["serviceAccount:gmail-api-push@system.gserviceaccount.com"],
                )
                policy.bindings.append(binding)
                self.publisher.set_iam_policy(
                    request={"resource": self.topic_path, "policy": policy}
                )

                logger.info(f"Created topic and granted permissions: {self.topic_path}")
                return True

        except Exception as e:
            logger.error(f"Failed to setup Pub/Sub topic: {e}")
            return False

    async def watch_mailbox(
        self,
        db: AsyncSession,
        email: str,
    ) -> bool:
        """
        Register Gmail watch for push notifications.

        Args:
            db: Async database session
            email: Gmail email address

        Returns:
            True if watch setup successfully
        """
        try:
            # Get Gmail service
            service = await self.gmail_client.get_gmail_service(db, email)

            # Create watch request
            request = {
                'labelIds': ['INBOX'],  # Watch inbox (can add more labels)
                'topicName': f'projects/{self.project_id}/topics/{self.topic_name}',
            }

            # Call Gmail API watch
            watch_response = service.users().watch(userId='me', body=request).execute()

            # Parse response
            history_id = watch_response.get('historyId')
            expiration = int(watch_response.get('expiration', 0))
            expiry_datetime = datetime.fromtimestamp(expiration / 1000.0, tz=timezone.utc)

            # Update database
            result = await db.execute(
                select(EmailAccount).where(EmailAccount.email_address == email)
            )
            account = result.scalar_one_or_none()

            if not account:
                logger.error(f"EmailAccount not found for {email}")
                return False

            account.watch_active = True
            account.watch_expiry = expiry_datetime
            account.pubsub_topic_name = self.topic_name
            account.history_id = history_id
            account.watch_error = None
            account.watch_last_renewed = datetime.now(timezone.utc)

            await db.commit()

            logger.info(f"Watch enabled for {email}, expires: {expiry_datetime}")
            return True

        except Exception as e:
            logger.error(f"Failed to setup watch for {email}: {e}")

            # Store error
            result = await db.execute(
                select(EmailAccount).where(EmailAccount.email_address == email)
            )
            account = result.scalar_one_or_none()

            if account:
                account.watch_active = False
                account.watch_error = str(e)
                await db.commit()

            return False

    async def renew_watch(self, db: AsyncSession, email: str) -> bool:
        """
        Renew watch for email account.

        Args:
            db: Async database session
            email: Gmail email address

        Returns:
            True if renewed successfully
        """
        logger.info(f"Renewing watch for {email}")
        return await self.watch_mailbox(db, email)

    async def stop_watch(self, db: AsyncSession, email: str) -> bool:
        """
        Stop push notifications for email account.

        Args:
            db: Async database session
            email: Gmail email address

        Returns:
            True if stopped successfully
        """
        try:
            service = await self.gmail_client.get_gmail_service(db, email)
            service.users().stop(userId='me').execute()

            # Update database
            result = await db.execute(
                select(EmailAccount).where(EmailAccount.email_address == email)
            )
            account = result.scalar_one_or_none()

            if account:
                account.watch_active = False
                account.watch_expiry = None
                await db.commit()

            logger.info(f"Watch stopped for {email}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop watch for {email}: {e}")
            return False

    async def handle_notification(
        self,
        db: AsyncSession,
        message_data: dict,
    ) -> Optional[dict]:
        """
        Process incoming Pub/Sub notification and trigger incremental sync.

        Args:
            db: Async database session
            message_data: Decoded Pub/Sub message

        Returns:
            Sync result dict or None
        """
        try:
            # Extract email and historyId
            email_address = message_data.get('emailAddress')
            history_id = message_data.get('historyId')

            if not email_address or not history_id:
                logger.warning(f"Invalid notification: {message_data}")
                return None

            logger.info(f"Notification for {email_address}, historyId: {history_id}")

            # Trigger incremental sync
            sync_result = await self.history_sync.sync_incremental(db, email_address)

            if not sync_result.get('success'):
                logger.error(f"Incremental sync failed: {sync_result}")

            return sync_result

        except Exception as e:
            logger.error(f"Failed to handle notification: {e}")
            return None

    async def get_accounts_needing_renewal(
        self,
        db: AsyncSession,
    ) -> list[str]:
        """
        Get list of accounts with watches expiring soon.

        Args:
            db: Async database session

        Returns:
            List of email addresses needing renewal
        """
        # Calculate cutoff time (24 hours from now by default)
        cutoff = datetime.now(timezone.utc) + timedelta(hours=self.renewal_hours_before_expiry)

        result = await db.execute(
            select(EmailAccount.email_address).where(
                EmailAccount.watch_active == 1,
                EmailAccount.watch_expiry <= cutoff,
            )
        )

        return [row[0] for row in result.all()]

    async def renew_all_watches(self, db: AsyncSession) -> dict:
        """
        Renew all watches that are expiring soon.

        Args:
            db: Async database session

        Returns:
            Dict with renewal counts
        """
        accounts = await self.get_accounts_needing_renewal(db)
        results = {'renewed': 0, 'failed': 0}

        for email in accounts:
            if await self.renew_watch(db, email):
                results['renewed'] += 1
            else:
                results['failed'] += 1

        logger.info(f"Watch renewal complete: {results}")
        return results


# Standalone functions for easy import

async def enable_push_notifications(db: AsyncSession, email: str) -> bool:
    """One-line function to enable push notifications."""
    push = GmailPushNotifications()
    await push.setup_pubsub_topic()
    return await push.watch_mailbox(db, email)


async def disable_push_notifications(db: AsyncSession, email: str) -> bool:
    """One-line function to disable push notifications."""
    push = GmailPushNotifications()
    return await push.stop_watch(db, email)


async def renew_all_watches(db: AsyncSession) -> dict:
    """Renew all expiring watches."""
    push = GmailPushNotifications()
    return await push.renew_all_watches(db)
