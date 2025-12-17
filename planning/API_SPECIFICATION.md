# API Specification: Life Graph Integration
**Version**: 1.0.0
**Date**: 2025-11-06
**Author**: AI Development Team
**Status**: Planning Phase
**OpenAPI Version**: 3.0.3

---

## Table of Contents
1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Common Patterns](#common-patterns)
4. [API Endpoints](#api-endpoints)
5. [Data Models](#data-models)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Versioning Strategy](#versioning-strategy)
9. [Example Requests](#example-requests)

---

## Overview

### Base URL
```
http://localhost:8765/api
```

### Content Types
- **Request**: `application/json`, `multipart/form-data`
- **Response**: `application/json`

### Design Principles
- **RESTful**: Resources identified by URIs, HTTP methods for CRUD
- **Idempotent**: POST endpoints use `X-Idempotency-Key` header
- **Paginated**: List endpoints return cursor-based pagination
- **Typed**: Pydantic models for all request/response validation
- **Consistent**: Standardized error responses across all endpoints

---

## Authentication

### Current: Development Mode (v1.0)
```http
# No authentication required
GET /api/documents HTTP/1.1
Host: localhost:8765
```

### Future: JWT Bearer Tokens (v2.0+)
```http
GET /api/documents HTTP/1.1
Host: localhost:8765
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Token Payload**:
```json
{
  "sub": "user_id",
  "exp": 1704067200,
  "iat": 1704063600,
  "scopes": ["documents:read", "documents:write"]
}
```

---

## Common Patterns

### Pagination
All list endpoints support cursor-based pagination:

**Request Parameters**:
```
?limit=50          # Max items per page (default: 50, max: 200)
?cursor=abc123     # Opaque continuation token
?order=desc        # Sort order (asc, desc)
```

**Response Format**:
```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "xyz789",
    "has_more": true,
    "total_count": 1523
  }
}
```

### Filtering
Resource-specific filters via query parameters:
```
?created_after=2024-01-01T00:00:00Z
?created_before=2024-12-31T23:59:59Z
?entity_type=vendor
?status=pending
?priority_min=50
```

### Sorting
```
?sort_by=created_at     # Field name
?order=desc             # asc or desc
```

### Field Selection
```
?fields=id,name,created_at    # Return only specified fields
```

### Idempotency
POST/PUT/PATCH endpoints support idempotency:
```http
POST /api/documents HTTP/1.1
X-Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
Content-Type: multipart/form-data
```

**Behavior**:
- Same key within 24 hours → return cached response (201/200)
- New key → process request normally

---

## API Endpoints

### 1. Document Management

#### POST /api/documents/upload
**Purpose**: Upload document, extract data, create entities, link graph

**Request**:
```http
POST /api/documents/upload HTTP/1.1
Content-Type: multipart/form-data
X-Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000

--boundary
Content-Disposition: form-data; name="file"; filename="invoice.pdf"
Content-Type: application/pdf

<binary data>
--boundary
Content-Disposition: form-data; name="detail_level"

high
--boundary--
```

**Request Schema**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file | File | Yes | PDF, PNG, JPG, JPEG (max 10MB) |
| detail_level | string | No | Vision detail: low/auto/high (default: auto) |
| force_new_vendor | boolean | No | Skip vendor matching (default: false) |
| skip_commitment | boolean | No | Don't auto-create commitment (default: false) |

**Response** (201 Created):
```json
{
  "document_id": "doc_abc123def456",
  "sha256": "a3b2c1...",
  "deduplicated": false,
  "extraction": {
    "vendor": {
      "party_id": "party_xyz789",
      "name": "Clipboard Health",
      "legal_name": "Twomagnets Inc.",
      "tax_id": "XX-XXXXXXX",
      "matched_existing": true,
      "confidence_score": 0.95
    },
    "invoice": {
      "invoice_id": "240470",
      "invoice_date": "2024-02-14",
      "due_date": "2024-02-28",
      "total_amount": 12419.83,
      "currency": "USD"
    },
    "commitment": {
      "commitment_id": "commit_aaa111",
      "title": "Pay Invoice #240470 - Clipboard Health",
      "due_date": "2024-02-28",
      "amount": 12419.83,
      "priority": 85,
      "priority_reason": "Due in 2 days, amount $12,419.83, legal obligation"
    }
  },
  "links": {
    "document": "/api/documents/doc_abc123def456",
    "vendor": "/api/parties/party_xyz789",
    "commitment": "/api/commitments/commit_aaa111",
    "download": "/api/documents/doc_abc123def456/download"
  },
  "metadata": {
    "extraction_cost": 0.0048675,
    "model_used": "gpt-4o",
    "processing_time_ms": 1842
  }
}
```

**Error Responses**:
- `400 Bad Request`: Invalid file type, file too large
- `422 Unprocessable Entity`: Vision extraction failed
- `409 Conflict`: Duplicate upload (if using idempotency key)
- `500 Internal Server Error`: Unexpected error

---

#### GET /api/documents
**Purpose**: List all documents with filtering

**Request**:
```http
GET /api/documents?limit=50&cursor=abc123&entity_type=invoice&created_after=2024-01-01T00:00:00Z HTTP/1.1
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| limit | integer | Items per page (default: 50, max: 200) |
| cursor | string | Pagination cursor |
| entity_type | string | Filter by type: invoice, receipt, contract, etc. |
| created_after | datetime | ISO 8601 timestamp |
| created_before | datetime | ISO 8601 timestamp |
| party_id | string | Filter by linked party |
| has_commitment | boolean | Filter docs with/without commitments |
| sort_by | string | created_at, file_size, extraction_cost |
| order | string | asc, desc |

**Response** (200 OK):
```json
{
  "data": [
    {
      "document_id": "doc_abc123",
      "sha256": "a3b2c1...",
      "filename": "invoice.pdf",
      "file_size": 245678,
      "mime_type": "application/pdf",
      "entity_type": "invoice",
      "created_at": "2024-02-26T10:30:00Z",
      "extracted_data": {
        "vendor_name": "Clipboard Health",
        "invoice_id": "240470",
        "total": 12419.83
      },
      "links": {
        "parties": [{"party_id": "party_xyz789", "role": "vendor"}],
        "commitments": [{"commitment_id": "commit_aaa111"}]
      }
    }
  ],
  "pagination": {
    "next_cursor": "xyz789",
    "has_more": true,
    "total_count": 1523
  }
}
```

---

#### GET /api/documents/{document_id}
**Purpose**: Get document details with full entity graph

**Request**:
```http
GET /api/documents/doc_abc123?include=parties,commitments,interactions HTTP/1.1
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| include | string | Comma-separated: parties, commitments, interactions, signals |

**Response** (200 OK):
```json
{
  "document_id": "doc_abc123",
  "sha256": "a3b2c1...",
  "filename": "invoice_240470.pdf",
  "file_size": 245678,
  "mime_type": "application/pdf",
  "entity_type": "invoice",
  "created_at": "2024-02-26T10:30:00Z",
  "updated_at": "2024-02-26T10:30:15Z",
  "extracted_data": {
    "vendor_name": "Clipboard Health",
    "legal_name": "Twomagnets Inc.",
    "invoice_id": "240470",
    "invoice_date": "2024-02-14",
    "due_date": "2024-02-28",
    "total_amount": 12419.83,
    "currency": "USD",
    "line_items": [
      {
        "description": "Staffing Services - January 2024",
        "quantity": 1,
        "unit_price": 12419.83,
        "total": 12419.83
      }
    ]
  },
  "parties": [
    {
      "party_id": "party_xyz789",
      "name": "Clipboard Health",
      "legal_name": "Twomagnets Inc.",
      "party_type": "vendor",
      "tax_id": "XX-XXXXXXX",
      "contact": {
        "email": "billing@clipboardhealth.com",
        "phone": "+1-555-0123"
      }
    }
  ],
  "commitments": [
    {
      "commitment_id": "commit_aaa111",
      "title": "Pay Invoice #240470 - Clipboard Health",
      "type": "obligation",
      "state": "pending",
      "due_date": "2024-02-28",
      "priority": 85,
      "priority_reason": "Due in 2 days, amount $12,419.83"
    }
  ],
  "interactions": [
    {
      "interaction_id": "int_111",
      "interaction_type": "document_uploaded",
      "timestamp": "2024-02-26T10:30:00Z",
      "actor": "user",
      "details": {"filename": "invoice_240470.pdf"}
    },
    {
      "interaction_id": "int_112",
      "interaction_type": "entity_created",
      "timestamp": "2024-02-26T10:30:05Z",
      "actor": "system",
      "details": {"entity_type": "vendor", "party_id": "party_xyz789"}
    },
    {
      "interaction_id": "int_113",
      "interaction_type": "commitment_created",
      "timestamp": "2024-02-26T10:30:10Z",
      "actor": "system",
      "details": {"commitment_id": "commit_aaa111"}
    }
  ],
  "metadata": {
    "extraction_cost": 0.0048675,
    "model_used": "gpt-4o",
    "processing_time_ms": 1842,
    "duplicate_of": null
  }
}
```

**Error Responses**:
- `404 Not Found`: Document does not exist

---

#### GET /api/documents/{document_id}/download
**Purpose**: Download original file

**Request**:
```http
GET /api/documents/doc_abc123/download HTTP/1.1
```

**Response** (200 OK):
```http
HTTP/1.1 200 OK
Content-Type: application/pdf
Content-Disposition: attachment; filename="invoice_240470.pdf"
Content-Length: 245678

<binary data>
```

**Error Responses**:
- `404 Not Found`: Document or file does not exist

---

#### DELETE /api/documents/{document_id}
**Purpose**: Soft-delete document (mark as deleted, keep audit trail)

**Request**:
```http
DELETE /api/documents/doc_abc123?hard_delete=false HTTP/1.1
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| hard_delete | boolean | Permanently delete file (default: false) |

**Response** (204 No Content)

**Error Responses**:
- `404 Not Found`: Document does not exist
- `409 Conflict`: Document linked to active commitments

---

### 2. Party Management (Vendors/Customers/Contacts)

#### GET /api/parties
**Purpose**: List all parties with filtering

**Request**:
```http
GET /api/parties?party_type=vendor&search=clipboard&limit=50 HTTP/1.1
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| party_type | string | vendor, customer, contact, organization, individual |
| search | string | Fuzzy search on name/legal_name (pg_trgm) |
| has_tax_id | boolean | Filter parties with/without tax ID |
| created_after | datetime | ISO 8601 timestamp |
| sort_by | string | name, created_at, last_interaction |
| order | string | asc, desc |

**Response** (200 OK):
```json
{
  "data": [
    {
      "party_id": "party_xyz789",
      "name": "Clipboard Health",
      "legal_name": "Twomagnets Inc.",
      "party_type": "vendor",
      "tax_id": "XX-XXXXXXX",
      "contact": {
        "email": "billing@clipboardhealth.com",
        "phone": "+1-555-0123",
        "address": {
          "street": "123 Main St",
          "city": "San Francisco",
          "state": "CA",
          "postal_code": "94105",
          "country": "USA"
        }
      },
      "metadata": {
        "total_documents": 47,
        "total_spent": 583475.12,
        "last_interaction": "2024-02-26T10:30:00Z"
      }
    }
  ],
  "pagination": {
    "next_cursor": "xyz789",
    "has_more": true,
    "total_count": 234
  }
}
```

---

#### POST /api/parties
**Purpose**: Manually create party (with duplicate detection)

**Request**:
```http
POST /api/parties HTTP/1.1
Content-Type: application/json

{
  "name": "Acme Corporation",
  "legal_name": "Acme Corp LLC",
  "party_type": "vendor",
  "tax_id": "12-3456789",
  "contact": {
    "email": "billing@acme.com",
    "phone": "+1-555-9999",
    "address": {
      "street": "456 Oak Ave",
      "city": "Austin",
      "state": "TX",
      "postal_code": "78701",
      "country": "USA"
    }
  },
  "skip_duplicate_check": false
}
```

**Response** (201 Created):
```json
{
  "party_id": "party_new123",
  "name": "Acme Corporation",
  "created": true,
  "duplicate_check": {
    "found_similar": false,
    "suggestions": []
  }
}
```

**OR** (200 OK - if duplicate detected):
```json
{
  "party_id": "party_existing456",
  "name": "Acme Corporation",
  "created": false,
  "duplicate_check": {
    "found_similar": true,
    "suggestions": [
      {
        "party_id": "party_existing456",
        "name": "Acme Corp",
        "legal_name": "Acme Corp LLC",
        "similarity_score": 0.92
      }
    ]
  }
}
```

---

#### GET /api/parties/{party_id}
**Purpose**: Get party details with full history

**Request**:
```http
GET /api/parties/party_xyz789?include=documents,commitments,interactions HTTP/1.1
```

**Response** (200 OK):
```json
{
  "party_id": "party_xyz789",
  "name": "Clipboard Health",
  "legal_name": "Twomagnets Inc.",
  "party_type": "vendor",
  "tax_id": "XX-XXXXXXX",
  "contact": {
    "email": "billing@clipboardhealth.com",
    "phone": "+1-555-0123",
    "address": {
      "street": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "postal_code": "94105",
      "country": "USA"
    }
  },
  "created_at": "2023-05-10T08:00:00Z",
  "updated_at": "2024-02-26T10:30:05Z",
  "documents": [
    {
      "document_id": "doc_abc123",
      "filename": "invoice_240470.pdf",
      "entity_type": "invoice",
      "created_at": "2024-02-26T10:30:00Z"
    }
  ],
  "commitments": [
    {
      "commitment_id": "commit_aaa111",
      "title": "Pay Invoice #240470",
      "state": "pending",
      "due_date": "2024-02-28",
      "priority": 85
    }
  ],
  "interactions": [
    {
      "interaction_id": "int_111",
      "interaction_type": "document_uploaded",
      "timestamp": "2024-02-26T10:30:00Z"
    }
  ],
  "analytics": {
    "total_documents": 47,
    "total_invoices": 45,
    "total_spent": 583475.12,
    "average_invoice": 12965.89,
    "pending_commitments": 3,
    "fulfilled_commitments": 42,
    "first_interaction": "2023-05-10T08:00:00Z",
    "last_interaction": "2024-02-26T10:30:00Z"
  }
}
```

---

#### PATCH /api/parties/{party_id}
**Purpose**: Update party information

**Request**:
```http
PATCH /api/parties/party_xyz789 HTTP/1.1
Content-Type: application/json

{
  "contact": {
    "email": "new-billing@clipboardhealth.com"
  },
  "metadata": {
    "preferred_payment_method": "ACH"
  }
}
```

**Response** (200 OK):
```json
{
  "party_id": "party_xyz789",
  "name": "Clipboard Health",
  "updated_fields": ["contact.email", "metadata.preferred_payment_method"],
  "updated_at": "2024-02-26T11:00:00Z"
}
```

---

#### POST /api/parties/resolve
**Purpose**: Find or create party with fuzzy matching

**Request**:
```http
POST /api/parties/resolve HTTP/1.1
Content-Type: application/json

{
  "name": "Clipboard Hlth",
  "legal_name": "Twomagnets Inc",
  "tax_id": "XX-XXXXXXX",
  "similarity_threshold": 0.85
}
```

**Response** (200 OK):
```json
{
  "action": "matched",
  "party_id": "party_xyz789",
  "confidence_score": 0.95,
  "matched_fields": ["legal_name", "tax_id"],
  "party": {
    "party_id": "party_xyz789",
    "name": "Clipboard Health",
    "legal_name": "Twomagnets Inc."
  }
}
```

**OR** (201 Created - if no match):
```json
{
  "action": "created",
  "party_id": "party_new999",
  "confidence_score": null,
  "party": {
    "party_id": "party_new999",
    "name": "Clipboard Hlth",
    "legal_name": "Twomagnets Inc"
  }
}
```

---

### 3. Commitment Management

#### GET /api/commitments
**Purpose**: List commitments with filtering (Focus View)

**Request**:
```http
GET /api/commitments?state=pending&priority_min=50&domain=Finance&limit=50 HTTP/1.1
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| type | string | obligation, goal, routine, appointment |
| state | string | pending, in_progress, fulfilled, cancelled |
| priority_min | integer | Minimum priority (0-100) |
| priority_max | integer | Maximum priority (0-100) |
| domain | string | Finance, Health, Legal, Operations, Personal |
| due_before | datetime | ISO 8601 timestamp |
| due_after | datetime | ISO 8601 timestamp |
| party_id | string | Filter by linked party |
| sort_by | string | priority, due_date, created_at |
| order | string | asc, desc |

**Response** (200 OK):
```json
{
  "data": [
    {
      "commitment_id": "commit_aaa111",
      "title": "Pay Invoice #240470 - Clipboard Health",
      "type": "obligation",
      "state": "pending",
      "domain": "Finance",
      "due_date": "2024-02-28",
      "amount": 12419.83,
      "currency": "USD",
      "priority": 85,
      "priority_reason": "Due in 2 days, amount $12,419.83, legal obligation",
      "linked_entities": {
        "parties": [{"party_id": "party_xyz789", "name": "Clipboard Health"}],
        "documents": [{"document_id": "doc_abc123", "filename": "invoice_240470.pdf"}]
      },
      "created_at": "2024-02-26T10:30:10Z"
    }
  ],
  "pagination": {
    "next_cursor": "xyz789",
    "has_more": false,
    "total_count": 12
  }
}
```

---

#### POST /api/commitments
**Purpose**: Manually create commitment

**Request**:
```http
POST /api/commitments HTTP/1.1
Content-Type: application/json

{
  "title": "Review Q1 Financial Statements",
  "description": "Analyze revenue, expenses, cash flow",
  "type": "goal",
  "domain": "Finance",
  "due_date": "2024-03-31",
  "recurrence": null,
  "linked_parties": ["party_xyz789"],
  "linked_documents": ["doc_abc123"],
  "metadata": {
    "requires_cpa_review": true
  }
}
```

**Response** (201 Created):
```json
{
  "commitment_id": "commit_new777",
  "title": "Review Q1 Financial Statements",
  "type": "goal",
  "state": "pending",
  "priority": 65,
  "priority_reason": "Goal with 33 days remaining, no monetary value",
  "created_at": "2024-02-26T11:15:00Z"
}
```

---

#### GET /api/commitments/{commitment_id}
**Purpose**: Get commitment details

**Request**:
```http
GET /api/commitments/commit_aaa111?include=parties,documents,tasks HTTP/1.1
```

**Response** (200 OK):
```json
{
  "commitment_id": "commit_aaa111",
  "title": "Pay Invoice #240470 - Clipboard Health",
  "description": null,
  "type": "obligation",
  "state": "pending",
  "domain": "Finance",
  "due_date": "2024-02-28",
  "amount": 12419.83,
  "currency": "USD",
  "priority": 85,
  "priority_reason": "Due in 2 days, amount $12,419.83, legal obligation",
  "priority_components": {
    "time_pressure": 27.0,
    "severity": 25.0,
    "amount": 15.0,
    "effort": 11.25,
    "dependency": 5.0,
    "preference": 2.5
  },
  "recurrence": null,
  "created_at": "2024-02-26T10:30:10Z",
  "updated_at": "2024-02-26T10:30:10Z",
  "fulfilled_at": null,
  "parties": [
    {
      "party_id": "party_xyz789",
      "name": "Clipboard Health",
      "party_type": "vendor"
    }
  ],
  "documents": [
    {
      "document_id": "doc_abc123",
      "filename": "invoice_240470.pdf",
      "entity_type": "invoice"
    }
  ],
  "tasks": [],
  "interactions": [
    {
      "interaction_id": "int_113",
      "interaction_type": "commitment_created",
      "timestamp": "2024-02-26T10:30:10Z",
      "actor": "system"
    }
  ]
}
```

---

#### PATCH /api/commitments/{commitment_id}
**Purpose**: Update commitment (change state, priority, etc.)

**Request**:
```http
PATCH /api/commitments/commit_aaa111 HTTP/1.1
Content-Type: application/json

{
  "state": "fulfilled",
  "fulfilled_at": "2024-02-27T14:30:00Z",
  "metadata": {
    "payment_method": "ACH",
    "confirmation_number": "ACH-20240227-123456"
  }
}
```

**Response** (200 OK):
```json
{
  "commitment_id": "commit_aaa111",
  "state": "fulfilled",
  "fulfilled_at": "2024-02-27T14:30:00Z",
  "updated_fields": ["state", "fulfilled_at", "metadata"],
  "updated_at": "2024-02-27T14:30:05Z"
}
```

---

### 4. Interaction Timeline

#### GET /api/interactions
**Purpose**: Get event log with filtering

**Request**:
```http
GET /api/interactions?entity_type=party&entity_id=party_xyz789&limit=100 HTTP/1.1
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| entity_type | string | party, document, commitment |
| entity_id | string | Specific entity ID |
| interaction_type | string | document_uploaded, entity_created, etc. |
| actor | string | user, system |
| timestamp_after | datetime | ISO 8601 timestamp |
| timestamp_before | datetime | ISO 8601 timestamp |
| sort_by | string | timestamp |
| order | string | asc, desc |

**Response** (200 OK):
```json
{
  "data": [
    {
      "interaction_id": "int_111",
      "interaction_type": "document_uploaded",
      "entity_type": "document",
      "entity_id": "doc_abc123",
      "actor": "user",
      "timestamp": "2024-02-26T10:30:00Z",
      "details": {
        "filename": "invoice_240470.pdf",
        "file_size": 245678
      },
      "cost": 0.0
    },
    {
      "interaction_id": "int_112",
      "interaction_type": "entity_created",
      "entity_type": "party",
      "entity_id": "party_xyz789",
      "actor": "system",
      "timestamp": "2024-02-26T10:30:05Z",
      "details": {
        "name": "Clipboard Health",
        "matched_existing": true,
        "confidence_score": 0.95
      },
      "cost": 0.0
    },
    {
      "interaction_id": "int_113",
      "interaction_type": "commitment_created",
      "entity_type": "commitment",
      "entity_id": "commit_aaa111",
      "actor": "system",
      "timestamp": "2024-02-26T10:30:10Z",
      "details": {
        "title": "Pay Invoice #240470",
        "priority": 85
      },
      "cost": 0.0
    },
    {
      "interaction_id": "int_114",
      "interaction_type": "vision_extraction",
      "entity_type": "document",
      "entity_id": "doc_abc123",
      "actor": "system",
      "timestamp": "2024-02-26T10:30:02Z",
      "details": {
        "model": "gpt-4o",
        "processing_time_ms": 1842
      },
      "cost": 0.0048675
    }
  ],
  "pagination": {
    "next_cursor": null,
    "has_more": false,
    "total_count": 4
  }
}
```

---

### 5. Signal Processing

#### POST /api/signals
**Purpose**: Create raw signal for processing (future: webhooks, email ingestion)

**Request**:
```http
POST /api/signals HTTP/1.1
Content-Type: application/json

{
  "signal_type": "email",
  "source": "gmail_api",
  "raw_content": "{\"from\": \"billing@vendor.com\", \"subject\": \"Invoice 12345\", ...}",
  "dedupe_key": "email:msg_id_12345",
  "priority": 50
}
```

**Response** (202 Accepted):
```json
{
  "signal_id": "sig_abc123",
  "state": "pending",
  "queued_at": "2024-02-26T11:00:00Z",
  "estimated_processing_time_seconds": 5
}
```

---

#### GET /api/signals/{signal_id}
**Purpose**: Get signal processing status

**Response** (200 OK):
```json
{
  "signal_id": "sig_abc123",
  "signal_type": "email",
  "state": "processed",
  "processed_at": "2024-02-26T11:00:05Z",
  "classification": {
    "entity_type": "invoice",
    "confidence": 0.92
  },
  "created_entities": {
    "documents": ["doc_xyz789"],
    "parties": ["party_abc123"],
    "commitments": ["commit_def456"]
  }
}
```

---

### 6. Analytics & Search

#### GET /api/analytics/summary
**Purpose**: Get high-level statistics

**Request**:
```http
GET /api/analytics/summary?start_date=2024-01-01&end_date=2024-12-31 HTTP/1.1
```

**Response** (200 OK):
```json
{
  "period": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  },
  "documents": {
    "total": 1523,
    "by_type": {
      "invoice": 1204,
      "receipt": 198,
      "contract": 87,
      "other": 34
    },
    "total_storage_bytes": 1847265920,
    "deduplication_savings_bytes": 245760000
  },
  "parties": {
    "total": 234,
    "vendors": 187,
    "customers": 32,
    "contacts": 15
  },
  "commitments": {
    "total": 2891,
    "pending": 47,
    "fulfilled": 2798,
    "cancelled": 46,
    "by_domain": {
      "Finance": 1205,
      "Operations": 892,
      "Legal": 456,
      "Personal": 338
    }
  },
  "financial": {
    "total_invoices_processed": 1204,
    "total_amount": 5842376.89,
    "pending_payments": 47821.33,
    "average_invoice": 4853.47
  },
  "extraction_costs": {
    "total": 73.45,
    "average_per_document": 0.048
  }
}
```

---

#### POST /api/search
**Purpose**: Natural language search across all entities

**Request**:
```http
POST /api/search HTTP/1.1
Content-Type: application/json

{
  "query": "Show all Clipboard Health invoices from January",
  "filters": {
    "entity_types": ["document"],
    "date_range": {
      "start": "2024-01-01",
      "end": "2024-01-31"
    }
  },
  "limit": 50
}
```

**Response** (200 OK):
```json
{
  "query": "Show all Clipboard Health invoices from January",
  "results": [
    {
      "entity_type": "document",
      "entity_id": "doc_jan001",
      "relevance_score": 0.98,
      "snippet": "Invoice #240401 from Clipboard Health dated 2024-01-15",
      "data": {
        "document_id": "doc_jan001",
        "filename": "invoice_240401.pdf",
        "vendor_name": "Clipboard Health",
        "invoice_date": "2024-01-15",
        "total": 11245.67
      }
    }
  ],
  "total_results": 3
}
```

---

### 7. Health & Diagnostics

#### GET /api/health
**Purpose**: Health check endpoint

**Response** (200 OK):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-02-26T12:00:00Z",
  "services": {
    "database": "connected",
    "storage": "available",
    "vision_api": "operational"
  }
}
```

---

#### GET /api/metrics
**Purpose**: Prometheus metrics endpoint

**Response** (200 OK):
```
# HELP api_requests_total Total API requests
# TYPE api_requests_total counter
api_requests_total{method="POST",endpoint="/api/documents/upload",status="201"} 1523

# HELP api_request_duration_seconds API request duration
# TYPE api_request_duration_seconds histogram
api_request_duration_seconds_bucket{le="0.5"} 892
api_request_duration_seconds_bucket{le="1.0"} 1420
api_request_duration_seconds_bucket{le="2.0"} 1510
api_request_duration_seconds_sum 2847.32
api_request_duration_seconds_count 1523

# HELP extraction_cost_dollars_total Total extraction cost
# TYPE extraction_cost_dollars_total counter
extraction_cost_dollars_total 73.45
```

---

## Data Models

### Pydantic Request/Response Models

#### DocumentUploadRequest
```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class DocumentUploadRequest(BaseModel):
    """Request model for document upload."""

    detail_level: Optional[str] = Field(
        default="auto",
        description="Vision detail level: low, auto, high"
    )
    force_new_vendor: Optional[bool] = Field(
        default=False,
        description="Skip vendor matching and create new"
    )
    skip_commitment: Optional[bool] = Field(
        default=False,
        description="Don't auto-create commitment"
    )

    @field_validator("detail_level")
    @classmethod
    def validate_detail_level(cls, v: str) -> str:
        if v not in ["low", "auto", "high"]:
            raise ValueError("detail_level must be: low, auto, high")
        return v
```

#### DocumentUploadResponse
```python
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class VendorInfo(BaseModel):
    party_id: str
    name: str
    legal_name: Optional[str]
    tax_id: Optional[str]
    matched_existing: bool
    confidence_score: float

class InvoiceInfo(BaseModel):
    invoice_id: str
    invoice_date: str
    due_date: Optional[str]
    total_amount: float
    currency: str

class CommitmentInfo(BaseModel):
    commitment_id: str
    title: str
    due_date: Optional[str]
    amount: Optional[float]
    priority: int
    priority_reason: str

class DocumentUploadResponse(BaseModel):
    document_id: str
    sha256: str
    deduplicated: bool
    extraction: Dict[str, Any]  # Contains vendor, invoice, commitment
    links: Dict[str, str]
    metadata: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "doc_abc123",
                "sha256": "a3b2c1...",
                "deduplicated": False,
                "extraction": {
                    "vendor": {
                        "party_id": "party_xyz789",
                        "name": "Clipboard Health"
                    }
                }
            }
        }
```

#### PartyCreateRequest
```python
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class Address(BaseModel):
    street: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    country: Optional[str]

class ContactInfo(BaseModel):
    email: Optional[EmailStr]
    phone: Optional[str]
    address: Optional[Address]

class PartyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    legal_name: Optional[str] = Field(None, max_length=255)
    party_type: str = Field(..., pattern="^(vendor|customer|contact|organization|individual)$")
    tax_id: Optional[str] = Field(None, max_length=50)
    contact: Optional[ContactInfo]
    skip_duplicate_check: bool = Field(default=False)
    metadata: Optional[Dict[str, Any]]
```

#### CommitmentCreateRequest
```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class CommitmentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    type: str = Field(..., pattern="^(obligation|goal|routine|appointment)$")
    domain: Optional[str] = Field(None, pattern="^(Finance|Health|Legal|Operations|Personal)$")
    due_date: Optional[date]
    amount: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(default="USD", max_length=3)
    recurrence: Optional[str]  # cron expression
    linked_parties: Optional[List[str]] = Field(default_factory=list)
    linked_documents: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]]
```

#### PaginationParams
```python
from pydantic import BaseModel, Field
from typing import Optional

class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    cursor: Optional[str] = None
    order: str = Field(default="desc", pattern="^(asc|desc)$")
```

---

## Error Handling

### Standard Error Response
All errors follow this format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "detail_level",
        "issue": "Must be one of: low, auto, high"
      }
    ],
    "request_id": "req_abc123",
    "timestamp": "2024-02-26T12:00:00Z"
  }
}
```

### Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `INVALID_REQUEST` | Malformed request body |
| 400 | `VALIDATION_ERROR` | Pydantic validation failed |
| 401 | `UNAUTHORIZED` | Missing or invalid authentication |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource does not exist |
| 409 | `CONFLICT` | Resource conflict (duplicate, idempotency) |
| 422 | `UNPROCESSABLE_ENTITY` | Business logic error (e.g., extraction failed) |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 503 | `SERVICE_UNAVAILABLE` | Temporary unavailability |

### Error Examples

#### Validation Error (400)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": [
      {
        "loc": ["body", "detail_level"],
        "msg": "value is not a valid enumeration member; permitted: 'low', 'auto', 'high'",
        "type": "type_error.enum"
      }
    ],
    "request_id": "req_abc123",
    "timestamp": "2024-02-26T12:00:00Z"
  }
}
```

#### Not Found (404)
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Document not found",
    "details": {
      "document_id": "doc_nonexistent"
    },
    "request_id": "req_def456",
    "timestamp": "2024-02-26T12:00:00Z"
  }
}
```

#### Rate Limit (429)
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "details": {
      "limit": 100,
      "window_seconds": 60,
      "retry_after_seconds": 45
    },
    "request_id": "req_ghi789",
    "timestamp": "2024-02-26T12:00:00Z"
  }
}
```

---

## Rate Limiting

### Current: Development Mode (v1.0)
No rate limiting enforced.

### Future: Production Limits (v2.0+)

| Endpoint Category | Limit | Window |
|-------------------|-------|--------|
| Document Upload | 100 requests | 1 hour |
| Document Download | 500 requests | 1 hour |
| Read Operations (GET) | 1000 requests | 1 minute |
| Write Operations (POST/PATCH) | 200 requests | 1 minute |
| Search/Analytics | 100 requests | 1 minute |

**Headers**:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 847
X-RateLimit-Reset: 1704067200
```

**Rate Limit Algorithm**: Token bucket with burst allowance

---

## Versioning Strategy

### URL Versioning (Future)
```
/api/v1/documents
/api/v2/documents  # Breaking changes
```

### Current: Unversioned (v1.0 implicit)
```
/api/documents  # Same as /api/v1/documents
```

### Breaking vs Non-Breaking Changes

**Breaking** (requires new version):
- Removing endpoints
- Removing fields from responses
- Changing field types
- Renaming fields

**Non-Breaking** (same version):
- Adding new endpoints
- Adding optional request fields
- Adding fields to responses
- Adding enum values

### Deprecation Policy
1. Announce deprecation 90 days in advance
2. Add `Deprecation` header to responses
3. Maintain deprecated version for 180 days
4. Return 410 Gone after sunset

**Deprecation Header**:
```http
Deprecation: Sat, 1 Jun 2024 23:59:59 GMT
Sunset: Sat, 1 Dec 2024 23:59:59 GMT
Link: <https://docs.example.com/api/migration-guide>; rel="deprecation"
```

---

## Example Requests

### 1. Complete Document Upload Flow

#### Step 1: Upload Document
```bash
curl -X POST http://localhost:8765/api/documents/upload \
  -H "X-Idempotency-Key: $(uuidgen)" \
  -F "file=@invoice_240470.pdf" \
  -F "detail_level=high"
```

**Response**:
```json
{
  "document_id": "doc_abc123",
  "sha256": "a3b2c1d4e5f6...",
  "deduplicated": false,
  "extraction": {
    "vendor": {
      "party_id": "party_xyz789",
      "name": "Clipboard Health",
      "matched_existing": true,
      "confidence_score": 0.95
    },
    "commitment": {
      "commitment_id": "commit_aaa111",
      "title": "Pay Invoice #240470",
      "priority": 85
    }
  },
  "links": {
    "document": "/api/documents/doc_abc123",
    "vendor": "/api/parties/party_xyz789",
    "commitment": "/api/commitments/commit_aaa111"
  }
}
```

#### Step 2: View Vendor History
```bash
curl -X GET "http://localhost:8765/api/parties/party_xyz789?include=documents,commitments"
```

**Response**: (See Party GET response above)

#### Step 3: Mark Commitment as Fulfilled
```bash
curl -X PATCH http://localhost:8765/api/commitments/commit_aaa111 \
  -H "Content-Type: application/json" \
  -d '{
    "state": "fulfilled",
    "fulfilled_at": "2024-02-27T14:30:00Z",
    "metadata": {
      "payment_method": "ACH",
      "confirmation_number": "ACH-20240227-123456"
    }
  }'
```

#### Step 4: View Interaction Timeline
```bash
curl -X GET "http://localhost:8765/api/interactions?entity_type=commitment&entity_id=commit_aaa111"
```

---

### 2. Search Vendor Invoices
```bash
curl -X POST http://localhost:8765/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show all Clipboard Health invoices from January 2024",
    "filters": {
      "entity_types": ["document"],
      "date_range": {
        "start": "2024-01-01",
        "end": "2024-01-31"
      }
    },
    "limit": 50
  }'
```

---

### 3. Get Focus View (High Priority Commitments)
```bash
curl -X GET "http://localhost:8765/api/commitments?state=pending&priority_min=50&sort_by=priority&order=desc&limit=20"
```

---

### 4. Analytics Dashboard Data
```bash
curl -X GET "http://localhost:8765/api/analytics/summary?start_date=2024-01-01&end_date=2024-12-31"
```

---

### 5. Download Original PDF
```bash
curl -X GET http://localhost:8765/api/documents/doc_abc123/download \
  --output invoice_240470.pdf
```

---

### 6. Create Party with Duplicate Detection
```bash
curl -X POST http://localhost:8765/api/parties \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "legal_name": "Acme Corporation LLC",
    "party_type": "vendor",
    "tax_id": "12-3456789",
    "contact": {
      "email": "billing@acme.com",
      "phone": "+1-555-9999"
    },
    "skip_duplicate_check": false
  }'
```

---

### 7. Entity Resolution (Fuzzy Match)
```bash
curl -X POST http://localhost:8765/api/parties/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Clipboard Hlth",
    "legal_name": "Twomagnets Inc",
    "similarity_threshold": 0.85
  }'
```

---

## OpenAPI 3.0 Specification

Complete machine-readable spec available at:
```
/api/openapi.json
```

Interactive documentation (Swagger UI):
```
/api/docs
```

ReDoc documentation:
```
/api/redoc
```

---

## Appendix: Response Time Targets

| Endpoint | P50 | P95 | P99 |
|----------|-----|-----|-----|
| GET /api/documents | 50ms | 150ms | 300ms |
| POST /api/documents/upload | 1.5s | 3.5s | 5s |
| GET /api/parties/{id} | 80ms | 200ms | 400ms |
| POST /api/parties/resolve | 300ms | 800ms | 1.5s |
| GET /api/commitments | 100ms | 250ms | 500ms |
| POST /api/search | 500ms | 1.5s | 3s |

---

## Appendix: Database Query Examples

These are the underlying SQL queries for reference:

### Get Party with Full History
```sql
SELECT
    p.*,
    json_agg(DISTINCT d.*) FILTER (WHERE d.document_id IS NOT NULL) AS documents,
    json_agg(DISTINCT c.*) FILTER (WHERE c.commitment_id IS NOT NULL) AS commitments,
    COUNT(DISTINCT d.document_id) AS total_documents,
    SUM(COALESCE((d.extracted_data->>'total_amount')::numeric, 0)) AS total_spent
FROM party p
LEFT JOIN document_links dl ON dl.entity_id = p.party_id AND dl.entity_type = 'party'
LEFT JOIN documents d ON d.document_id = dl.document_id
LEFT JOIN document_links dl2 ON dl2.document_id = d.document_id AND dl2.entity_type = 'commitment'
LEFT JOIN commitments c ON c.commitment_id = dl2.entity_id
WHERE p.party_id = $1
GROUP BY p.party_id;
```

### Fuzzy Party Matching
```sql
SELECT
    party_id,
    name,
    legal_name,
    GREATEST(
        similarity(name, $1),
        similarity(legal_name, $2)
    ) AS confidence_score
FROM party
WHERE
    name % $1 OR legal_name % $2
ORDER BY confidence_score DESC
LIMIT 5;
```

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-06 | Initial API specification |

---

**Next Steps**: Review TESTING_STRATEGY.md for comprehensive test plans covering these API endpoints.
