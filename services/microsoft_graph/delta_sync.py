"""
Delta Sync + Webhooks Engine

Implements the BEST PRACTICE pattern from research:
"Webhooks and delta query are often used better together - using webhooks
as the trigger to make delta query calls provides 'the best of both worlds'."

Architecture:
1. Create webhook subscription for change notifications
2. Immediately fetch initial data using delta query
3. Store delta link for incremental updates
4. When webhook fires, use delta link to fetch only changes
5. Backstop: Scheduled process (6/12/24 hours) triggers delta query
6. Never rely entirely on webhooks (they have no guaranteed delivery)

This ensures:
- Real-time notifications (via webhooks)
- Efficient sync (only changed data via delta)
- No missed changes (backstop polling)
- Resilience to webhook failures

References:
- https://www.voitanos.io/blog/microsoft-graph-webhook-delta-query/
- https://learn.microsoft.com/en-us/graph/delta-query-overview
"""

import structlog
import asyncio
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum
import uuid

logger = structlog.get_logger(__name__)


class ChangeType(str, Enum):
    """Types of changes in delta sync."""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class EntityType(str, Enum):
    """Types of entities that can be synced."""
    TODO_LIST = "todo_list"
    TODO_TASK = "todo_task"
    PLANNER_PLAN = "planner_plan"
    PLANNER_TASK = "planner_task"


class DeltaSyncEngine:
    """
    Delta sync + webhook subscription manager.

    Implements best practice pattern for reliable, efficient sync.
    """

    def __init__(
        self,
        base_client,
        webhook_base_url: str,
        sync_state_store,  # Database store for delta links and sync state
    ):
        """
        Initialize delta sync engine.

        Args:
            base_client: GraphBaseClient instance
            webhook_base_url: Base URL for webhook endpoints (e.g., https://yourapp.com)
            sync_state_store: Store for persisting delta links and sync state
        """
        self.client = base_client
        self.webhook_base_url = webhook_base_url
        self.sync_state = sync_state_store

        # Subscription management
        self.subscriptions: Dict[EntityType, Dict[str, Any]] = {}
        self.subscription_renew_threshold = timedelta(hours=12)

        # Change handlers
        self.change_handlers: Dict[EntityType, List[Callable]] = {
            EntityType.TODO_TASK: [],
            EntityType.TODO_LIST: [],
            EntityType.PLANNER_TASK: [],
            EntityType.PLANNER_PLAN: [],
        }

        logger.info(
            "delta_sync_engine_initialized",
            webhook_base_url=webhook_base_url,
        )

    async def initialize_sync(
        self,
        entity_type: EntityType,
        endpoint: str,
    ) -> Dict[str, Any]:
        """
        Initialize delta sync for an entity type.

        Steps:
        1. Create webhook subscription
        2. Fetch initial data using delta query
        3. Store delta link for future incremental syncs
        4. Return initial data

        Args:
            entity_type: Type of entity to sync
            endpoint: Graph API endpoint (e.g., "/me/todo/lists")

        Returns:
            Dict with keys:
            - items: Initial list of items
            - delta_link: Delta link for next sync
            - subscription_id: Webhook subscription ID
        """
        logger.info(
            "initializing_delta_sync",
            entity_type=entity_type,
            endpoint=endpoint,
        )

        # Step 1: Create webhook subscription
        subscription = await self._create_subscription(entity_type, endpoint)
        subscription_id = subscription["id"]

        logger.info("webhook_subscription_created", subscription_id=subscription_id)

        # Step 2: Fetch initial data with delta query
        items, delta_link = await self._fetch_delta(endpoint)

        logger.info(
            "initial_delta_fetch_complete",
            item_count=len(items),
            has_delta_link=bool(delta_link),
        )

        # Step 3: Store delta link and subscription
        await self.sync_state.save_delta_link(
            entity_type=entity_type.value,
            delta_link=delta_link,
            subscription_id=subscription_id,
        )

        self.subscriptions[entity_type] = subscription

        return {
            "items": items,
            "delta_link": delta_link,
            "subscription_id": subscription_id,
        }

    async def _fetch_delta(
        self,
        endpoint_or_link: str,
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Fetch data using delta query.

        Args:
            endpoint_or_link: Either initial endpoint with /delta or delta link

        Returns:
            Tuple of (items, delta_link)
        """
        all_items = []
        next_link = endpoint_or_link

        # Add /delta if not present
        if "/delta" not in next_link:
            next_link = f"{next_link}/delta"

        while next_link:
            logger.debug("fetching_delta_page", url=next_link)

            # If it's a full URL (from delta/next link), extract path
            if next_link.startswith("http"):
                from urllib.parse import urlparse
                parsed = urlparse(next_link)
                next_link = parsed.path + ("?" + parsed.query if parsed.query else "")

            response = await self.client.get(next_link)

            # Extract items
            items = response.get("value", [])

            # Categorize changes
            for item in items:
                if "@removed" in item:
                    item["_change_type"] = ChangeType.DELETED
                elif item.get("id") in {i.get("id") for i in all_items}:
                    item["_change_type"] = ChangeType.UPDATED
                else:
                    item["_change_type"] = ChangeType.CREATED

            all_items.extend(items)

            # Check for next page or delta link
            next_link = response.get("@odata.nextLink")
            delta_link = response.get("@odata.deltaLink")

            # If we have delta link, we're done
            if delta_link:
                logger.debug(
                    "delta_sync_complete",
                    total_items=len(all_items),
                    has_delta_link=True,
                )
                return all_items, delta_link

        # No delta link found (shouldn't happen, but handle gracefully)
        logger.warning("no_delta_link_in_response")
        return all_items, None

    async def sync_changes(
        self,
        entity_type: EntityType,
    ) -> Dict[str, Any]:
        """
        Sync changes using stored delta link.

        This is called:
        1. When webhook notification received
        2. By backstop scheduled process

        Args:
            entity_type: Type of entity to sync

        Returns:
            Dict with keys:
            - created: List of created items
            - updated: List of updated items
            - deleted: List of deleted items
            - delta_link: New delta link for next sync
        """
        logger.info("syncing_changes", entity_type=entity_type)

        # Get stored delta link
        sync_state = await self.sync_state.get_sync_state(entity_type.value)
        if not sync_state or not sync_state.get("delta_link"):
            logger.error("no_delta_link_found", entity_type=entity_type)
            raise ValueError(f"No delta link for {entity_type}. Run initialize_sync first.")

        delta_link = sync_state["delta_link"]

        # Fetch changes
        items, new_delta_link = await self._fetch_delta(delta_link)

        # Categorize changes
        created = [i for i in items if i.get("_change_type") == ChangeType.CREATED]
        updated = [i for i in items if i.get("_change_type") == ChangeType.UPDATED]
        deleted = [i for i in items if i.get("_change_type") == ChangeType.DELETED]

        logger.info(
            "changes_synced",
            created=len(created),
            updated=len(updated),
            deleted=len(deleted),
        )

        # Store new delta link
        if new_delta_link:
            await self.sync_state.save_delta_link(
                entity_type=entity_type.value,
                delta_link=new_delta_link,
            )

        # Invoke change handlers
        await self._invoke_handlers(entity_type, created, updated, deleted)

        return {
            "created": created,
            "updated": updated,
            "deleted": deleted,
            "delta_link": new_delta_link,
        }

    async def _create_subscription(
        self,
        entity_type: EntityType,
        resource: str,
    ) -> Dict[str, Any]:
        """
        Create webhook subscription.

        Args:
            entity_type: Type of entity
            resource: Graph resource to monitor (e.g., "/me/todo/lists")

        Returns:
            Subscription dict
        """
        # Webhook notification URL
        notification_url = f"{self.webhook_base_url}/api/v1/graph/webhooks/{entity_type.value}"

        # Client state for validation
        client_state = str(uuid.uuid4())

        # Subscription data
        subscription_data = {
            "changeType": "created,updated,deleted",
            "notificationUrl": notification_url,
            "resource": resource,
            "expirationDateTime": (
                datetime.utcnow() + timedelta(hours=72)  # Max 3 days for user resources
            ).isoformat() + "Z",
            "clientState": client_state,
        }

        logger.debug(
            "creating_webhook_subscription",
            resource=resource,
            notification_url=notification_url,
        )

        subscription = await self.client.post("/subscriptions", subscription_data)

        # Store client state for validation
        await self.sync_state.save_subscription(
            entity_type=entity_type.value,
            subscription_id=subscription["id"],
            client_state=client_state,
            expires_at=subscription["expirationDateTime"],
        )

        return subscription

    async def renew_subscription(
        self,
        subscription_id: str,
    ) -> Dict[str, Any]:
        """
        Renew webhook subscription.

        Subscriptions expire after 3 days (for user resources) or 42 hours
        (for other resources). Must be renewed periodically.

        Args:
            subscription_id: Subscription ID to renew

        Returns:
            Updated subscription dict
        """
        logger.info("renewing_subscription", subscription_id=subscription_id)

        new_expiration = (
            datetime.utcnow() + timedelta(hours=72)
        ).isoformat() + "Z"

        subscription = await self.client.patch(
            f"/subscriptions/{subscription_id}",
            json_data={"expirationDateTime": new_expiration},
        )

        # Update stored expiration
        await self.sync_state.update_subscription_expiration(
            subscription_id=subscription_id,
            expires_at=new_expiration,
        )

        logger.info("subscription_renewed", subscription_id=subscription_id)
        return subscription

    async def delete_subscription(
        self,
        subscription_id: str,
    ) -> None:
        """
        Delete webhook subscription.

        Args:
            subscription_id: Subscription ID to delete
        """
        logger.info("deleting_subscription", subscription_id=subscription_id)

        await self.client.delete(f"/subscriptions/{subscription_id}")

        await self.sync_state.delete_subscription(subscription_id)

        logger.info("subscription_deleted", subscription_id=subscription_id)

    def register_change_handler(
        self,
        entity_type: EntityType,
        handler: Callable[[List, List, List], Awaitable[None]],
    ) -> None:
        """
        Register handler for change events.

        Handler will be called with:
        - created: List of created items
        - updated: List of updated items
        - deleted: List of deleted items

        Args:
            entity_type: Type of entity
            handler: Async function to handle changes
        """
        self.change_handlers[entity_type].append(handler)
        logger.info("change_handler_registered", entity_type=entity_type)

    async def _invoke_handlers(
        self,
        entity_type: EntityType,
        created: List[Dict[str, Any]],
        updated: List[Dict[str, Any]],
        deleted: List[Dict[str, Any]],
    ) -> None:
        """
        Invoke all registered handlers for an entity type.

        Args:
            entity_type: Type of entity
            created: Created items
            updated: Updated items
            deleted: Deleted items
        """
        handlers = self.change_handlers.get(entity_type, [])
        if not handlers:
            return

        logger.debug(
            "invoking_change_handlers",
            entity_type=entity_type,
            handler_count=len(handlers),
        )

        for handler in handlers:
            try:
                await handler(created, updated, deleted)
            except Exception as e:
                logger.error(
                    "change_handler_failed",
                    entity_type=entity_type,
                    error=str(e),
                    exc_info=True,
                )

    async def backstop_sync(
        self,
        interval_hours: int = 12,
    ) -> None:
        """
        Run backstop sync process.

        Best practice: "Set up a scheduled process that runs on a long
        interval such as 6/12/24/48 hours to trigger your process that's
        normally triggered by the webhook."

        This ensures no changes are missed if webhooks fail.

        Args:
            interval_hours: Interval between syncs (default: 12)
        """
        logger.info("starting_backstop_sync", interval_hours=interval_hours)

        while True:
            try:
                # Sync all entity types
                for entity_type in EntityType:
                    try:
                        await self.sync_changes(entity_type)
                    except Exception as e:
                        logger.error(
                            "backstop_sync_failed",
                            entity_type=entity_type,
                            error=str(e),
                        )

                # Check and renew expiring subscriptions
                await self._check_and_renew_subscriptions()

            except Exception as e:
                logger.error("backstop_sync_error", error=str(e), exc_info=True)

            # Wait for next interval
            await asyncio.sleep(interval_hours * 3600)

    async def _check_and_renew_subscriptions(self) -> None:
        """
        Check for expiring subscriptions and renew them.

        Best practice: Renew subscriptions before they expire.
        """
        logger.debug("checking_subscription_expirations")

        subscriptions = await self.sync_state.get_all_subscriptions()

        for sub in subscriptions:
            sub_id = sub["subscription_id"]
            expires_at = datetime.fromisoformat(
                sub["expires_at"].replace("Z", "+00:00")
            )

            # Renew if expiring within threshold
            if expires_at - datetime.now(expires_at.tzinfo) < self.subscription_renew_threshold:
                try:
                    await self.renew_subscription(sub_id)
                except Exception as e:
                    logger.error(
                        "subscription_renewal_failed",
                        subscription_id=sub_id,
                        error=str(e),
                    )

    async def validate_webhook_notification(
        self,
        client_state: str,
        entity_type: EntityType,
    ) -> bool:
        """
        Validate webhook notification client state.

        Args:
            client_state: Client state from notification
            entity_type: Entity type

        Returns:
            True if valid, False otherwise
        """
        sync_state = await self.sync_state.get_sync_state(entity_type.value)
        if not sync_state:
            return False

        stored_client_state = sync_state.get("client_state")
        valid = stored_client_state == client_state

        if not valid:
            logger.warning(
                "invalid_webhook_client_state",
                entity_type=entity_type,
                expected=stored_client_state,
                received=client_state,
            )

        return valid

    async def handle_webhook_notification(
        self,
        entity_type: EntityType,
        notification: Dict[str, Any],
    ) -> None:
        """
        Handle incoming webhook notification.

        Best practice: "When webhooks notify your application that something
        changed, use this as a trigger to resubmit the delta query."

        Args:
            entity_type: Entity type from notification
            notification: Notification payload
        """
        logger.info(
            "webhook_notification_received",
            entity_type=entity_type,
            subscription_id=notification.get("subscriptionId"),
        )

        # Validate client state
        client_state = notification.get("clientState")
        if not await self.validate_webhook_notification(client_state, entity_type):
            logger.error("webhook_validation_failed", entity_type=entity_type)
            return

        # Trigger delta sync
        try:
            await self.sync_changes(entity_type)
        except Exception as e:
            logger.error(
                "webhook_sync_failed",
                entity_type=entity_type,
                error=str(e),
                exc_info=True,
            )
