# API Versioning Migration Guide

## Overview

The Local Assistant API now implements versioning with the `/api/v1` prefix. All new development should use the versioned endpoints.

## What Changed

### New Structure

```
/api/v1/
├── /health          - Health check endpoints
├── /documents       - Document intelligence endpoints
│   ├── POST /upload
│   ├── GET /{document_id}
│   └── GET /{document_id}/download
└── /vendors         - Vendor management endpoints
    ├── GET /
    ├── GET /{vendor_id}
    ├── GET /{vendor_id}/documents
    └── GET /{vendor_id}/commitments
```

### Version Information

- **Current Version**: 1.0.0
- **API Version Header**: `X-API-Version: 1.0.0` (added to all v1 responses)
- **Deprecation Date**: Legacy endpoints sunset on 2026-01-01

## Migration Path

### 1. Documents API

**Old (Deprecated)**:
```
POST /api/documents/upload
GET  /api/documents/{id}
GET  /api/documents/{id}/download
```

**New (v1)**:
```
POST /api/v1/documents/upload
GET  /api/v1/documents/{id}
GET  /api/v1/documents/{id}/download
```

**Example Migration**:
```python
# Before
response = requests.post("http://localhost:8000/api/documents/upload", files=files)

# After
response = requests.post("http://localhost:8000/api/v1/documents/upload", files=files)

# Check version header
api_version = response.headers.get("X-API-Version")  # "1.0.0"
```

### 2. Vendors API

**Old (Deprecated)**:
```
GET /api/vendors
GET /api/vendors/{id}
GET /api/vendors/{id}/documents
GET /api/vendors/{id}/commitments
```

**New (v1)**:
```
GET /api/v1/vendors
GET /api/v1/vendors/{id}
GET /api/v1/vendors/{id}/documents
GET /api/v1/vendors/{id}/commitments
```

### 3. Health Check

**Old (Deprecated)**:
```
GET /api/health
```

**New (v1)**:
```
GET /api/v1/health
```

## Deprecation Warnings

Legacy endpoints now return deprecation headers:

```http
Warning: 299 - "This endpoint is deprecated. Please use /api/v1/* endpoints."
Deprecation: true
Sunset: 2026-01-01T00:00:00Z
```

## Root Endpoint

New root endpoint provides API metadata:

```
GET /
```

**Response**:
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

## Backward Compatibility

- **Legacy endpoints remain functional** until 2026-01-01
- **No breaking changes** to existing functionality
- **Dual endpoints** during migration period
- **Gradual migration** recommended

## Implementation Details

### Files Created

1. **`/api/versions.py`** - Version constants and metadata
2. **`/api/v1/__init__.py`** - Version 1 router aggregator
3. **`/api/v1/documents.py`** - Versioned documents endpoints
4. **`/api/v1/vendors.py`** - Versioned vendors endpoints
5. **`/api/v1/health.py`** - Versioned health check

### Updated Files

- **`/api/main.py`** - Added v1 router, deprecation middleware, version headers

### Version Header Middleware

All `/api/v1/*` responses include:
```http
X-API-Version: 1.0.0
```

## Testing

Verify versioned endpoints:

```bash
# Test v1 health endpoint
curl -i http://localhost:8000/api/v1/health

# Check for X-API-Version header in response
# X-API-Version: 1.0.0

# Test legacy endpoint (should include deprecation headers)
curl -i http://localhost:8000/api/documents/upload

# Check for deprecation headers
# Warning: 299 - "This endpoint is deprecated. Please use /api/v1/* endpoints."
# Deprecation: true
# Sunset: 2026-01-01T00:00:00Z
```

## Next Steps

1. **Update client applications** to use `/api/v1/*` endpoints
2. **Monitor deprecation headers** in production logs
3. **Complete migration** before 2026-01-01 sunset date
4. **Remove legacy endpoints** after sunset date

## Future Versions

When introducing v2:
- Create `/api/v2/` directory structure
- Add v2 metadata to `versions.py`
- Include v2 router in `main.py`
- Maintain v1 for backward compatibility
- Document breaking changes in v2
