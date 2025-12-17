"""
Pytest Fixtures for Microsoft Graph Tests

Provides reusable fixtures for testing Graph integration:
- Mock authenticators
- Mock Graph API responses
- Test data factories
- Database fixtures
"""

import pytest
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timedelta, date
from unittest.mock import Mock, AsyncMock, patch
import uuid


# =====================================================
# Event Loop Fixtures
# =====================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =====================================================
# Authentication Fixtures
# =====================================================

@pytest.fixture
def mock_authenticator():
    """Mock GraphAuthenticator."""
    auth = Mock()
    auth.get_access_token.return_value = "mock_access_token_" + str(uuid.uuid4())
    auth.get_account_info.return_value = {
        "username": "test@example.com",
        "home_account_id": "test_account_id",
        "environment": "login.microsoftonline.com",
    }
    return auth


@pytest.fixture
def mock_msal_app():
    """Mock MSAL ConfidentialClientApplication."""
    with patch("msal.ConfidentialClientApplication") as mock:
        app = mock.return_value
        app.acquire_token_silent.return_value = {
            "access_token": "mock_token",
            "expires_in": 3600,
        }
        app.acquire_token_for_client.return_value = {
            "access_token": "mock_app_token",
            "expires_in": 3600,
        }
        app.get_accounts.return_value = [{
            "username": "test@example.com",
            "home_account_id": "test_id",
        }]
        yield app


# =====================================================
# HTTP Client Fixtures
# =====================================================

@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient."""
    client = AsyncMock()

    # Default success responses
    client.get.return_value = Mock(
        status_code=200,
        json=Mock(return_value={"value": []}),
        headers={},
    )

    client.post.return_value = Mock(
        status_code=201,
        json=Mock(return_value={"id": "mock_id"}),
        headers={},
    )

    client.patch.return_value = Mock(
        status_code=200,
        json=Mock(return_value={"id": "mock_id"}),
        headers={},
    )

    client.delete.return_value = Mock(status_code=204)

    return client


@pytest.fixture
async def mock_base_client(mock_authenticator):
    """Mock GraphBaseClient."""
    from services.microsoft_graph.base_client import GraphBaseClient

    with patch.object(GraphBaseClient, "_get_headers", return_value={"Authorization": "Bearer mock_token"}):
        client = GraphBaseClient(mock_authenticator)
        yield client
        await client.close()


# =====================================================
# Test Data Factories
# =====================================================

@pytest.fixture
def planner_task_factory():
    """Factory for creating mock Planner tasks."""

    def _create_task(
        task_id: str = None,
        title: str = "Test Task",
        priority: int = 5,
        due_date: date = None,
        percent_complete: int = 0,
        bucket_id: str = "bucket123",
        plan_id: str = "plan123",
        **kwargs
    ) -> Dict[str, Any]:
        task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"

        task = {
            "id": task_id,
            "title": title,
            "priority": priority,
            "percentComplete": percent_complete,
            "bucketId": bucket_id,
            "planId": plan_id,
            "@odata.etag": f'W/"{uuid.uuid4()}"',
            "createdDateTime": datetime.utcnow().isoformat() + "Z",
            "assignments": {},
            "appliedCategories": {},
        }

        if due_date:
            task["dueDateTime"] = due_date.isoformat() + "T00:00:00Z"

        # Merge any additional fields
        task.update(kwargs)

        return task

    return _create_task


@pytest.fixture
def todo_task_factory():
    """Factory for creating mock To Do tasks."""

    def _create_task(
        task_id: str = None,
        title: str = "Test To Do",
        importance: str = "normal",
        status: str = "notStarted",
        due_date: date = None,
        list_id: str = "list123",
        **kwargs
    ) -> Dict[str, Any]:
        task_id = task_id or f"todo_{uuid.uuid4().hex[:8]}"

        task = {
            "id": task_id,
            "title": title,
            "importance": importance,
            "status": status,
            "listId": list_id,
            "createdDateTime": datetime.utcnow().isoformat() + "Z",
            "body": {"content": "", "contentType": "text"},
            "categories": [],
        }

        if due_date:
            task["dueDateTime"] = {
                "dateTime": due_date.isoformat() + "T00:00:00",
                "timeZone": "UTC",
            }

        task.update(kwargs)
        return task

    return _create_task


@pytest.fixture
def commitment_factory():
    """Factory for creating mock Commitment objects."""

    def _create_commitment(
        commitment_id: uuid.UUID = None,
        title: str = "Test Commitment",
        tier: int = 2,
        status: str = "not_started",
        target_date: date = None,
        graph_source: str = None,
        graph_task_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        commitment_id = commitment_id or uuid.uuid4()

        commitment = {
            "id": commitment_id,
            "title": title,
            "type": "task",
            "tier": tier,
            "status": status,
            "priority_score": 0.5,
            "graph_source": graph_source,
            "graph_task_id": graph_task_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        if target_date:
            commitment["target_date"] = target_date

        commitment.update(kwargs)
        return commitment

    return _create_commitment


# =====================================================
# Graph API Response Fixtures
# =====================================================

@pytest.fixture
def mock_graph_response():
    """Factory for creating mock Graph API responses."""

    def _create_response(
        items: List[Dict[str, Any]] = None,
        next_link: str = None,
        delta_link: str = None,
    ) -> Dict[str, Any]:
        response = {
            "value": items or [],
        }

        if next_link:
            response["@odata.nextLink"] = next_link

        if delta_link:
            response["@odata.deltaLink"] = delta_link

        return response

    return _create_response


@pytest.fixture
def mock_delta_response():
    """Mock delta query response."""

    def _create_delta_response(
        created: List[Dict[str, Any]] = None,
        updated: List[Dict[str, Any]] = None,
        deleted: List[str] = None,
    ) -> Dict[str, Any]:
        items = []

        # Add created items
        if created:
            items.extend(created)

        # Add updated items
        if updated:
            items.extend(updated)

        # Add deleted items (marked with @removed)
        if deleted:
            for item_id in deleted:
                items.append({
                    "id": item_id,
                    "@removed": {"reason": "deleted"}
                })

        return {
            "value": items,
            "@odata.deltaLink": f"https://graph.microsoft.com/v1.0/delta?$deltatoken={uuid.uuid4()}",
        }

    return _create_delta_response


@pytest.fixture
def mock_webhook_notification():
    """Factory for creating mock webhook notifications."""

    def _create_notification(
        subscription_id: str = "sub123",
        client_state: str = "secret123",
        change_type: str = "created",
        resource: str = "me/planner/tasks",
        resource_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        return {
            "subscriptionId": subscription_id,
            "clientState": client_state,
            "changeType": change_type,
            "resource": resource,
            "resourceData": resource_data or {},
            "subscriptionExpirationDateTime": (
                datetime.utcnow() + timedelta(hours=72)
            ).isoformat() + "Z",
            "tenantId": "tenant123",
        }

    return _create_notification


# =====================================================
# Configuration Fixtures
# =====================================================

@pytest.fixture
def mock_graph_config():
    """Mock Microsoft Graph configuration."""
    return {
        "authentication": {
            "flow_type": "delegated",
            "delegated_scopes": ["Tasks.ReadWrite", "User.Read"],
        },
        "api": {
            "use_beta": False,
            "timeout": 30.0,
            "rate_limit": {
                "max_requests": 10000,
                "window_minutes": 10,
            },
        },
        "planner": {
            "category_mappings": {
                "category1": {"tier": 0, "label": "Tier 0"},
                "category2": {"tier": 1, "label": "Tier 1"},
            },
            "bucket_mappings": {
                "In Progress": "in_progress",
                "Done": "completed",
            },
            "priority_mapping": {i: (10 - i) / 10 for i in range(11)},
            "plans": [
                {"name": "Vouchra", "area": "work", "domain": "product"},
            ],
        },
        "todo": {
            "importance_mapping": {
                "high": 0.9,
                "normal": 0.5,
                "low": 0.1,
            },
            "status_mapping": {
                "notStarted": "not_started",
                "inProgress": "in_progress",
                "completed": "completed",
            },
            "lists": [
                {"name": "CEO/Today", "area": "work", "domain": "leadership"},
            ],
        },
        "sync": {
            "backstop_interval_hours": 12,
            "conflict_resolution": "last_write_wins",
        },
    }


# =====================================================
# Database Fixtures
# =====================================================

@pytest.fixture
async def mock_sync_state_store():
    """Mock sync state store."""
    store = AsyncMock()

    store.save_delta_link = AsyncMock()
    store.get_sync_state = AsyncMock(return_value={
        "entity_type": "planner_task",
        "delta_link": "https://graph.microsoft.com/v1.0/delta?token=abc123",
        "last_sync_at": datetime.utcnow(),
        "client_state": "secret123",
    })
    store.save_subscription = AsyncMock()
    store.update_subscription_expiration = AsyncMock()
    store.delete_subscription = AsyncMock()
    store.get_all_subscriptions = AsyncMock(return_value=[])

    return store


# =====================================================
# Integration Test Fixtures
# =====================================================

@pytest.fixture
def integration_env():
    """Environment variables for integration tests."""
    import os

    # Only run integration tests if env vars are set
    if not os.getenv("GRAPH_CLIENT_ID"):
        pytest.skip("Integration tests require GRAPH_CLIENT_ID env var")

    return {
        "client_id": os.getenv("GRAPH_CLIENT_ID"),
        "tenant_id": os.getenv("GRAPH_TENANT_ID"),
        "client_secret": os.getenv("GRAPH_CLIENT_SECRET"),
    }


# =====================================================
# Performance Test Fixtures
# =====================================================

@pytest.fixture
def performance_timer():
    """Timer for performance tests."""
    from time import perf_counter

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = perf_counter()

        def stop(self):
            self.end_time = perf_counter()

        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None

    return Timer()


# =====================================================
# Async Test Utilities
# =====================================================

@pytest.fixture
def async_return():
    """Helper to create async functions that return a value."""

    def _async_return(value):
        async def _inner():
            return value
        return _inner()

    return _async_return
