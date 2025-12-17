# Development Log - Sprint 04: Life Graph API & UI

**Sprint**: 04 - API & UI Integration
**Date Started**: TBD
**Duration**: 5 days (Days 11-15)
**Team**: Andrew + Claude Code Agent
**Goal**: Build REST API endpoints, integrate with React UI, create user-facing features

---

## Executive Summary

Sprint 04 builds the **API and UI layer** for Life Graph Integration:
- Complete REST API endpoints (documents, vendors, commitments, interactions)
- OpenAPI schema with Swagger/ReDoc
- Enhanced React vision view with entity cards
- Commitments dashboard with filters and quick actions
- Interactions timeline view

**Final State**: TBD
- [ ] All API endpoints documented (OpenAPI spec)
- [ ] All API tests pass (>80% coverage)
- [ ] UI shows complete entity graph after upload
- [ ] Commitments dashboard functional
- [ ] E2E tests pass (upload → UI updates)

---

## Sprint 04 Overview

### Goal
Build the **user-facing layer** that exposes Life Graph features:
1. REST API endpoints (FastAPI)
2. OpenAPI schema generation (Swagger/ReDoc)
3. Enhanced vision view (React components)
4. Commitments dashboard (filterable, sortable)
5. Interactions timeline (audit trail view)

### Success Criteria
- ✅ All API endpoints working and tested
- ✅ OpenAPI schema auto-generated
- ✅ React UI shows vendor, commitment, extraction details
- ✅ Commitments dashboard with filters (state, domain, priority)
- ✅ E2E tests pass (API → UI flow)

---

## Development Session Timeline

### Day 11: Documents API

**Owner**: Backend Engineer
**Duration**: 1 day
**Status**: Not Started

#### Tasks
1. **Upload Endpoint**
   - [ ] Create `api/routes/documents.py`
   - [ ] `POST /api/documents/upload`
   - [ ] Accept multipart file upload
   - [ ] Call `DocumentProcessingPipeline.process_document_upload()`
   - [ ] Return complete entity graph:
     - Document ID
     - Vendor (matched or created)
     - Commitment (auto-created)
     - Extraction details (cost, model)
     - Links (timeline URL)

2. **Get Document Endpoint**
   - [ ] `GET /api/documents/{document_id}`
   - [ ] Return document with all linked entities
   - [ ] Include: vendor, commitments, signal, interactions

3. **Download Endpoint**
   - [ ] `GET /api/documents/{document_id}/download`
   - [ ] Stream original PDF file
   - [ ] Set appropriate content-type headers

4. **OpenAPI Annotations**
   - [ ] Add Pydantic response models
   - [ ] Add request/response examples
   - [ ] Add error responses (400, 404, 500)

5. **API Tests**
   - [ ] Create `tests/unit/api/test_documents_api.py`
   - [ ] Test upload with mock pipeline
   - [ ] Test get document
   - [ ] Test download

6. **Integration Tests**
   - [ ] Create `tests/integration/test_documents_api_integration.py`
   - [ ] Test full upload flow with real database

#### Acceptance Criteria
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
  "extraction": {"cost": 0.0048675, "model": "gpt-4o"},
  "links": {"timeline": "/api/interactions?entity_id={document_id}"}
}

# Download original
curl http://localhost:8765/api/documents/{id}/download > invoice.pdf
```

#### Files Created
```
api/routes/
├── __init__.py
└── documents.py                        # NEW

api/schemas/
└── document_schemas.py                 # ENHANCED

tests/unit/api/
└── test_documents_api.py               # NEW

tests/integration/
└── test_documents_api_integration.py   # NEW
```

---

### Day 12: Vendors & Commitments API

**Owner**: Backend Engineer
**Duration**: 1 day
**Status**: Not Started

#### Tasks
1. **Vendors API**
   - [ ] Create `api/routes/vendors.py`
   - [ ] `GET /api/vendors` - List vendors with fuzzy search
   - [ ] `GET /api/vendors/{vendor_id}` - Get vendor details
   - [ ] `GET /api/vendors/{vendor_id}/documents` - All documents
   - [ ] `GET /api/vendors/{vendor_id}/commitments` - All commitments
   - [ ] `GET /api/vendors/{vendor_id}/stats` - Summary stats

2. **Commitments API**
   - [ ] Create `api/routes/commitments.py`
   - [ ] `GET /api/commitments` - List with filters:
     - state (active, fulfilled, canceled)
     - domain (finance, legal, health)
     - due_before (date filter)
     - priority_min (threshold)
   - [ ] `GET /api/commitments/{commitment_id}` - Get details
   - [ ] `POST /api/commitments/{commitment_id}/fulfill` - Mark fulfilled
   - [ ] `PATCH /api/commitments/{commitment_id}` - Update

3. **Pydantic Schemas**
   - [ ] `VendorSummary`, `VendorDetail` schemas
   - [ ] `CommitmentSummary`, `CommitmentDetail` schemas
   - [ ] Request/response models

4. **API Tests**
   - [ ] Create `tests/unit/api/test_vendors_api.py`
   - [ ] Create `tests/unit/api/test_commitments_api.py`
   - [ ] Test all endpoints with mocks

5. **Integration Tests**
   - [ ] Test vendor fuzzy search
   - [ ] Test commitment filters
   - [ ] Test fulfill action

#### Acceptance Criteria
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

# Fulfill commitment
curl -X POST http://localhost:8765/api/commitments/{id}/fulfill
# Returns updated commitment with state=fulfilled
```

#### Files Created
```
api/routes/
├── vendors.py                          # NEW
└── commitments.py                      # NEW

api/schemas/
├── vendor_schemas.py                   # ENHANCED
└── commitment_schemas.py               # ENHANCED

tests/unit/api/
├── test_vendors_api.py                 # NEW
└── test_commitments_api.py             # NEW

tests/integration/
├── test_vendors_api_integration.py     # NEW
└── test_commitments_api_integration.py # NEW
```

---

### Day 13: Interactions API

**Owner**: Backend Engineer
**Duration**: 1 day
**Status**: Not Started

#### Tasks
1. **Timeline Endpoint**
   - [ ] Create `api/routes/interactions.py`
   - [ ] `GET /api/interactions/timeline`
   - [ ] Query parameters:
     - entity_type (party, document, commitment)
     - entity_id (filter by entity)
     - type (filter by interaction type)
     - limit (pagination)
     - offset (pagination)
   - [ ] Return chronological list

2. **Export Endpoint**
   - [ ] `GET /api/interactions/export`
   - [ ] Query parameters:
     - format (csv, json)
     - date_from, date_to (date range)
   - [ ] Stream file response

3. **Pydantic Schemas**
   - [ ] `InteractionSummary` schema
   - [ ] `InteractionDetail` schema

4. **API Tests**
   - [ ] Create `tests/unit/api/test_interactions_api.py`
   - [ ] Test timeline with filters
   - [ ] Test export formats

5. **Integration Tests**
   - [ ] Test timeline with real data
   - [ ] Test CSV export
   - [ ] Test JSON export

#### Acceptance Criteria
```bash
# Get timeline for vendor
curl "http://localhost:8765/api/interactions/timeline?entity_type=party&entity_id={vendor_id}"
# Returns chronological list of all interactions

# Export all interactions
curl http://localhost:8765/api/interactions/export?format=csv > interactions.csv

# Export with date range
curl "http://localhost:8765/api/interactions/export?format=json&date_from=2025-01-01&date_to=2025-12-31" > interactions.json
```

#### Files Created
```
api/routes/
└── interactions.py                     # NEW

api/schemas/
└── interaction_schemas.py              # NEW

tests/unit/api/
└── test_interactions_api.py            # NEW

tests/integration/
└── test_interactions_api_integration.py  # NEW
```

---

### Day 14: Enhanced Vision View (React UI)

**Owner**: Frontend Engineer
**Duration**: 1 day
**Status**: Not Started

#### Tasks
1. **API Client**
   - [ ] Update `ui/src/api/client.js`
   - [ ] Add document upload function
   - [ ] Add vendor/commitment fetch functions

2. **New React Components**
   - [ ] Create `ui/src/components/VendorCard.jsx`
     - Display vendor name, address, tax ID
     - Show "matched existing" badge if matched
     - Link to vendor history
   - [ ] Create `ui/src/components/CommitmentCard.jsx`
     - Display title, due date, priority
     - Show reason string (explainability)
     - Quick action: "Mark as fulfilled"
   - [ ] Create `ui/src/components/ExtractionCard.jsx`
     - Display extraction cost, model, time
     - Link to download PDF

3. **Update Vision View**
   - [ ] Update `ui/src/App.jsx` or vision page
   - [ ] After upload, display:
     - Document card (SHA-256, size, type)
     - Vendor card (with matched badge)
     - Commitment card (with priority)
     - Extraction card (cost details)
     - Quick links (timeline, vendor history, download)

4. **CSS Styling**
   - [ ] Create `ui/src/styles/VisionResult.css`
   - [ ] Card layout with shadow and border
   - [ ] Priority color coding (red/yellow/green)

5. **Frontend Tests**
   - [ ] Create `ui/src/components/__tests__/VendorCard.test.jsx`
   - [ ] Create `ui/src/components/__tests__/CommitmentCard.test.jsx`
   - [ ] Use React Testing Library

#### Acceptance Criteria
```jsx
// After upload, UI shows:
<VisionResult>
  <DocumentCard id={documentId} sha256={sha256} />
  <VendorCard vendor={vendor} matched={true} />
  <CommitmentCard
    commitment={commitment}
    priority={85}
    reason="Due in 2 days, $12,419.83"
  />
  <ExtractionCard cost={0.0048} model="gpt-4o" />
  <QuickLinks
    timelineUrl={timelineUrl}
    vendorUrl={vendorUrl}
    downloadUrl={downloadUrl}
  />
</VisionResult>

// User can click "View vendor history" → navigates to /vendors/{id}
// User can click "Download PDF" → downloads original file
```

#### Files Created
```
ui/src/
├── components/
│   ├── VisionResult.jsx                # ENHANCED
│   ├── VendorCard.jsx                  # NEW
│   ├── CommitmentCard.jsx              # NEW
│   ├── ExtractionCard.jsx              # NEW
│   └── __tests__/
│       ├── VendorCard.test.jsx         # NEW
│       └── CommitmentCard.test.jsx     # NEW
├── styles/
│   └── VisionResult.css                # NEW
└── App.jsx                             # ENHANCED
```

---

### Day 15: Commitments Dashboard (React UI)

**Owner**: Frontend Engineer
**Duration**: 1 day
**Status**: Not Started

#### Tasks
1. **New Page: Commitments**
   - [ ] Create `ui/src/pages/CommitmentsPage.jsx`
   - [ ] React Router route: `/commitments`

2. **Dashboard Component**
   - [ ] Create `ui/src/components/CommitmentsDashboard.jsx`
   - [ ] Fetch commitments from API
   - [ ] Filter controls:
     - State (active, fulfilled, canceled)
     - Domain (finance, legal, health)
     - Priority threshold (slider 0-100)
   - [ ] Sort controls:
     - Priority (high to low)
     - Due date (soonest first)

3. **Commitments List Component**
   - [ ] Create `ui/src/components/CommitmentsList.jsx`
   - [ ] Display commitments as cards
   - [ ] Each card shows:
     - Title
     - Due date (relative: "in 2 days")
     - Priority badge (color-coded)
     - Reason string
     - Quick action: "Mark as fulfilled"

4. **Commitment Detail Modal**
   - [ ] Create `ui/src/components/CommitmentDetail.jsx`
   - [ ] Show on card click
   - [ ] Display:
     - Full commitment details
     - Linked vendor
     - Linked documents
     - Interaction timeline

5. **API Integration**
   - [ ] Fetch commitments with filters
   - [ ] Update commitment state (fulfill action)
   - [ ] Real-time updates after actions

6. **CSS Styling**
   - [ ] Create `ui/src/styles/CommitmentsDashboard.css`
   - [ ] Priority color coding:
     - Red (80-100): High priority
     - Yellow (50-79): Medium priority
     - Green (0-49): Low priority

7. **Frontend Tests**
   - [ ] Create `ui/src/pages/__tests__/CommitmentsPage.test.jsx`
   - [ ] Test filtering
   - [ ] Test sorting
   - [ ] Test fulfill action

#### Acceptance Criteria
```jsx
// User navigates to /commitments
<CommitmentsDashboard>
  <Filters
    states={["active", "fulfilled"]}
    domains={["Finance", "Legal", "Health"]}
    priorityMin={50}
  />
  <CommitmentsList>
    <CommitmentCard
      title="Pay Invoice #240470 - Clipboard Health"
      priority={85}
      dueDate="2024-02-28"
      reason="Due in 2 days, legal risk, $12,419.83"
      onFulfill={() => markAsFulfilled(commitmentId)}
    />
    {/* More commitments... */}
  </CommitmentsList>
</CommitmentsDashboard>

// Click card → opens CommitmentDetail modal
// Click "Mark as fulfilled" → updates state, refreshes list
```

#### Files Created
```
ui/src/
├── pages/
│   ├── CommitmentsPage.jsx             # NEW
│   └── __tests__/
│       └── CommitmentsPage.test.jsx    # NEW
├── components/
│   ├── CommitmentsDashboard.jsx        # NEW
│   ├── CommitmentsList.jsx             # NEW
│   ├── CommitmentDetail.jsx            # NEW
│   └── __tests__/
│       ├── CommitmentsDashboard.test.jsx  # NEW
│       └── CommitmentsList.test.jsx    # NEW
├── styles/
│   └── CommitmentsDashboard.css        # NEW
└── App.jsx                             # ENHANCED (add route)
```

---

## Technical Decisions & Rationale

### Decision 1: OpenAPI Auto-Generation
**Decision**: Use FastAPI's built-in OpenAPI schema generation
**Rationale**: Automatic documentation, type-safe, Swagger UI included
**Alternative**: Manually write OpenAPI spec
**Trade-off**: Requires Pydantic models for all endpoints

### Decision 2: Polymorphic Filtering
**Decision**: Support multiple filters per endpoint (state, domain, priority)
**Rationale**: Flexible, user-friendly, reduces API calls
**Alternative**: Separate endpoints per filter
**Trade-off**: More complex query logic

### Decision 3: Color-Coded Priority
**Decision**: Red/yellow/green color coding for priority
**Rationale**: Instant visual recognition, accessibility
**Alternative**: Numbers only
**Trade-off**: Requires consistent color scheme

### Decision 4: Modal for Detail View
**Decision**: Use modal overlay for commitment detail
**Rationale**: Keeps context, faster than navigation
**Alternative**: Separate detail page
**Trade-off**: More complex state management

### Decision 5: Real-Time Updates
**Decision**: Refresh list after fulfill action
**Rationale**: Immediate feedback, data consistency
**Alternative**: Manual refresh
**Trade-off**: Extra API calls

---

## Architecture Patterns Used

### 1. REST API Design
**Pattern**: Resource-based URLs, standard HTTP methods
**Files**: `api/routes/*.py`
**Benefits**: Intuitive, standard, tooling support

### 2. OpenAPI Schema
**Pattern**: Auto-generated from Pydantic models
**Files**: FastAPI automatic generation
**Benefits**: Always up-to-date, Swagger UI

### 3. Component-Based UI
**Pattern**: Reusable React components
**Files**: `ui/src/components/*.jsx`
**Benefits**: DRY, testable, maintainable

### 4. Controlled Components
**Pattern**: React controlled inputs for filters
**Files**: `CommitmentsDashboard.jsx`
**Benefits**: Centralized state, predictable

### 5. Modal Pattern
**Pattern**: Overlay detail view
**Files**: `CommitmentDetail.jsx`
**Benefits**: Context preservation, faster UX

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
api/routes/                     # REST API endpoints
ui/src/pages/                   # React pages
ui/src/components/              # React components
ui/src/styles/                  # CSS files
```

### New Files (Estimated: 25+)
- API routes (3 files)
- API tests (6 files)
- React components (7 files)
- React tests (5 files)
- CSS files (2 files)
- Integration tests (2 files)

---

## Key Metrics

### Code Statistics (Estimated)
- **Total Python Files**: 10+
- **Total JavaScript Files**: 15+
- **Total Lines of Code**: ~2,500
- **API Endpoints**: 12+
- **React Components**: 7+

### API Endpoints
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/documents/upload` | Upload document |
| GET | `/api/documents/{id}` | Get document |
| GET | `/api/documents/{id}/download` | Download PDF |
| GET | `/api/vendors` | List vendors |
| GET | `/api/vendors/{id}` | Get vendor details |
| GET | `/api/vendors/{id}/documents` | Vendor documents |
| GET | `/api/vendors/{id}/commitments` | Vendor commitments |
| GET | `/api/commitments` | List commitments (filters) |
| GET | `/api/commitments/{id}` | Get commitment |
| POST | `/api/commitments/{id}/fulfill` | Mark fulfilled |
| GET | `/api/interactions/timeline` | Timeline view |
| GET | `/api/interactions/export` | Export CSV/JSON |

---

## Sprint 04 Completion Checklist

### API Layer
- [ ] All endpoints implemented and documented
- [ ] OpenAPI schema auto-generated (Swagger UI working)
- [ ] All API unit tests pass
- [ ] All API integration tests pass
- [ ] Error handling (400, 404, 500)

### React UI
- [ ] Enhanced vision view with entity cards
- [ ] Vendor card with matched badge
- [ ] Commitment card with priority + reason
- [ ] Extraction card with cost details
- [ ] Quick links working (timeline, vendor history, download)

### Commitments Dashboard
- [ ] Commitments page working
- [ ] Filters working (state, domain, priority)
- [ ] Sorting working (priority, due date)
- [ ] Fulfill action working
- [ ] Detail modal working

### Interactions
- [ ] Timeline API working
- [ ] Export working (CSV, JSON)
- [ ] Timeline UI component (future)

### Testing & Quality
- [ ] All unit tests pass (API + UI)
- [ ] All integration tests pass
- [ ] E2E tests pass (upload → UI updates)
- [ ] Test coverage >80%

---

## Next Sprint Preparation

### Sprint 05: Production Ready (Days 16-20)
API and UI complete. Next sprint focuses on:
1. Observability (structured logging, Prometheus metrics, Grafana dashboard)
2. Integration tests (E2E test suite)
3. Documentation (API docs, developer guide, user guide)
4. Deployment automation (Docker Compose, backup/restore)
5. Performance testing (load testing, query optimization)

**Handoff Requirements**:
- ✅ All API endpoints working
- ✅ All UI components functional
- ✅ E2E flow tested (upload → API → UI)
- ✅ Documentation in place

---

## Lessons Learned

### 1. TBD
TBD

---

## Appendix: Commands Reference

### API Development
```bash
# Start FastAPI server
uvicorn api.main:app --reload --port 8765

# View OpenAPI docs
open http://localhost:8765/docs      # Swagger UI
open http://localhost:8765/redoc     # ReDoc

# Test API endpoints
curl -X POST http://localhost:8765/api/documents/upload -F "file=@test.pdf"
curl http://localhost:8765/api/commitments?priority_min=50
```

### UI Development
```bash
# Start React dev server
cd ui && npm run dev

# Run tests
npm test

# Build for production
npm run build
```

### Testing
```bash
# API tests
pytest tests/unit/api/ -v
pytest tests/integration/ -v

# UI tests
cd ui && npm test

# E2E tests
pytest tests/e2e/ -v
```

---

**End of Sprint 04 Dev Log**
**Status**: Not Started
**Next Sprint**: Sprint 05 - Production Ready (Observability, Testing, Deployment)
