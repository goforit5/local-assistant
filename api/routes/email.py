"""
Email API Routes.

Endpoints:
- OAuth flow (login, callback)
- Push notification webhook
- Email management (list, sync, search)
- Attachment processing
"""

import base64
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.database import get_db
from memory.models import Email, EmailAccount, EmailAttachment
from services.email.oauth_manager import GmailOAuthManager
from services.email.gmail_client import GmailClient
from services.email.history_sync import GmailHistorySync
from services.email.push_notifications import GmailPushNotifications
from services.email.document_integration import EmailDocumentProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])

# Initialize services
oauth_manager = GmailOAuthManager()
gmail_client = GmailClient()
history_sync = GmailHistorySync()
push_notifications = GmailPushNotifications()
document_processor = EmailDocumentProcessor()


# ============================================================================
# OAuth Flow
# ============================================================================

@router.get("/auth/gmail/login")
async def gmail_login():
    """
    Step 1: Get Google OAuth authorization URL.

    Returns:
        Authorization URL for user to visit
    """
    try:
        auth_url = oauth_manager.get_auth_url()
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Error generating auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request."""
    code: str


@router.post("/auth/gmail/callback")
async def gmail_callback(
    request: OAuthCallbackRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Step 2: Handle OAuth callback and exchange code for tokens.

    Args:
        request: OAuth authorization code
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Success message and email address
    """
    try:
        # Exchange code for tokens
        tokens = oauth_manager.exchange_code_for_tokens(request.code)

        # Get user email from token (decode JWT)
        import jwt
        decoded = jwt.decode(tokens['access_token'], options={"verify_signature": False})
        email = decoded.get('email')

        if not email:
            raise HTTPException(status_code=400, detail="Could not extract email from token")

        # Store tokens
        await oauth_manager.store_tokens(db, email, tokens)

        # Enable push notifications in background
        if push_notifications.publisher:
            background_tasks.add_task(
                push_notifications.setup_pubsub_topic,
            )
            background_tasks.add_task(
                push_notifications.watch_mailbox,
                db,
                email,
            )

        # Start initial sync in background
        background_tasks.add_task(
            gmail_client.initial_sync,
            db,
            email,
        )

        return {
            "success": True,
            "email": email,
            "message": "Gmail account connected successfully",
        }

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Push Notification Webhook
# ============================================================================

@router.post("/webhooks/gmail")
async def gmail_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive push notifications from Google Cloud Pub/Sub.

    Expected format:
    {
        "message": {
            "data": "base64_encoded_json",
            "messageId": "...",
            "publishTime": "..."
        },
        "subscription": "..."
    }

    Returns:
        200 OK (must respond quickly for Pub/Sub)
    """
    try:
        body = await request.json()
        message = body.get('message', {})

        # Decode base64 data
        data_b64 = message.get('data', '')
        if not data_b64:
            return {"success": False, "error": "No data in message"}

        data_json = base64.b64decode(data_b64).decode('utf-8')
        data = json.loads(data_json)

        # Process notification in background
        background_tasks.add_task(
            push_notifications.handle_notification,
            db,
            data,
        )

        # Return 200 OK quickly (Pub/Sub requirement)
        return {"success": True}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        # Still return 200 to avoid Pub/Sub retries
        return {"success": False, "error": str(e)}


# ============================================================================
# Email Operations
# ============================================================================

@router.get("/accounts")
async def list_accounts(db: AsyncSession = Depends(get_db)):
    """
    List all connected email accounts.

    Returns:
        List of email accounts with sync status
    """
    result = await db.execute(
        select(EmailAccount).where(EmailAccount.is_active == 1)
    )
    accounts = result.scalars().all()

    return {
        "accounts": [
            {
                "email": acc.email_address,
                "total_messages": acc.total_messages,
                "last_sync": acc.last_successful_sync,
                "watch_active": bool(acc.watch_active),
                "watch_expiry": acc.watch_expiry,
            }
            for acc in accounts
        ]
    }


class SyncRequest(BaseModel):
    """Sync request."""
    email: str
    full_sync: bool = False


@router.post("/sync")
async def sync_email(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger email sync for an account.

    Args:
        request: Sync parameters
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Sync status
    """
    if request.full_sync:
        # Full sync
        background_tasks.add_task(
            gmail_client.initial_sync,
            db,
            request.email,
        )
        return {"success": True, "sync_type": "full", "status": "started"}
    else:
        # Incremental sync
        result = await history_sync.sync_incremental(db, request.email)
        return result


@router.get("/emails")
async def list_emails(
    limit: int = 50,
    offset: int = 0,
    account: Optional[str] = None,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    List emails with filtering and pagination.

    Args:
        limit: Number of emails to return
        offset: Pagination offset
        account: Filter by email account
        unread_only: Show only unread emails
        db: Database session

    Returns:
        List of emails
    """
    query = select(Email)

    # Filters
    if account:
        query = query.where(Email.account_email == account)
    if unread_only:
        query = query.where(Email.is_read == 0)

    # Pagination
    query = query.order_by(Email.date_received.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    emails = result.scalars().all()

    return {
        "emails": [
            {
                "id": email.id,
                "subject": email.subject,
                "sender": email.sender,
                "snippet": email.snippet,
                "date_received": email.date_received,
                "is_read": bool(email.is_read),
                "fast_category": email.fast_category,
                "fast_priority": email.fast_priority,
            }
            for email in emails
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/emails/{email_id}")
async def get_email(
    email_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get full email details.

    Args:
        email_id: Gmail message ID
        db: Database session

    Returns:
        Email details with attachments
    """
    result = await db.execute(
        select(Email).where(Email.id == email_id)
    )
    email = result.scalar_one_or_none()

    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    # Get attachments
    att_result = await db.execute(
        select(EmailAttachment).where(EmailAttachment.email_id == email_id)
    )
    attachments = att_result.scalars().all()

    return {
        "id": email.id,
        "thread_id": email.thread_id,
        "subject": email.subject,
        "sender": email.sender,
        "recipient": email.recipient,
        "date_received": email.date_received,
        "body_text": email.body_text,
        "body_html": email.body_html,
        "labels": json.loads(email.labels) if email.labels else [],
        "is_read": bool(email.is_read),
        "fast_category": email.fast_category,
        "fast_priority": email.fast_priority,
        "attachments": [
            {
                "filename": att.filename,
                "mime_type": att.mime_type,
                "size": att.size,
                "processed": bool(att.processed),
                "document_id": str(att.document_id) if att.document_id else None,
            }
            for att in attachments
        ],
    }


@router.post("/emails/{email_id}/process-attachments")
async def process_email_attachments(
    email_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Process attachments for an email through document intelligence pipeline.

    Args:
        email_id: Gmail message ID
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Processing status
    """
    # Queue for background processing
    background_tasks.add_task(
        document_processor.process_email_with_attachments,
        db,
        email_id,
    )

    return {
        "success": True,
        "message": "Attachment processing started",
        "email_id": email_id,
    }


# ============================================================================
# Push Notification Management
# ============================================================================

@router.post("/push/enable/{email}")
async def enable_push(
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Enable push notifications for an account.

    Args:
        email: Gmail email address
        db: Database session

    Returns:
        Push notification status
    """
    try:
        await push_notifications.setup_pubsub_topic()
        success = await push_notifications.watch_mailbox(db, email)

        if success:
            return {
                "success": True,
                "email": email,
                "message": "Push notifications enabled",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to enable push notifications")

    except Exception as e:
        logger.error(f"Error enabling push for {email}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/push/disable/{email}")
async def disable_push(
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Disable push notifications for an account.

    Args:
        email: Gmail email address
        db: Database session

    Returns:
        Success status
    """
    success = await push_notifications.stop_watch(db, email)

    if success:
        return {
            "success": True,
            "email": email,
            "message": "Push notifications disabled",
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to disable push notifications")


@router.get("/push/status")
async def push_status(db: AsyncSession = Depends(get_db)):
    """
    Get push notification status for all accounts.

    Returns:
        Push notification status for each account
    """
    result = await db.execute(
        select(EmailAccount).where(EmailAccount.is_active == 1)
    )
    accounts = result.scalars().all()

    return {
        "accounts": [
            {
                "email": acc.email_address,
                "watch_active": bool(acc.watch_active),
                "watch_expiry": acc.watch_expiry,
                "watch_error": acc.watch_error,
                "watch_last_renewed": acc.watch_last_renewed,
            }
            for acc in accounts
        ]
    }
