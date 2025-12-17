# Implementation Plan: Life Graph Integration
**Version**: 1.0.0
**Date**: 2025-11-06
**Status**: Planning Phase
**Total Duration**: 4 weeks (20 working days)

---

## Overview

This document provides the **complete implementation roadmap** following unicorn-grade software engineering practices. Each phase includes detailed tasks, acceptance criteria, testing requirements, and deliverables.

### Guiding Principles
- ✅ **DRY**: Zero code duplication, config-driven everything
- ✅ **Type-Safe**: Pydantic models, SQLAlchemy Mapped[], mypy strict
- ✅ **Tested**: >80% coverage, E2E tests for critical paths
- ✅ **Observable**: Structured logging, Prometheus metrics, distributed tracing
- ✅ **Versioned**: Alembic migrations, semantic versioning for prompts/configs
- ✅ **Professional**: FAANG/YC quality code, impresses PE investors

---

## Phase 1: Foundation (Days 1-5)

### Goal
Establish core infrastructure: database schema, config system, shared libraries

### Tasks

#### 1.1 Database Migrations (Day 1)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: None

**Deliverables**:
- [ ] Alembic migration 001: PostgreSQL extensions
- [ ] Alembic migration 002: Core tables (parties, roles, commitments)
- [ ] Alembic migration 003: Enhance documents table
- [ ] Alembic migration 004: Signals, links, interactions
- [ ] Migration test suite (upgrade/downgrade validation)
- [ ] Backup script (`scripts/backup_database.sh`)
- [ ] Health check script (`scripts/check_migration_health.sh`)

**Acceptance Criteria**:
```bash
# All migrations run successfully
alembic upgrade head
alembic current  # Should show: 004_create_signals_links

# Rollback works
alembic downgrade base
alembic upgrade head  # Clean re-upgrade

# Test data inserts work
psql -U assistant -d assistant -c "INSERT INTO parties (kind, name) VALUES ('org', 'Test Vendor') RETURNING id;"
```

**Code Location**:
```
migrations/versions/
├── 001_add_extensions.py
├── 002_create_core_tables.py
├── 003_enhance_documents.py
└── 004_create_signals_links.py
```

---

#### 1.2 SQLAlchemy Models (Day 2)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: 1.1 Complete

**Deliverables**:
- [ ] `memory/models.py` - Add Life Graph models (Party, Role, Commitment, etc.)
- [ ] Update existing `Document` model with new columns
- [ ] Pydantic schemas for API I/O (`api/schemas.py`)
- [ ] Model unit tests (`tests/unit/models/test_lifegraph_models.py`)

**Acceptance Criteria**:
```python
# Models instantiate correctly
party = Party(kind="org", name="ACME Corp")
db.add(party)
db.commit()

# Relationships work
role = Role(party_id=party.id, role_name="Vendor", user_id=user.id)
commitment = Commitment(role_id=role.id, title="Pay Invoice", commitment_type="obligation")

# Type checking passes
mypy memory/models.py --strict
```

**Code Location**:
```
memory/
├── models.py              # ENHANCED (add Life Graph models)
└── __init__.py

api/schemas/
├── __init__.py
├── party_schemas.py       # NEW
├── commitment_schemas.py  # NEW
└── document_schemas.py    # ENHANCED
```

---

#### 1.3 Configuration System (Day 3)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: None (parallel with 1.1-1.2)

**Deliverables**:
- [ ] Config files (YAML):
  - `config/document_intelligence_config.yaml`
  - `config/entity_resolution_config.yaml`
  - `config/commitment_priority_config.yaml`
  - `config/storage_config.yaml`
- [ ] Config loaders (`lib/shared/local_assistant_shared/config/`)
- [ ] Pydantic config models
- [ ] Config validation script (`scripts/validate_config.py`)
- [ ] Unit tests for config loaders

**Acceptance Criteria**:
```python
# Configs load successfully
from local_assistant_shared.config import ConfigLoader
from config.models import DocumentIntelligenceConfig

loader = ConfigLoader(DocumentIntelligenceConfig, "config/document_intelligence_config.yaml")
config = loader.load()

# Type-safe access
fuzzy_threshold = config.entity_resolution.vendor_matching.fuzzy_threshold
assert fuzzy_threshold == 0.90

# Validation script passes
python scripts/validate_config.py  # Exit code 0
```

**Code Location**:
```
config/
├── document_intelligence_config.yaml
├── entity_resolution_config.yaml
├── commitment_priority_config.yaml
└── storage_config.yaml

lib/shared/local_assistant_shared/
├── config/
│   ├── __init__.py
│   ├── config_loader.py
│   ├── pipeline_config.py
│   └── models.py            # Pydantic config models
```

---

#### 1.4 Prompt Management (Day 4)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: 1.3 Complete

**Deliverables**:
- [ ] PromptManager (reuse from brokerage project)
- [ ] Initial prompts:
  - `config/prompts/entity-resolution/vendor_matching_v1.0.0.yaml`
  - `config/prompts/commitment-creation/invoice_to_commitment_v1.0.0.yaml`
  - `config/prompts/validation/validate_vendor_v1.0.0.yaml`
- [ ] Prompt unit tests
- [ ] Prompt versioning documentation

**Acceptance Criteria**:
```python
from local_assistant_shared.prompts import PromptManager

manager = PromptManager(backend="local", prompts_dir="config/prompts")
prompt = manager.load_prompt(
    service_name="entity-resolution",
    prompt_name="vendor_matching",
    version="1.0.0"
)

# Render with variables
rendered = prompt.render(
    candidate_name="Clipboard Health",
    existing_name="Clipboard Health (Twomagnets Inc.)"
)

# Prompt hash for provenance
print(f"Prompt hash: {prompt.hash()}")  # 8-char SHA-256
```

**Code Location**:
```
config/prompts/
├── entity-resolution/
│   ├── vendor_matching_v1.0.0.yaml
│   └── party_deduplication_v1.0.0.yaml
├── commitment-creation/
│   └── invoice_to_commitment_v1.0.0.yaml
└── validation/
    └── validate_vendor_v1.0.0.yaml

lib/shared/local_assistant_shared/prompts/
├── __init__.py
└── prompt_manager.py         # REUSE from brokerage
```

---

#### 1.5 Shared Utilities (Day 5)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: 1.2, 1.3 Complete

**Deliverables**:
- [ ] `lib/shared/local_assistant_shared/utils/`:
  - `hash_utils.py` - SHA-256 helpers
  - `date_utils.py` - Date parsing, formatting
  - `priority_calculator.py` - Commitment priority algorithm
  - `fuzzy_matcher.py` - Entity matching utilities
- [ ] Unit tests for all utilities
- [ ] Documentation (docstrings + examples)

**Acceptance Criteria**:
```python
from local_assistant_shared.utils import (
    calculate_sha256,
    calculate_priority,
    fuzzy_match_name
)

# Hash calculation
file_hash = calculate_sha256(file_bytes)
assert len(file_hash) == 64  # 256 bits / 4 bits per hex char

# Priority calculation
priority_result = calculate_priority(
    due_date=datetime(2025, 11, 8),  # 2 days from now
    amount=12419.83,
    severity=8  # Finance domain
)
assert 80 <= priority_result.score <= 100
assert "Due in 2 days" in priority_result.reason

# Fuzzy matching
match_score = fuzzy_match_name("ACME Corp", "Corp ACME")
assert match_score >= 0.90
```

---

### Phase 1 Completion Checklist
- [ ] All migrations run cleanly (up + down)
- [ ] All models defined with types (mypy strict passes)
- [ ] All configs load successfully (validation script passes)
- [ ] All prompts load and render correctly
- [ ] All utilities tested (>80% coverage)
- [ ] CI pipeline green (pytest + mypy + ruff)

---

## Phase 2: Core Services (Days 6-10)

### Goal
Build document intelligence services: storage, entity resolution, commitment creation

### Tasks

#### 2.1 Content-Addressable Storage (Day 6)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: Phase 1 Complete

**Deliverables**:
- [ ] `services/document_intelligence/storage.py`:
  - `ContentAddressableStorage` class
  - Local filesystem backend (MVP)
  - SHA-256 hash calculation
  - Deduplication check
- [ ] Storage unit tests
- [ ] Integration test with real files

**Acceptance Criteria**:
```python
from services.document_intelligence.storage import ContentAddressableStorage

storage = ContentAddressableStorage(base_path="./data/documents")

# Store file
result = await storage.store(file_bytes, filename="invoice.pdf")
assert result.sha256 == expected_hash
assert result.storage_path == f"data/documents/{expected_hash}.pdf"
assert result.deduplicated == False  # First upload

# Deduplication
result2 = await storage.store(file_bytes, filename="invoice_copy.pdf")
assert result2.sha256 == result.sha256
assert result2.deduplicated == True  # Same file
```

**Code Location**:
```
services/document_intelligence/
├── __init__.py
├── storage.py                # NEW
└── backends/
    ├── __init__.py
    ├── local.py              # NEW
    └── s3.py                 # Future
```

---

#### 2.2 Signal Processor (Day 7)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: 2.1 Complete

**Deliverables**:
- [ ] `services/document_intelligence/signal_processor.py`:
  - `SignalProcessor` class
  - Classification logic (invoice, receipt, contract)
  - Idempotency checks (dedupe_key)
- [ ] Signal model integration
- [ ] Unit tests + integration tests

**Acceptance Criteria**:
```python
from services/document_intelligence.signal_processor import SignalProcessor

processor = SignalProcessor()

# Create signal
signal = await processor.create_signal(
    source="vision_upload",
    payload={"filename": "invoice.pdf", "size": 1024000},
    dedupe_key=file_hash
)
assert signal.status == "processing"

# Idempotency check
signal2 = await processor.create_signal(
    source="vision_upload",
    payload={"filename": "invoice.pdf", "size": 1024000},
    dedupe_key=file_hash
)
assert signal2.id == signal.id  # Same signal returned
```

**Code Location**:
```
services/document_intelligence/
├── signal_processor.py       # NEW
└── classifiers/
    ├── __init__.py
    └── document_classifier.py  # NEW
```

---

#### 2.3 Entity Resolver (Day 8)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: 2.2 Complete

**Deliverables**:
- [ ] `services/document_intelligence/entity_resolver.py`:
  - `EntityResolver` class
  - Fuzzy matching algorithm (fuzzywuzzy + pg_trgm)
  - Vendor resolution logic
  - Confidence scoring
  - Manual review queue (low confidence)
- [ ] Entity resolution tests

**Acceptance Criteria**:
```python
from services.document_intelligence.entity_resolver import EntityResolver

resolver = EntityResolver()

# Resolve vendor (high confidence match)
resolution = await resolver.resolve_vendor(
    name="Clipboard Health",
    address="P.O. Box 103125, Pasadena CA",
    tax_id=None
)
assert resolution.matched == True
assert resolution.vendor.name == "Clipboard Health (Twomagnets Inc.)"
assert resolution.confidence >= 0.90

# No match (create new vendor)
resolution2 = await resolver.resolve_vendor(
    name="Unknown Vendor LLC",
    address=None,
    tax_id=None
)
assert resolution2.matched == False
assert resolution2.vendor.id is not None  # New vendor created
```

**Code Location**:
```
services/document_intelligence/
├── entity_resolver.py        # NEW
└── matchers/
    ├── __init__.py
    ├── fuzzy_matcher.py      # NEW
    └── exact_matcher.py      # NEW
```

---

#### 2.4 Commitment Manager (Day 9)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: 2.3 Complete

**Deliverables**:
- [ ] `services/document_intelligence/commitment_manager.py`:
  - `CommitmentManager` class
  - Auto-create commitments from invoices
  - Priority calculation (weighted algorithm)
  - Reason string generation
- [ ] Priority calculation tests (all factors)
- [ ] Integration tests

**Acceptance Criteria**:
```python
from services.document_intelligence.commitment_manager import CommitmentManager

manager = CommitmentManager()

# Create commitment from invoice
commitment = await manager.create_from_invoice(
    invoice_data={
        "InvoiceId": "240470",
        "InvoiceTotal": 12419.83,
        "DueDate": "2024-02-28"
    },
    vendor_id=vendor.id,
    role_id=role.id
)

assert commitment.title == "Pay Invoice #240470 - Clipboard Health"
assert commitment.commitment_type == "obligation"
assert commitment.priority >= 80  # Due soon + high amount
assert "Due in 2 days" in commitment.reason
assert "$12,419.83" in commitment.reason
```

**Code Location**:
```
services/document_intelligence/
├── commitment_manager.py      # NEW
└── priority/
    ├── __init__.py
    ├── calculator.py          # NEW
    └── factors.py             # NEW (time, severity, amount...)
```

---

#### 2.5 Document Intelligence Pipeline (Day 10)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: 2.1, 2.2, 2.3, 2.4 Complete

**Deliverables**:
- [ ] `services/document_intelligence/pipeline.py`:
  - `DocumentProcessingPipeline` class (orchestrator)
  - `process_document_upload()` main entry point
  - Transaction management (ACID)
  - Error handling with rollback
  - Interaction logging
- [ ] E2E pipeline tests

**Acceptance Criteria**:
```python
from services.document_intelligence.pipeline import DocumentProcessingPipeline

pipeline = DocumentProcessingPipeline()

# Process upload (end-to-end)
result = await pipeline.process_document_upload(
    file=uploaded_file,
    extraction_type="invoice",
    user_id=user.id
)

# Verify all entities created
assert result.document_id is not None
assert result.vendor_id is not None
assert result.commitment_id is not None
assert result.interaction_id is not None

# Verify links
links = await db.query(DocumentLink).filter_by(document_id=result.document_id).all()
assert len(links) >= 3  # signal, vendor, commitment
```

**Code Location**:
```
services/document_intelligence/
├── pipeline.py               # NEW (main orchestrator)
└── __init__.py               # Export public API
```

---

### Phase 2 Completion Checklist
- [ ] Content-addressable storage working (deduplication verified)
- [ ] Signal processing with idempotency
- [ ] Entity resolution >90% accuracy (test dataset)
- [ ] Commitment priority calculation tested (all weight factors)
- [ ] E2E pipeline test passes (upload → entities → commit)
- [ ] All services have >80% test coverage

---

## Phase 3: API & Integration (Days 11-15)

### Goal
Build REST API endpoints, integrate with existing vision service, update UI

### Tasks

#### 3.1 API Routes: Documents (Day 11)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: Phase 2 Complete

**Deliverables**:
- [ ] `api/routes/documents.py`:
  - `POST /api/documents/upload` (main endpoint)
  - `GET /api/documents/{id}`
  - `GET /api/documents/{id}/download`
- [ ] OpenAPI schema annotations
- [ ] API tests (FastAPI TestClient)

**Acceptance Criteria**:
```bash
# Upload document
curl -X POST http://localhost:8765/api/documents/upload \
  -F "file=@test_invoice.pdf" \
  -F "extraction_type=invoice"

# Response includes all entities
{
  "document_id": "uuid",
  "vendor": {"id": "uuid", "name": "Clipboard Health", "matched": true},
  "commitment": {"id": "uuid", "title": "Pay Invoice #240470", "priority": 85},
  "extraction": {"cost": 0.0048, "model": "gpt-4o"}
}

# Download original
curl http://localhost:8765/api/documents/{id}/download > invoice.pdf
```

**Code Location**:
```
api/routes/
├── documents.py              # NEW
└── __init__.py               # Register routes
```

---

#### 3.2 API Routes: Vendors & Commitments (Day 12)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: 3.1 Complete

**Deliverables**:
- [ ] `api/routes/vendors.py`:
  - `GET /api/vendors`
  - `GET /api/vendors/{id}`
  - `GET /api/vendors/{id}/documents`
  - `GET /api/vendors/{id}/commitments`
- [ ] `api/routes/commitments.py`:
  - `GET /api/commitments` (focus view with filters)
  - `POST /api/commitments/{id}/fulfill`
- [ ] API tests

**Acceptance Criteria**:
```bash
# List vendors
curl http://localhost:8765/api/vendors?query=clipboard
# Returns fuzzy matches

# Get vendor details
curl http://localhost:8765/api/vendors/{id}
# Returns: name, contact, document count, commitment count

# List commitments (focus view)
curl http://localhost:8765/api/commitments?state=active&priority_min=50
# Returns high-priority commitments sorted by priority
```

**Code Location**:
```
api/routes/
├── vendors.py                # NEW
├── commitments.py            # NEW
└── interactions.py           # NEW (Day 13)
```

---

#### 3.3 API Routes: Interactions & Timeline (Day 13)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: 3.2 Complete

**Deliverables**:
- [ ] `api/routes/interactions.py`:
  - `GET /api/interactions/timeline`
  - `GET /api/interactions/export` (CSV/JSON)
- [ ] Interaction service integration
- [ ] API tests

**Acceptance Criteria**:
```bash
# Get timeline for vendor
curl "http://localhost:8765/api/interactions/timeline?entity_type=party&entity_id={vendor_id}"
# Returns chronological list of all interactions

# Export all interactions
curl http://localhost:8765/api/interactions/export?format=csv > interactions.csv
```

---

#### 3.4 UI: Enhanced Vision View (Day 14)
**Owner**: Frontend Engineer
**Duration**: 1 day
**Dependencies**: 3.1, 3.2, 3.3 Complete

**Deliverables**:
- [ ] Update `ui/src/App.jsx`:
  - Enhanced upload result display
  - Show vendor card (with "matched existing" badge)
  - Show commitment card (priority + reason)
  - Quick links (timeline, vendor history, download PDF)
- [ ] CSS styling for new components
- [ ] Frontend tests (React Testing Library)

**Acceptance Criteria**:
```jsx
// After upload, UI shows:
<VisionResult>
  <DocumentCard id={documentId} />
  <VendorCard vendor={vendor} matched={true} />
  <CommitmentCard commitment={commitment} priority={85} reason={reason} />
  <ExtractionCard cost={0.0048} model="gpt-4o" />
</VisionResult>

// User can click "View vendor history" → navigates to /vendors/{id}
// User can click "Download PDF" → downloads original file
```

**Code Location**:
```
ui/src/
├── components/
│   ├── VisionResult.jsx      # ENHANCED
│   ├── VendorCard.jsx        # NEW
│   ├── CommitmentCard.jsx    # NEW
│   └── ExtractionCard.jsx    # NEW
└── App.jsx                   # ENHANCED
```

---

#### 3.5 UI: Commitments Dashboard (Day 15)
**Owner**: Frontend Engineer
**Duration**: 1 day
**Dependencies**: 3.4 Complete

**Deliverables**:
- [ ] New tab: Commitments Dashboard
- [ ] Components:
  - `CommitmentsDashboard.jsx` (main view)
  - `CommitmentsList.jsx` (filterable list)
  - `CommitmentDetail.jsx` (modal/side panel)
- [ ] Filters: state, domain, priority
- [ ] Quick actions: "Mark as fulfilled"

**Acceptance Criteria**:
```jsx
// User navigates to /commitments
<CommitmentsDashboard>
  <Filters domains={["Finance", "Legal", "Health"]} />
  <CommitmentsList>
    <CommitmentCard
      title="Pay Invoice #240470 - Clipboard Health"
      priority={85}
      due="2024-02-28"
      reason="Due in 2 days, legal risk, $12,419.83"
      onFulfill={() => markAsFulfilled(commitmentId)}
    />
    {/* More commitments... */}
  </CommitmentsList>
</CommitmentsDashboard>
```

**Code Location**:
```
ui/src/
├── pages/
│   └── CommitmentsPage.jsx   # NEW
├── components/
│   ├── CommitmentsDashboard.jsx  # NEW
│   └── CommitmentsList.jsx       # NEW
└── App.jsx                   # Add route
```

---

### Phase 3 Completion Checklist
- [ ] All API endpoints documented (OpenAPI spec)
- [ ] All API tests pass (>80% coverage)
- [ ] UI shows complete entity graph after upload
- [ ] Commitments dashboard functional
- [ ] E2E tests pass (upload → UI updates)

---

## Phase 4: Polish & Production Ready (Days 16-20)

### Goal
Add observability, testing, documentation, and deployment automation

### Tasks

#### 4.1 Observability (Day 16)
**Owner**: DevOps/Backend Engineer
**Duration**: 1 day
**Dependencies**: Phase 3 Complete

**Deliverables**:
- [ ] Structured logging (JSON format) for all services
- [ ] Prometheus metrics:
  - `documents_processed_total` (counter)
  - `extraction_duration_seconds` (histogram)
  - `entity_resolution_accuracy` (gauge)
- [ ] Grafana dashboard (import JSON)
- [ ] Trace IDs for distributed tracing

**Acceptance Criteria**:
```python
# Structured logs
logger.info(
    "document_uploaded",
    extra={
        "document_id": str(document_id),
        "vendor_id": str(vendor_id),
        "extraction_cost": cost,
        "trace_id": trace_id
    }
)

# Metrics exposed
curl http://localhost:8765/metrics
# documents_processed_total{type="invoice"} 42
# extraction_duration_seconds_bucket{le="5.0"} 38
```

**Code Location**:
```
observability/
├── __init__.py
├── logging_config.py         # NEW
├── metrics.py                # NEW (Prometheus)
└── tracing.py                # NEW (OpenTelemetry)

config/grafana/
└── dashboards/
    └── lifegraph_dashboard.json  # NEW
```

---

#### 4.2 Integration Tests (Day 17)
**Owner**: QA Engineer / Backend Engineer
**Duration**: 1 day
**Dependencies**: Phase 3 Complete

**Deliverables**:
- [ ] E2E test suite:
  - Upload invoice → verify all entities created
  - Vendor deduplication test
  - Commitment priority calculation test
  - API endpoint tests (all routes)
- [ ] Test fixtures (sample PDFs, invoices)
- [ ] CI pipeline integration (GitHub Actions / Jenkins)

**Acceptance Criteria**:
```bash
# All tests pass
pytest tests/integration/ -v --cov=services --cov=api

# Coverage >80%
pytest --cov=services --cov=api --cov-report=html

# CI pipeline green
git push origin feature/lifegraph-integration
# GitHub Actions runs: pytest + mypy + ruff + coverage
```

**Code Location**:
```
tests/integration/
├── test_document_pipeline.py    # NEW
├── test_entity_resolution.py    # NEW
├── test_api_endpoints.py        # NEW
└── fixtures/
    ├── sample_invoice.pdf       # NEW
    └── sample_receipt.pdf       # NEW
```

---

#### 4.3 Documentation (Day 18)
**Owner**: Tech Writer / Backend Engineer
**Duration**: 1 day
**Dependencies**: Phase 4.1, 4.2 Complete

**Deliverables**:
- [ ] API documentation (OpenAPI/Swagger UI)
- [ ] Developer guide (setup, architecture, workflows)
- [ ] User guide (how to upload documents, view commitments)
- [ ] Deployment guide (Docker Compose, env vars)
- [ ] Architecture diagrams (Mermaid.js)

**Acceptance Criteria**:
```markdown
# Documentation includes:
1. README.md (quickstart)
2. docs/API.md (all endpoints with examples)
3. docs/ARCHITECTURE.md (system design)
4. docs/DEVELOPER_GUIDE.md (dev setup, best practices)
5. docs/USER_GUIDE.md (end-user instructions)
6. docs/DEPLOYMENT.md (production deployment)

# OpenAPI spec served at:
http://localhost:8765/docs (Swagger UI)
http://localhost:8765/redoc (ReDoc)
```

**Code Location**:
```
docs/
├── API.md                    # ENHANCED
├── ARCHITECTURE.md           # NEW (from planning/)
├── DEVELOPER_GUIDE.md        # NEW
├── USER_GUIDE.md             # NEW
└── DEPLOYMENT.md             # NEW
```

---

#### 4.4 Deployment Automation (Day 19)
**Owner**: DevOps Engineer
**Duration**: 1 day
**Dependencies**: Phase 4.3 Complete

**Deliverables**:
- [ ] Docker Compose updated:
  - `services/api` (FastAPI backend)
  - `services/ui` (React frontend)
  - `services/postgres` (database)
- [ ] Environment variable management (`.env.example`)
- [ ] Database initialization script
- [ ] Backup/restore scripts
- [ ] Health check endpoints

**Acceptance Criteria**:
```bash
# Start all services
docker-compose up -d

# Verify health
curl http://localhost:8765/health
# {"status": "healthy", "database": "connected", "version": "1.0.0"}

# Run migrations
docker-compose exec api alembic upgrade head

# Backup database
./scripts/backup_database.sh

# Restore database
./scripts/restore_database.sh backup_20251106.dump
```

**Code Location**:
```
docker-compose.yml            # ENHANCED
.env.example                  # ENHANCED
scripts/
├── backup_database.sh        # NEW
├── restore_database.sh       # NEW
└── init_database.sh          # NEW
```

---

#### 4.5 Performance Testing & Optimization (Day 20)
**Owner**: Backend Engineer
**Duration**: 1 day
**Dependencies**: Phase 4.4 Complete

**Deliverables**:
- [ ] Load testing (Locust / k6):
  - 100 documents/hour sustained
  - P95 latency <2s
- [ ] Database query optimization (EXPLAIN ANALYZE)
- [ ] Index tuning (add missing indexes)
- [ ] Caching strategy (Redis for hot entities - future)
- [ ] Performance report

**Acceptance Criteria**:
```bash
# Load test
locust -f tests/performance/load_test.py --headless -u 10 -r 1 --run-time 30m

# Results:
# - 100 req/hour sustained
# - P95 latency: 1.8s
# - Error rate: <1%
# - CPU usage: <70%

# Database performance
EXPLAIN ANALYZE
SELECT * FROM commitments
WHERE state = 'active' AND priority >= 50
ORDER BY priority DESC
LIMIT 50;
# Execution Time: <50ms
```

**Code Location**:
```
tests/performance/
├── load_test.py              # NEW (Locust)
├── benchmark.py              # NEW (measure latencies)
└── results/
    └── report_20251106.md    # NEW
```

---

### Phase 4 Completion Checklist
- [ ] Structured logging + metrics exposed
- [ ] All integration tests pass (E2E coverage)
- [ ] Complete documentation (API + dev guides)
- [ ] Docker Compose deployment working
- [ ] Performance targets met (P95 <2s, 100 docs/hour)
- [ ] Ready for production deployment

---

## Risk Mitigation

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Migration failures | LOW | HIGH | Thorough testing + rollback plan |
| Vision API rate limits | LOW | MEDIUM | Implement retry + exponential backoff |
| Entity resolution accuracy | MEDIUM | MEDIUM | Use fuzzy matching + manual review queue |
| Performance degradation | MEDIUM | HIGH | Load testing + query optimization |

### Schedule Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Scope creep | HIGH | HIGH | Strict MVP definition, reject features |
| Dependencies blocking | LOW | MEDIUM | Parallel tasks where possible |
| Resource unavailability | LOW | MEDIUM | Clear task ownership + documentation |

---

## Success Criteria

### Must Have (MVP)
- ✅ Document upload creates vendor + commitment
- ✅ Vendor deduplication >90% accuracy
- ✅ Commitment priority calculation works
- ✅ All entities linked (document → vendor → commitment)
- ✅ UI shows complete entity graph
- ✅ API response <2s (P95)

### Should Have
- ✅ Commitments dashboard with filters
- ✅ Interaction timeline view
- ✅ Export to CSV
- ✅ Prometheus metrics + Grafana dashboard

### Could Have (Future)
- ⚠️ Email integration (inbox parsing)
- ⚠️ Recurring commitments (RRULE support)
- ⚠️ Mobile app
- ⚠️ Advanced analytics

---

## Post-Launch Plan

### Week 5: Monitoring & Iteration
- [ ] Monitor production metrics (errors, latency, costs)
- [ ] Collect user feedback
- [ ] Fix bugs (priority: P0/P1)
- [ ] Performance tuning based on real usage

### Week 6+: Enhancements
- [ ] Tasks & events tables (migration 005)
- [ ] Recurring commitments
- [ ] Advanced search (semantic similarity)
- [ ] Vendor pricing analytics

---

## Appendix: Daily Standup Template

```markdown
# Daily Standup - Day X

## Yesterday
- Completed: [list tasks]
- Blockers: [list blockers]

## Today
- Plan: [list tasks]
- Dependencies: [list dependencies]

## Risks
- [list new risks]

## Metrics
- Tests passing: X/Y
- Coverage: X%
- Open issues: X
```

---

**Next Steps**: Review DEVELOPER_GUIDE.md for pro-level coding standards and best practices.
