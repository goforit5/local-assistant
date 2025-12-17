# Database Migration Plan: Life Graph Integration
**Version**: 1.0.0
**Date**: 2025-11-06
**Status**: Planning Phase

---

## Overview

This document provides the complete database migration plan to integrate Life Graph schema with the existing Local Assistant database. All migrations use **Alembic** for version control and rollback support.

### Migration Strategy
- **Additive Only**: No breaking changes to existing tables
- **Backward Compatible**: Existing functionality continues to work
- **Incremental**: Split into 5 migration files for safety
- **Tested**: Each migration has rollback verified

---

## Current Database State

### Existing Tables (DO NOT MODIFY)
```sql
conversations
messages
documents  -- ENHANCE (add new columns)
cost_entries
```

### Database Info
- **RDBMS**: PostgreSQL 16
- **Port**: 5433
- **Database**: assistant
- **ORM**: SQLAlchemy 2.0
- **Migration Tool**: Alembic

---

## Migration Sequence

### Migration 001: PostgreSQL Extensions
**File**: `migrations/versions/001_add_extensions.py`
**Purpose**: Add required PostgreSQL extensions

```python
"""Add PostgreSQL extensions for Life Graph

Revision ID: 001_add_extensions
Revises:
Create Date: 2025-11-06

"""
from alembic import op

# revision identifiers
revision = '001_add_extensions'
down_revision = None  # Or existing latest revision
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgcrypto for UUID generation
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto;')

    # Enable pg_trgm for fuzzy text search
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')

    # Enable btree_gist for date range constraints
    op.execute('CREATE EXTENSION IF NOT EXISTS btree_gist;')

    print("✅ Extensions created: pgcrypto, pg_trgm, btree_gist")


def downgrade():
    # Note: Don't drop extensions in downgrade (may be used by other schemas)
    print("⚠️  Extensions left in place (may be used by other schemas)")
```

---

### Migration 002: Core Life Graph Tables
**File**: `migrations/versions/002_create_core_tables.py`
**Purpose**: Create parties, roles, commitments

```python
"""Create core Life Graph tables

Revision ID: 002_create_core_tables
Revises: 001_add_extensions
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_create_core_tables'
down_revision = '001_add_extensions'
branch_labels = None
depends_on = None


def upgrade():
    # Create ENUM types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE commitment_type AS ENUM (
                'obligation', 'responsibility', 'goal',
                'routine', 'appointment', 'compliance'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE commitment_state AS ENUM (
                'proposed', 'accepted', 'active', 'paused',
                'fulfilled', 'canceled', 'delinquent'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # Create parties table
    op.create_table(
        'parties',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('tax_id', sa.String(50)),
        sa.Column('contact_json', postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column('metadata', postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint("kind IN ('person', 'org')", name='check_party_kind')
    )

    # Indexes for parties
    op.create_index('idx_parties_name_trgm', 'parties', ['name'], postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_index('idx_parties_kind', 'parties', ['kind'])
    op.create_index('idx_parties_tax_id', 'parties', ['tax_id'], postgresql_where=sa.text('tax_id IS NOT NULL'))

    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('party_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parties.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_name', sa.String(100), nullable=False),
        sa.Column('domain_tags', postgresql.ARRAY(sa.Text), server_default=sa.text("'{}'::text[]")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    )

    # Indexes for roles
    op.create_index('idx_roles_user', 'roles', ['user_id'])
    op.create_index('idx_roles_party', 'roles', ['party_id'])
    op.create_index('idx_roles_domains', 'roles', ['domain_tags'], postgresql_using='gin')

    # Create commitments table
    op.create_table(
        'commitments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('commitment_type', sa.Enum('obligation', 'responsibility', 'goal', 'routine', 'appointment', 'compliance', name='commitment_type'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('counterparty_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parties.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('due_at', sa.DateTime(timezone=True)),
        sa.Column('rrule', sa.Text),
        sa.Column('priority', sa.Integer, server_default=sa.text('50')),
        sa.Column('state', sa.Enum('proposed', 'accepted', 'active', 'paused', 'fulfilled', 'canceled', 'delinquent', name='commitment_state'), nullable=False, server_default=sa.text("'accepted'")),
        sa.Column('severity', sa.Integer, server_default=sa.text('0')),
        sa.Column('domain_tags', postgresql.ARRAY(sa.Text), server_default=sa.text("'{}'::text[]")),
        sa.Column('reason', sa.Text),
        sa.Column('metadata', postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint('source IN (\'email\', \'doc\', \'vision_extract\', \'api\', \'manual\')', name='check_commitment_source'),
        sa.CheckConstraint('priority BETWEEN 0 AND 100', name='check_commitment_priority')
    )

    # Indexes for commitments
    op.create_index('idx_commitments_role', 'commitments', ['role_id'])
    op.create_index('idx_commitments_state_due', 'commitments', ['state', 'due_at'])
    op.create_index('idx_commitments_priority', 'commitments', ['priority'], postgresql_ops={'priority': 'DESC'})
    op.create_index('idx_commitments_domains', 'commitments', ['domain_tags'], postgresql_using='gin')
    op.create_index('idx_commitments_counterparty', 'commitments', ['counterparty_id'], postgresql_where=sa.text('counterparty_id IS NOT NULL'))

    print("✅ Created: parties, roles, commitments")


def downgrade():
    op.drop_table('commitments')
    op.drop_table('roles')
    op.drop_table('parties')

    op.execute('DROP TYPE IF EXISTS commitment_state;')
    op.execute('DROP TYPE IF EXISTS commitment_type;')

    print("✅ Dropped: commitments, roles, parties")
```

---

### Migration 003: Enhance Documents Table
**File**: `migrations/versions/003_enhance_documents.py`
**Purpose**: Add Life Graph columns to existing documents table

```python
"""Enhance documents table for Life Graph

Revision ID: 003_enhance_documents
Revises: 002_create_core_tables
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_enhance_documents'
down_revision = '002_create_core_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to existing documents table
    op.add_column('documents', sa.Column('sha256', sa.String(64)))
    op.add_column('documents', sa.Column('source', sa.String(50)))
    op.add_column('documents', sa.Column('mime_type', sa.String(100)))
    op.add_column('documents', sa.Column('file_size', sa.BigInteger))
    op.add_column('documents', sa.Column('storage_uri', sa.Text))
    op.add_column('documents', sa.Column('extraction_type', sa.String(50)))
    op.add_column('documents', sa.Column('extraction_data', postgresql.JSONB))
    op.add_column('documents', sa.Column('extraction_cost', sa.Numeric(10, 4)))
    op.add_column('documents', sa.Column('extracted_at', sa.DateTime(timezone=True)))

    # Rename content_hash if it exists (for consistency)
    # op.alter_column('documents', 'content_hash', new_column_name='sha256')  # If needed

    # Add indexes
    op.create_unique_index('idx_documents_sha256', 'documents', ['sha256'])
    op.create_index('idx_documents_source', 'documents', ['source'])
    op.create_index('idx_documents_extraction_type', 'documents', ['extraction_type'], postgresql_where=sa.text('extraction_type IS NOT NULL'))
    op.create_index('idx_documents_created', 'documents', ['created_at'], postgresql_ops={'created_at': 'DESC'})

    print("✅ Enhanced documents table with Life Graph columns")


def downgrade():
    # Drop indexes
    op.drop_index('idx_documents_created', 'documents')
    op.drop_index('idx_documents_extraction_type', 'documents')
    op.drop_index('idx_documents_source', 'documents')
    op.drop_index('idx_documents_sha256', 'documents')

    # Drop columns
    op.drop_column('documents', 'extracted_at')
    op.drop_column('documents', 'extraction_cost')
    op.drop_column('documents', 'extraction_data')
    op.drop_column('documents', 'extraction_type')
    op.drop_column('documents', 'storage_uri')
    op.drop_column('documents', 'file_size')
    op.drop_column('documents', 'mime_type')
    op.drop_column('documents', 'source')
    op.drop_column('documents', 'sha256')

    print("✅ Removed Life Graph columns from documents")
```

---

### Migration 004: Signals and Links
**File**: `migrations/versions/004_create_signals_links.py`
**Purpose**: Create signals, document_links, interactions tables

```python
"""Create signals, document_links, interactions tables

Revision ID: 004_create_signals_links
Revises: 003_enhance_documents
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '004_create_signals_links'
down_revision = '003_enhance_documents'
branch_labels = None
depends_on = None


def upgrade():
    # Create signals table
    op.create_table(
        'signals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('payload_json', postgresql.JSONB, nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('status', sa.String(50), nullable=False, server_default=sa.text("'new'")),
        sa.Column('dedupe_key', sa.String(255)),
        sa.Column('extraction_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id')),
        sa.Column('extraction_cost', sa.Numeric(10, 4)),
        sa.CheckConstraint("source IN ('vision_upload', 'email', 'api', 'manual')", name='check_signal_source'),
        sa.CheckConstraint("status IN ('new', 'processing', 'attached', 'archived')", name='check_signal_status')
    )

    # Indexes for signals
    op.create_index('idx_signals_status', 'signals', ['status'])
    op.create_index('idx_signals_received', 'signals', ['received_at'], postgresql_ops={'received_at': 'DESC'})
    op.create_unique_index('idx_signals_dedupe', 'signals', ['dedupe_key'], postgresql_where=sa.text('dedupe_key IS NOT NULL'))

    # Create document_links table (polymorphic)
    op.create_table(
        'document_links',
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('entity_type', sa.String(50), primary_key=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    )

    # Indexes for document_links
    op.create_index('idx_doclinks_entity', 'document_links', ['entity_type', 'entity_id'])
    op.create_index('idx_doclinks_document', 'document_links', ['document_id'])

    # Create interactions table (event log)
    op.create_table(
        'interactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('actor_type', sa.String(20), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True)),
        sa.Column('primary_entity_type', sa.String(50), nullable=False),
        sa.Column('primary_entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('related_entities', postgresql.JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column('metadata', postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column('cost', sa.Numeric(10, 4)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    )

    # Indexes for interactions
    op.create_index('idx_interactions_entity', 'interactions', ['primary_entity_type', 'primary_entity_id'])
    op.create_index('idx_interactions_type', 'interactions', ['type'])
    op.create_index('idx_interactions_created', 'interactions', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    op.create_index('idx_interactions_actor', 'interactions', ['actor_type', 'actor_id'], postgresql_where=sa.text('actor_id IS NOT NULL'))

    print("✅ Created: signals, document_links, interactions")


def downgrade():
    op.drop_table('interactions')
    op.drop_table('document_links')
    op.drop_table('signals')

    print("✅ Dropped: signals, document_links, interactions")
```

---

### Migration 005: Tasks and Events (Optional - Future)
**File**: `migrations/versions/005_create_tasks_events.py`
**Purpose**: Create tasks and events tables (Future roadmap)

```python
"""Create tasks and events tables

Revision ID: 005_create_tasks_events
Revises: 004_create_signals_links
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '005_create_tasks_events'
down_revision = '004_create_signals_links'
branch_labels = None
depends_on = None


def upgrade():
    # Create task_status ENUM
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE task_status AS ENUM (
                'todo', 'in_progress', 'blocked', 'done', 'canceled'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('commitment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('commitments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('instructions', sa.Text),
        sa.Column('status', sa.Enum('todo', 'in_progress', 'blocked', 'done', 'canceled', name='task_status'), nullable=False, server_default=sa.text("'todo'")),
        sa.Column('effort_estimate', sa.Numeric(6, 2)),
        sa.Column('due_at', sa.DateTime(timezone=True)),
        sa.Column('rrule', sa.Text),
        sa.Column('deps', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=sa.text("'{}'::uuid[]"))
    )

    # Indexes for tasks
    op.create_index('idx_tasks_commitment', 'tasks', ['commitment_id'])
    op.create_index('idx_tasks_status_due', 'tasks', ['status', 'due_at'])

    # Create locations table
    op.create_table(
        'locations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('label', sa.String(255)),
        sa.Column('address_json', postgresql.JSONB),
        sa.Column('geo_json', postgresql.JSONB)
    )

    # Create events table
    op.create_table(
        'events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True)),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id')),
        sa.Column('confirmed', sa.Boolean, server_default=sa.text('false'))
    )

    # Indexes for events
    op.create_index('idx_events_time', 'events', ['starts_at'])

    print("✅ Created: tasks, locations, events")


def downgrade():
    op.drop_table('events')
    op.drop_table('locations')
    op.drop_table('tasks')

    op.execute('DROP TYPE IF EXISTS task_status;')

    print("✅ Dropped: tasks, locations, events")
```

---

## Migration Execution Plan

### Pre-Migration Checklist
```bash
# 1. Backup existing database
pg_dump -U assistant -d assistant -F c -f backup_pre_lifegraph_$(date +%Y%m%d).dump

# 2. Verify connection
psql -U assistant -d assistant -c "SELECT version();"

# 3. Check Alembic current revision
alembic current

# 4. Dry-run (generate SQL without executing)
alembic upgrade head --sql > migration_preview.sql
```

### Execution Steps

```bash
# Step 1: Run migrations one by one (safer)
alembic upgrade 001_add_extensions
# Verify: SELECT * FROM pg_extension WHERE extname IN ('pgcrypto', 'pg_trgm', 'btree_gist');

alembic upgrade 002_create_core_tables
# Verify: SELECT table_name FROM information_schema.tables WHERE table_name IN ('parties', 'roles', 'commitments');

alembic upgrade 003_enhance_documents
# Verify: SELECT column_name FROM information_schema.columns WHERE table_name = 'documents' AND column_name IN ('sha256', 'extraction_data');

alembic upgrade 004_create_signals_links
# Verify: SELECT table_name FROM information_schema.tables WHERE table_name IN ('signals', 'document_links', 'interactions');

# Step 2: Or run all at once
alembic upgrade head

# Step 3: Verify final state
alembic current
```

### Post-Migration Verification

```sql
-- 1. Check all tables exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'parties', 'roles', 'commitments', 'documents',
    'signals', 'document_links', 'interactions'
  )
ORDER BY table_name;

-- 2. Check indexes
SELECT indexname, tablename
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname LIKE 'idx_%'
ORDER BY tablename, indexname;

-- 3. Check ENUMs
SELECT typname
FROM pg_type
WHERE typtype = 'e'
  AND typname IN ('commitment_type', 'commitment_state', 'task_status');

-- 4. Insert test data
INSERT INTO parties (kind, name, tax_id)
VALUES ('org', 'Test Vendor', '12-3456789')
RETURNING id;

-- 5. Query test data
SELECT * FROM parties WHERE name = 'Test Vendor';
```

---

## Rollback Plan

### Emergency Rollback (Full)
```bash
# Rollback all Life Graph migrations
alembic downgrade 001_add_extensions

# Verify rollback
alembic current
# Should show: <base>

# Restore from backup if needed
pg_restore -U assistant -d assistant -c backup_pre_lifegraph_20251106.dump
```

### Partial Rollback (One Step)
```bash
# Rollback last migration only
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 003_enhance_documents
```

---

## Data Migration (Optional)

### Migrate Existing Documents
If you have existing documents, update them with new fields:

```sql
-- Add SHA-256 to existing documents
UPDATE documents
SET sha256 = encode(sha256(path::bytea), 'hex')
WHERE sha256 IS NULL;

-- Set source for existing documents
UPDATE documents
SET source = 'legacy'
WHERE source IS NULL;

-- Set storage_uri
UPDATE documents
SET storage_uri = 'local://data/documents/' || sha256 || '.pdf'
WHERE storage_uri IS NULL;
```

---

## Testing Strategy

### Unit Tests for Migrations
**Location**: `tests/migrations/test_migrations.py`

```python
import pytest
from alembic import command
from alembic.config import Config


def test_upgrade_downgrade_001():
    """Test extensions migration."""
    config = Config("alembic.ini")

    # Upgrade
    command.upgrade(config, "001_add_extensions")
    # Verify extensions exist

    # Downgrade
    command.downgrade(config, "base")


def test_upgrade_downgrade_002():
    """Test core tables migration."""
    config = Config("alembic.ini")

    command.upgrade(config, "002_create_core_tables")
    # Verify tables exist
    # Insert test data
    # Query test data

    command.downgrade(config, "001_add_extensions")
    # Verify tables dropped
```

---

## Performance Considerations

### Index Analysis
```sql
-- Analyze query performance
EXPLAIN ANALYZE
SELECT * FROM commitments
WHERE state = 'active' AND priority >= 50
ORDER BY priority DESC
LIMIT 50;

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

### Vacuum and Analyze
```sql
-- After migration, update statistics
VACUUM ANALYZE parties;
VACUUM ANALYZE roles;
VACUUM ANALYZE commitments;
VACUUM ANALYZE documents;
VACUUM ANALYZE signals;
VACUUM ANALYZE document_links;
VACUUM ANALYZE interactions;
```

---

## Monitoring

### Migration Health Check Script
**Location**: `scripts/check_migration_health.sh`

```bash
#!/bin/bash
# Check migration health and report issues

echo "=== Migration Health Check ==="

# Check Alembic current revision
echo "Current revision:"
alembic current

# Check table counts
echo -e "\nTable row counts:"
psql -U assistant -d assistant -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    n_live_tup AS rows
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# Check for missing indexes
echo -e "\nChecking for missing indexes..."
psql -U assistant -d assistant -c "
SELECT DISTINCT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename NOT IN (
    SELECT DISTINCT tablename FROM pg_indexes WHERE schemaname = 'public'
  );
"

echo -e "\n✅ Health check complete"
```

---

## Summary

### Migration Files Created
1. `001_add_extensions.py` - PostgreSQL extensions
2. `002_create_core_tables.py` - parties, roles, commitments
3. `003_enhance_documents.py` - Add Life Graph columns
4. `004_create_signals_links.py` - signals, document_links, interactions
5. `005_create_tasks_events.py` - tasks, events (future)

### Estimated Duration
- **Migration Execution**: 5-10 minutes
- **Verification**: 5 minutes
- **Total**: 15 minutes

### Rollback Time
- **Full Rollback**: <5 minutes
- **Partial Rollback**: <2 minutes

---

**Next Steps**: Review IMPLEMENTATION_PLAN.md for phased development approach.
