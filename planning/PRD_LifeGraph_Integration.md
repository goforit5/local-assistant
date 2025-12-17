# Product Requirements Document: Life Graph Integration
**Version**: 1.0.0
**Date**: 2025-11-06
**Author**: AI Development Team
**Status**: Planning Phase

---

## Executive Summary

Integrate the **Life Graph** data model with the Local AI Assistant to create a unicorn-grade document intelligence and CRM system. This integration transforms the assistant from a stateless vision extraction tool into a complete personal+business management platform that understands entities, relationships, and obligations.

### The Silicon Valley Pitch
> "We built an AI assistant that doesn't just extract invoices—it understands your entire obligation graph. Upload a document, and we automatically identify vendors, create commitments, link everything in a queryable graph, calculate priority, and give you a complete audit trail. Content-addressable storage eliminates duplicates. Event sourcing enables time-travel debugging. Entity resolution turns chaos into knowledge."

---

## Problem Statement

### Current Limitations
1. **Stateless Processing**: Vision extraction results are displayed but not persisted
2. **No Entity Management**: Vendors/customers aren't tracked or deduplicated
3. **No Relationship Tracking**: Documents aren't linked to business entities
4. **No Action Management**: No system to track obligations or commitments
5. **No Timeline**: Can't see history of interactions with vendors
6. **No Intelligence**: No priority calculation or smart recommendations

### Impact
- Users lose extraction results when refreshing the page
- Same vendor appears multiple times (no deduplication)
- Can't answer questions like "Show all Clipboard Health invoices from January"
- No way to track "what do I owe" or "when is this due"
- No audit trail or provenance tracking

---

## Solution Overview

### Core Capabilities
1. **Universal Document Storage** (content-addressable, SHA-256-based)
2. **Entity Resolution** (vendors, customers, contacts with fuzzy matching)
3. **Commitment Management** (obligations, goals, routines with priority scoring)
4. **Interaction Timeline** (event-sourced audit log of all actions)
5. **Polymorphic Document Linking** (documents → entities graph)
6. **Signal Processing Pipeline** (classify → normalize → create entities)

### Key Innovation: Event-Sourced Document Intelligence
Every document upload creates an **immutable event chain**:
```
Upload PDF → Store (SHA-256) → Extract (Vision API) → Resolve Vendor →
Create Commitment → Link All Entities → Log Interaction
```

All in ONE database transaction with rollback support.

---

## User Stories

### Priority 1 (MVP - Week 1-2)

#### US-001: Upload Invoice and Auto-Create Vendor
**As a** business owner
**I want to** upload an invoice PDF
**So that** the system automatically identifies the vendor and creates a record

**Acceptance Criteria**:
- Upload PDF via drag-and-drop or file picker
- System extracts vendor name, address, tax ID
- System fuzzy-matches existing vendors (>90% similarity)
- If new vendor: creates Party record with all details
- Returns vendor ID and "matched existing" vs "created new" status

#### US-002: Auto-Create "Pay Invoice" Commitment
**As a** business owner
**I want** invoices to automatically create payment commitments
**So that** I never miss a due date

**Acceptance Criteria**:
- System extracts invoice ID, total, due date
- Creates Commitment (type='obligation') with title "Pay Invoice #{id} - {vendor}"
- Calculates priority based on due date and amount
- Provides explainable reason ("Due in 2 days, amount $12,419.83")
- Links commitment to vendor and document

#### US-003: View Document with Full Entity Graph
**As a** user
**I want to** see all entities linked to a document
**So that** I understand the complete context

**Acceptance Criteria**:
- Shows vendor name and link to vendor history
- Shows commitment with due date and priority
- Shows original PDF download link
- Shows extraction cost and model used
- Shows timeline of interactions

### Priority 2 (Post-MVP - Week 3-4)

#### US-004: Search All Vendor Invoices
**As a** business owner
**I want to** search "Show all Clipboard Health invoices from January"
**So that** I can analyze spending patterns

**Acceptance Criteria**:
- Natural language search via API
- Fuzzy vendor name matching
- Date range filtering
- Results include: invoice ID, date, amount, status
- Supports export to CSV

#### US-005: View Commitment Dashboard
**As a** user
**I want to** see my high-priority commitments (Focus View)
**So that** I know what needs attention today

**Acceptance Criteria**:
- Shows commitments with priority ≥ 50
- Sorted by priority (highest first)
- Filters by domain (Finance, Health, Legal, etc.)
- Shows explainable reason for priority
- Quick action: "Mark as fulfilled"

#### US-006: View Entity Timeline
**As a** user
**I want to** see all interactions with a vendor
**So that** I have complete audit trail

**Acceptance Criteria**:
- Chronological list of interactions
- Shows: document uploads, extractions, commitments created
- Includes cost tracking per interaction
- Filterable by interaction type
- Exportable to JSON/CSV

---

## Success Metrics

### Operational Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Document upload success rate | >99% | POST /api/documents/upload |
| Vendor match accuracy | >90% | Fuzzy matching algorithm |
| Commitment creation rate | 100% (for invoices) | Auto-creation on invoice type |
| API response time (P95) | <2s | Prometheus metrics |
| Database query time (P95) | <200ms | PostgreSQL slow query log |

### User Experience Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to see extraction results | <10s | Frontend timer |
| Duplicate vendor creation rate | <5% | Party.name uniqueness checks |
| User action: Download original PDF | >50% usage | Analytics event |
| User action: View vendor history | >30% usage | Analytics event |

### Business Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Storage deduplication savings | >20% | SHA-256 hash collisions |
| Extraction cost per document | <$0.05 | Cost tracking table |
| Documents processed per month | 1000+ | Signal table count |

---

## Technical Requirements

### Performance
- **Latency**: P95 API response < 2s
- **Throughput**: 100 documents/hour sustained
- **Storage**: Support 10,000+ documents (50GB+)
- **Concurrent Users**: 10+ simultaneous uploads

### Reliability
- **Uptime**: 99.9% (8.76 hours downtime/year)
- **Data Durability**: Zero data loss (PostgreSQL + backups)
- **Transaction Integrity**: ACID compliance (all or nothing)
- **Error Recovery**: Automatic retry with exponential backoff

### Security
- **Authentication**: JWT tokens (future: multi-user)
- **Authorization**: Row-level security on user_id
- **Data Privacy**: PII encryption at rest (contact_json fields)
- **Audit Trail**: Immutable interaction log with actor tracking

### Scalability
- **Horizontal Scaling**: Stateless API servers (Future)
- **Database Sharding**: By user_id (Future: 10,000+ users)
- **CDN for Documents**: S3 + CloudFront (Future: production)
- **Cache Strategy**: Redis for hot entities (Future)

---

## Out of Scope (for v1.0)

### Not Included
- ❌ Real-time collaborative editing
- ❌ Mobile apps (iOS/Android)
- ❌ Full accounting GL integration
- ❌ Multi-tenancy / team workspaces
- ❌ Advanced analytics dashboard (beyond basic queries)
- ❌ OCR fallback (rely on existing vision pipeline)
- ❌ Email integration (direct inbox parsing)
- ❌ Calendar sync (iCal/Google Calendar)

### Future Roadmap (v2.0+)
- Purchase order management (goods + services)
- Vendor pricing analytics
- Automated payment scheduling
- Recurring commitment templates
- Smart notifications (due date alerts)
- Bulk document import (batch processing)
- Advanced search (semantic similarity via embeddings)

---

## Dependencies

### Existing Systems
| System | Purpose | Status |
|--------|---------|--------|
| PostgreSQL 16 | Primary database | ✅ Running (port 5433) |
| Vision Service | Invoice extraction | ✅ Working (GPT-4o) |
| SQLAlchemy ORM | Database models | ✅ Implemented |
| FastAPI | REST API framework | ✅ Running (port 8765) |
| React UI | Frontend | ✅ Running (port 5173) |

### New Components
| Component | Purpose | Status |
|-----------|---------|--------|
| Life Graph Schema | Core data model | 📋 Planned |
| Document Storage | Content-addressable files | 📋 Planned |
| Entity Resolver | Vendor/party matching | 📋 Planned |
| Signal Processor | Classification pipeline | 📋 Planned |
| Interaction Logger | Event tracking | 📋 Planned |

---

## Risk Assessment

### Technical Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Database migration failures | HIGH | LOW | Thorough testing + rollback plan |
| Vision API rate limits | MEDIUM | LOW | Implement retry + backoff |
| Entity resolution accuracy | MEDIUM | MEDIUM | Fuzzy matching + manual review queue |
| Storage costs (S3) | LOW | LOW | Start with local filesystem |

### Business Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| User adoption | HIGH | MEDIUM | Clear UI + progressive disclosure |
| Data migration complexity | MEDIUM | HIGH | Phased rollout + thorough testing |
| Scope creep | MEDIUM | HIGH | Strict MVP definition |

---

## Glossary

| Term | Definition |
|------|------------|
| **Life Graph** | Universal data model for tracking entities, commitments, and relationships across all life domains |
| **Party** | Person or organization (vendor, customer, contact) |
| **Role** | Context-specific identity (Employee, Parent, Taxpayer) |
| **Commitment** | Obligation, goal, routine, or appointment requiring action |
| **Signal** | Raw input (uploaded PDF, email, API call) awaiting classification |
| **Document** | Stored file with extraction results and SHA-256 hash |
| **Interaction** | Event record of user/system action (upload, extract, fulfill) |
| **Entity Resolution** | Process of matching and deduplicating entities (fuzzy matching) |
| **Content-Addressable Storage** | File storage where filename = SHA-256 hash (enables deduplication) |
| **Event Sourcing** | Architecture where all state changes are stored as immutable events |

---

## Appendix A: Comparable Systems

### Inspiration
- **Linear** (issue tracking): Clean UI, keyboard shortcuts, fast
- **Notion** (knowledge management): Polymorphic linking, flexible schemas
- **Stripe Dashboard** (payment tracking): Excellent entity detail pages
- **Salesforce** (CRM): Relationship management, timeline views
- **n8n** (workflow automation): Visual pipeline builder

### Key Differentiators
1. **AI-First**: Vision extraction + entity resolution built-in
2. **Personal + Business**: Unified model (not just B2B CRM)
3. **Explainable Priority**: Every commitment has a reason string
4. **Content-Addressable**: Automatic deduplication via SHA-256
5. **Event-Sourced**: Complete audit trail from day 1

---

## Appendix B: User Personas

### Persona 1: Solo Entrepreneur
**Name**: Sarah
**Context**: Runs a small consulting business
**Pain Points**: Manually tracking invoices in spreadsheets, missing payment deadlines
**Goals**: Automate invoice tracking, never miss a due date, see vendor spending
**Technical Savvy**: Medium (uses Google Workspace, basic APIs)

### Persona 2: Healthcare Administrator
**Name**: Marcus
**Context**: Manages facility operations at SNF
**Pain Points**: Vendor compliance, purchase order management, budget tracking
**Goals**: Track all vendor interactions, ensure compliance docs, analyze spending
**Technical Savvy**: Low (relies on staff for technical tasks)

### Persona 3: Busy Parent + Professional
**Name**: Jamie
**Context**: Full-time job + managing household admin
**Pain Points**: Overwhelmed by bills, taxes, school forms, medical records
**Goals**: Single system for all obligations, smart reminders, easy document retrieval
**Technical Savvy**: High (software engineer, comfortable with CLI tools)

---

## Appendix C: Wireframes (Conceptual)

### Document Upload View
```
┌─────────────────────────────────────────┐
│  Vision Service                        │
│  Extract data from documents          │
├─────────────────────────────────────────┤
│  [Drag & Drop Area]                    │
│  or                                    │
│  [Browse Files]                        │
└─────────────────────────────────────────┘

After Upload:
┌─────────────────────────────────────────┐
│ ✅ Document Processed                  │
│ Saved as: abc123def456...              │
│                                         │
│ 🏢 Vendor Identified                   │
│ Clipboard Health (Twomagnets Inc.)    │
│ [✓ Matched existing vendor]            │
│ [View vendor history →]                │
│                                         │
│ 📋 Commitment Created                  │
│ Pay Invoice #240470 - Clipboard Health│
│ Due: 2024-02-28                       │
│ Priority: 85/100                       │
│ Reason: Due in 2 days, $12,419.83     │
│ [Mark as paid] [Edit]                 │
│                                         │
│ 💰 Extraction Details                 │
│ Cost: $0.0048675                       │
│ Model: gpt-4o                          │
│ [View JSON] [Download PDF]            │
└─────────────────────────────────────────┘
```

### Commitments Dashboard
```
┌─────────────────────────────────────────┐
│  Your Focus (High Priority)            │
│  [All] [Finance] [Health] [Legal]      │
├─────────────────────────────────────────┤
│ 🔴 Pay Invoice #240470 - Clipboard    │
│    Due: Feb 28 (2 days)               │
│    Priority: 85/100                    │
│    "Due in 2 days, legal risk"        │
│    [Mark Complete] [View Details]     │
│                                         │
│ 🟡 File Q4 Taxes                       │
│    Due: Apr 15 (68 days)              │
│    Priority: 70/100                    │
│    "Legal requirement, high severity"  │
│    [Mark Complete] [View Details]     │
└─────────────────────────────────────────┘
```

---

## Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| **Product Owner** | Andrew | ________ | 2025-11-06 |
| **Tech Lead** | AI Dev Team | ________ | 2025-11-06 |
| **Stakeholder** | Andrew | ________ | 2025-11-06 |

---

**Next Steps**: Review ARCHITECTURE.md for technical design details.
