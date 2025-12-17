"""
Email → Document Intelligence Pipeline Integration.

Processes email attachments (invoices, PDFs, etc.) through the existing
document_intelligence pipeline to extract vendors, amounts, and create commitments.

Flow:
1. Email arrives → Attachment detected
2. Download attachment → Calculate SHA-256 hash
3. Store in content-addressable storage
4. Create Document record
5. Run document_intelligence pipeline
6. Extract vendor → Create/link Party
7. Extract amount/date → Create Commitment
8. Link to original Email via EmailAttachment
"""

import base64
import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.models import Document, EmailAttachment, Email, Party
from services.document_intelligence.pipeline import DocumentProcessingPipeline
from services.email.gmail_client import GmailClient

logger = logging.getLogger(__name__)


class EmailDocumentProcessor:
    """
    Processes email attachments through document intelligence pipeline.

    Features:
    - Content-addressable storage (SHA-256 deduplication)
    - Automatic invoice detection
    - Vendor extraction and resolution
    - Commitment creation
    - Party relationship tracking
    """

    def __init__(self):
        """Initialize processor with Gmail client and pipeline."""
        self.gmail_client = GmailClient()
        self.storage_path = Path(os.getenv("EMAIL_STORAGE_PATH", "./data/email-storage/attachments"))
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Supported file types for processing
        self.processable_types = {
            'application/pdf',
            'image/png',
            'image/jpeg',
            'image/jpg',
        }

    async def process_email_attachments(
        self,
        db: AsyncSession,
        email_id: str,
        email_account: str,
    ) -> list[Document]:
        """
        Process all attachments for an email.

        Args:
            db: Async database session
            email_id: Gmail message ID
            email_account: Gmail email address

        Returns:
            List of created Document records
        """
        try:
            # Get Gmail service
            service = await self.gmail_client.get_gmail_service(db, email_account)

            # Fetch message with full payload
            message = service.users().messages().get(
                userId='me',
                id=email_id,
                format='full',
            ).execute()

            payload = message.get('payload', {})
            attachments = []

            # Extract attachments from parts
            def extract_attachments(parts):
                for part in parts:
                    filename = part.get('filename')
                    if filename and part.get('body', {}).get('attachmentId'):
                        mime_type = part.get('mimeType', '')
                        attachments.append({
                            'filename': filename,
                            'mime_type': mime_type,
                            'attachment_id': part['body']['attachmentId'],
                            'size': part['body'].get('size', 0),
                        })
                    elif 'parts' in part:
                        extract_attachments(part['parts'])

            if 'parts' in payload:
                extract_attachments(payload['parts'])

            logger.info(f"Found {len(attachments)} attachments in email {email_id}")

            # Process each attachment
            documents = []
            for attachment in attachments:
                doc = await self._process_attachment(
                    db,
                    service,
                    email_id,
                    email_account,
                    attachment,
                )
                if doc:
                    documents.append(doc)

            return documents

        except HttpError as e:
            logger.error(f"Error processing attachments for {email_id}: {e}")
            return []

    async def _process_attachment(
        self,
        db: AsyncSession,
        service,
        email_id: str,
        email_account: str,
        attachment: dict,
    ) -> Optional[Document]:
        """
        Process a single email attachment.

        Args:
            db: Async database session
            service: Gmail API service
            email_id: Gmail message ID
            email_account: Gmail email address
            attachment: Attachment metadata dict

        Returns:
            Created Document or None
        """
        try:
            # Check if processable
            if attachment['mime_type'] not in self.processable_types:
                logger.info(f"Skipping non-processable type: {attachment['mime_type']}")
                return None

            # Download attachment
            att_data = service.users().messages().attachments().get(
                userId='me',
                messageId=email_id,
                id=attachment['attachment_id'],
            ).execute()

            # Decode base64url data
            file_data = base64.urlsafe_b64decode(att_data['data'])

            # Calculate SHA-256 hash
            content_hash = hashlib.sha256(file_data).hexdigest()

            # Check if already processed (deduplication)
            result = await db.execute(
                select(EmailAttachment).where(EmailAttachment.content_hash == content_hash)
            )
            existing = result.scalar_one_or_none()

            if existing and existing.processed:
                logger.info(f"Attachment already processed: {content_hash}")
                return None

            # Store file in content-addressable storage
            file_path = self.storage_path / content_hash[:2] / content_hash[2:4] / content_hash
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(file_data)

            # Create Document record
            document = Document(
                file_path=str(file_path),
                file_name=attachment['filename'],
                file_type=attachment['mime_type'],
                file_size=len(file_data),
                content_hash=content_hash,
                upload_source='email',
                uploaded_at=datetime.now(timezone.utc),
            )
            db.add(document)
            await db.commit()
            await db.refresh(document)

            # Create EmailAttachment record
            email_attachment = EmailAttachment(
                email_id=email_id,
                filename=attachment['filename'],
                mime_type=attachment['mime_type'],
                size=attachment['size'],
                content_hash=content_hash,
                storage_path=str(file_path),
                storage_type='local',
                gmail_attachment_id=attachment['attachment_id'],
                processed=False,
                document_id=document.id,
            )
            db.add(email_attachment)
            await db.commit()

            # Process through document intelligence pipeline
            try:
                pipeline = DocumentProcessingPipeline()
                result = await pipeline.process_document(db, document.id)

                if result['success']:
                    # Mark as processed
                    email_attachment.processed = True
                    await db.commit()

                    logger.info(f"Successfully processed attachment: {attachment['filename']}")
                    logger.info(f"  Vendor: {result.get('vendor_name')}")
                    logger.info(f"  Amount: {result.get('commitment_amount')}")
                    logger.info(f"  Due: {result.get('commitment_due_date')}")
                else:
                    email_attachment.processing_error = result.get('error')
                    await db.commit()
                    logger.warning(f"Processing failed: {result.get('error')}")

            except Exception as e:
                email_attachment.processing_error = str(e)
                await db.commit()
                logger.error(f"Pipeline error for {attachment['filename']}: {e}")

            return document

        except Exception as e:
            logger.error(f"Error processing attachment {attachment['filename']}: {e}")
            return None

    async def process_email_with_attachments(
        self,
        db: AsyncSession,
        email_id: str,
    ) -> dict:
        """
        Complete processing flow for an email with attachments.

        Args:
            db: Async database session
            email_id: Gmail message ID

        Returns:
            Processing result dict
        """
        # Get email
        result = await db.execute(
            select(Email).where(Email.id == email_id)
        )
        email = result.scalar_one_or_none()

        if not email:
            return {'success': False, 'error': 'Email not found'}

        # Process attachments
        documents = await self.process_email_attachments(
            db,
            email.id,
            email.account_email,
        )

        return {
            'success': True,
            'email_id': email_id,
            'documents_created': len(documents),
            'document_ids': [str(doc.id) for doc in documents],
        }


# Background worker function for processing queue

async def process_attachment_queue(db: AsyncSession):
    """
    Background worker to process email attachments from Redis queue.

    Queue format (Redis: email:attachment_queue):
    {
        "email_id": "gmail_message_id",
        "account_email": "user@gmail.com"
    }
    """
    import json
    from redis.asyncio import from_url as redis_from_url

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6380/0")
    redis = await redis_from_url(redis_url)
    processor = EmailDocumentProcessor()

    try:
        while True:
            # Pop from queue (blocking)
            item = await redis.brpop('email:attachment_queue', timeout=5)
            if not item:
                continue

            try:
                data = json.loads(item[1])
                email_id = data['email_id']
                account_email = data['account_email']

                logger.info(f"Processing attachments for {email_id}")
                result = await processor.process_email_attachments(
                    db,
                    email_id,
                    account_email,
                )
                logger.info(f"Processed {len(result)} attachments")

            except Exception as e:
                logger.error(f"Error processing queue item: {e}")

    finally:
        await redis.close()
