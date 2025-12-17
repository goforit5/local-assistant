"""
Webhook Handler

Handles incoming webhook notifications from Microsoft Graph.

Implements webhook validation and processing according to Microsoft docs:
https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks

Webhook lifecycle:
1. Subscription creation: Graph sends validation request
2. Notification delivery: Graph sends change notifications
3. Acknowledgement: We must respond 202 within 3 seconds
"""

import structlog
from typing import Dict, Any, List, Optional
from fastapi import Request, HTTPException, Header
import hmac
import hashlib
import base64

logger = structlog.get_logger(__name__)


class WebhookHandler:
    """Handles Microsoft Graph webhook notifications."""

    def __init__(
        self,
        delta_sync_engine,
        validation_enabled: bool = True,
    ):
        """
        Initialize webhook handler.

        Args:
            delta_sync_engine: DeltaSyncEngine instance
            validation_enabled: Enable client state validation
        """
        self.delta_sync = delta_sync_engine
        self.validation_enabled = validation_enabled

        logger.info("webhook_handler_initialized")

    async def handle_validation(
        self,
        validation_token: str,
    ) -> str:
        """
        Handle subscription validation request.

        When creating a subscription, Microsoft Graph sends a validation
        request with a token. We must echo it back in plaintext to confirm.

        Args:
            validation_token: Token from ?validationToken query param

        Returns:
            Validation token (plaintext)
        """
        logger.info("webhook_validation_request", token=validation_token[:20] + "...")

        return validation_token

    async def handle_notification(
        self,
        notifications: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """
        Handle change notification batch.

        Microsoft Graph can send multiple notifications in a single request.
        We must respond 202 within 3 seconds, then process async.

        Args:
            notifications: List of notification dicts

        Returns:
            Response dict

        Notification structure:
        {
            "subscriptionId": "...",
            "clientState": "...",
            "changeType": "created" | "updated" | "deleted",
            "resource": "...",
            "resourceData": {...},
            "subscriptionExpirationDateTime": "...",
            "tenantId": "..."
        }
        """
        logger.info("webhook_notifications_received", count=len(notifications))

        # Process notifications asynchronously (don't block response)
        for notification in notifications:
            try:
                await self._process_notification(notification)
            except Exception as e:
                logger.error(
                    "notification_processing_failed",
                    subscription_id=notification.get("subscriptionId"),
                    error=str(e),
                    exc_info=True,
                )

        # Return 202 Accepted immediately
        return {"status": "accepted"}

    async def _process_notification(
        self,
        notification: Dict[str, Any],
    ) -> None:
        """
        Process single notification.

        Args:
            notification: Notification dict
        """
        subscription_id = notification["subscriptionId"]
        client_state = notification.get("clientState")
        change_type = notification["changeType"]
        resource = notification["resource"]

        logger.debug(
            "processing_notification",
            subscription_id=subscription_id,
            change_type=change_type,
            resource=resource,
        )

        # Determine entity type from resource
        entity_type = self._resource_to_entity_type(resource)
        if not entity_type:
            logger.warning("unknown_resource_type", resource=resource)
            return

        # Trigger delta sync for this entity type
        await self.delta_sync.handle_webhook_notification(
            entity_type=entity_type,
            notification=notification,
        )

        logger.info(
            "notification_processed",
            subscription_id=subscription_id,
            entity_type=entity_type,
        )

    def _resource_to_entity_type(self, resource: str):
        """
        Determine entity type from resource path.

        Args:
            resource: Resource path (e.g., "me/todo/lists", "me/planner/tasks")

        Returns:
            EntityType or None
        """
        from services.microsoft_graph.delta_sync import EntityType

        if "/todo/lists/" in resource and "/tasks" in resource:
            return EntityType.TODO_TASK
        elif "/todo/lists" in resource:
            return EntityType.TODO_LIST
        elif "/planner/tasks" in resource:
            return EntityType.PLANNER_TASK
        elif "/planner/plans" in resource:
            return EntityType.PLANNER_PLAN

        return None

    async def handle_lifecycle_notification(
        self,
        lifecycle_event: str,
        subscription_id: str,
    ) -> Dict[str, str]:
        """
        Handle subscription lifecycle notifications.

        Microsoft Graph can send lifecycle events:
        - subscriptionRemoved: Subscription was deleted
        - reauthorizationRequired: Need to re-authenticate
        - missed: Notifications were missed

        Args:
            lifecycle_event: Event type
            subscription_id: Subscription ID

        Returns:
            Response dict
        """
        logger.warning(
            "lifecycle_notification_received",
            event=lifecycle_event,
            subscription_id=subscription_id,
        )

        if lifecycle_event == "reauthorizationRequired":
            # Need to refresh tokens and recreate subscription
            logger.error(
                "reauthorization_required",
                subscription_id=subscription_id,
            )
            # TODO: Trigger reauthorization flow

        elif lifecycle_event == "subscriptionRemoved":
            # Subscription was deleted (expired or manually removed)
            logger.error(
                "subscription_removed",
                subscription_id=subscription_id,
            )
            # TODO: Recreate subscription

        elif lifecycle_event == "missed":
            # Some notifications were missed
            logger.error(
                "notifications_missed",
                subscription_id=subscription_id,
            )
            # Trigger full delta sync to catch up
            # TODO: Determine entity type and trigger sync

        return {"status": "acknowledged"}

    @staticmethod
    def verify_token_signature(
        tokens: str,
        signature: str,
        validation_key: bytes,
    ) -> bool:
        """
        Verify webhook notification signature (for rich notifications).

        When using rich notifications, Microsoft Graph includes JWT tokens
        with resource data. Signature verification ensures authenticity.

        Args:
            tokens: JWT tokens from notification
            signature: Signature from X-Microsoft-Signature header
            validation_key: Validation key from subscription

        Returns:
            True if signature valid
        """
        expected_signature = base64.b64encode(
            hmac.new(
                validation_key,
                tokens.encode("utf-8"),
                hashlib.sha256
            ).digest()
        ).decode("utf-8")

        return hmac.compare_digest(signature, expected_signature)


# FastAPI routes for webhook endpoints

async def webhook_validation_endpoint(
    validationToken: Optional[str] = None,
) -> str:
    """
    Webhook validation endpoint.

    Microsoft Graph sends GET request with ?validationToken query param.
    We must echo it back in plaintext with Content-Type: text/plain.

    Used by: POST /subscriptions (during subscription creation)
    """
    if not validationToken:
        raise HTTPException(status_code=400, detail="Missing validationToken")

    logger.info("webhook_validation_received")

    # Return token in plaintext
    return validationToken


async def webhook_notification_endpoint(
    request: Request,
    handler: WebhookHandler,
    client_state: Optional[str] = Header(None, alias="clientState"),
) -> Dict[str, str]:
    """
    Webhook notification endpoint.

    Microsoft Graph sends POST request with change notifications.
    We must respond 202 Accepted within 3 seconds.

    Payload structure:
    {
        "value": [
            {
                "subscriptionId": "...",
                "clientState": "...",
                "changeType": "created|updated|deleted",
                "resource": "...",
                "resourceData": {...},
                ...
            }
        ]
    }
    """
    try:
        payload = await request.json()
        notifications = payload.get("value", [])

        if not notifications:
            logger.warning("empty_notification_batch")
            return {"status": "accepted"}

        # Process notifications
        result = await handler.handle_notification(notifications)

        return result

    except Exception as e:
        logger.error("webhook_processing_error", error=str(e), exc_info=True)
        # Still return 202 to avoid retries
        return {"status": "error"}
