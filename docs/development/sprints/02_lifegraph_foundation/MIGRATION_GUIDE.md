# Migration Guide - Life Graph Foundation

**Sprint**: 02 - Foundation & Database Schema
**Version**: 1.0.0
**Date**: 2025-11-06

---

## Overview

This guide covers all database migrations for Life Graph Integration, including upgrade/downgrade procedures, troubleshooting, and best practices.

---

## Migration Sequence

### Complete Migration Order

```
migrations/versions/
├── 001_add_extensions.py           # PostgreSQL extensions (pgcrypto, pg_trgm, btree_gist)
├── 002_create_core_tables.py       # Core Life Graph tables (parties, roles, commitments)
├── 003_enhance_documents.py        # Enhance existing documents table
└── 004_create_signals_links.py     # Signals, links, interactions tables
```

---

## Migration 001: Add Extensions

### Purpose
Install PostgreSQL extensions required for Life Graph features.

### Extensions Added
1. **pgcrypto**: UUID generation (`gen_random_uuid()`)
2. **pg_trgm**: Fuzzy text search (trigram matching)
3. **btree_gist**: Date range constraints and exclusion constraints

### Upgrade
```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;
```

### Downgrade
```sql
DROP EXTENSION IF EXISTS btree_gist;
DROP EXTENSION IF EXISTS pg_trgm;
DROP EXTENSION IF EXISTS pgcrypto;
```

### Commands
```bash
# Upgrade
alembic upgrade 001

# Downgrade
alembic downgrade -1

# Verify
psql -U assistant -d assistant -c "\dx"
```

---

## Migration 002: Create Core Tables

### Purpose
Create core Life Graph tables for entities, roles, and commitments.

### Tables Created

#### 1. `parties`
Vendors, customers, contacts (people and organizations).

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

**Indexes**:
- `idx_parties_name_trgm`: GIN index for fuzzy name search (pg_trgm)
- `idx_parties_kind`: B-tree index for filtering by kind (person/org)
- `idx_parties_tax_id`: Partial index for tax ID lookups (only when non-NULL)

#### 2. `roles`
Context-specific identities (e.g., "Employee", "Parent", "Taxpayer").

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

**Indexes**:
- `idx_roles_user`: Filter roles by user
- `idx_roles_party`: Filter roles by party
- `idx_roles_domains`: GIN index for domain tag searches

#### 3. `commitments`
Obligations, goals, routines, appointments.

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
    rrule TEXT,

    priority INT DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
    state commitment_state NOT NULL DEFAULT 'accepted',
    severity INT DEFAULT 0,
    domain_tags TEXT[] DEFAULT '{}',

    reason TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_commitments_role ON commitments(role_id);
CREATE INDEX idx_commitments_state_due ON commitments(state, due_at);
CREATE INDEX idx_commitments_priority ON commitments(priority DESC);
CREATE INDEX idx_commitments_domains ON commitments USING GIN (domain_tags);
CREATE INDEX idx_commitments_counterparty ON commitments(counterparty_id) WHERE counterparty_id IS NOT NULL;
```

**Indexes**:
- `idx_commitments_role`: Filter by role
- `idx_commitments_state_due`: Composite index for state + due date queries (focus view)
- `idx_commitments_priority`: Descending B-tree for priority sorting
- `idx_commitments_domains`: GIN index for domain tag searches
- `idx_commitments_counterparty`: Partial index for counterparty lookups

### Upgrade
```bash
alembic upgrade 002
```

### Downgrade
```sql
DROP TABLE commitments;
DROP TABLE roles;
DROP TABLE parties;
DROP TYPE commitment_state;
DROP TYPE commitment_type;
```

```bash
alembic downgrade 001
```

### Testing
```sql
-- Test party creation
INSERT INTO parties (kind, name) VALUES ('org', 'Test Vendor') RETURNING id;

-- Test role creation
INSERT INTO roles (party_id, user_id, role_name)
VALUES ('<party_id>', '00000000-0000-0000-0000-000000000001', 'Vendor');

-- Test commitment creation
INSERT INTO commitments (role_id, commitment_type, title, source)
VALUES ('<role_id>', 'obligation', 'Pay Invoice #123', 'vision_extract');

-- Test fuzzy search
SELECT name, similarity(name, 'ACME Corp') AS score
FROM parties
WHERE name % 'ACME Corp'
ORDER BY score DESC
LIMIT 5;
```

---

## Migration 003: Enhance Documents

### Purpose
Add Life Graph columns to existing `documents` table.

### Columns Added
- `sha256` (VARCHAR(64) UNIQUE): Content hash for deduplication
- `source` (VARCHAR(50)): upload, email, vision_extract
- `mime_type` (VARCHAR(100)): File MIME type
- `file_size` (BIGINT): File size in bytes
- `storage_uri` (TEXT): local://data/documents/{sha256}
- `extraction_type` (VARCHAR(50)): invoice, receipt, contract
- `extraction_data` (JSONB): Parsed extraction results
- `extraction_cost` (NUMERIC(10, 4)): AI cost
- `extracted_at` (TIMESTAMPTZ): Extraction timestamp

### Upgrade
```sql
ALTER TABLE documents
    ADD COLUMN sha256 VARCHAR(64) UNIQUE,
    ADD COLUMN source VARCHAR(50) NOT NULL,
    ADD COLUMN mime_type VARCHAR(100),
    ADD COLUMN file_size BIGINT,
    ADD COLUMN storage_uri TEXT NOT NULL,
    ADD COLUMN extraction_type VARCHAR(50),
    ADD COLUMN extraction_data JSONB,
    ADD COLUMN extraction_cost NUMERIC(10, 4),
    ADD COLUMN extracted_at TIMESTAMPTZ;

CREATE UNIQUE INDEX idx_documents_sha256 ON documents(sha256);
CREATE INDEX idx_documents_source ON documents(source);
CREATE INDEX idx_documents_extraction_type ON documents(extraction_type) WHERE extraction_type IS NOT NULL;
CREATE INDEX idx_documents_created ON documents(created_at DESC);
```

### Downgrade
```sql
DROP INDEX idx_documents_created;
DROP INDEX idx_documents_extraction_type;
DROP INDEX idx_documents_source;
DROP INDEX idx_documents_sha256;

ALTER TABLE documents
    DROP COLUMN extracted_at,
    DROP COLUMN extraction_cost,
    DROP COLUMN extraction_data,
    DROP COLUMN extraction_type,
    DROP COLUMN storage_uri,
    DROP COLUMN file_size,
    DROP COLUMN mime_type,
    DROP COLUMN source,
    DROP COLUMN sha256;
```

### Upgrade Command
```bash
alembic upgrade 003
```

### Downgrade Command
```bash
alembic downgrade 002
```

---

## Migration 004: Signals, Links, Interactions

### Purpose
Create tables for signals, polymorphic document linking, and audit logging.

### Tables Created

#### 1. `signals`
Raw inputs awaiting classification.

```sql
CREATE TABLE signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL CHECK (source IN ('vision_upload', 'email', 'api', 'manual')),
    payload_json JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(50) NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'processing', 'attached', 'archived')),
    dedupe_key VARCHAR(255) UNIQUE,

    extraction_id UUID REFERENCES documents(id),
    extraction_cost NUMERIC(10, 4)
);

CREATE INDEX idx_signals_status ON signals(status);
CREATE INDEX idx_signals_received ON signals(received_at DESC);
CREATE UNIQUE INDEX idx_signals_dedupe ON signals(dedupe_key) WHERE dedupe_key IS NOT NULL;
```

#### 2. `document_links`
Polymorphic linking (document → any entity).

```sql
CREATE TABLE document_links (
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (document_id, entity_type, entity_id)
);

CREATE INDEX idx_doclinks_entity ON document_links(entity_type, entity_id);
CREATE INDEX idx_doclinks_document ON document_links(document_id);
```

#### 3. `interactions`
Immutable audit log (event sourcing).

```sql
CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50) NOT NULL,
    actor_type VARCHAR(20) NOT NULL,
    actor_id UUID,

    primary_entity_type VARCHAR(50) NOT NULL,
    primary_entity_id UUID NOT NULL,

    related_entities JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    cost NUMERIC(10, 4),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_interactions_entity ON interactions(primary_entity_type, primary_entity_id);
CREATE INDEX idx_interactions_type ON interactions(type);
CREATE INDEX idx_interactions_created ON interactions(created_at DESC);
CREATE INDEX idx_interactions_actor ON interactions(actor_type, actor_id) WHERE actor_id IS NOT NULL;
```

### Upgrade
```bash
alembic upgrade head  # Applies all remaining migrations
```

### Downgrade
```sql
DROP TABLE interactions;
DROP TABLE document_links;
DROP TABLE signals;
```

```bash
alembic downgrade 003
```

---

## Complete Migration Workflow

### First-Time Setup

```bash
# 1. Check current migration status
alembic current

# 2. Apply all migrations
alembic upgrade head

# 3. Verify all tables created
psql -U assistant -d assistant -c "\dt"

# Expected tables:
# - parties
# - roles
# - commitments
# - documents (enhanced)
# - signals
# - document_links
# - interactions
```

### Rolling Back All Migrations

```bash
# Downgrade to base (remove all Life Graph changes)
alembic downgrade base

# Verify
alembic current  # Should show: (empty or previous migration)
```

### Testing Migrations

```bash
# Test upgrade/downgrade cycle
alembic upgrade head    # Apply all
alembic downgrade base  # Remove all
alembic upgrade head    # Re-apply all

# Verify data persistence (should be empty after downgrade → upgrade)
psql -U assistant -d assistant -c "SELECT COUNT(*) FROM parties;"
```

---

## Database Backup & Restore

### Backup Before Migration

```bash
# Backup database
./scripts/backup_database.sh

# Verify backup created
ls -lh backups/
```

### Restore After Failed Migration

```bash
# If migration fails, restore from backup
./scripts/restore_database.sh backups/backup_20251106_153045.dump

# Verify restoration
psql -U assistant -d assistant -c "\dt"
```

---

## Troubleshooting

### Issue 1: Extension Already Exists

**Error**:
```
ERROR: extension "pg_trgm" already exists
```

**Solution**:
This is not an error. The migration uses `CREATE EXTENSION IF NOT EXISTS`, so it's safe to ignore.

### Issue 2: Table Already Exists

**Error**:
```
ERROR: relation "parties" already exists
```

**Solution**:
Check current migration status:
```bash
alembic current
```

If migration was already applied, skip it:
```bash
alembic stamp head  # Mark as applied without running
```

### Issue 3: Foreign Key Constraint Failure

**Error**:
```
ERROR: insert or update on table "roles" violates foreign key constraint
```

**Solution**:
Ensure parent records exist before inserting child records:
```sql
-- Create party first
INSERT INTO parties (kind, name) VALUES ('org', 'ACME Corp') RETURNING id;

-- Then create role
INSERT INTO roles (party_id, user_id, role_name)
VALUES ('<party_id>', '<user_id>', 'Vendor');
```

### Issue 4: Migration Conflict

**Error**:
```
ERROR: Can't locate revision identified by 'abc123'
```

**Solution**:
Reset Alembic state:
```bash
# 1. Backup database
./scripts/backup_database.sh

# 2. Drop alembic_version table
psql -U assistant -d assistant -c "DROP TABLE alembic_version;"

# 3. Stamp current state
alembic stamp head

# 4. Verify
alembic current
```

---

## Health Check Script

### Usage

```bash
# Run health check
./scripts/check_migration_health.sh

# Expected output:
# ✅ PostgreSQL extensions installed
# ✅ All tables exist
# ✅ All indexes created
# ✅ Migration status: head
# ✅ Database health: OK
```

---

## Performance Considerations

### Index Strategy

1. **B-Tree Indexes**: For equality and range queries
   - `parties(kind)`, `commitments(priority DESC)`

2. **GIN Indexes**: For full-text search and JSONB/array queries
   - `parties(name gin_trgm_ops)`, `commitments(domain_tags)`

3. **Partial Indexes**: For sparse columns
   - `parties(tax_id) WHERE tax_id IS NOT NULL`

### Query Optimization

```sql
-- Use EXPLAIN ANALYZE to check query performance
EXPLAIN ANALYZE
SELECT * FROM commitments
WHERE state = 'active' AND priority >= 50
ORDER BY priority DESC
LIMIT 50;

-- Expected: Index Scan using idx_commitments_priority
-- Execution Time: <50ms
```

---

## Best Practices

### Before Migration
1. **Backup database**: Always backup before applying migrations
2. **Test in dev environment**: Test migrations on development database first
3. **Review migration code**: Ensure SQL is correct and safe

### During Migration
1. **Monitor logs**: Watch for errors during migration
2. **Check performance**: Ensure migrations complete in reasonable time
3. **Verify data integrity**: Check data after migration

### After Migration
1. **Test queries**: Verify indexes are used correctly
2. **Check foreign keys**: Ensure referential integrity
3. **Run health check**: Use `check_migration_health.sh`

---

## Appendix: Full Schema Reference

### ERD Diagram

```
┌─────────────┐
│   parties   │──┐
│ (vendors,   │  │
│  customers) │  │
└─────────────┘  │ 1:N
                 │
┌─────────────┐  │
│    roles    │◄─┘
│ (contexts)  │
└─────────────┘
       │ 1:N
       ▼
┌─────────────┐
│commitments  │
│ (what you   │
│   owe)      │
└─────────────┘

┌─────────────┐       ┌─────────────┐
│  documents  │──────►│document_links│──► Any entity
│ (PDFs, imgs)│  N:M  │ (polymorphic)│
└─────────────┘       └─────────────┘

┌─────────────┐
│   signals   │
│ (raw inputs)│
└─────────────┘

┌──────────────┐
│interactions  │
│ (audit log)  │
└──────────────┘
```

### Table Sizes (Estimated)

| Table | Rows (1 year) | Size |
|-------|---------------|------|
| parties | 1,000 | 200 KB |
| roles | 2,000 | 150 KB |
| commitments | 10,000 | 5 MB |
| documents | 5,000 | 2 MB |
| signals | 5,000 | 2 MB |
| document_links | 15,000 | 1 MB |
| interactions | 50,000 | 20 MB |
| **Total** | **88,000** | **~30 MB** |

---

**End of Migration Guide**
**Version**: 1.0.0
**Last Updated**: 2025-11-06
