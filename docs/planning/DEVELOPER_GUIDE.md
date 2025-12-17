# Developer Guide: Unicorn-Grade Engineering Practices
**Version**: 1.0.0
**Date**: 2025-11-06
**Audience**: Software Engineers (FAANG/YC/PE quality)

---

## Overview

This guide defines the **engineering standards** for the Local Assistant + Life Graph integration. Every line of code must meet these standards. This is unicorn-grade software that would impress Silicon Valley investors, FAANG interview panels, and Y Combinator partners.

### Core Philosophy
> "Code is read 10x more than it's written. Optimize for clarity, maintainability, and future developers (including yourself)."

---

## Table of Contents
1. [Architecture Principles](#architecture-principles)
2. [Code Organization](#code-organization)
3. [Coding Standards](#coding-standards)
4. [Configuration Management](#configuration-management)
5. [Database Best Practices](#database-best-practices)
6. [Testing Strategy](#testing-strategy)
7. [Error Handling](#error-handling)
8. [Performance](#performance)
9. [Security](#security)
10. [Observability](#observability)
11. [Version Control](#version-control)
12. [Code Review Checklist](#code-review-checklist)

---

## Architecture Principles

### 1. DRY (Don't Repeat Yourself)
**Rule**: Every piece of knowledge should have a single, unambiguous representation in the system.

**Examples**:
```python
# ❌ BAD: Hardcoded magic number repeated
class DocumentService:
    def __init__(self):
        self.fuzzy_threshold = 0.90  # Duplicated in 3 places

    def match_vendor(self, name):
        if similarity > 0.90:  # Magic number again!
            ...

# ✅ GOOD: Config-driven, single source of truth
from local_assistant_shared.config import config

class DocumentService:
    def __init__(self):
        self.fuzzy_threshold = config.entity_resolution.vendor_matching.fuzzy_threshold

    def match_vendor(self, name):
        if similarity > self.fuzzy_threshold:
            ...
```

### 2. Separation of Concerns
**Rule**: Each module/class should have ONE responsibility.

**Layer Responsibilities**:
```python
# API Layer (api/routes/) - HTTP I/O only
@router.post("/documents/upload")
async def upload_document(file: UploadFile):
    result = await document_service.process_upload(file)  # Delegate to service
    return DocumentUploadResponse(**result)

# Service Layer (services/) - Business logic
class DocumentService:
    async def process_upload(self, file):
        # Orchestrate: storage → extraction → entities
        ...

# Repository Layer (repositories/) - Database access
class DocumentRepository:
    async def create(self, document: Document):
        db.add(document)
        await db.commit()
```

### 3. Dependency Injection
**Rule**: Inject dependencies rather than hardcoding them.

```python
# ❌ BAD: Tight coupling
class DocumentService:
    def __init__(self):
        self.storage = ContentAddressableStorage()  # Hardcoded!

# ✅ GOOD: Dependency injection (testable, flexible)
class DocumentService:
    def __init__(self, storage: StorageProvider):
        self.storage = storage

# Usage
storage = ContentAddressableStorage(config.storage)
service = DocumentService(storage=storage)

# Testing
mock_storage = MagicMock(spec=StorageProvider)
service = DocumentService(storage=mock_storage)
```

### 4. Interface Segregation
**Rule**: Many small interfaces are better than one large interface.

```python
# ✅ GOOD: Small, focused protocols
class StorageProvider(Protocol):
    async def store(self, file_bytes: bytes, filename: str) -> StorageResult:
        ...

    async def retrieve(self, file_hash: str) -> bytes:
        ...

class ExtractorProvider(Protocol):
    async def extract(self, file_path: str, type: str) -> ExtractionResult:
        ...

# Services depend on interfaces, not implementations
class DocumentService:
    def __init__(self, storage: StorageProvider, extractor: ExtractorProvider):
        self.storage = storage
        self.extractor = extractor
```

---

## Code Organization

### Directory Structure (Final)
```
local_assistant/
├── api/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app
│   ├── dependencies.py            # Dependency injection
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── documents.py           # Document endpoints
│   │   ├── vendors.py             # Vendor endpoints
│   │   ├── commitments.py         # Commitment endpoints
│   │   └── interactions.py        # Interaction endpoints
│   └── schemas/
│       ├── __init__.py
│       ├── document_schemas.py
│       ├── party_schemas.py
│       └── commitment_schemas.py
│
├── services/
│   ├── document_intelligence/
│   │   ├── __init__.py
│   │   ├── pipeline.py            # Main orchestrator
│   │   ├── storage.py             # Content-addressable storage
│   │   ├── signal_processor.py   # Classification
│   │   ├── entity_resolver.py    # Fuzzy matching
│   │   ├── commitment_manager.py # Priority calculation
│   │   └── interaction_logger.py # Event tracking
│   └── vision/                    # Existing (reuse)
│       ├── __init__.py
│       ├── processor.py
│       └── models.py
│
├── repositories/
│   ├── __init__.py
│   ├── party_repository.py
│   ├── commitment_repository.py
│   └── document_repository.py
│
├── memory/
│   ├── __init__.py
│   └── models.py                  # SQLAlchemy models
│
├── lib/shared/
│   └── local_assistant_shared/
│       ├── config/
│       │   ├── __init__.py
│       │   ├── config_loader.py
│       │   ├── model_registry.py
│       │   └── models.py          # Pydantic config models
│       ├── prompts/
│       │   ├── __init__.py
│       │   └── prompt_manager.py
│       └── utils/
│           ├── __init__.py
│           ├── hash_utils.py
│           ├── date_utils.py
│           ├── priority_calculator.py
│           └── fuzzy_matcher.py
│
├── config/
│   ├── document_intelligence_config.yaml
│   ├── entity_resolution_config.yaml
│   ├── commitment_priority_config.yaml
│   ├── storage_config.yaml
│   └── prompts/
│       ├── entity-resolution/
│       ├── commitment-creation/
│       └── validation/
│
├── migrations/
│   └── versions/
│       ├── 001_add_extensions.py
│       ├── 002_create_core_tables.py
│       ├── 003_enhance_documents.py
│       └── 004_create_signals_links.py
│
├── tests/
│   ├── unit/
│   │   ├── services/
│   │   ├── repositories/
│   │   └── utils/
│   ├── integration/
│   │   ├── test_document_pipeline.py
│   │   └── test_api_endpoints.py
│   └── performance/
│       └── load_test.py
│
├── scripts/
│   ├── backup_database.sh
│   ├── restore_database.sh
│   ├── validate_config.py
│   └── check_migration_health.sh
│
├── docs/
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── DEVELOPER_GUIDE.md         # This file
│   └── USER_GUIDE.md
│
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

### Naming Conventions

#### Python Files
```python
# ✅ snake_case for modules/files
document_service.py
entity_resolver.py
priority_calculator.py

# ❌ Avoid CamelCase for files
DocumentService.py  # NO
EntityResolver.py   # NO
```

#### Classes
```python
# ✅ PascalCase for classes
class DocumentService:
    ...

class EntityResolver:
    ...

class CommitmentManager:
    ...
```

#### Functions/Methods
```python
# ✅ snake_case for functions
async def process_document_upload(file: UploadFile) -> ProcessingResult:
    ...

def calculate_priority(commitment: Commitment) -> PriorityResult:
    ...
```

#### Constants
```python
# ✅ SCREAMING_SNAKE_CASE for constants
MAX_FILE_SIZE_MB = 50
DEFAULT_PRIORITY = 50
FUZZY_THRESHOLD = 0.90  # But better: load from config!
```

#### Private Methods
```python
# ✅ Leading underscore for private
class DocumentService:
    async def process_upload(self, file):  # Public
        return await self._extract_and_create_entities(file)  # Private

    async def _extract_and_create_entities(self, file):  # Private helper
        ...
```

---

## Coding Standards

### Type Hints (MANDATORY)
**Rule**: Every function signature MUST have type hints.

```python
# ✅ GOOD: Full type hints
from typing import Optional, List
from uuid import UUID

async def resolve_vendor(
    name: str,
    address: Optional[str] = None,
    tax_id: Optional[str] = None
) -> VendorResolution:
    ...

# ❌ BAD: No type hints
async def resolve_vendor(name, address=None, tax_id=None):
    ...
```

### Docstrings (MANDATORY)
**Rule**: Every public function/class must have a docstring (Google style).

```python
# ✅ GOOD: Comprehensive docstring
def calculate_priority(
    due_date: datetime,
    amount: float,
    severity: int
) -> PriorityResult:
    """
    Calculate commitment priority using weighted algorithm.

    Args:
        due_date: When the commitment is due
        amount: Dollar amount (for financial commitments)
        severity: Domain-based risk score (0-10)

    Returns:
        PriorityResult with score (0-100), reason string, and factor breakdown

    Raises:
        ValueError: If amount is negative or severity out of range

    Example:
        >>> result = calculate_priority(
        ...     due_date=datetime(2025, 11, 8),
        ...     amount=12419.83,
        ...     severity=8
        ... )
        >>> print(result.score)
        85
        >>> print(result.reason)
        "Due in 2 days, high financial risk, $12,419.83"
    """
    ...
```

### Pydantic Models (MANDATORY for I/O)
**Rule**: Use Pydantic for all API input/output and config.

```python
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

# ✅ GOOD: Pydantic model with validation
class DocumentUploadRequest(BaseModel):
    """Request schema for document upload."""
    extraction_type: str = Field(
        ...,
        description="Type of extraction (invoice, receipt, contract)",
        regex="^(invoice|receipt|contract)$"
    )
    user_id: UUID = Field(..., description="User uploading the document")

class DocumentUploadResponse(BaseModel):
    """Response schema for document upload."""
    document_id: UUID
    vendor: VendorSummary
    commitment: CommitmentSummary
    extraction: ExtractionSummary

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "vendor": {...},
                "commitment": {...},
                "extraction": {...}
            }
        }
```

### SQLAlchemy Models (Type-Safe)
**Rule**: Use SQLAlchemy 2.0 `Mapped[]` for type safety.

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime
from uuid import UUID
import uuid

# ✅ GOOD: Modern SQLAlchemy 2.0 with type hints
class Party(Base):
    __tablename__ = "parties"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(255), index=True)
    tax_id: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    roles: Mapped[List["Role"]] = relationship("Role", back_populates="party")
```

### Async/Await (ALWAYS)
**Rule**: Use async/await for all I/O operations.

```python
# ✅ GOOD: Async for database + external APIs
async def process_document_upload(file: UploadFile) -> ProcessingResult:
    # Store file (I/O)
    storage_result = await storage.store(file)

    # Extract with Vision API (I/O)
    extraction = await vision_service.extract(storage_result.path)

    # Resolve vendor (database I/O)
    vendor = await entity_resolver.resolve_vendor(extraction.vendor_name)

    # Create commitment (database I/O)
    commitment = await commitment_manager.create(...)

    return ProcessingResult(...)

# ❌ BAD: Blocking calls
def process_document_upload(file):
    storage_result = storage.store(file)  # Blocks!
    ...
```

### Error Handling (Defensive)
**Rule**: Handle errors gracefully, provide context, never swallow exceptions.

```python
# ✅ GOOD: Specific exceptions with context
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

async def resolve_vendor(name: str) -> VendorResolution:
    try:
        # Fuzzy match
        candidates = await _fuzzy_match(name)

        if not candidates:
            # No match found - create new vendor
            return await _create_new_vendor(name)

        # Return best match
        return VendorResolution(matched=True, vendor=candidates[0])

    except DatabaseError as e:
        logger.error(
            "Database error during vendor resolution",
            extra={
                "vendor_name": name,
                "error": str(e),
                "trace_id": current_trace_id()
            }
        )
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again."
        ) from e

    except Exception as e:
        logger.exception("Unexpected error during vendor resolution")
        raise

# ❌ BAD: Silent failure
async def resolve_vendor(name):
    try:
        return await _fuzzy_match(name)
    except:
        return None  # NO! Lost error context
```

---

## Configuration Management

### Config-Driven Everything
**Rule**: ZERO hardcoded values. Everything comes from config files.

```python
# ❌ BAD: Hardcoded values scattered in code
class EntityResolver:
    def __init__(self):
        self.threshold = 0.90  # Magic number!
        self.max_candidates = 5  # Magic number!

    async def match(self, name):
        if similarity > 0.90:  # Repeated magic number!
            ...

# ✅ GOOD: Config-driven
from local_assistant_shared.config import ConfigLoader
from config.models import EntityResolutionConfig

# Load config once at startup
config_loader = ConfigLoader(EntityResolutionConfig, "config/entity_resolution_config.yaml")
config = config_loader.load()

class EntityResolver:
    def __init__(self, config: EntityResolutionConfig):
        self.config = config

    async def match(self, name: str) -> List[VendorMatch]:
        threshold = self.config.fuzzy_matching.name_similarity.threshold
        max_candidates = self.config.deduplication.max_candidates

        if similarity > threshold:
            ...
```

### Versioned Prompts
**Rule**: All AI prompts must be versioned and stored in YAML files.

```python
# ❌ BAD: Prompt hardcoded in Python
VENDOR_MATCHING_PROMPT = """
You are an expert entity resolver.
Given two vendor names, determine if they match.
...
"""  # Impossible to version, test, or A/B test

# ✅ GOOD: Versioned prompt in YAML
from local_assistant_shared.prompts import PromptManager

manager = PromptManager(backend="local", prompts_dir="config/prompts")
prompt = manager.load_prompt(
    service_name="entity-resolution",
    prompt_name="vendor_matching",
    version="1.0.0"  # Semantic versioning
)

rendered = prompt.render(
    candidate_name="Clipboard Health",
    existing_name="Clipboard Health (Twomagnets Inc.)"
)

# Prompt hash for provenance
logger.info(f"Using prompt {prompt.get_id()} (hash={prompt.hash()})")
```

### Environment Variables
**Rule**: Use `.env` for secrets and environment-specific config.

```python
# .env (NEVER commit this file!)
DATABASE_URL=postgresql://user:pass@localhost:5433/assistant
OPENAI_API_KEY=sk-...
STORAGE_BACKEND=local
ENVIRONMENT=development

# Load with python-dotenv
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
```

---

## Database Best Practices

### Migrations (Alembic)
**Rule**: ALL schema changes via versioned migrations. Never modify production DB manually.

```bash
# Create migration
alembic revision -m "add_vendor_metadata_column"

# Edit migration file
# migrations/versions/xxx_add_vendor_metadata_column.py

# Test upgrade
alembic upgrade head

# Test downgrade
alembic downgrade -1

# Verify rollback works
alembic upgrade head
```

### Indexes (Strategic)
**Rule**: Index columns used in WHERE, JOIN, ORDER BY.

```python
# ✅ GOOD: Index on frequently queried columns
CREATE INDEX idx_commitments_state_due ON commitments(state, due_at);
CREATE INDEX idx_parties_name_trgm ON parties USING GIN (name gin_trgm_ops);

# Query uses index
SELECT * FROM commitments
WHERE state = 'active' AND due_at < NOW()
ORDER BY priority DESC;
```

### Transactions (ACID)
**Rule**: Use transactions for multi-step operations.

```python
# ✅ GOOD: All-or-nothing transaction
async def process_document_upload(file: UploadFile) -> ProcessingResult:
    async with db_session.begin():  # Transaction start
        # 1. Store file
        document = await document_repo.create(...)

        # 2. Create vendor
        vendor = await party_repo.create(...)

        # 3. Create commitment
        commitment = await commitment_repo.create(...)

        # 4. Link entities
        await link_repo.create_links(...)

        # 5. Log interaction
        await interaction_repo.create(...)

        # Commit happens here (automatic)
        # If ANY step fails → rollback ALL

    return ProcessingResult(...)
```

### Query Optimization
**Rule**: Use EXPLAIN ANALYZE to verify query performance.

```sql
-- Check query plan
EXPLAIN ANALYZE
SELECT * FROM commitments
WHERE state = 'active' AND priority >= 50
ORDER BY priority DESC
LIMIT 50;

-- Should show: Index Scan on idx_commitments_priority
-- NOT: Seq Scan on commitments

-- Add missing indexes if needed
CREATE INDEX idx_commitments_state_priority ON commitments(state, priority);
```

---

## Testing Strategy

### Pyramid (Unit > Integration > E2E)
```
        /\
       /E2E\        10% - Slow, expensive
      /------\
     /  Integ \     20% - Medium speed
    /----------\
   /    Unit    \   70% - Fast, cheap
  /--------------\
```

### Unit Tests (70% of tests)
**Rule**: Test each function in isolation.

```python
# tests/unit/services/test_priority_calculator.py
import pytest
from datetime import datetime, timedelta
from services.document_intelligence.priority.calculator import calculate_priority


def test_priority_high_due_soon():
    """Test priority is high when due in 2 days."""
    result = calculate_priority(
        due_date=datetime.now() + timedelta(days=2),
        amount=12419.83,
        severity=8
    )

    assert result.score >= 80
    assert "Due in 2 days" in result.reason


def test_priority_low_due_far():
    """Test priority is low when due in 3 months."""
    result = calculate_priority(
        due_date=datetime.now() + timedelta(days=90),
        amount=100.00,
        severity=3
    )

    assert result.score <= 30
```

### Integration Tests (20% of tests)
**Rule**: Test multiple components together with real database.

```python
# tests/integration/test_document_pipeline.py
import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_document_upload_creates_entities(client, db_session):
    """Test complete document upload flow."""
    # Upload file
    with open("tests/fixtures/sample_invoice.pdf", "rb") as f:
        response = client.post(
            "/api/documents/upload",
            files={"file": f},
            data={"extraction_type": "invoice"}
        )

    assert response.status_code == 200
    data = response.json()

    # Verify entities created
    document_id = data["document_id"]
    vendor_id = data["vendor"]["id"]
    commitment_id = data["commitment"]["id"]

    # Check database
    document = db_session.get(Document, document_id)
    assert document is not None
    assert document.sha256 is not None

    vendor = db_session.get(Party, vendor_id)
    assert vendor is not None
    assert vendor.kind == "org"

    commitment = db_session.get(Commitment, commitment_id)
    assert commitment is not None
    assert commitment.commitment_type == "obligation"
```

### E2E Tests (10% of tests)
**Rule**: Test user workflows from UI to database.

```python
# tests/e2e/test_user_workflows.py
from playwright.sync_api import Page, expect


def test_upload_invoice_and_view_commitment(page: Page):
    """Test: Upload invoice → See commitment in dashboard."""
    # Navigate to Vision page
    page.goto("http://localhost:5173/vision")

    # Upload file
    page.set_input_files("input[type=file]", "tests/fixtures/sample_invoice.pdf")
    page.click("button:has-text('Extract Data')")

    # Wait for extraction
    page.wait_for_selector("text=Document Processed", timeout=30000)

    # Verify vendor shown
    expect(page.locator("text=Clipboard Health")).to_be_visible()

    # Navigate to commitments
    page.click("a:has-text('Commitments')")

    # Verify commitment appears
    expect(page.locator("text=Pay Invoice")).to_be_visible()
```

---

## Error Handling

### Exception Hierarchy
```python
# lib/shared/local_assistant_shared/exceptions.py

class LocalAssistantError(Exception):
    """Base exception for all Local Assistant errors."""
    pass


class StorageError(LocalAssistantError):
    """File storage errors."""
    pass


class EntityResolutionError(LocalAssistantError):
    """Entity matching errors."""
    pass


class ExtractionError(LocalAssistantError):
    """Vision extraction errors."""
    pass
```

### Logging with Context
```python
import logging
from contextvars import ContextVar

logger = logging.getLogger(__name__)
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="unknown")


async def process_document_upload(file: UploadFile) -> ProcessingResult:
    trace_id = str(uuid.uuid4())
    trace_id_var.set(trace_id)

    logger.info(
        "document_upload_started",
        extra={
            "trace_id": trace_id,
            "filename": file.filename,
            "size": file.size,
            "extraction_type": extraction_type
        }
    )

    try:
        result = await _process(file)

        logger.info(
            "document_upload_completed",
            extra={
                "trace_id": trace_id,
                "document_id": str(result.document_id),
                "vendor_id": str(result.vendor_id),
                "cost": result.extraction.cost
            }
        )

        return result

    except Exception as e:
        logger.error(
            "document_upload_failed",
            extra={
                "trace_id": trace_id,
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise
```

---

## Performance

### Database Connection Pooling
```python
# api/main.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,           # 10 connections in pool
    max_overflow=20,        # Allow 20 extra connections
    pool_pre_ping=True,     # Check connection health
    echo=False              # Disable SQL logging in prod
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)
```

### Caching Strategy (Future)
```python
# 3-tier caching
from functools import lru_cache
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)


@lru_cache(maxsize=1000)  # Level 1: Memory cache
async def get_vendor_by_id(vendor_id: UUID) -> Party:
    # Level 2: Redis cache
    cached = redis_client.get(f"vendor:{vendor_id}")
    if cached:
        return Party.parse_raw(cached)

    # Level 3: Database
    vendor = await db.get(Party, vendor_id)

    # Cache for 1 hour
    redis_client.setex(f"vendor:{vendor_id}", 3600, vendor.json())

    return vendor
```

---

## Security

### SQL Injection Prevention
```python
# ✅ GOOD: Use SQLAlchemy ORM (parameterized queries)
from sqlalchemy import select

stmt = select(Party).where(Party.name == user_input)
result = await db.execute(stmt)

# ❌ BAD: Raw SQL with string interpolation
query = f"SELECT * FROM parties WHERE name = '{user_input}'"  # SQL INJECTION!
```

### Secrets Management
```python
# ❌ BAD: Hardcoded secrets
OPENAI_API_KEY = "sk-proj-..."  # NEVER commit this!

# ✅ GOOD: Environment variables
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")
```

---

## Observability

### Structured Logging (JSON)
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "document_processed",
    document_id=str(document_id),
    vendor_id=str(vendor_id),
    extraction_cost=0.0048,
    processing_time_ms=1234
)

# Output (JSON):
# {"event": "document_processed", "document_id": "...", "vendor_id": "...", ...}
```

### Prometheus Metrics
```python
from prometheus_client import Counter, Histogram

documents_processed = Counter(
    'documents_processed_total',
    'Total documents processed',
    ['type', 'status']
)

extraction_duration = Histogram(
    'extraction_duration_seconds',
    'Time spent extracting documents',
    ['type']
)

# Usage
documents_processed.labels(type='invoice', status='success').inc()
extraction_duration.labels(type='invoice').observe(1.234)
```

---

## Version Control

### Commit Messages (Conventional Commits)
```bash
# Format: <type>(<scope>): <subject>

feat(api): add document upload endpoint
fix(entity-resolver): handle null tax IDs
docs(readme): update installation instructions
test(pipeline): add integration test for document upload
refactor(storage): extract interface for storage providers
chore(deps): upgrade SQLAlchemy to 2.0.25
```

### Branch Strategy
```bash
# Main branches
main               # Production-ready code
develop            # Integration branch

# Feature branches
feature/lifegraph-integration
feature/vendor-matching
fix/priority-calculation-bug
docs/api-documentation
```

---

## Code Review Checklist

### Before Submitting PR
- [ ] All tests pass (`pytest`)
- [ ] Type checking passes (`mypy --strict`)
- [ ] Linting passes (`ruff check`)
- [ ] Code coverage >80% (`pytest --cov`)
- [ ] Documentation updated (docstrings + README if needed)
- [ ] Config changes documented (if any)
- [ ] Migration tested (up + down if DB changes)
- [ ] No hardcoded values (everything config-driven)
- [ ] Error handling tested (failure scenarios)
- [ ] Observability added (logs + metrics)

### Reviewer Checklist
- [ ] Code follows DRY principles
- [ ] Functions have single responsibility
- [ ] Type hints on all signatures
- [ ] Docstrings on public functions
- [ ] Error handling is defensive
- [ ] Tests cover edge cases
- [ ] Config-driven (no magic numbers)
- [ ] Performance considered (queries optimized)
- [ ] Security reviewed (no SQL injection, secrets handling)
- [ ] Observability adequate (can debug in production)

---

## Quick Reference

### Commands
```bash
# Development
python -m pytest                      # Run all tests
mypy --strict services/ api/          # Type check
ruff check .                          # Lint code
python scripts/validate_config.py    # Validate configs

# Database
alembic upgrade head                  # Run migrations
alembic downgrade -1                  # Rollback one step
./scripts/backup_database.sh         # Backup DB

# Deployment
docker-compose up -d                  # Start services
docker-compose logs -f api            # View logs
curl http://localhost:8765/health    # Health check
```

### Standards Summary
| Aspect | Standard |
|--------|----------|
| **Code Style** | ruff (PEP 8 + Black) |
| **Type Checking** | mypy strict mode |
| **Documentation** | Google-style docstrings |
| **Testing** | pytest (>80% coverage) |
| **Database** | Alembic migrations |
| **Config** | YAML (semantic versioning) |
| **Logging** | Structured JSON (structlog) |
| **Metrics** | Prometheus + Grafana |
| **Commits** | Conventional Commits |

---

**Remember**: This is unicorn-grade software. Every decision should impress a FAANG engineer, YC partner, or PE investor. Code quality is non-negotiable.

---

**Next Steps**: Load this guide every time you start coding on this project!
