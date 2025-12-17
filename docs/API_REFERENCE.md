# API Reference

## Overview

The Local Assistant API is a RESTful API for document processing, vendor management, and commitment tracking with integrated AI capabilities.

### Base URL

```
http://localhost:8000
```

### Versioning Strategy

The API uses URL-based versioning:
- **Current Version**: v1 (stable)
- **Base Path**: `/api/v1`
- **Legacy Endpoints**: `/api/*` (deprecated, sunset: 2026-01-01)

All v1 endpoints return an `X-API-Version: 1.0.0` header.

Legacy endpoints include deprecation headers:
- `Warning: 299 - "This endpoint is deprecated. Please use /api/v1/* endpoints."`
- `Deprecation: true`
- `Sunset: 2026-01-01T00:00:00Z`

---

## Authentication

### JWT Bearer Token

The API uses JWT (JSON Web Tokens) for authentication.

**Token Types**:
- **Access Token**: Short-lived (15 minutes), used for API requests
- **Refresh Token**: Long-lived (7 days), used to obtain new access tokens

**Authentication Header**:
```http
Authorization: Bearer <access_token>
```

**Token Structure**:
```json
{
  "sub": "username",
  "user_id": 123,
  "type": "access",
  "exp": 1640995200
}
```

**Obtaining Tokens**:
```bash
# Login endpoint (to be implemented)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "secret123"
  }'
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Authentication Errors**:
- `401 Unauthorized`: Invalid or expired token
- `403 Forbidden`: Valid token but insufficient permissions

---

## Rate Limiting

The API enforces rate limits per client (IP address or authenticated user) using Redis-backed distributed limiting.

### Rate Limit Headers

Every response includes rate limit information:
```http
X-RateLimit-Limit-Minute: 100
X-RateLimit-Remaining-Minute: 95
X-RateLimit-Limit-Hour: 1000
X-RateLimit-Remaining-Hour: 980
```

### Rate Limit Tiers

| Endpoint Category | Requests/Minute | Requests/Hour |
|------------------|-----------------|---------------|
| Health checks    | 300             | 3,000         |
| Metrics          | 200             | 2,000         |
| Chat API         | 60              | 600           |
| Vendors/Commitments | 50           | 500           |
| Documents        | 30              | 300           |
| Reasoning        | 20              | 200           |
| Vision           | 10              | 100           |
| Computer Use     | 5               | 50            |
| Default          | 100             | 1,000         |

### Rate Limit Exceeded Response

When rate limits are exceeded, you'll receive a `429 Too Many Requests` response:

```json
{
  "type": "https://api.local-assistant.dev/errors/rate-limit-exceeded",
  "title": "Rate Limit Exceeded",
  "status": 429,
  "detail": "Rate limit exceeded. Please retry after 60 seconds.",
  "instance": "/api/v1/documents/upload",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "request_id": "req-abc123def456",
  "retry_after": 60
}
```

**Headers**:
```http
Retry-After: 60
```

---

## Error Responses

All errors follow **RFC 7807 Problem Details** format.

### Error Structure

```json
{
  "type": "https://api.local-assistant.dev/errors/document-not-found",
  "title": "Document Not Found",
  "status": 404,
  "detail": "Document with ID '550e8400-e29b-41d4-a716-446655440000' does not exist",
  "instance": "/api/v1/documents/550e8400-e29b-41d4-a716-446655440000",
  "error_code": "DOCUMENT_NOT_FOUND",
  "request_id": "req-abc123def456"
}
```

### Common Error Codes

| HTTP Status | Error Code              | Description                           |
|-------------|-------------------------|---------------------------------------|
| 400         | VALIDATION_ERROR        | Invalid request parameters            |
| 401         | UNAUTHORIZED            | Missing or invalid authentication     |
| 403         | FORBIDDEN               | Insufficient permissions              |
| 404         | DOCUMENT_NOT_FOUND      | Document does not exist               |
| 404         | VENDOR_NOT_FOUND        | Vendor does not exist                 |
| 404         | COMMITMENT_NOT_FOUND    | Commitment does not exist             |
| 429         | RATE_LIMIT_EXCEEDED     | Too many requests                     |
| 500         | INTERNAL_ERROR          | Unexpected server error               |
| 502         | PROVIDER_ERROR          | AI provider error (OpenAI, Anthropic) |
| 503         | CIRCUIT_BREAKER_OPEN    | Service temporarily unavailable       |

---

## Pagination

List endpoints support offset-based pagination.

### Query Parameters

- `offset`: Starting index (default: 0)
- `limit`: Page size (default: 50, max: 100)

### Pagination Response

```json
{
  "items": [...],
  "total": 250,
  "offset": 0,
  "limit": 50
}
```

### Example

```bash
# Get second page of 20 items
curl http://localhost:8000/api/v1/vendors?offset=20&limit=20
```

---

## Endpoints

### Health

#### GET /api/v1/health

Health check endpoint for monitoring service availability.

**Tags**: `health`

**Response**: `200 OK`
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-11-26T12:00:00Z",
  "uptime_seconds": 3600,
  "services": {
    "database": {
      "available": true,
      "latency_ms": 12.34
    }
  }
}
```

**Response**: `503 Service Unavailable` (if unhealthy)
```json
{
  "status": "unhealthy",
  "version": "1.0.0",
  "timestamp": "2025-11-26T12:00:00Z",
  "uptime_seconds": 3600,
  "services": {
    "database": {
      "available": false,
      "error": "Connection refused"
    }
  }
}
```

**Example**:
```bash
curl http://localhost:8000/api/v1/health
```

---

### Documents

#### POST /api/v1/documents/upload

Upload and process a document through the document intelligence pipeline.

**Tags**: `documents`

**Request**: `multipart/form-data`

| Parameter        | Type   | Required | Description                                    |
|-----------------|--------|----------|------------------------------------------------|
| file            | file   | Yes      | Document file (PDF, PNG, JPG)                  |
| extraction_type | string | No       | Extraction type: invoice, receipt, contract, form (default: invoice) |

**Workflow**:
1. Store file (content-addressable storage with SHA-256)
2. Create signal (idempotency check)
3. Extract via Vision API (GPT-4o)
4. Classify document type
5. Resolve vendor (fuzzy matching)
6. Create commitment (if invoice)
7. Link all entities
8. Log interactions

**Idempotency**: If the same file (SHA-256 hash) is uploaded twice, the second upload returns the existing result.

**Response**: `200 OK`
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "sha256": "a1b2c3d4e5f6...",
  "vendor": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "Clipboard Health",
    "matched": true,
    "confidence": 0.95,
    "tier": "fuzzy"
  },
  "commitment": {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "title": "Pay Invoice #240470 - Clipboard Health",
    "priority": 85,
    "reason": "Due in 2 days, legal risk, $12,419.83",
    "due_date": "2024-02-28T00:00:00",
    "commitment_type": "obligation",
    "state": "active"
  },
  "extraction": {
    "cost": 0.0048675,
    "model": "gpt-4o",
    "pages_processed": 3,
    "duration_seconds": 1.23
  },
  "links": {
    "timeline": "/api/v1/interactions/timeline?entity_id=550e8400-e29b-41d4-a716-446655440000",
    "vendor": "/api/v1/vendors/660e8400-e29b-41d4-a716-446655440001",
    "download": "/api/v1/documents/550e8400-e29b-41d4-a716-446655440000/download"
  },
  "metrics": {
    "storage": {
      "sha256": "a1b2c3d4e5f6...",
      "deduplicated": false
    },
    "extraction": {
      "cost": 0.0048675,
      "duration_seconds": 1.23
    }
  }
}
```

**Error Responses**:
- `400 Bad Request`: Invalid file type or empty file
- `500 Internal Server Error`: Processing failed

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@invoice.pdf" \
  -F "extraction_type=invoice"
```

---

#### GET /api/v1/documents/{document_id}

Retrieve complete document details including all linked entities.

**Tags**: `documents`

**Path Parameters**:
| Parameter   | Type | Required | Description      |
|-------------|------|----------|------------------|
| document_id | UUID | Yes      | Document ID      |

**Response**: `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "sha256": "a1b2c3d4e5f6...",
  "path": "data/documents/a1b2c3d4.pdf",
  "mime_type": "application/pdf",
  "file_size": 524288,
  "extraction_type": "invoice",
  "extraction_cost": 0.0048675,
  "extracted_at": "2025-11-08T12:00:00",
  "created_at": "2025-11-08T12:00:00",
  "vendor": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "Clipboard Health",
    "matched": true
  },
  "commitments": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "title": "Pay Invoice #240470",
      "priority": 85,
      "reason": "Due in 2 days, legal risk, $12,419.83",
      "due_date": "2024-02-28T00:00:00",
      "commitment_type": "obligation",
      "state": "active"
    }
  ],
  "signal_id": "880e8400-e29b-41d4-a716-446655440003",
  "extraction_preview": "INVOICE\n\nFrom: Clipboard Health\nInvoice #: 240470..."
}
```

**Error Responses**:
- `404 Not Found`: Document does not exist

**Example**:
```bash
curl http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440000
```

---

#### GET /api/v1/documents/{document_id}/download

Stream the original uploaded document file.

**Tags**: `documents`

**Path Parameters**:
| Parameter   | Type | Required | Description      |
|-------------|------|----------|------------------|
| document_id | UUID | Yes      | Document ID      |

**Response**: `200 OK`
- **Content-Type**: Original file MIME type (e.g., `application/pdf`)
- **Content-Disposition**: `attachment; filename="document.pdf"`
- **Body**: Binary file content

**Error Responses**:
- `404 Not Found`: Document or file does not exist

**Example**:
```bash
curl http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440000/download \
  -o downloaded_invoice.pdf
```

---

### Vendors

#### GET /api/v1/vendors

List all vendors with optional fuzzy search by name.

**Tags**: `vendors`

**Query Parameters**:
| Parameter | Type   | Required | Default | Description                        |
|-----------|--------|----------|---------|-------------------------------------|
| query     | string | No       | -       | Fuzzy search by vendor name         |
| offset    | int    | No       | 0       | Pagination offset                   |
| limit     | int    | No       | 50      | Page size (max: 100)                |

**Response**: `200 OK`
```json
{
  "vendors": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "name": "Clipboard Health",
      "kind": "org",
      "address": "123 Main St, San Francisco, CA 94102",
      "email": "billing@clipboardhealth.com",
      "phone": "+1-555-0123",
      "created_at": "2025-11-01T10:00:00"
    }
  ],
  "total": 42,
  "offset": 0,
  "limit": 50
}
```

**Example**:
```bash
# List all vendors
curl http://localhost:8000/api/v1/vendors

# Search for vendors
curl "http://localhost:8000/api/v1/vendors?query=clipboard&limit=10"
```

---

#### GET /api/v1/vendors/{vendor_id}

Get complete vendor information including statistics.

**Tags**: `vendors`

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| vendor_id | UUID | Yes      | Vendor ID   |

**Response**: `200 OK`
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "Clipboard Health",
  "kind": "org",
  "address": "123 Main St, San Francisco, CA 94102",
  "email": "billing@clipboardhealth.com",
  "phone": "+1-555-0123",
  "tax_id": "12-3456789",
  "contact_name": "John Doe",
  "notes": "Preferred vendor for healthcare staffing",
  "created_at": "2025-11-01T10:00:00",
  "updated_at": "2025-11-15T14:30:00",
  "stats": {
    "document_count": 15,
    "commitment_count": 8,
    "total_amount": null,
    "last_interaction": null
  }
}
```

**Error Responses**:
- `404 Not Found`: Vendor does not exist

**Example**:
```bash
curl http://localhost:8000/api/v1/vendors/660e8400-e29b-41d4-a716-446655440001
```

---

#### GET /api/v1/vendors/{vendor_id}/documents

Get all documents linked to a vendor.

**Tags**: `vendors`

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| vendor_id | UUID | Yes      | Vendor ID   |

**Response**: `200 OK`
```json
{
  "vendor_id": "660e8400-e29b-41d4-a716-446655440001",
  "vendor_name": "Clipboard Health",
  "documents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "path": "data/documents/a1b2c3d4.pdf",
      "extraction_type": "invoice",
      "extracted_at": "2025-11-08T12:00:00",
      "extraction_cost": 0.0048675
    }
  ],
  "total": 15
}
```

**Error Responses**:
- `404 Not Found`: Vendor does not exist

**Example**:
```bash
curl http://localhost:8000/api/v1/vendors/660e8400-e29b-41d4-a716-446655440001/documents
```

---

#### GET /api/v1/vendors/{vendor_id}/commitments

Get all commitments linked to a vendor (through roles).

**Tags**: `vendors`

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| vendor_id | UUID | Yes      | Vendor ID   |

**Response**: `200 OK`
```json
{
  "commitments": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "title": "Pay Invoice #240470 - Clipboard Health",
      "commitment_type": "obligation",
      "state": "active",
      "priority": 85,
      "reason": "Due in 2 days, legal risk, $12,419.83",
      "due_date": "2024-02-28T00:00:00",
      "domain": "financial",
      "created_at": "2025-11-08T12:00:00"
    }
  ],
  "total": 8,
  "offset": 0,
  "limit": 8
}
```

**Error Responses**:
- `404 Not Found`: Vendor does not exist

**Example**:
```bash
curl http://localhost:8000/api/v1/vendors/660e8400-e29b-41d4-a716-446655440001/commitments
```

---

## API Root

#### GET /

API root endpoint with version information.

**Response**: `200 OK`
```json
{
  "name": "Local Assistant API",
  "version": "1.0.0",
  "description": "Unicorn-grade AI assistant with vision, reasoning, and computer use",
  "api_versions": {
    "v1": {
      "version": "1.0.0",
      "status": "stable",
      "deprecated": false,
      "sunset_date": null,
      "prefix": "/api/v1"
    }
  },
  "endpoints": {
    "v1": "/api/v1",
    "legacy": "/api (deprecated)",
    "docs": "/docs",
    "metrics": "/metrics"
  },
  "deprecation_notice": "Legacy /api/* endpoints are deprecated. Please migrate to /api/v1/*"
}
```

**Example**:
```bash
curl http://localhost:8000/
```

---

## Metrics

#### GET /metrics

Prometheus metrics endpoint for monitoring.

**Response**: `200 OK`
- **Content-Type**: `text/plain; version=0.0.4; charset=utf-8`

**Metrics Collected**:
- General metrics: request count, latency, costs, errors
- Life Graph metrics: document count, vendor count, commitment count

**Example**:
```bash
curl http://localhost:8000/metrics
```

**Sample Output**:
```
# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/api/v1/health"} 1234

# HELP http_request_duration_seconds HTTP request latency
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.005"} 100
http_request_duration_seconds_bucket{le="0.01"} 250

# HELP lifegraph_documents_total Total number of documents processed
# TYPE lifegraph_documents_total gauge
lifegraph_documents_total 156

# HELP lifegraph_vendors_total Total number of vendors
# TYPE lifegraph_vendors_total gauge
lifegraph_vendors_total 42
```

---

## Additional Resources

### Interactive API Documentation

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### OpenAPI Specification

- **JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

### Related Documentation

- [Architecture Overview](./ARCHITECTURE.md)
- [Improvement Plan](./IMPROVEMENT_PLAN.md)
- [Development Guide](./DEVELOPMENT.md)

---

## Version History

| Version | Release Date | Status | Changes |
|---------|--------------|--------|---------|
| 1.0.0   | 2025-11-26   | Stable | Initial API reference documentation |
