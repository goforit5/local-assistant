# Development Log - Sprint 03: Life Graph Services

**Sprint**: 03 - Core Services Implementation
**Date Started**: TBD
**Duration**: 5 days (Days 6-10)
**Team**: Andrew + Claude Code Agent
**Goal**: Build document intelligence pipeline - storage, entity resolution, commitment management

---

## Executive Summary

Sprint 03 implements the **core service layer** for Life Graph Integration:
- Content-addressable storage with SHA-256 deduplication
- Signal processor with classification and idempotency
- Entity resolver with fuzzy matching (>90% accuracy)
- Commitment manager with priority calculation
- End-to-end document processing pipeline

**Final State**: TBD
- [ ] Content-addressable storage working (deduplication verified)
- [ ] Signal processing with idempotency checks
- [ ] Entity resolution >90% accuracy (test dataset)
- [ ] Commitment priority calculation tested (all weight factors)
- [ ] E2E pipeline test passes (upload → entities → commit)
- [ ] All services have >80% test coverage

---

## Sprint 03 Overview

### Goal
Build the **service layer** that processes documents and creates Life Graph entities:
1. Content-addressable storage (SHA-256 based)
2. Signal processor (classify documents, check idempotency)
3. Entity resolver (fuzzy match vendors, create parties)
4. Commitment manager (auto-create commitments, calculate priority)
5. Document processing pipeline (orchestrate full workflow)

### Success Criteria
- ✅ Storage deduplication working (same SHA-256 = same file)
- ✅ Signal processing with idempotency (no duplicate processing)
- ✅ Entity resolution >90% accuracy
- ✅ Priority calculation with explainable reasons
- ✅ E2E test passes (upload → vendor → commitment)
- ✅ All services >80% test coverage

---

## Development Session Timeline

### Day 6: Content-Addressable Storage

**Owner**: Backend Engineer
**Duration**: 1 day
**Status**: Not Started

#### Tasks
1. **Storage Backend Interface**
   - [ ] Create `services/document_intelligence/backends/base.py`
   - [ ] Define `StorageBackend` abstract class
   - [ ] Methods: `store()`, `retrieve()`, `exists()`, `delete()`

2. **Local Filesystem Backend**
   - [ ] Create `services/document_intelligence/backends/local.py`
   - [ ] Implement `LocalStorageBackend`
   - [ ] Store files as `data/documents/{sha256}.{ext}`
   - [ ] Handle file metadata (size, mime_type, created_at)

3. **Content-Addressable Storage Service**
   - [ ] Create `services/document_intelligence/storage.py`
   - [ ] `ContentAddressableStorage` class
   - [ ] Calculate SHA-256 hash
   - [ ] Check if file exists (deduplication)
   - [ ] Store file with hash as filename
   - [ ] Return `StorageResult` dataclass

4. **Storage Unit Tests**
   - [ ] Create `tests/unit/services/document_intelligence/test_storage.py`
   - [ ] Test file storage
   - [ ] Test deduplication (same content → same hash)
   - [ ] Test retrieval

5. **Integration Tests**
   - [ ] Create `tests/integration/test_storage_integration.py`
   - [ ] Test with real PDF files
   - [ ] Test with multiple file types

#### Acceptance Criteria
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

#### Files Created
```
services/document_intelligence/
├── __init__.py
├── storage.py                          # NEW
└── backends/
    ├── __init__.py
    ├── base.py                         # NEW
    ├── local.py                        # NEW
    └── s3.py                           # Future

tests/unit/services/document_intelligence/
└── test_storage.py                     # NEW

tests/integration/
└── test_storage_integration.py         # NEW
```

---

### Day 7: Signal Processor

**Owner**: Backend Engineer
**Duration**: 1 day
**Status**: Not Started

#### Tasks
1. **Signal Classifier**
   - [ ] Create `services/document_intelligence/classifiers/document_classifier.py`
   - [ ] `DocumentClassifier` class
   - [ ] Classify by filename extension + content analysis
   - [ ] Types: invoice, receipt, contract, form, other

2. **Signal Processor Service**
   - [ ] Create `services/document_intelligence/signal_processor.py`
   - [ ] `SignalProcessor` class
   - [ ] Create `Signal` record in database
   - [ ] Idempotency check using `dedupe_key`
   - [ ] Update signal status (new → processing → attached)

3. **Signal Model Integration**
   - [ ] Wire up to SQLAlchemy `Signal` model
   - [ ] Handle signal lifecycle states

4. **Unit Tests**
   - [ ] Create `tests/unit/services/document_intelligence/test_signal_processor.py`
   - [ ] Test classification
   - [ ] Test idempotency (same dedupe_key → same signal)

5. **Integration Tests**
   - [ ] Test signal creation with real database
   - [ ] Test idempotency across multiple calls

#### Acceptance Criteria
```python
from services.document_intelligence.signal_processor import SignalProcessor

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

#### Files Created
```
services/document_intelligence/
├── signal_processor.py                 # NEW
└── classifiers/
    ├── __init__.py
    └── document_classifier.py          # NEW

tests/unit/services/document_intelligence/
└── test_signal_processor.py            # NEW

tests/integration/
└── test_signal_integration.py          # NEW
```

---

### Day 8: Entity Resolver

**Owner**: Backend Engineer
**Duration**: 1 day
**Status**: Not Started

#### Tasks
1. **Fuzzy Matching Algorithms**
   - [ ] Create `services/document_intelligence/matchers/fuzzy_matcher.py`
   - [ ] Implement fuzzy name matching (fuzzywuzzy)
   - [ ] Implement exact matching (tax_id, email)
   - [ ] Confidence scoring (0.0-1.0)

2. **PostgreSQL Trigram Matching**
   - [ ] Create `services/document_intelligence/matchers/database_matcher.py`
   - [ ] Use pg_trgm for fast text search
   - [ ] Query: `SELECT * FROM parties WHERE name % 'search_term' ORDER BY similarity(name, 'search_term') DESC`

3. **Entity Resolver Service**
   - [ ] Create `services/document_intelligence/entity_resolver.py`
   - [ ] `EntityResolver` class
   - [ ] `resolve_vendor()` method (cascade matching):
     1. Exact match (tax_id)
     2. Exact match (normalized name)
     3. Fuzzy match (>90% similarity)
     4. Address + name match (>80% similarity)
     5. Manual review queue (<80% confidence)
   - [ ] Create new `Party` if no match

4. **Unit Tests**
   - [ ] Create `tests/unit/services/document_intelligence/test_entity_resolver.py`
   - [ ] Test exact matching
   - [ ] Test fuzzy matching
   - [ ] Test vendor creation

5. **Integration Tests**
   - [ ] Test with real database
   - [ ] Test vendor deduplication accuracy

#### Acceptance Criteria
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

#### Files Created
```
services/document_intelligence/
├── entity_resolver.py                  # NEW
└── matchers/
    ├── __init__.py
    ├── fuzzy_matcher.py                # NEW
    ├── exact_matcher.py                # NEW
    └── database_matcher.py             # NEW

tests/unit/services/document_intelligence/
└── test_entity_resolver.py             # NEW

tests/integration/
└── test_entity_resolution_integration.py  # NEW
```

---

### Day 9: Commitment Manager

**Owner**: Backend Engineer
**Duration**: 1 day
**Status**: Not Started

#### Tasks
1. **Priority Calculation Algorithm**
   - [ ] Create `services/document_intelligence/priority/calculator.py`
   - [ ] Implement weighted priority calculation:
     - Time pressure (30%): days_until_due → exponential decay
     - Severity/risk (25%): domain-based (legal=10, finance=8)
     - Amount (15%): logarithmic scale ($100-$100k)
     - Effort (15%): estimated hours
     - Dependency (10%): blocked by other commitments
     - User preference (5%): manual boost flag
   - [ ] Return `PriorityResult` (score, reason, factors)

2. **Priority Factors**
   - [ ] Create `services/document_intelligence/priority/factors.py`
   - [ ] `TimeFactor` (exponential decay)
   - [ ] `SeverityFactor` (domain mapping)
   - [ ] `AmountFactor` (logarithmic scale)
   - [ ] `EffortFactor` (estimated hours)
   - [ ] `DependencyFactor` (blocked by)
   - [ ] `PreferenceFactor` (manual boost)

3. **Reason String Generation**
   - [ ] Explainable reason strings
   - [ ] Examples:
     - "Due in 2 days, legal risk, $12,419.83"
     - "High priority: overdue by 5 days, financial penalty"

4. **Commitment Manager Service**
   - [ ] Create `services/document_intelligence/commitment_manager.py`
   - [ ] `CommitmentManager` class
   - [ ] `create_from_invoice()` method
   - [ ] Extract invoice data (id, total, due date)
   - [ ] Calculate priority
   - [ ] Create `Commitment` record
   - [ ] Link to vendor and document

5. **Unit Tests**
   - [ ] Create `tests/unit/services/document_intelligence/test_commitment_manager.py`
   - [ ] Test priority calculation (all factors)
   - [ ] Test commitment creation
   - [ ] Test reason string generation

#### Acceptance Criteria
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

#### Files Created
```
services/document_intelligence/
├── commitment_manager.py               # NEW
└── priority/
    ├── __init__.py
    ├── calculator.py                   # NEW
    └── factors.py                      # NEW

tests/unit/services/document_intelligence/
└── test_commitment_manager.py          # NEW

tests/integration/
└── test_commitment_integration.py      # NEW
```

---

### Day 10: Document Processing Pipeline

**Owner**: Backend Engineer
**Duration**: 1 day
**Status**: Not Started

#### Tasks
1. **Pipeline Orchestrator**
   - [ ] Create `services/document_intelligence/pipeline.py`
   - [ ] `DocumentProcessingPipeline` class
   - [ ] `process_document_upload()` main entry point
   - [ ] Orchestrate full workflow:
     1. Store file (SHA-256)
     2. Create signal (idempotency check)
     3. Extract via Vision API (reuse existing service)
     4. Resolve vendor (fuzzy matching)
     5. Create commitment (auto-create from invoice)
     6. Link all entities (document_links)
     7. Log interaction (audit trail)

2. **Transaction Management**
   - [ ] Wrap entire pipeline in database transaction (ACID)
   - [ ] Rollback on any failure
   - [ ] Commit on success

3. **Error Handling**
   - [ ] Graceful degradation (continue if non-critical step fails)
   - [ ] Structured error logging
   - [ ] Return partial results on failure

4. **Interaction Logging**
   - [ ] Create `services/document_intelligence/interaction_logger.py`
   - [ ] Log all actions to `interactions` table
   - [ ] Track costs, timing, results

5. **E2E Tests**
   - [ ] Create `tests/integration/test_pipeline_e2e.py`
   - [ ] Test full upload → entities → commit flow
   - [ ] Test with real PDF invoice
   - [ ] Verify all entities created
   - [ ] Verify all links created

#### Acceptance Criteria
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

#### Files Created
```
services/document_intelligence/
├── pipeline.py                         # NEW (main orchestrator)
├── interaction_logger.py               # NEW
└── __init__.py                         # Export public API

tests/integration/
└── test_pipeline_e2e.py                # NEW
```

---

## Technical Decisions & Rationale

### Decision 1: Content-Addressable Storage
**Decision**: Use SHA-256 as unique identifier
**Rationale**: Automatic deduplication, cache-friendly, provenance
**Alternative**: Sequential IDs
**Trade-off**: Hash calculation adds ~1ms per upload

### Decision 2: Fuzzy Matching Cascade
**Decision**: Multi-tier matching (exact → fuzzy → manual review)
**Rationale**: Balance accuracy with automation
**Alternative**: Exact match only
**Trade-off**: More complex logic, potential false positives

### Decision 3: Weighted Priority Algorithm
**Decision**: 6 factors with configurable weights
**Rationale**: Explainable, adjustable, comprehensive
**Alternative**: Simple due date sorting
**Trade-off**: More computation, needs tuning

### Decision 4: Transaction-Based Pipeline
**Decision**: Wrap entire pipeline in single DB transaction
**Rationale**: ACID guarantees, easy rollback
**Alternative**: Individual transactions per step
**Trade-off**: Longer transaction time, potential lock contention

### Decision 5: Idempotent Signal Processing
**Decision**: Use `dedupe_key` for idempotency
**Rationale**: Prevent duplicate processing, safe retries
**Alternative**: No idempotency
**Trade-off**: Requires dedupe_key generation

---

## Architecture Patterns Used

### 1. Pipeline Pattern
**Pattern**: Chain of processing steps
**Files**: `pipeline.py`
**Benefits**: Clear flow, easy to add steps

### 2. Strategy Pattern (Matching)
**Pattern**: Multiple matching strategies (exact, fuzzy, database)
**Files**: `matchers/`
**Benefits**: Pluggable, testable

### 3. Weighted Scoring
**Pattern**: Multiple factors with configurable weights
**Files**: `priority/calculator.py`, `priority/factors.py`
**Benefits**: Explainable, adjustable

### 4. Transaction Script
**Pattern**: Single transaction for entire operation
**Files**: `pipeline.py`
**Benefits**: ACID guarantees, easy rollback

### 5. Event Logging
**Pattern**: Immutable audit log
**Files**: `interaction_logger.py`
**Benefits**: Complete audit trail, time-travel debugging

---

## Challenges & Solutions

### Challenge 1: TBD
**Problem**: TBD
**Root Cause**: TBD
**Solution**: TBD
**Learning**: TBD

---

## Files Created/Modified Summary

### New Directories
```
services/document_intelligence/
├── backends/                   # Storage backends
├── classifiers/                # Document classifiers
├── matchers/                   # Entity matching
└── priority/                   # Priority calculation
```

### New Files (Estimated: 20+)
- Storage service (3 files)
- Signal processor (2 files)
- Entity resolver (4 files)
- Commitment manager (3 files)
- Pipeline orchestrator (2 files)
- Unit tests (5 files)
- Integration tests (5 files)

---

## Key Metrics

### Code Statistics (Estimated)
- **Total Python Files**: 20+
- **Total Lines of Code**: ~2,000
- **Services Implemented**: 5
- **Test Coverage**: >80% target

### Performance Targets
- **Upload latency**: <2s (P95)
- **Storage deduplication**: >99% accuracy
- **Vendor matching**: >90% accuracy
- **Priority calculation**: <10ms

---

## Sprint 03 Completion Checklist

### Storage Layer
- [ ] Content-addressable storage working
- [ ] Deduplication verified (same SHA-256 → same file)
- [ ] Local filesystem backend tested
- [ ] Storage unit tests pass

### Signal Processing
- [ ] Signal classification working
- [ ] Idempotency checks working (same dedupe_key → same signal)
- [ ] Signal lifecycle states implemented
- [ ] Signal unit tests pass

### Entity Resolution
- [ ] Fuzzy matching implemented (fuzzywuzzy + pg_trgm)
- [ ] Vendor resolution >90% accuracy (test dataset)
- [ ] Confidence scoring working
- [ ] Entity resolver tests pass

### Commitment Management
- [ ] Priority calculation implemented (6 factors)
- [ ] Reason string generation working
- [ ] Commitment creation from invoice
- [ ] Priority tests pass (all weight factors)

### Pipeline Orchestrator
- [ ] E2E pipeline working (upload → entities → commit)
- [ ] Transaction management (ACID)
- [ ] Error handling with rollback
- [ ] Interaction logging working
- [ ] E2E tests pass

### Testing & Quality
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Test coverage >80%
- [ ] CI pipeline green

---

## Next Sprint Preparation

### Sprint 04: API & UI (Days 11-15)
Services are complete. Next sprint focuses on:
1. REST API endpoints (documents, vendors, commitments)
2. OpenAPI schema generation
3. React UI integration (enhanced vision view)
4. Commitments dashboard (filterable list)
5. Interactions timeline

**Handoff Requirements**:
- ✅ All services working and tested
- ✅ E2E pipeline test passing
- ✅ All entity types created successfully
- ✅ Documentation complete

---

## Lessons Learned

### 1. TBD
TBD

---

## Appendix: Commands Reference

### Development Workflow
```bash
# Run unit tests
pytest tests/unit/services/document_intelligence/ -v

# Run integration tests
pytest tests/integration/ -v

# Run with coverage
pytest --cov=services/document_intelligence --cov-report=html

# Type checking
mypy services/document_intelligence/ --strict
```

### Testing Services
```python
# Test storage
from services.document_intelligence.storage import ContentAddressableStorage
storage = ContentAddressableStorage(base_path="./data/documents")
result = await storage.store(file_bytes, filename="test.pdf")

# Test entity resolution
from services.document_intelligence.entity_resolver import EntityResolver
resolver = EntityResolver()
resolution = await resolver.resolve_vendor(name="Test Vendor")

# Test commitment creation
from services.document_intelligence.commitment_manager import CommitmentManager
manager = CommitmentManager()
commitment = await manager.create_from_invoice(invoice_data, vendor_id, role_id)

# Test full pipeline
from services.document_intelligence.pipeline import DocumentProcessingPipeline
pipeline = DocumentProcessingPipeline()
result = await pipeline.process_document_upload(file, "invoice", user_id)
```

---

**End of Sprint 03 Dev Log**
**Status**: Not Started
**Next Sprint**: Sprint 04 - API & UI Integration
