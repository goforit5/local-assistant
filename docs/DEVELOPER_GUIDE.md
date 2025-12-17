# Life Graph Integration - Developer Guide

**Version**: 1.0.0
**Last Updated**: November 2025
**Status**: Production Ready

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Setup Instructions](#setup-instructions)
4. [Database Schema](#database-schema)
5. [Service Layer](#service-layer)
6. [API Layer](#api-layer)
7. [Testing Strategy](#testing-strategy)
8. [Code Style](#code-style)
9. [Development Workflow](#development-workflow)
10. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

Life Graph is a **document intelligence and CRM system** that automatically extracts entities, creates commitments, and maintains relationships from uploaded documents.

### High-Level Architecture

```
┌──────────────┐
│   Upload PDF │
└──────┬───────┘
       │
       v
┌──────────────────────────────────────────────────────┐
│              Document Processing Pipeline             │
│                                                       │
│  1. Content-Addressable Storage (SHA-256)           │
│  2. Signal Creation (Idempotency)                    │
│  3. Vision API Extraction (GPT-4o/Claude)           │
│  4. Entity Resolution (Fuzzy Matching)               │
│  5. Commitment Creation (Priority Calculation)       │
│  6. Document Links (Polymorphic Relationships)       │
│  7. Interaction Logging (Audit Trail)                │
└──────────────────────────────────────────────────────┘
       │
       v
┌──────────────────────────────────────────────────────┐
│                   Life Graph                          │
│                                                       │
│  • Parties (Vendors, Customers, Contacts)           │
│  • Roles (Context-specific identities)               │
│  • Commitments (Obligations, Goals, Routines)        │
│  • Documents (Files + Extraction Results)            │
│  • Links (Polymorphic Entity Relationships)          │
│  • Interactions (Event-sourced Audit Log)            │
└──────────────────────────────────────────────────────┘
       │
       v
┌──────────────────────────────────────────────────────┐
│                   REST API                            │
│                                                       │
│  • Documents API (Upload, Download)                  │
│  • Vendors API (List, Search, History)               │
│  • Commitments API (Focus View, Fulfill)             │
│  • Interactions API (Timeline, Export)               │
└──────────────────────────────────────────────────────┘
       │
       v
┌──────────────────────────────────────────────────────┐
│                   React UI                            │
│                                                       │
│  • Vision Result View (Entity Cards)                 │
│  • Commitments Dashboard (Filters, Quick Actions)    │
│  • Vendor History Timeline                           │
└──────────────────────────────────────────────────────┘
```

### Key Design Patterns

#### 1. Content-Addressable Storage
Files are stored with SHA-256 hash as filename → automatic deduplication

#### 2. Event-Sourced Audit Log
All actions stored in `interactions` table → complete audit trail

#### 3. Polymorphic Linking
Single `document_links` table connects documents to any entity type

#### 4. Config-Driven Architecture
Prompts, configs, weights stored in YAML → no hardcoded values

#### 5. Weighted Priority Scoring
6-factor algorithm (time, severity, amount, effort, dependency, preference)

---

## Project Structure

```
local_assistant/
├── api/                        # FastAPI REST API
│   ├── main.py                 # App initialization, /metrics endpoint
│   ├── routes/                 # API endpoints
│   │   ├── documents.py        # Document upload/download
│   │   ├── vendors.py          # Vendor CRUD
│   │   ├── commitments.py      # Commitment management
│   │   ├── interactions.py     # Timeline & export
│   │   └── health.py           # Health check endpoint
│   └── schemas/                # Pydantic request/response models
│
├── services/                   # Business logic layer
│   ├── document_intelligence/  # Core Life Graph services
│   │   ├── pipeline.py         # Orchestrator (7-step workflow)
│   │   ├── storage.py          # Content-addressable storage
│   │   ├── signal_processor.py # Signal classification
│   │   ├── entity_resolver.py  # Fuzzy matching (>90% accuracy)
│   │   ├── commitment_manager.py # Priority calculation
│   │   └── backends/           # Storage backends (local, S3)
│   │       ├── base.py
│   │       └── local.py
│   └── vision/                 # Vision extraction service
│
├── memory/                     # Database layer
│   ├── database.py             # SQLAlchemy async session
│   ├── models.py               # SQLAlchemy 2.0 models
│   └── migrations/             # Alembic migrations
│       ├── 001_extensions.py   # PostgreSQL extensions
│       ├── 002_core_tables.py  # Parties, roles, commitments
│       ├── 003_documents.py    # Documents table
│       └── 004_signals_links.py # Signals, links, interactions
│
├── config/                     # Configuration files
│   ├── document_intelligence_config.yaml
│   ├── entity_resolution_config.yaml
│   ├── commitment_priority_config.yaml
│   ├── storage_config.yaml
│   ├── prometheus.yml          # Prometheus scrape config
│   └── grafana/                # Grafana dashboards
│       ├── dashboards/
│       │   └── lifegraph_dashboard.json
│       └── provisioning/
│
├── observability/              # Monitoring & logging
│   ├── logs.py                 # Structured logging (JSON)
│   ├── metrics.py              # Prometheus metrics (general)
│   ├── lifegraph_metrics.py    # Life Graph specific metrics
│   ├── lifegraph_logging.py    # Life Graph event logging
│   ├── traces.py               # Distributed tracing
│   └── costs.py                # Cost tracking
│
├── utils/                      # Shared utilities
│   ├── hash_utils.py           # SHA-256 hashing
│   ├── date_utils.py           # Date parsing & relative dates
│   ├── priority_calculator.py  # 6-factor priority algorithm
│   └── fuzzy_matcher.py        # String similarity matching
│
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests (95% coverage)
│   │   ├── utils/              # Utility tests (81 tests)
│   │   ├── services/           # Service tests
│   │   └── api/                # API endpoint tests (89 tests)
│   └── integration/            # Integration tests (E2E)
│       ├── test_pipeline_e2e.py
│       ├── test_entity_resolution_integration.py
│       ├── test_commitment_integration.py
│       └── test_storage_integration.py
│
├── ui/                         # React frontend
│   ├── src/
│   │   ├── components/         # React components
│   │   │   ├── VendorCard.jsx
│   │   │   ├── CommitmentCard.jsx
│   │   │   ├── ExtractionCard.jsx
│   │   │   ├── CommitmentsDashboard.jsx
│   │   │   └── CommitmentsList.jsx
│   │   ├── pages/
│   │   │   └── CommitmentsPage.jsx
│   │   └── api/
│   │       └── client.js       # API client wrapper
│   └── package.json
│
├── scripts/                    # Utility scripts
│   ├── backup_database.sh      # Database backup
│   ├── restore_database.sh     # Database restore
│   └── check_migration_health.sh
│
├── docs/                       # Documentation
│   ├── DEVELOPER_GUIDE.md      # This file
│   ├── USER_GUIDE.md           # End-user guide
│   ├── DEPLOYMENT_GUIDE.md     # Production deployment
│   └── API_GUIDE.md            # API reference
│
├── docker-compose.yml          # Docker services
├── pyproject.toml              # Python dependencies (uv)
└── alembic.ini                 # Alembic configuration
```

---

## Setup Instructions

### Prerequisites

- **Python**: 3.11+ (with `uv` package manager)
- **PostgreSQL**: 16+ (running on port 5433)
- **Node.js**: 18+ (for React UI)
- **Docker**: 20+ (optional, for Docker Compose)

### Environment Setup

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd local_assistant
   ```

2. **Create virtual environment**
   ```bash
   uv venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**
   ```bash
   uv sync
   ```

4. **Set environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and database URL
   ```

   Required variables:
   ```env
   DATABASE_URL=postgresql+asyncpg://assistant:assistant@localhost:5433/assistant
   ANTHROPIC_API_KEY=sk-ant-...
   OPENAI_API_KEY=sk-...
   GOOGLE_API_KEY=AI...
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Verify setup**
   ```bash
   ./scripts/check_migration_health.sh
   ```

### Running the Application

#### Backend API
```bash
# Development mode (auto-reload)
uvicorn api.main:app --reload --port 8000

# Production mode
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Frontend UI
```bash
cd ui
npm install
npm run dev
# Visit http://localhost:5173
```

#### Docker Compose (All Services)
```bash
docker-compose up -d
```

Services exposed:
- API: `http://localhost:8000`
- UI: `http://localhost:5173`
- Postgres: `localhost:5433`
- Prometheus: `http://localhost:9091`
- Grafana: `http://localhost:3001` (admin/admin)

---

## Database Schema

### Core Tables

#### parties
Vendors, customers, contacts, organizations
```sql
CREATE TABLE parties (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT,  -- person, organization
    email TEXT,
    phone TEXT,
    address TEXT,
    tax_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fuzzy matching index
CREATE INDEX idx_parties_name_trgm ON parties USING gin(name gin_trgm_ops);
```

#### roles
Context-specific identities (Employee, Parent, Taxpayer)
```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY,
    party_id UUID REFERENCES parties(id),
    role_type TEXT NOT NULL,  -- employee, parent, taxpayer
    context TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### commitments
Obligations, goals, routines
```sql
CREATE TABLE commitments (
    id UUID PRIMARY KEY,
    role_id UUID REFERENCES roles(id),
    party_id UUID REFERENCES parties(id),  -- Counterparty (vendor)
    title TEXT NOT NULL,
    description TEXT,
    commitment_type TEXT,  -- obligation, goal, routine
    domain TEXT,  -- finance, legal, health
    state TEXT DEFAULT 'active',
    priority INTEGER,  -- 0-100
    reason TEXT,  -- Explainable priority reason
    due_date TIMESTAMPTZ,
    amount NUMERIC(12, 2),
    fulfilled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Strategic indexes
CREATE INDEX idx_commitments_state_priority
    ON commitments(state, priority DESC) WHERE state = 'active';
CREATE INDEX idx_commitments_due_date
    ON commitments(due_date) WHERE state = 'active';
```

#### documents
Uploaded files with SHA-256 deduplication
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    file_path TEXT NOT NULL,  -- data/documents/{sha256}.{ext}
    filename TEXT NOT NULL,
    sha256 TEXT UNIQUE NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    extraction_type TEXT,  -- invoice, receipt, contract
    extraction_result JSONB,  -- Structured extraction data
    extraction_cost NUMERIC(10, 6),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_sha256 ON documents(sha256);
```

#### document_links
Polymorphic relationships (document → entity)
```sql
CREATE TABLE document_links (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    entity_type TEXT NOT NULL,  -- signal, party, commitment
    entity_id UUID NOT NULL,
    link_type TEXT,  -- source, extracted_from
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_document_links_entity
    ON document_links(entity_type, entity_id);
```

#### interactions
Event-sourced audit log (append-only)
```sql
CREATE TABLE interactions (
    id UUID PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    interaction_type TEXT NOT NULL,  -- document_upload, vendor_match, commitment_create
    metadata JSONB,
    cost NUMERIC(10, 6),
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_interactions_entity
    ON interactions(entity_type, entity_id);
CREATE INDEX idx_interactions_created
    ON interactions(created_at DESC);
```

---

## Service Layer

### Document Processing Pipeline

**File**: `services/document_intelligence/pipeline.py`

**7-Step Workflow**:
1. **Store**: SHA-256 deduplication
2. **Signal**: Create idempotent signal
3. **Extract**: Vision API (GPT-4o/Claude)
4. **Resolve**: Fuzzy match vendor (>90% accuracy)
5. **Commit**: Create commitment with priority
6. **Link**: Polymorphic document links
7. **Log**: Interaction audit trail

**Usage**:
```python
from services.document_intelligence.pipeline import DocumentProcessingPipeline

pipeline = DocumentProcessingPipeline()

result = await pipeline.process_document_upload(
    file=uploaded_file,
    extraction_type="invoice",
    user_id=user.id
)

# Result contains:
# - document_id
# - vendor_id (matched or created)
# - commitment_id
# - extraction_cost
# - all entity links
```

### Entity Resolution

**File**: `services/document_intelligence/entity_resolver.py`

**5-Tier Cascade Matching**:
1. Exact tax_id match (100% confidence)
2. Exact normalized name (95%)
3. Fuzzy name >90% (90-95%)
4. Address + name >80% (80-90%)
5. Manual review queue (<80%)

**Usage**:
```python
from services.document_intelligence.entity_resolver import EntityResolver

resolver = EntityResolver()

resolution = await resolver.resolve_vendor(
    name="Clipboard Health",
    address="P.O. Box 103125, Pasadena CA",
    tax_id=None
)

if resolution.matched:
    print(f"Matched: {resolution.vendor.name} ({resolution.confidence:.0%})")
else:
    print(f"Created new vendor: {resolution.vendor.name}")
```

### Priority Calculation

**File**: `utils/priority_calculator.py`

**6-Factor Algorithm**:
- **Time Pressure (30%)**: days_until_due → exponential decay
- **Severity/Risk (25%)**: domain-based (legal=10, finance=8)
- **Amount (15%)**: logarithmic scale ($100-$100k)
- **Effort (15%)**: estimated hours
- **Dependency (10%)**: blocked by other commitments
- **User Preference (5%)**: manual boost flag

**Usage**:
```python
from utils.priority_calculator import PriorityCalculator

calculator = PriorityCalculator()

result = calculator.calculate(
    due_date="2024-02-28",
    amount=12419.83,
    domain="finance",
    severity=8,
)

print(f"Priority: {result.score}")  # 0-100
print(f"Reason: {result.reason}")   # "Due in 2 days, financial risk, $12,419.83"
```

---

## API Layer

### OpenAPI Documentation

Visit `/docs` for interactive Swagger UI:
```
http://localhost:8000/docs
```

Visit `/redoc` for ReDoc:
```
http://localhost:8000/redoc
```

### Key Endpoints

#### Documents API
- `POST /api/documents/upload` - Upload & process document
- `GET /api/documents/{id}` - Get document details
- `GET /api/documents/{id}/download` - Download original file

#### Vendors API
- `GET /api/vendors` - List vendors (with fuzzy search)
- `GET /api/vendors/{id}` - Get vendor details + stats
- `GET /api/vendors/{id}/documents` - Vendor's documents
- `GET /api/vendors/{id}/commitments` - Vendor's commitments

#### Commitments API
- `GET /api/commitments` - List with filters (state, domain, priority)
- `POST /api/commitments/{id}/fulfill` - Mark as fulfilled

#### Monitoring
- `GET /health` - Health check (database, uptime)
- `GET /metrics` - Prometheus metrics

---

## Testing Strategy

### Test Pyramid
- **70% Unit Tests**: Fast, isolated
- **20% Integration Tests**: Real database, E2E workflows
- **10% E2E Tests**: Full stack (future: Playwright)

### Running Tests

```bash
# All tests
pytest -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# With coverage
pytest --cov=services --cov=api --cov-report=html

# Coverage threshold check
coverage report --fail-under=80
```

### Writing Tests

**Unit Test Example**:
```python
import pytest
from utils.hash_utils import calculate_sha256

def test_sha256_calculation():
    data = b"hello world"
    expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    assert calculate_sha256(data) == expected
```

**Integration Test Example**:
```python
import pytest
from services.document_intelligence.pipeline import DocumentProcessingPipeline

@pytest.mark.asyncio
async def test_full_pipeline():
    pipeline = DocumentProcessingPipeline()

    with open("tests/fixtures/sample_invoice.pdf", "rb") as f:
        result = await pipeline.process_document_upload(
            file=f,
            extraction_type="invoice"
        )

    assert result.document_id is not None
    assert result.vendor_id is not None
    assert result.commitment_id is not None
```

---

## Code Style

### Python Style Guide

**Tools**:
- **Linter**: Ruff
- **Formatter**: Ruff format
- **Type Checker**: mypy

**Commands**:
```bash
# Lint
ruff check .

# Format
ruff format .

# Type check
mypy . --strict
```

**Conventions**:
- Use `Mapped[]` type hints (SQLAlchemy 2.0)
- Async/await for all database operations
- Pydantic models for all API schemas
- Structured logging with `structlog`
- No hardcoded values (use config files)

**Example**:
```python
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID

class Party(Base):
    __tablename__ = "parties"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[Optional[str]]
```

---

## Development Workflow

### Creating a New Feature

1. **Create feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes**
   - Write code
   - Write tests
   - Update documentation

3. **Run tests locally**
   ```bash
   pytest -v
   ruff check .
   mypy .
   ```

4. **Commit changes**
   ```bash
   git add .
   git commit -m "feat: add my feature"
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/my-feature
   ```

### Database Migrations

**Create migration**:
```bash
alembic revision -m "Add new column"
```

**Apply migration**:
```bash
alembic upgrade head
```

**Rollback migration**:
```bash
alembic downgrade -1
```

**Check current version**:
```bash
alembic current
```

---

## Troubleshooting

### Database Connection Issues

**Error**: `asyncpg.exceptions.InvalidCatalogNameError: database "assistant" does not exist`

**Solution**:
```bash
# Create database
psql -U postgres -h localhost -p 5433
CREATE DATABASE assistant;
\q

# Run migrations
alembic upgrade head
```

### Migration Conflicts

**Error**: `alembic.util.exc.CommandError: Target database is not up to date`

**Solution**:
```bash
# Check current version
alembic current

# Check migration history
alembic history

# Reset to specific version
alembic downgrade <revision>
alembic upgrade head
```

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'services'`

**Solution**:
```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH=/path/to/local_assistant:$PYTHONPATH

# Or activate virtual environment
source .venv/bin/activate
```

### Test Failures

**Error**: `pytest: command not found`

**Solution**:
```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate
```

---

## Additional Resources

- [User Guide](USER_GUIDE.md) - End-user instructions
- [Deployment Guide](DEPLOYMENT_GUIDE.md) - Production deployment
- [API Guide](API_GUIDE.md) - API reference with examples
- [Sprint Documentation](development/sprints/) - Development logs

---

**Questions?** Open an issue on GitHub or contact the development team.
