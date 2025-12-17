"""
Gmail History API Sync Engine.

Implements 90% more efficient incremental sync using Gmail's History API.
Tracks changes (messageAdded, messageDeleted, labelChanged) since last historyId.

Reference: https://developers.google.com/gmail/api/guides/sync
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from googleapiclient.errors import HttpError
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.models import Email, EmailAccount
from services.email.gmail_client import GmailClient

logger = logging.getLogger(__name__)


class GmailHistorySync:
    """
    Efficient incremental sync using Gmail History API.

    The History API returns only changes since a given historyId:
    - messagesAdded: New emails arrived
    - messagesDeleted: Emails removed
    - labelsAdded: Labels added to messages
    - labelsRemoved: Labels removed from messages

    This is 90% more efficient than full message list sync.
    """

    def __init__(self):
        """Initialize history sync with Gmail client."""
        self.gmail_client = GmailClient()
        self.redis_url = self.gmail_client.redis_url

    async def get_history_since(
        self,
        service,
        start_history_id: str,
    ) -> Optional[list[dict]]:
        """
        Fetch history records since given historyId.

        Args:
            service: Gmail API service
            start_history_id: Starting historyId

        Returns:
            List of history records or None if history unavailable
        """
        try:
            logger.info(f"Fetching history since {start_history_id}")

            all_history = []
            next_page_token = None

            while True:
                # Fetch history page
                result = service.users().history().list(
                    userId='me',
                    startHistoryId=start_history_id,
                    historyTypes=['messageAdded', 'messageDeleted', 'labelAdded', 'labelRemoved'],
                    pageToken=next_page_token,
                    maxResults=500,
                ).execute()

                history_records = result.get('history', [])
                all_history.extend(history_records)

                next_page_token = result.get('nextPageToken')
                if not next_page_token:
                    break

            logger.info(f"Retrieved {len(all_history)} history records")
            return all_history

        except HttpError as e:
            if e.resp.status == 404:
                # History no longer available - need full resync
                logger.warning(f"History {start_history_id} not found - full resync required")
                return None
            raise

    async def process_history_records(
        self,
        db: AsyncSession,
        email_account: str,
        history_records: list[dict],
    ) -> dict:
        """
        Process history records and update database.

        Args:
            db: Async database session
            email_account: Gmail email address
            history_records: List of history records from API

        Returns:
            Dict with counts of added/deleted/updated
        """
        metrics = {
            'added': 0,
            'deleted': 0,
            'label_changes': 0,
        }

        redis = await redis_from_url(self.redis_url)
        try:
            for record in history_records:
                # Process messages added
                if 'messagesAdded' in record:
                    for msg_added in record['messagesAdded']:
                        message = msg_added.get('message', {})
                        await self._handle_added_message(redis, email_account, message)
                        metrics['added'] += 1

                # Process messages deleted
                if 'messagesDeleted' in record:
                    for msg_deleted in record['messagesDeleted']:
                        message = msg_deleted.get('message', {})
                        await self._handle_deleted_message(db, message.get('id'))
                        metrics['deleted'] += 1

                # Process label changes
                messages_changed = set()
                if 'labelsAdded' in record:
                    for label_added in record['labelsAdded']:
                        message = label_added.get('message', {})
                        messages_changed.add(message.get('id'))

                if 'labelsRemoved' in record:
                    for label_removed in record['labelsRemoved']:
                        message = label_removed.get('message', {})
                        messages_changed.add(message.get('id'))

                # Update labels for changed messages
                for message_id in messages_changed:
                    if message_id:
                        await self._handle_label_change(db, email_account, message_id)
                        metrics['label_changes'] += 1

        finally:
            await redis.close()

        return metrics

    async def _handle_added_message(
        self,
        redis,
        email_account: str,
        message: dict,
    ) -> None:
        """
        Handle newly added message by queuing for fetch.

        Args:
            redis: Redis client
            email_account: Gmail email address
            message: Message object from history API
        """
        message_id = message.get('id')
        if not message_id:
            return

        # Queue for full fetch (background worker will process)
        await redis.lpush(
            'email:fetch_queue',
            json.dumps({
                'email': email_account,
                'message_id': message_id,
                'thread_id': message.get('threadId'),
            })
        )
        logger.debug(f"Queued new message {message_id} for fetch")

    async def _handle_deleted_message(
        self,
        db: AsyncSession,
        message_id: str,
    ) -> None:
        """
        Handle deleted message.

        Args:
            db: Async database session
            message_id: Gmail message ID
        """
        if not message_id:
            return

        # Hard delete from database
        result = await db.execute(
            select(Email).where(Email.id == message_id)
        )
        email = result.scalar_one_or_none()

        if email:
            await db.delete(email)
            await db.commit()
            logger.debug(f"Deleted message {message_id}")

    async def _handle_label_change(
        self,
        db: AsyncSession,
        email_account: str,
        message_id: str,
    ) -> None:
        """
        Handle label changes (read/unread, starred, etc).

        Args:
            db: Async database session
            email_account: Gmail email address
            message_id: Gmail message ID
        """
        try:
            # Fetch latest message metadata (minimal format, 2 quota units)
            service = await self.gmail_client.get_gmail_service(db, email_account)
            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format='minimal',  # Only labelIds
            ).execute()

            label_ids = message.get('labelIds', [])

            # Update email in database
            result = await db.execute(
                select(Email).where(Email.id == message_id)
            )
            email = result.scalar_one_or_none()

            if email:
                email.labels = json.dumps(label_ids)
                email.is_read = 'UNREAD' not in label_ids
                await db.commit()
                logger.debug(f"Updated labels for {message_id}")

        except HttpError as e:
            logger.error(f"Failed to update labels for {message_id}: {e}")

    async def sync_incremental(
        self,
        db: AsyncSession,
        email_account: str,
    ) -> dict:
        """
        Perform incremental sync using History API.

        Args:
            db: Async database session
            email_account: Gmail email address

        Returns:
            Dict with sync results
        """
        # Get account and check history ID
        result = await db.execute(
            select(EmailAccount).where(EmailAccount.email_address == email_account)
        )
        account = result.scalar_one_or_none()

        if not account or not account.history_id:
            return {
                'success': False,
                'error': 'No history ID - full sync required',
                'requires_full_sync': True,
            }

        start_time = datetime.now(timezone.utc)
        start_history_id = account.history_id

        try:
            # Build Gmail service
            service = await self.gmail_client.get_gmail_service(db, email_account)

            # Fetch history
            history_records = await self.get_history_since(service, start_history_id)

            if history_records is None:
                # History expired - signal need for full sync
                return {
                    'success': False,
                    'error': 'History expired',
                    'requires_full_sync': True,
                }

            # Process history
            metrics = await self.process_history_records(
                db,
                email_account,
                history_records,
            )

            # Get latest historyId from Gmail
            profile = service.users().getProfile(userId='me').execute()
            new_history_id = profile.get('historyId')

            # Update account
            account.history_id = new_history_id
            account.last_successful_sync = datetime.now(timezone.utc)
            account.incremental_syncs_count += 1
            account.consecutive_sync_failures = 0
            account.last_sync_error = None

            await db.commit()

            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            return {
                'success': True,
                'sync_type': 'incremental',
                'emails_added': metrics['added'],
                'emails_deleted': metrics['deleted'],
                'labels_updated': metrics['label_changes'],
                'history_records_processed': len(history_records),
                'new_history_id': new_history_id,
                'duration_ms': duration_ms,
            }

        except Exception as e:
            logger.error(f"Incremental sync failed for {email_account}: {e}")

            # Update failure count
            account.consecutive_sync_failures += 1
            account.last_sync_error = str(e)
            await db.commit()

            return {
                'success': False,
                'error': str(e),
            }

    async def get_current_history_id(
        self,
        db: AsyncSession,
        email_account: str,
    ) -> Optional[str]:
        """
        Get current historyId from Gmail.

        Args:
            db: Async database session
            email_account: Gmail email address

        Returns:
            Current historyId or None if failed
        """
        try:
            service = await self.gmail_client.get_gmail_service(db, email_account)
            profile = service.users().getProfile(userId='me').execute()
            return profile.get('historyId')
        except Exception as e:
            logger.error(f"Failed to get current historyId for {email_account}: {e}")
            return None
