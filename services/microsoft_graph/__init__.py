"""
Microsoft Graph Integration Service

Provides unified access to Microsoft Planner and Microsoft To Do through
the Microsoft Graph API, enabling bidirectional sync with the Life Graph system.

Key Features:
- OAuth 2.0 authentication with MSAL
- Delta query for efficient incremental sync
- Webhook subscriptions for real-time notifications
- Batch processing for task details (20 at a time)
- Client-side filtering (Planner doesn't support $filter)
- Mapping between Graph tasks and Life Graph commitments

Components:
- auth: MSAL OAuth authentication and token management
- base_client: Base HTTP client with retry logic and rate limiting
- planner_client: Planner API wrapper (plans, buckets, tasks)
- todo_client: To Do API wrapper (lists, tasks)
- delta_sync: Delta query + webhook subscription manager
- graph_mapper: Bidirectional mapping between Graph and Life Graph models
- webhook_handler: Webhook notification receiver and processor
"""

from services.microsoft_graph.auth import GraphAuthenticator
from services.microsoft_graph.base_client import GraphBaseClient
from services.microsoft_graph.planner_client import PlannerClient
from services.microsoft_graph.todo_client import TodoClient
from services.microsoft_graph.delta_sync import DeltaSyncEngine
from services.microsoft_graph.graph_mapper import GraphMapper
from services.microsoft_graph.webhook_handler import WebhookHandler

__all__ = [
    "GraphAuthenticator",
    "GraphBaseClient",
    "PlannerClient",
    "TodoClient",
    "DeltaSyncEngine",
    "GraphMapper",
    "WebhookHandler",
]

__version__ = "1.0.0"
