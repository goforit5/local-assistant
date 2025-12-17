"""OpenAPI metadata customization for FastAPI."""

from fastapi.openapi.utils import get_openapi
from typing import Dict, Any

# API Metadata
API_TITLE = "Local Assistant API"
API_VERSION = "1.0.0"
API_DESCRIPTION = """
# Local Assistant API

Unicorn-grade AI assistant with vision, reasoning, and computer use capabilities.

## Features

- **Document Intelligence**: Process invoices, receipts, contracts with GPT-4o Vision
- **Vendor Management**: Fuzzy matching, deduplication, relationship tracking
- **Commitment Tracking**: Priority scoring, due date management, state tracking
- **Multi-Provider AI**: Anthropic, OpenAI, Google with intelligent routing
- **Observability**: Prometheus metrics, structured logging, health checks
- **Life Graph**: Entity relationship tracking across documents, vendors, commitments

## Architecture

This API follows a clean architecture pattern with:
- **API Layer**: FastAPI routes with Pydantic schemas
- **Service Layer**: Business logic for document processing, entity resolution
- **Persistence Layer**: PostgreSQL with SQLAlchemy ORM
- **Provider Layer**: Multi-provider AI abstraction with circuit breakers
- **Observability Layer**: Metrics, logging, tracing

## Authentication

All authenticated endpoints require a JWT Bearer token:

```http
Authorization: Bearer <access_token>
```

See [Authentication](#authentication) section for details.

## Rate Limiting

Rate limits are enforced per client (IP or authenticated user):
- Default: 100 req/min, 1000 req/hour
- Vision: 10 req/min, 100 req/hour
- Documents: 30 req/min, 300 req/hour

See [Rate Limiting](#rate-limiting) section for full details.

## Error Handling

All errors follow **RFC 7807 Problem Details** format:

```json
{
  "type": "https://api.local-assistant.dev/errors/document-not-found",
  "title": "Document Not Found",
  "status": 404,
  "detail": "Document with ID 'doc-123' does not exist",
  "instance": "/api/v1/documents/doc-123",
  "error_code": "DOCUMENT_NOT_FOUND",
  "request_id": "req-abc123def456"
}
```

## Versioning

The API uses URL-based versioning:
- Current: `/api/v1` (stable)
- Legacy: `/api/*` (deprecated, sunset: 2026-01-01)

All v1 endpoints include `X-API-Version: 1.0.0` header.

## Resources

- [Full API Reference](https://github.com/yourusername/local_assistant/blob/main/docs/API_REFERENCE.md)
- [Architecture Overview](https://github.com/yourusername/local_assistant/blob/main/docs/ARCHITECTURE.md)
- [Development Guide](https://github.com/yourusername/local_assistant/blob/main/docs/DEVELOPMENT.md)
"""

# Contact Information
CONTACT_INFO = {
    "name": "Local Assistant Team",
    "url": "https://github.com/yourusername/local_assistant",
    "email": "support@local-assistant.dev"
}

# License
LICENSE_INFO = {
    "name": "MIT",
    "url": "https://opensource.org/licenses/MIT"
}

# OpenAPI Tags (for endpoint grouping)
TAGS_METADATA = [
    {
        "name": "health",
        "description": """
Health check endpoints for monitoring service availability and dependencies.

Use these endpoints to:
- Monitor database connectivity
- Check service uptime
- Verify API availability
- Integrate with monitoring tools (e.g., Prometheus, Kubernetes)
        """
    },
    {
        "name": "documents",
        "description": """
Document processing endpoints using the document intelligence pipeline.

**Capabilities**:
- Upload PDFs, images (PNG, JPG)
- Extract structured data with GPT-4o Vision
- Auto-classify document types (invoice, receipt, contract)
- Content-addressable storage (SHA-256 deduplication)
- Link documents to vendors and commitments

**Workflow**:
1. Upload → 2. Store → 3. Extract → 4. Classify → 5. Link entities → 6. Return graph

**Supported Types**: invoice, receipt, contract, form
        """
    },
    {
        "name": "vendors",
        "description": """
Vendor management with fuzzy matching and relationship tracking.

**Capabilities**:
- List vendors with pagination
- Fuzzy search by name (PostgreSQL pg_trgm)
- View vendor statistics (document count, commitment count)
- Access vendor documents and commitments
- Track vendor relationships

**Entity Resolution**:
- Exact name matching
- Fuzzy matching with confidence scores
- Automatic deduplication
- Manual vendor creation
        """
    },
    {
        "name": "chat (legacy)",
        "description": """
**DEPRECATED** - Please use `/api/v1/chat` instead.

Legacy chat endpoints will be removed on 2026-01-01.
        """
    },
    {
        "name": "vision (legacy)",
        "description": """
**DEPRECATED** - Please use `/api/v1/vision` instead.

Legacy vision endpoints will be removed on 2026-01-01.
        """
    },
    {
        "name": "reasoning (legacy)",
        "description": """
**DEPRECATED** - Please use `/api/v1/reasoning` instead.

Legacy reasoning endpoints will be removed on 2026-01-01.
        """
    },
    {
        "name": "computer (legacy)",
        "description": """
**DEPRECATED** - Please use `/api/v1/computer` instead.

Legacy computer use endpoints will be removed on 2026-01-01.
        """
    },
    {
        "name": "costs (legacy)",
        "description": """
**DEPRECATED** - Please use `/api/v1/costs` instead.

Legacy cost tracking endpoints will be removed on 2026-01-01.
        """
    },
    {
        "name": "documents (legacy)",
        "description": """
**DEPRECATED** - Please use `/api/v1/documents` instead.

Legacy document endpoints will be removed on 2026-01-01.
        """
    },
    {
        "name": "vendors (legacy)",
        "description": """
**DEPRECATED** - Please use `/api/v1/vendors` instead.

Legacy vendor endpoints will be removed on 2026-01-01.
        """
    },
    {
        "name": "commitments (legacy)",
        "description": """
**DEPRECATED** - Please use `/api/v1/commitments` instead.

Legacy commitment endpoints will be removed on 2026-01-01.
        """
    },
    {
        "name": "interactions (legacy)",
        "description": """
**DEPRECATED** - Please use `/api/v1/interactions` instead.

Legacy interaction endpoints will be removed on 2026-01-01.
        """
    }
]

# Servers
SERVERS = [
    {
        "url": "http://localhost:8000",
        "description": "Local development server"
    },
    {
        "url": "http://127.0.0.1:8000",
        "description": "Local development server (alternative)"
    }
]


def custom_openapi(app) -> Dict[str, Any]:
    """
    Generate custom OpenAPI schema with enhanced metadata.

    This function enriches the default FastAPI OpenAPI schema with:
    - Custom title, description, version
    - Contact information and license
    - Tag descriptions for endpoint grouping
    - Server configurations
    - Security scheme definitions (JWT)

    Args:
        app: FastAPI application instance

    Returns:
        Dict containing complete OpenAPI 3.1.0 schema
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        routes=app.routes,
        tags=TAGS_METADATA,
    )

    # Add contact and license info
    openapi_schema["info"]["contact"] = CONTACT_INFO
    openapi_schema["info"]["license"] = LICENSE_INFO

    # Add servers
    openapi_schema["servers"] = SERVERS

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token obtained from /auth/login endpoint"
        }
    }

    # Add global security (can be overridden per endpoint)
    # Uncomment when authentication is fully implemented:
    # openapi_schema["security"] = [{"HTTPBearer": []}]

    # Add custom extensions
    openapi_schema["x-logo"] = {
        "url": "https://local-assistant.dev/logo.png",
        "altText": "Local Assistant Logo"
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema
