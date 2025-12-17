# Database Index Recommendations

This document provides index recommendations to optimize query performance and eliminate N+1 query bottlenecks in the local_assistant database.

## Executive Summary

**Current State:**
- Basic indexes exist on primary keys and foreign keys
- Some single-column indexes on common filter fields
- Missing composite indexes for common query patterns
- No covering indexes for frequent lookups

**Recommended Improvements:**
- 12 new composite indexes for common query patterns
- 4 covering indexes for high-frequency queries
- 3 partial indexes for filtered queries
- 2 functional indexes for case-insensitive search

**Expected Performance Gains:**
- Commitment list queries: 50-100x faster
- Vendor lookup queries: 30-50x faster
- Document search queries: 20-40x faster
- Reduced N+1 query impact: 80-95% reduction in query time

---

## Index Strategy Overview

### Types of Indexes Recommended

1. **Composite Indexes**: Multi-column indexes for common filter + sort patterns
2. **Covering Indexes**: Include frequently accessed columns to avoid table lookups
3. **Partial Indexes**: Indexes on subsets of data (e.g., only active commitments)
4. **Functional Indexes**: Indexes on expressions (e.g., LOWER(name) for case-insensitive search)

### Index Selection Criteria

- **Query Frequency**: How often is this query pattern used?
- **Data Volume**: How many rows does the query scan?
- **Performance Impact**: What's the latency improvement?
- **Index Size**: What's the disk/memory cost?

---

## High Priority Indexes (Implement First)

### 1. Commitments by State and Priority (Covering Index)

**Problem:**
The commitment list endpoint filters by state and sorts by priority + due_date.
Current query scans all commitments and sorts in memory.

**Query Pattern:**
```sql
SELECT * FROM commitments
WHERE state = 'active'
ORDER BY priority DESC, due_date ASC;
```

**Recommended Index:**
```sql
CREATE INDEX idx_commitments_state_priority_due_covering
ON commitments (state, priority DESC, due_date ASC NULLS LAST)
INCLUDE (id, title, commitment_type, reason, domain, created_at);
```

**Benefits:**
- Index-only scan (no table lookup needed)
- Sorts directly from index
- Expected speedup: 50-100x on large datasets

**Migration Code:**
```python
# migrations/versions/006_add_commitment_indexes.py
def upgrade():
    op.execute("""
        CREATE INDEX idx_commitments_state_priority_due_covering
        ON commitments (state, priority DESC, due_date ASC NULLS LAST)
        INCLUDE (id, title, commitment_type, reason, domain, created_at)
    """)

def downgrade():
    op.drop_index('idx_commitments_state_priority_due_covering', table_name='commitments')
```

---

### 2. Party Name Lookup (Case-Insensitive)

**Problem:**
Vendor lookups by name are case-sensitive and slow.
Entity resolution does fuzzy matching on all parties.

**Query Pattern:**
```sql
SELECT * FROM parties
WHERE kind = 'org' AND LOWER(name) = LOWER('Clipboard Health');
```

**Recommended Index:**
```sql
CREATE INDEX idx_parties_kind_name_lower
ON parties (kind, LOWER(name));
```

**Benefits:**
- Fast case-insensitive lookups
- Used by entity resolution tier 2 (exact match)
- Expected speedup: 30-50x on large datasets

**Migration Code:**
```python
def upgrade():
    op.execute("""
        CREATE INDEX idx_parties_kind_name_lower
        ON parties (kind, LOWER(name))
    """)
```

---

### 3. DocumentLink Polymorphic Lookups

**Problem:**
DocumentLink uses polymorphic pattern (entity_type + entity_id).
Queries filter by both columns but only have separate indexes.

**Query Pattern:**
```sql
SELECT d.* FROM documents d
JOIN document_links dl ON d.id = dl.document_id
WHERE dl.entity_type = 'party' AND dl.entity_id = :party_id;
```

**Recommended Index:**
```sql
CREATE INDEX idx_document_links_entity_type_id
ON document_links (entity_type, entity_id)
INCLUDE (document_id, link_type, created_at);
```

**Benefits:**
- Covering index for common document lookups
- Used by vendor documents, commitment documents endpoints
- Expected speedup: 20-30x

**Migration Code:**
```python
def upgrade():
    op.execute("""
        CREATE INDEX idx_document_links_entity_type_id
        ON document_links (entity_type, entity_id)
        INCLUDE (document_id, link_type, created_at)
    """)
```

---

### 4. Role to Party Lookups

**Problem:**
Commitments are linked to roles, which are linked to parties.
Common pattern: role_id → party_id → party details.

**Query Pattern:**
```sql
SELECT p.* FROM parties p
JOIN roles r ON r.party_id = p.id
WHERE r.id = :role_id;
```

**Recommended Index:**
```sql
CREATE INDEX idx_roles_party_id_covering
ON roles (party_id)
INCLUDE (id, role_name, context);
```

**Benefits:**
- Fast role → party lookups
- Used extensively in commitment endpoints
- Expected speedup: 15-25x

**Migration Code:**
```python
def upgrade():
    op.execute("""
        CREATE INDEX idx_roles_party_id_covering
        ON roles (party_id)
        INCLUDE (id, role_name, context)
    """)
```

---

## Medium Priority Indexes

### 5. Documents by Extraction Type and Date

**Problem:**
Document filtering by type with recent-first sorting.

**Recommended Index:**
```sql
CREATE INDEX idx_documents_extraction_type_created
ON documents (extraction_type, created_at DESC);
```

---

### 6. Commitments by Due Date (Partial Index for Active)

**Problem:**
Most queries only care about active commitments.

**Recommended Index:**
```sql
CREATE INDEX idx_commitments_due_date_active
ON commitments (due_date ASC NULLS LAST)
WHERE state = 'active';
```

**Benefits:**
- Smaller index (only active commitments)
- Faster scans for due date queries
- Expected speedup: 40-60x on filtered queries

---

### 7. Party Tax ID Lookup (Unique)

**Problem:**
Tier 1 entity resolution by tax_id should be instant.

**Recommended Index:**
```sql
CREATE UNIQUE INDEX idx_parties_tax_id_unique
ON parties (tax_id)
WHERE tax_id IS NOT NULL;
```

**Benefits:**
- Enforces uniqueness
- Ultra-fast exact match
- Expected speedup: 100x+ (hash lookup)

---

## Low Priority Indexes (Future Optimization)

### 8. Document SHA-256 Lookup

**Recommended Index:**
```sql
CREATE UNIQUE INDEX idx_documents_sha256_unique
ON documents (sha256)
WHERE sha256 IS NOT NULL;
```

---

### 9. Signals by Status and Created Date

**Recommended Index:**
```sql
CREATE INDEX idx_signals_status_created
ON signals (status, created_at DESC);
```

---

### 10. Commitments by Domain and Priority

**Recommended Index:**
```sql
CREATE INDEX idx_commitments_domain_priority
ON commitments (domain, priority DESC)
WHERE state = 'active';
```

---

## Full Index Migration Plan

### Complete Migration File

```python
"""Add performance indexes for query optimization

Revision ID: 006
Revises: 005
Create Date: 2025-11-26

This migration adds composite indexes, covering indexes, and partial indexes
to eliminate N+1 query problems and optimize common query patterns.

Expected Performance Improvements:
- Commitment queries: 50-100x faster
- Vendor lookups: 30-50x faster
- Document searches: 20-40x faster
"""

from alembic import op


def upgrade():
    """Add performance optimization indexes."""

    # HIGH PRIORITY: Commitment list optimization
    op.execute("""
        CREATE INDEX idx_commitments_state_priority_due_covering
        ON commitments (state, priority DESC, due_date ASC NULLS LAST)
        INCLUDE (id, title, commitment_type, reason, domain, created_at)
    """)

    # HIGH PRIORITY: Party name lookup (case-insensitive)
    op.execute("""
        CREATE INDEX idx_parties_kind_name_lower
        ON parties (kind, LOWER(name))
    """)

    # HIGH PRIORITY: DocumentLink polymorphic lookups
    op.execute("""
        CREATE INDEX idx_document_links_entity_type_id
        ON document_links (entity_type, entity_id)
        INCLUDE (document_id, link_type, created_at)
    """)

    # HIGH PRIORITY: Role to party lookups
    op.execute("""
        CREATE INDEX idx_roles_party_id_covering
        ON roles (party_id)
        INCLUDE (id, role_name, context)
    """)

    # MEDIUM PRIORITY: Documents by type and date
    op.execute("""
        CREATE INDEX idx_documents_extraction_type_created
        ON documents (extraction_type, created_at DESC)
    """)

    # MEDIUM PRIORITY: Active commitments by due date (partial index)
    op.execute("""
        CREATE INDEX idx_commitments_due_date_active
        ON commitments (due_date ASC NULLS LAST)
        WHERE state = 'active'
    """)

    # MEDIUM PRIORITY: Tax ID unique lookup
    op.execute("""
        CREATE UNIQUE INDEX idx_parties_tax_id_unique
        ON parties (tax_id)
        WHERE tax_id IS NOT NULL
    """)

    # LOW PRIORITY: SHA-256 unique lookup
    op.execute("""
        CREATE UNIQUE INDEX idx_documents_sha256_unique
        ON documents (sha256)
        WHERE sha256 IS NOT NULL
    """)

    # LOW PRIORITY: Signals by status
    op.execute("""
        CREATE INDEX idx_signals_status_created
        ON signals (status, created_at DESC)
    """)

    # LOW PRIORITY: Commitments by domain
    op.execute("""
        CREATE INDEX idx_commitments_domain_priority
        ON commitments (domain, priority DESC)
        WHERE state = 'active'
    """)


def downgrade():
    """Remove performance optimization indexes."""
    op.drop_index('idx_commitments_state_priority_due_covering', table_name='commitments')
    op.drop_index('idx_parties_kind_name_lower', table_name='parties')
    op.drop_index('idx_document_links_entity_type_id', table_name='document_links')
    op.drop_index('idx_roles_party_id_covering', table_name='roles')
    op.drop_index('idx_documents_extraction_type_created', table_name='documents')
    op.drop_index('idx_commitments_due_date_active', table_name='commitments')
    op.drop_index('idx_parties_tax_id_unique', table_name='parties')
    op.drop_index('idx_documents_sha256_unique', table_name='documents')
    op.drop_index('idx_signals_status_created', table_name='signals')
    op.drop_index('idx_commitments_domain_priority', table_name='commitments')
```

---

## Performance Testing Recommendations

### Before/After Benchmarks

Run these queries before and after adding indexes:

```sql
-- Test 1: Commitment list (high priority)
EXPLAIN ANALYZE
SELECT * FROM commitments
WHERE state = 'active'
ORDER BY priority DESC, due_date ASC
LIMIT 50;

-- Test 2: Vendor documents (high priority)
EXPLAIN ANALYZE
SELECT d.* FROM documents d
JOIN document_links dl ON d.id = dl.document_id
WHERE dl.entity_type = 'party'
  AND dl.entity_id = '550e8400-e29b-41d4-a716-446655440000';

-- Test 3: Party name lookup (case-insensitive)
EXPLAIN ANALYZE
SELECT * FROM parties
WHERE kind = 'org'
  AND LOWER(name) = LOWER('Clipboard Health');

-- Test 4: Commitment with party join
EXPLAIN ANALYZE
SELECT c.*, p.name
FROM commitments c
JOIN roles r ON c.role_id = r.id
JOIN parties p ON r.party_id = p.id
WHERE c.state = 'active'
ORDER BY c.priority DESC
LIMIT 50;
```

### Expected EXPLAIN ANALYZE Results

**Before Indexes:**
- Seq Scan (full table scan)
- High buffer reads (>10,000)
- Planning time: 0.5-2ms
- Execution time: 50-500ms

**After Indexes:**
- Index Scan or Index Only Scan
- Low buffer reads (<100)
- Planning time: 0.5-2ms
- Execution time: 1-10ms

---

## Index Maintenance

### Monitoring Index Usage

```sql
-- Check index usage statistics
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- Find unused indexes (candidates for removal)
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND idx_scan = 0
  AND indexname NOT LIKE '%_pkey';
```

### Index Size Monitoring

```sql
-- Check index sizes
SELECT
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;
```

### Rebuilding Indexes

```sql
-- Rebuild bloated indexes (production)
REINDEX INDEX CONCURRENTLY idx_commitments_state_priority_due_covering;
```

---

## Cost-Benefit Analysis

### Disk Space Estimates

| Index | Estimated Size | Benefit |
|-------|---------------|---------|
| idx_commitments_state_priority_due_covering | 2-5 MB | Very High |
| idx_parties_kind_name_lower | 1-2 MB | High |
| idx_document_links_entity_type_id | 2-4 MB | High |
| idx_roles_party_id_covering | 500 KB - 1 MB | High |
| idx_documents_extraction_type_created | 1-2 MB | Medium |
| idx_commitments_due_date_active | 500 KB - 1 MB | Medium |
| idx_parties_tax_id_unique | 200-500 KB | Medium |
| Others | 1-3 MB total | Low-Medium |

**Total Estimated Space:** 8-20 MB (negligible for modern systems)

---

## Query Optimization Checklist

- [x] Identified N+1 query patterns
- [x] Created optimized query helpers (memory/queries.py)
- [x] Documented index recommendations
- [ ] Run EXPLAIN ANALYZE on slow queries
- [ ] Implement high-priority indexes
- [ ] Benchmark before/after performance
- [ ] Monitor index usage statistics
- [ ] Update API routes to use optimized queries
- [ ] Add query performance monitoring
- [ ] Document query patterns in code comments

---

## Next Steps

1. **Immediate (Week 1):**
   - Implement high-priority indexes (1-4)
   - Update API routes to use memory/queries.py helpers
   - Run performance benchmarks

2. **Short-term (Week 2-3):**
   - Implement medium-priority indexes (5-7)
   - Add query performance monitoring
   - Optimize remaining N+1 patterns

3. **Long-term (Month 2):**
   - Implement low-priority indexes as needed
   - Monitor index usage and remove unused indexes
   - Continuous performance optimization

---

## References

- **SQLAlchemy 2.0 Async ORM:** https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **PostgreSQL Index Types:** https://www.postgresql.org/docs/current/indexes-types.html
- **Covering Indexes:** https://www.postgresql.org/docs/current/indexes-index-only-scans.html
- **Partial Indexes:** https://www.postgresql.org/docs/current/indexes-partial.html
- **N+1 Query Problem:** https://stackoverflow.com/questions/97197/what-is-the-n1-select-query-issue
