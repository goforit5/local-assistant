# System Architecture: Life Graph Integration
**Version**: 1.0.0
**Date**: 2025-11-06
**Status**: Planning Phase

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [Component Architecture](#component-architecture)
4. [Database Schema](#database-schema)
5. [Service Layer](#service-layer)
6. [API Layer](#api-layer)
7. [Data Flow](#data-flow)
8. [Security Architecture](#security-architecture)
9. [Performance & Scalability](#performance--scalability)
10. [Observability](#observability)

---

## System Overview

### High-Level Architecture
```
┌──────────────────────────────────────────────────────────────────┐
│                      React UI (Port 5173)                        │
│  Vision Upload │ Commitments Dashboard │ Vendor Timeline         │
└──────────────────────────────────────────────────────────────────┘
                              │ HTTP/JSON
┌──────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (Port 8765)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐            │
│  │  Documents  │  │  Commitments │  │   Vendors   │            │
│  │     API     │  │     API      │  │     API     │            │
│  └─────────────┘  └──────────────┘  └─────────────┘            │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────────┐
│                      Service Layer                               │
│  ┌──────────────────────────────────────────────────┐           │
│  │  Document Intelligence Pipeline                   │           │
│  │  ├─ Storage Service (Content-Addressable)        │           │
│  │  ├─ Signal Processor (Classify & Normalize)      │           │
│  │  ├─ Entity Resolver (Fuzzy Matching)             │           │
│  │  ├─ Commitment Manager (Priority Calc)           │           │
│  │  └─ Interaction Logger (Event Tracking)          │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                   │
│  ┌──────────────────────────────────────────────────┐           │
│  │  Existing Vision Service (Reuse)                 │           │
│  │  ├─ Vision Processor (GPT-4o)                    │           │
│  │  ├─ Document Loader (PDF→Images)                 │           │
│  │  └─ Provider Manager (OpenAI)                    │           │
│  └──────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────────┐
│                   Data Layer                                     │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐              │
│  │ PostgreSQL │  │   Local    │  │   ChromaDB   │              │
│  │   (Core)   │  │ Filesystem │  │  (Vectors)   │              │
│  │            │  │  (PDFs)    │  │   (Future)   │              │
│  └────────────┘  └────────────┘  └──────────────┘              │
└──────────────────────────────────────────────────────────────────┘
```

### Technology Stack
| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Frontend** | React | 18+ | UI components |
| **API** | FastAPI | 0.100+ | REST API framework |
| **ORM** | SQLAlchemy | 2.0+ | Database abstraction |
| **Database** | PostgreSQL | 16+ | Primary data store |
| **Storage** | Local Filesystem | - | Document files (MVP) |
| **Cache** | Redis | 7+ | Future: hot entity cache |
| **Vectors** | ChromaDB | - | Future: semantic search |
| **AI** | OpenAI GPT-4o | - | Vision extraction |
| **Language** | Python | 3.11+ | Backend services |

---

## Architecture Principles

### 1. DRY (Don't Repeat Yourself)
- **Config-Driven**: All prompts, models, and settings in YAML files
- **Single Source of Truth**: Model registry, routing config, prompt versions
- **Reusable Components**: Shared services, utilities, validators

### 2. Separation of Concerns
- **Layered Architecture**: API → Service → Repository → Database
- **Domain-Driven Design**: Clear entity boundaries (Party, Commitment, Document)
- **Interface Segregation**: Small, focused service interfaces

### 3. Fail-Safe & Observable
- **Graceful Degradation**: Continue pipeline if non-critical steps fail
- **Comprehensive Logging**: Structured logs with trace IDs
- **Metrics Everywhere**: Prometheus counters, histograms, gauges
- **Audit Trail**: Immutable interaction log for all changes

### 4. Performance First
- **Content-Addressable Storage**: Automatic deduplication via SHA-256
- **Database Indexes**: Strategic B-tree and GIN indexes
- **Lazy Loading**: Relationships loaded on-demand
- **Caching Strategy**: 3-tier (memory → disk → database)

### 5. Type Safety
- **Pydantic Models**: Runtime validation for all I/O
- **SQLAlchemy 2.0**: Modern type hints with Mapped[]
- **OpenAPI Schema**: Auto-generated from FastAPI routes

---

## Component Architecture

### Core Components

#### 1. Document Intelligence Pipeline
**Location**: `services/document_intelligence/`

**Purpose**: Orchestrate the complete document processing workflow

**Components**:
```python
services/document_intelligence/
├── __init__.py                   # Public API
├── pipeline.py                   # DocumentProcessingPipeline (orchestrator)
├── storage.py                    # ContentAddressableStorage
├── extractors/
│   ├── __init__.py
│   ├── base.py                   # BaseExtractor (interface)
│   ├── invoice_extractor.py     # InvoiceExtractor
│   └── receipt_extractor.py     # ReceiptExtractor (future)
├── entity_resolver.py            # EntityResolver (fuzzy matching)
├── signal_processor.py           # SignalProcessor (classifier)
├── commitment_manager.py         # CommitmentManager (priority calc)
└── interaction_logger.py         # InteractionLogger (event tracking)
```

**Key Classes**:
```python
class DocumentProcessingPipeline:
    """
    Orchestrates complete document intelligence workflow.

    Flow:
    1. Store file (SHA-256 → filename)
    2. Create Signal (dedupe check)
    3. Extract via Vision API
    4. Resolve entities (vendor, party)
    5. Create commitment
    6. Link all entities
    7. Log interaction

    All in ONE database transaction (ACID).
    """

    async def process_document_upload(
        self, file: UploadFile, extraction_type: str, user_id: UUID
    ) -> ProcessingResult:
        ...
```

#### 2. Entity Resolver
**Purpose**: Match and deduplicate entities using fuzzy algorithms

**Fuzzy Matching Strategy**:
```python
class EntityResolver:
    """
    Vendor/party matching with fallback cascade:

    1. Exact match (name, tax_id)         → 100% confidence
    2. Fuzzy name (>90% similarity)       → High confidence
    3. Address + name (>80% similarity)   → Medium confidence
    4. Manual review queue                → Low confidence (<80%)

    Uses: fuzzywuzzy + pg_trgm (PostgreSQL trigram index)
    """

    async def resolve_vendor(
        self, name: str, address: Optional[str], tax_id: Optional[str]
    ) -> VendorResolution:
        ...
```

#### 3. Commitment Manager
**Purpose**: Calculate priority and manage commitment lifecycle

**Priority Algorithm**:
```python
def calculate_priority(commitment: CommitmentInput) -> PriorityResult:
    """
    Priority score (0-100) = weighted sum:

    - Time pressure (30%):    days_until_due → exponential decay
    - Severity/risk (25%):    domain-based (legal=10, finance=8, etc.)
    - Amount (15%):           logarithmic scale ($100-$100k)
    - Effort (15%):           estimated hours
    - Dependency (10%):       blocked by other commitments?
    - User preference (5%):   manual boost flag

    Returns: (score: int, reason: str, factors: dict)
    """
```

---

## Database Schema

### Schema Design Principles
1. **Normalized to 3NF**: Eliminate redundancy
2. **Polymorphic Linking**: `document_links` table (entity_type + entity_id)
3. **Audit Trail**: `interactions` table (immutable event log)
4. **Flexible Metadata**: JSONB columns for extensibility
5. **Content Addressable**: `sha256` for document deduplication

### Complete Entity-Relationship Diagram
```
┌─────────────┐
│   parties   │──┐
│ (vendors,   │  │
│  customers, │  │
│  contacts)  │  │
└─────────────┘  │
                 │ 1:N
┌─────────────┐  │
│    roles    │◄─┘
│ (contexts)  │
└─────────────┘
       │ 1:N
       ▼
┌─────────────┐       ┌──────────────┐
│commitments  │──────►│    tasks     │
│ (what you   │ 1:N   │  (actions)   │
│   owe)      │       └──────────────┘
└─────────────┘              │
       │                     │ 1:1
       │ N:1                 ▼
       │              ┌──────────────┐
       │              │    events    │
       │              │ (scheduled)  │
       │              └──────────────┘
       │
┌─────────────┐
│  documents  │
│ (PDFs, imgs)│
└─────────────┘
       │
       │ N:M (polymorphic)
       ▼
┌─────────────────┐
│ document_links  │ ──► Any entity (party, commitment, signal)
└─────────────────┘

┌─────────────┐
│   signals   │ ──► Raw inputs (uploaded PDFs, emails)
│ (raw inputs)│
└─────────────┘

┌──────────────┐
│interactions  │ ──► Event log (immutable audit trail)
│ (audit log)  │
└──────────────┘
```

### Table Definitions

#### Core Tables

**parties**
```sql
CREATE TABLE parties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind VARCHAR(20) NOT NULL CHECK (kind IN ('person', 'org')),
    name VARCHAR(255) NOT NULL,
    tax_id VARCHAR(50),
    contact_json JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_parties_name_trgm ON parties USING GIN (name gin_trgm_ops);
CREATE INDEX idx_parties_kind ON parties(kind);
CREATE INDEX idx_parties_tax_id ON parties(tax_id) WHERE tax_id IS NOT NULL;
```

**roles**
```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    role_name VARCHAR(100) NOT NULL,
    domain_tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_roles_user ON roles(user_id);
CREATE INDEX idx_roles_party ON roles(party_id);
CREATE INDEX idx_roles_domains ON roles USING GIN (domain_tags);
```

**commitments**
```sql
CREATE TYPE commitment_type AS ENUM (
    'obligation', 'responsibility', 'goal', 'routine', 'appointment', 'compliance'
);

CREATE TYPE commitment_state AS ENUM (
    'proposed', 'accepted', 'active', 'paused', 'fulfilled', 'canceled', 'delinquent'
);

CREATE TABLE commitments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    commitment_type commitment_type NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    source VARCHAR(50) NOT NULL CHECK (source IN ('email', 'doc', 'vision_extract', 'api', 'manual')),
    counterparty_id UUID REFERENCES parties(id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    due_at TIMESTAMPTZ,
    rrule TEXT,  -- iCal RRULE for recurring

    priority INT DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
    state commitment_state NOT NULL DEFAULT 'accepted',
    severity INT DEFAULT 0,
    domain_tags TEXT[] DEFAULT '{}',

    reason TEXT,  -- Explainability!
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_commitments_role ON commitments(role_id);
CREATE INDEX idx_commitments_state_due ON commitments(state, due_at);
CREATE INDEX idx_commitments_priority ON commitments(priority DESC);
CREATE INDEX idx_commitments_domains ON commitments USING GIN (domain_tags);
CREATE INDEX idx_commitments_counterparty ON commitments(counterparty_id) WHERE counterparty_id IS NOT NULL;
```

**documents** (Enhanced from existing)
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- File identification
    path TEXT NOT NULL,  -- EXISTING
    content_hash VARCHAR(64) NOT NULL,  -- ENHANCED: SHA-256
    sha256 VARCHAR(64) UNIQUE,  -- NEW: Deduplication key

    -- File metadata
    source VARCHAR(50) NOT NULL,  -- NEW: 'upload', 'email', 'vision_extract'
    mime_type VARCHAR(100),  -- NEW
    file_size BIGINT,  -- NEW
    storage_uri TEXT NOT NULL,  -- NEW: 'local://data/documents/{sha256}'

    -- Extraction results
    extraction_type VARCHAR(50),  -- NEW: 'invoice', 'receipt', 'contract'
    extraction_data JSONB,  -- NEW: Parsed JSON (invoice data)
    extraction_cost NUMERIC(10, 4),  -- NEW: AI cost
    extracted_at TIMESTAMPTZ,  -- NEW

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),  -- EXISTING
    conversation_id UUID  -- EXISTING (for chat context)
);

CREATE UNIQUE INDEX idx_documents_sha256 ON documents(sha256);
CREATE INDEX idx_documents_source ON documents(source);
CREATE INDEX idx_documents_extraction_type ON documents(extraction_type) WHERE extraction_type IS NOT NULL;
CREATE INDEX idx_documents_created ON documents(created_at DESC);
```

**signals**
```sql
CREATE TABLE signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL CHECK (source IN ('vision_upload', 'email', 'api', 'manual')),
    payload_json JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(50) NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'processing', 'attached', 'archived')),
    dedupe_key VARCHAR(255) UNIQUE,  -- Idempotency

    extraction_id UUID REFERENCES documents(id),
    extraction_cost NUMERIC(10, 4)
);

CREATE INDEX idx_signals_status ON signals(status);
CREATE INDEX idx_signals_received ON signals(received_at DESC);
CREATE UNIQUE INDEX idx_signals_dedupe ON signals(dedupe_key) WHERE dedupe_key IS NOT NULL;
```

**document_links** (Polymorphic)
```sql
CREATE TABLE document_links (
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,  -- 'party', 'commitment', 'signal', 'task'
    entity_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (document_id, entity_type, entity_id)
);

CREATE INDEX idx_doclinks_entity ON document_links(entity_type, entity_id);
CREATE INDEX idx_doclinks_document ON document_links(document_id);
```

**interactions** (Event Log)
```sql
CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50) NOT NULL,  -- 'document_upload', 'invoice_extract', 'commitment_fulfilled'
    actor_type VARCHAR(20) NOT NULL,  -- 'user', 'system'
    actor_id UUID,

    primary_entity_type VARCHAR(50) NOT NULL,
    primary_entity_id UUID NOT NULL,

    related_entities JSONB DEFAULT '[]'::jsonb,  -- [{"type": "vendor", "id": "uuid"}]
    metadata JSONB DEFAULT '{}'::jsonb,
    cost NUMERIC(10, 4),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_interactions_entity ON interactions(primary_entity_type, primary_entity_id);
CREATE INDEX idx_interactions_type ON interactions(type);
CREATE INDEX idx_interactions_created ON interactions(created_at DESC);
CREATE INDEX idx_interactions_actor ON interactions(actor_type, actor_id) WHERE actor_id IS NOT NULL;
```

### PostgreSQL Extensions
```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- Fuzzy text search
CREATE EXTENSION IF NOT EXISTS btree_gist; -- Date range constraints
```

---

## Service Layer

### Service Responsibilities

#### DocumentIntelligenceService
**Responsibility**: Orchestrate document processing pipeline

**Key Methods**:
```python
class DocumentIntelligenceService:
    async def process_upload(
        self, file: UploadFile, extraction_type: str, user_id: UUID
    ) -> ProcessingResult:
        """Main entry point - orchestrates full pipeline"""

    async def store_file(self, file: UploadFile) -> StorageResult:
        """Content-addressable storage (SHA-256)"""

    async def classify_signal(self, payload: dict) -> Classification:
        """Determine document type and extraction strategy"""
```

#### EntityResolutionService
**Responsibility**: Match and deduplicate entities

**Key Methods**:
```python
class EntityResolutionService:
    async def resolve_vendor(
        self, name: str, address: Optional[str], tax_id: Optional[str]
    ) -> VendorResolution:
        """Fuzzy match or create vendor"""

    async def fuzzy_match_parties(
        self, name: str, threshold: float = 0.9
    ) -> List[PartyMatch]:
        """Find similar parties (pg_trgm + fuzzywuzzy)"""
```

#### CommitmentService
**Responsibility**: Manage commitments and calculate priority

**Key Methods**:
```python
class CommitmentService:
    async def create_from_invoice(
        self, invoice_data: dict, vendor_id: UUID, role_id: UUID
    ) -> Commitment:
        """Auto-create payment commitment from invoice"""

    def calculate_priority(
        self, due_date: datetime, amount: float, severity: int
    ) -> PriorityResult:
        """Calculate priority score with explanation"""

    async def list_high_priority(
        self, user_id: UUID, threshold: int = 50
    ) -> List[Commitment]:
        """Get focus view (commitments dashboard)"""
```

#### InteractionService
**Responsibility**: Log all events for audit trail

**Key Methods**:
```python
class InteractionService:
    async def log_interaction(
        self,
        type: str,
        primary_entity: EntityRef,
        related_entities: List[EntityRef],
        actor_id: UUID,
        metadata: dict,
        cost: Optional[float] = None
    ) -> Interaction:
        """Create immutable interaction record"""

    async def get_timeline(
        self, entity_type: str, entity_id: UUID
    ) -> List[Interaction]:
        """Get chronological event timeline"""
```

---

## API Layer

### REST API Endpoints

#### Documents API
```python
# POST /api/documents/upload
@router.post("/upload")
async def upload_document(
    file: UploadFile,
    extraction_type: str = Form("invoice"),
    user_id: UUID = Depends(get_current_user)
) -> DocumentUploadResponse:
    """
    Upload document, extract, create entities, return graph.

    Returns:
    {
        "document_id": "uuid",
        "vendor": {"id": "uuid", "name": "Clipboard Health", "matched": true},
        "commitment": {"id": "uuid", "title": "Pay Invoice #240470", "priority": 85},
        "extraction": {"cost": 0.0048675, "model": "gpt-4o"},
        "links": {"timeline": "/api/interactions?entity_id={document_id}"}
    }
    """

# GET /api/documents/{document_id}
@router.get("/{document_id}")
async def get_document(document_id: UUID) -> DocumentDetail:
    """Get document with all linked entities"""

# GET /api/documents/{document_id}/download
@router.get("/{document_id}/download")
async def download_document(document_id: UUID) -> FileResponse:
    """Download original PDF"""
```

#### Vendors API
```python
# GET /api/vendors
@router.get("/")
async def list_vendors(
    query: Optional[str] = None,
    limit: int = 50
) -> List[VendorSummary]:
    """List vendors with fuzzy search"""

# GET /api/vendors/{vendor_id}
@router.get("/{vendor_id}")
async def get_vendor(vendor_id: UUID) -> VendorDetail:
    """Get vendor details with stats"""

# GET /api/vendors/{vendor_id}/documents
@router.get("/{vendor_id}/documents")
async def get_vendor_documents(vendor_id: UUID) -> List[DocumentSummary]:
    """All documents for this vendor"""

# GET /api/vendors/{vendor_id}/commitments
@router.get("/{vendor_id}/commitments")
async def get_vendor_commitments(vendor_id: UUID) -> List[CommitmentSummary]:
    """All commitments (invoices to pay) for vendor"""
```

#### Commitments API
```python
# GET /api/commitments
@router.get("/")
async def list_commitments(
    user_id: UUID = Depends(get_current_user),
    state: Optional[str] = None,
    domain: Optional[str] = None,
    due_before: Optional[datetime] = None,
    priority_min: int = 0
) -> List[CommitmentSummary]:
    """Get commitments with filters (Focus View)"""

# POST /api/commitments/{commitment_id}/fulfill
@router.post("/{commitment_id}/fulfill")
async def fulfill_commitment(commitment_id: UUID) -> Commitment:
    """Mark commitment as fulfilled (creates audit log)"""
```

#### Interactions API
```python
# GET /api/interactions/timeline
@router.get("/timeline")
async def get_timeline(
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    type: Optional[str] = None,
    limit: int = 50
) -> List[InteractionSummary]:
    """Get interaction timeline (activity feed)"""

# GET /api/interactions/export
@router.get("/export")
async def export_interactions(format: str = "csv") -> FileResponse:
    """Export interactions to CSV/JSON"""
```

---

## Data Flow

### Primary Flow: Document Upload

```
┌──────────┐
│  User    │
│ (React)  │
└────┬─────┘
     │ POST /api/documents/upload (file=pdf, extraction_type=invoice)
     ▼
┌────────────────────────────────────────────────────────────┐
│  FastAPI Endpoint                                          │
│  /api/documents/upload                                     │
└────┬───────────────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────────────────────┐
│  DocumentIntelligenceService.process_upload()             │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 1. Store File (content-addressable)                  │ │
│  │    - Calculate SHA-256                               │ │
│  │    - Check if exists (deduplication)                 │ │
│  │    - Save to data/documents/{sha256}.pdf             │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 2. Create Signal (idempotency check)                │ │
│  │    - dedupe_key = sha256                            │ │
│  │    - Check if already processed                      │ │
│  │    - Status = 'processing'                          │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 3. Extract with Vision API (REUSE EXISTING!)        │ │
│  │    - VisionService.extract_document()               │ │
│  │    - Returns: invoice JSON + cost                   │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 4. Resolve Vendor (fuzzy matching)                  │ │
│  │    - EntityResolver.resolve_vendor()                │ │
│  │    - Fuzzy match by name + address                  │ │
│  │    - If match: return existing                       │ │
│  │    - If new: create Party record                     │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 5. Create Commitment                                 │ │
│  │    - CommitmentService.create_from_invoice()        │ │
│  │    - Title: "Pay Invoice #{id} - {vendor}"          │ │
│  │    - Calculate priority (time + amount + risk)      │ │
│  │    - Generate reason string                          │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 6. Link All Entities (polymorphic)                  │ │
│  │    - document → signal                               │ │
│  │    - document → vendor (party)                       │ │
│  │    - document → commitment                           │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 7. Log Interaction (audit trail)                    │ │
│  │    - InteractionService.log_interaction()           │ │
│  │    - Type: 'invoice_upload_and_extract'             │ │
│  │    - Related entities: [vendor, commitment]         │ │
│  │    - Cost tracking                                   │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ALL IN ONE DATABASE TRANSACTION (ACID)                  │
└────┬───────────────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────────────────────┐
│  Return ProcessingResult                                   │
│  {                                                         │
│    "document_id": "abc123...",                            │
│    "vendor": {"id": "...", "matched": true},              │
│    "commitment": {"id": "...", "priority": 85},           │
│    "extraction": {"cost": 0.0048, "model": "gpt-4o"}     │
│  }                                                         │
└────┬───────────────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────────────────────┐
│  React UI Updates                                          │
│  - Show vendor (with "matched existing" badge)            │
│  - Show commitment card (with priority + reason)          │
│  - Show extraction cost                                    │
│  - Provide links to timeline, vendor history              │
└────────────────────────────────────────────────────────────┘
```

---

## Security Architecture

### Authentication (Current: Single-User)
```python
# Placeholder for future multi-user auth
async def get_current_user() -> UUID:
    """
    Future: JWT token validation
    Current: Return hardcoded user UUID
    """
    return UUID("00000000-0000-0000-0000-000000000001")
```

### Authorization
- **Row-Level Security**: Filter by `user_id` in all queries
- **Entity Ownership**: Only access your own commitments/documents
- **API Rate Limiting**: 100 requests/minute per user (future)

### Data Privacy
- **PII Encryption**: `contact_json` fields encrypted at rest (future)
- **Redaction Support**: `privacy_level` field on commitments
- **Export Control**: User can export all their data (GDPR compliance)

---

## Performance & Scalability

### Database Optimization
1. **Strategic Indexes**: B-tree for lookups, GIN for JSONB/arrays
2. **Materialized Views**: Pre-computed aggregations (future)
3. **Partitioning**: By `created_at` for high-volume tables (future)
4. **Connection Pooling**: SQLAlchemy pool (size=10, max_overflow=20)

### Caching Strategy (Future)
```
Level 1: Memory Cache (in-process, 0ms)
Level 2: Redis (1ms, hot entities)
Level 3: PostgreSQL (10ms, source of truth)
```

### Scalability Path
- **Current**: Single server (supports 100+ users)
- **Phase 2**: Horizontal API scaling (stateless FastAPI pods)
- **Phase 3**: Read replicas (PostgreSQL replication)
- **Phase 4**: Sharding by `user_id` (10,000+ users)

---

## Observability

### Logging
```python
# Structured logging (JSON format)
logger.info(
    "document_uploaded",
    extra={
        "document_id": str(document_id),
        "extraction_type": extraction_type,
        "file_size": file.size,
        "user_id": str(user_id),
        "cost": extraction_cost
    }
)
```

### Metrics (Prometheus)
```python
# Counter: Total documents processed
documents_processed_total.inc()

# Histogram: Extraction latency
extraction_duration_seconds.observe(duration)

# Gauge: Active commitments
active_commitments_count.set(count)
```

### Tracing (Future)
- OpenTelemetry spans for async operations
- Distributed tracing with Jaeger

---

## Deployment Architecture

### MVP (Single Server)
```
┌──────────────────────────────────────┐
│  Docker Compose                      │
│  ┌────────────────────────────────┐  │
│  │ local_assistant_api:8765       │  │
│  │ (FastAPI + Services)           │  │
│  └────────────────────────────────┘  │
│                                      │
│  ┌────────────────────────────────┐  │
│  │ local_assistant_ui:5173        │  │
│  │ (React + Vite)                 │  │
│  └────────────────────────────────┘  │
│                                      │
│  ┌────────────────────────────────┐  │
│  │ postgres:5433                  │  │
│  │ (PostgreSQL 16)                │  │
│  └────────────────────────────────┘  │
│                                      │
│  Volume:                             │
│  ./data/documents → content-addressed│
└──────────────────────────────────────┘
```

### Future (Production)
- Load balancer (Nginx/Traefik)
- Kubernetes pods (API replicas)
- Managed PostgreSQL (AWS RDS)
- S3 for document storage
- CloudFront CDN

---

## Appendix: Key Design Decisions

### Decision Log

#### 1. Content-Addressable Storage
**Decision**: Use SHA-256 as filename
**Rationale**: Automatic deduplication, provenance tracking
**Alternative**: Sequential IDs (no deduplication)
**Trade-off**: Slightly slower writes (hash calculation)

#### 2. Polymorphic Document Links
**Decision**: Single `document_links` table with `entity_type` + `entity_id`
**Rationale**: Flexible, avoids schema changes for new entity types
**Alternative**: Separate link tables per entity (more normalized)
**Trade-off**: Requires application-level polymorphism

#### 3. Commitment Priority as Computed Field
**Decision**: Store `priority` and `reason` in database (denormalized)
**Rationale**: Fast queries, avoids recomputation
**Alternative**: Compute priority on-demand
**Trade-off**: Must recompute when dependencies change

#### 4. Event-Sourced Interactions
**Decision**: Immutable `interactions` table (append-only)
**Rationale**: Complete audit trail, time-travel debugging
**Alternative**: Update records in-place
**Trade-off**: More storage, requires event replay for state reconstruction

---

**Next Steps**: Review CONFIG_SPECIFICATION.md for configuration design.
