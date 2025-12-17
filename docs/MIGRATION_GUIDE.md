# Database Migration Guide

**Version:** 1.0
**Last Updated:** 2025-11-26
**Target:** Local Assistant Production Deployment

---

## Table of Contents

1. [Overview](#overview)
2. [Database Migration Strategy](#database-migration-strategy)
3. [Zero-Downtime Deployment](#zero-downtime-deployment)
4. [Backup and Restore Procedures](#backup-and-restore-procedures)
5. [Migration Workflow](#migration-workflow)
6. [Advanced Scenarios](#advanced-scenarios)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

This guide provides comprehensive procedures for:
- Running database migrations safely in production
- Achieving zero-downtime deployments
- Backing up and restoring data
- Handling migration failures and rollbacks

### Database Stack

- **Primary Database**: PostgreSQL 16 (port 5433)
- **Migration Tool**: Alembic
- **Backup Format**: SQL dump (gzip compressed)
- **Retention Policy**: 30 days default

### Migration Types

| Type | Downtime | Risk | Use Case |
|------|----------|------|----------|
| Additive (new columns/tables) | None | Low | New features |
| Backward compatible changes | None | Low | Schema evolution |
| Data transformations | Minimal | Medium | Data refactoring |
| Breaking changes | Required | High | Major refactors |

---

## Database Migration Strategy

### Alembic Workflow

Alembic manages database schema versions through migration scripts stored in `/migrations/versions/`.

```bash
# Check current database version
alembic current

# Expected output:
# abc123def456 (head)

# View migration history
alembic history --verbose

# Check pending migrations
alembic heads
```

### Migration Script Structure

```python
# Example: migrations/versions/abc123_add_user_sessions.py

"""Add user sessions table

Revision ID: abc123def456
Revises: previous123
Create Date: 2025-11-26 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = 'abc123def456'
down_revision = 'previous123'
branch_labels = None
depends_on = None

def upgrade():
    """Apply migration."""
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_sessions_token', 'user_sessions', ['token'])

def downgrade():
    """Revert migration."""
    op.drop_index('ix_user_sessions_token', 'user_sessions')
    op.drop_table('user_sessions')
```

### Migration Safety Checklist

Before running migrations, verify:

- [ ] **Backup created** - Recent backup exists
- [ ] **Tests passed** - All tests pass in staging
- [ ] **Reversibility** - Downgrade script tested
- [ ] **Data validation** - No data loss expected
- [ ] **Lock analysis** - Migration won't cause long locks
- [ ] **Monitoring ready** - Alerts configured
- [ ] **Rollback plan** - Clear rollback procedure documented

---

## Zero-Downtime Deployment

### Strategy Overview

Zero-downtime deployments require careful sequencing to ensure the database schema supports both the old and new application versions simultaneously.

### Phase 1: Additive Changes

**Goal**: Add new schema elements without removing old ones.

```bash
# Step 1: Create migration for additive changes
alembic revision -m "add_new_feature_columns"

# Step 2: Write upgrade() with only additions
# Example: Add new column with default value
def upgrade():
    op.add_column('users', sa.Column('preferences', sa.JSON(), nullable=True))
    # Set default for existing rows
    op.execute("UPDATE users SET preferences = '{}' WHERE preferences IS NULL")

# Step 3: Apply migration
alembic upgrade head

# Step 4: Deploy new application code
# Application now uses new columns but doesn't require them

# Step 5: Verify application health
./scripts/health_check.sh
```

### Phase 2: Data Migration

**Goal**: Migrate data while both old and new schemas coexist.

```bash
# Create data migration
alembic revision -m "migrate_user_preferences"

def upgrade():
    # Use batch operations for large tables
    from alembic import op
    from sqlalchemy import text

    connection = op.get_bind()

    # Process in batches to avoid locks
    batch_size = 1000
    offset = 0

    while True:
        result = connection.execute(text(
            f"UPDATE users SET new_column = old_column "
            f"WHERE new_column IS NULL "
            f"LIMIT {batch_size} OFFSET {offset}"
        ))

        if result.rowcount == 0:
            break

        offset += batch_size

    # Verify migration
    count = connection.execute(text(
        "SELECT COUNT(*) FROM users WHERE new_column IS NULL AND old_column IS NOT NULL"
    )).scalar()

    if count > 0:
        raise Exception(f"Data migration incomplete: {count} rows remaining")
```

### Phase 3: Cleanup

**Goal**: Remove deprecated schema elements after all instances use new schema.

```bash
# ONLY after all application instances upgraded
alembic revision -m "remove_deprecated_columns"

def upgrade():
    op.drop_column('users', 'old_column')
```

### Blue-Green Deployment Pattern

For maximum safety, use blue-green deployment:

```bash
# Terminal 1: Current production (Blue)
docker-compose -p assistant-blue up -d

# Terminal 2: New version (Green)
docker-compose -p assistant-green up -d

# Run migrations on shared database
alembic upgrade head

# Switch traffic to green
# (Load balancer or DNS change)

# Monitor for issues
./scripts/health_check.sh

# If successful, stop blue
docker-compose -p assistant-blue down

# If issues, switch back to blue and rollback
alembic downgrade -1
```

---

## Backup and Restore Procedures

### Automated Backup

The system includes automated backup scripts:

```bash
# Create immediate backup
./scripts/backup_database.sh

# Expected output:
# [2025-11-26 10:00:00] Creating backup directory: ./data/backups
# [2025-11-26 10:00:01] Backing up database to: assistant_20251126_100001.sql.gz
# [2025-11-26 10:00:05] Backup size: 2.3 MB
# [2025-11-26 10:00:05] Backup completed successfully
# [2025-11-26 10:00:06] Cleaning up old backups (retention: 30 days)
# [2025-11-26 10:00:06] Removed 3 old backups
```

### Manual Backup

For custom backup scenarios:

```bash
# Full database dump
PGPASSWORD=assistant pg_dump \
  -h localhost \
  -p 5433 \
  -U assistant \
  -F c \
  -b \
  -v \
  -f "backup_$(date +%Y%m%d_%H%M%S).dump" \
  assistant

# Expected output:
# pg_dump: saving encoding = UTF8
# pg_dump: saving standard_conforming_strings = on
# pg_dump: creating TABLE "public.users"
# pg_dump: creating INDEX "ix_users_email"
# ...

# Compressed SQL dump (faster, larger)
PGPASSWORD=assistant pg_dump \
  -h localhost \
  -p 5433 \
  -U assistant \
  assistant | gzip > "backup_$(date +%Y%m%d_%H%M%S).sql.gz"

# Schema-only backup
PGPASSWORD=assistant pg_dump \
  -h localhost \
  -p 5433 \
  -U assistant \
  --schema-only \
  assistant > schema_$(date +%Y%m%d_%H%M%S).sql

# Data-only backup
PGPASSWORD=assistant pg_dump \
  -h localhost \
  -p 5433 \
  -U assistant \
  --data-only \
  assistant | gzip > data_$(date +%Y%m%d_%H%M%S).sql.gz

# Specific table backup
PGPASSWORD=assistant pg_dump \
  -h localhost \
  -p 5433 \
  -U assistant \
  -t users \
  assistant > users_backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore Procedures

#### Full Restore

```bash
# Using automated script
./scripts/restore_database.sh data/backups/assistant_20251126_100001.sql.gz

# Expected output:
# [2025-11-26 10:05:00] Starting database restore
# [2025-11-26 10:05:01] Stopping assistant services...
# [2025-11-26 10:05:05] Services stopped
# [2025-11-26 10:05:06] Dropping existing database...
# [2025-11-26 10:05:07] Creating fresh database...
# [2025-11-26 10:05:08] Restoring from: assistant_20251126_100001.sql.gz
# [2025-11-26 10:05:15] Restore completed successfully
# [2025-11-26 10:05:16] Restarting services...
# [2025-11-26 10:05:20] Services restarted
# [2025-11-26 10:05:21] Running health checks...
# [2025-11-26 10:05:25] ✓ All health checks passed
```

#### Manual Restore

```bash
# Stop application
docker-compose down

# Restore from custom format backup
PGPASSWORD=assistant pg_restore \
  -h localhost \
  -p 5433 \
  -U assistant \
  -d assistant \
  -c \
  -v \
  backup_20251126_100001.dump

# Restore from SQL dump
gunzip < backup_20251126_100001.sql.gz | \
PGPASSWORD=assistant psql \
  -h localhost \
  -p 5433 \
  -U assistant \
  -d assistant

# Restart services
docker-compose up -d
```

#### Partial Restore

For restoring specific tables:

```bash
# Restore single table
PGPASSWORD=assistant pg_restore \
  -h localhost \
  -p 5433 \
  -U assistant \
  -d assistant \
  -t users \
  backup_20251126_100001.dump

# Restore with data-only
PGPASSWORD=assistant pg_restore \
  -h localhost \
  -p 5433 \
  -U assistant \
  -d assistant \
  --data-only \
  -t users \
  backup_20251126_100001.dump
```

### Point-in-Time Recovery (PITR)

For production systems, configure continuous archiving:

```bash
# Enable WAL archiving in PostgreSQL config
# In postgresql.conf:
wal_level = replica
archive_mode = on
archive_command = 'cp %p /path/to/archive/%f'

# Create base backup
PGPASSWORD=assistant pg_basebackup \
  -h localhost \
  -p 5433 \
  -U assistant \
  -D /path/to/basebackup \
  -F tar \
  -z \
  -P

# Restore to specific point in time
# Create recovery.conf:
restore_command = 'cp /path/to/archive/%f %p'
recovery_target_time = '2025-11-26 10:00:00'
```

---

## Migration Workflow

### Development Environment

```bash
# 1. Create new migration
alembic revision -m "descriptive_name"

# 2. Edit migration file
vim migrations/versions/abc123_descriptive_name.py

# 3. Test upgrade
alembic upgrade head

# 4. Test downgrade
alembic downgrade -1

# 5. Re-test upgrade
alembic upgrade head

# 6. Commit migration
git add migrations/versions/abc123_descriptive_name.py
git commit -m "Add migration: descriptive_name"
```

### Staging Environment

```bash
# 1. Pull latest code
git pull origin main

# 2. Backup staging database
./scripts/backup_database.sh

# 3. Apply migrations
alembic upgrade head

# 4. Run integration tests
pytest tests/integration/

# 5. Verify data integrity
./scripts/check_migration_health.sh

# Expected output:
# ✓ All tables accessible
# ✓ All indexes present
# ✓ Foreign key constraints valid
# ✓ No orphaned records
# ✓ Data types consistent
```

### Production Environment

**Pre-Migration Checklist:**

```bash
# 1. Verify staging success
echo "Staging migration successful? (yes/no)"
read confirmation

# 2. Create production backup
./scripts/backup_database.sh

# 3. Notify team
echo "Starting production migration at $(date)"

# 4. Enable maintenance mode (if downtime required)
# docker-compose stop

# 5. Apply migrations
alembic upgrade head

# 6. Run health checks
./scripts/health_check.sh

# 7. Disable maintenance mode
# docker-compose up -d

# 8. Monitor for 30 minutes
# Watch logs, metrics, error rates

# 9. Document completion
echo "Migration completed at $(date)" >> migrations/production_log.txt
```

### Rollback Workflow

```bash
# If issues detected within 30 minutes:

# 1. Check current version
alembic current

# 2. Identify target version
alembic history

# 3. Rollback migration
alembic downgrade -1

# 4. Verify rollback
alembic current
./scripts/health_check.sh

# 5. If rollback fails, restore from backup
./scripts/restore_database.sh data/backups/assistant_YYYYMMDD_HHMMSS.sql.gz

# 6. Document incident
cat > migrations/rollback_$(date +%Y%m%d_%H%M%S).md << 'EOF'
# Rollback Report

**Date**: $(date)
**Migration**: abc123_descriptive_name
**Reason**: [Description of issue]
**Resolution**: Rolled back to previous123

## Actions Taken
1. Attempted rollback via alembic downgrade
2. [Additional steps]

## Root Cause
[Analysis of what went wrong]

## Prevention
[Steps to prevent recurrence]
EOF
```

---

## Advanced Scenarios

### Scenario 1: Large Table Alterations

For tables with millions of rows, use these techniques:

#### Method 1: Shadow Table

```python
def upgrade():
    # Create new table with desired schema
    op.create_table(
        'users_new',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('preferences', sa.JSON(), nullable=False),  # New column
    )

    # Copy data in batches
    connection = op.get_bind()
    batch_size = 10000
    offset = 0

    while True:
        result = connection.execute(text(
            f"INSERT INTO users_new (id, email, preferences) "
            f"SELECT id, email, '{{}}' FROM users "
            f"LIMIT {batch_size} OFFSET {offset}"
        ))

        if result.rowcount == 0:
            break
        offset += batch_size

    # Atomic swap
    op.rename_table('users', 'users_old')
    op.rename_table('users_new', 'users')

    # Keep old table for safety, drop later
    # op.drop_table('users_old')
```

#### Method 2: Concurrent Index Creation

```python
def upgrade():
    # Use CONCURRENT to avoid locking
    from sqlalchemy import text
    connection = op.get_bind()

    # Create index without blocking writes
    connection.execute(text(
        'CREATE INDEX CONCURRENTLY ix_users_email ON users (email)'
    ))
```

### Scenario 2: Data Type Changes

```python
def upgrade():
    # Add new column with new type
    op.add_column('users', sa.Column('age_new', sa.Integer()))

    # Migrate data
    op.execute('UPDATE users SET age_new = CAST(age_old AS INTEGER)')

    # Drop old column
    op.drop_column('users', 'age_old')

    # Rename new column
    op.alter_column('users', 'age_new', new_column_name='age')
```

### Scenario 3: Multi-Database Migration

For systems with multiple databases:

```bash
# Define multiple database URLs
export PRIMARY_DB_URL="postgresql://user:pass@host:5433/primary"
export ANALYTICS_DB_URL="postgresql://user:pass@host:5433/analytics"

# Run migrations for each database
alembic -n primary upgrade head
alembic -n analytics upgrade head

# Configure in alembic.ini:
[primary]
sqlalchemy.url = %(PRIMARY_DB_URL)s

[analytics]
sqlalchemy.url = %(ANALYTICS_DB_URL)s
```

### Scenario 4: Tenant Database Migrations

For multi-tenant systems:

```bash
# Script to migrate all tenant databases
for tenant_db in $(psql -t -c "SELECT datname FROM pg_database WHERE datname LIKE 'tenant_%'"); do
    echo "Migrating $tenant_db..."

    export DATABASE_URL="postgresql://user:pass@host:5433/$tenant_db"
    alembic upgrade head

    if [ $? -eq 0 ]; then
        echo "✓ $tenant_db migrated successfully"
    else
        echo "✗ $tenant_db migration failed!"
        exit 1
    fi
done
```

---

## Troubleshooting

### Issue 1: Migration Hangs

**Symptoms**: `alembic upgrade head` hangs indefinitely.

**Cause**: Table locks from other transactions.

**Diagnosis**:

```sql
-- Check for blocking queries
SELECT
    pid,
    usename,
    state,
    query,
    wait_event_type,
    wait_event
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;

-- Check table locks
SELECT
    l.pid,
    l.mode,
    l.granted,
    a.query
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE relation::regclass::text = 'users';
```

**Solution**:

```bash
# Terminate blocking queries (use with caution)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE pid != pg_backend_pid()
AND state != 'idle';

# Or increase lock timeout
export PGCONNECT_TIMEOUT=300
alembic upgrade head
```

### Issue 2: Constraint Violation

**Symptoms**: `IntegrityError: duplicate key value violates unique constraint`.

**Cause**: Data doesn't satisfy new constraint.

**Solution**:

```python
def upgrade():
    # Clean data before adding constraint
    op.execute("""
        DELETE FROM users a USING users b
        WHERE a.id < b.id AND a.email = b.email
    """)

    # Now add constraint
    op.create_unique_constraint('uq_users_email', 'users', ['email'])
```

### Issue 3: Out of Memory

**Symptoms**: `MemoryError` or database crashes during migration.

**Cause**: Batch operation loading too much data.

**Solution**:

```python
def upgrade():
    # Process in smaller batches
    connection = op.get_bind()
    batch_size = 1000

    while True:
        result = connection.execute(text(
            f"UPDATE large_table SET processed = true "
            f"WHERE id IN ("
            f"  SELECT id FROM large_table "
            f"  WHERE processed = false "
            f"  LIMIT {batch_size}"
            f")"
        ))

        if result.rowcount == 0:
            break

        # Commit each batch
        connection.commit()
```

### Issue 4: Version Conflicts

**Symptoms**: `Multiple head revisions are present`.

**Cause**: Branches in migration history.

**Solution**:

```bash
# List branches
alembic branches

# Merge branches
alembic merge -m "merge branches" <rev1> <rev2>

# Apply merged migration
alembic upgrade head
```

### Issue 5: Failed Partial Migration

**Symptoms**: Migration partially applied, database in inconsistent state.

**Solution**:

```bash
# Mark migration as failed
alembic stamp head-1

# Manually fix database
psql -h localhost -p 5433 -U assistant -d assistant << 'EOF'
-- Manually apply or revert changes
DROP TABLE IF EXISTS partially_created_table;
EOF

# Retry migration
alembic upgrade head
```

---

## Appendix

### Migration Best Practices

1. **Always create backups** before migrations
2. **Test in staging** before production
3. **Use transactions** for atomic changes
4. **Avoid long-running migrations** during peak hours
5. **Document migrations** with clear descriptions
6. **Version control** all migration files
7. **Monitor database locks** during migrations
8. **Plan rollback procedures** before executing
9. **Use batch operations** for large data changes
10. **Communicate with team** before production migrations

### Useful SQL Queries

```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('assistant'));

-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan;

-- Check slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;
```

### Migration Templates

**Add Column:**

```python
alembic revision -m "add_column_name"

def upgrade():
    op.add_column('table_name',
        sa.Column('column_name', sa.String(), nullable=True))

def downgrade():
    op.drop_column('table_name', 'column_name')
```

**Add Index:**

```python
alembic revision -m "add_index_name"

def upgrade():
    op.create_index('ix_table_column', 'table_name', ['column_name'])

def downgrade():
    op.drop_index('ix_table_column', 'table_name')
```

**Add Foreign Key:**

```python
alembic revision -m "add_foreign_key"

def upgrade():
    op.create_foreign_key(
        'fk_child_parent_id',
        'child_table', 'parent_table',
        ['parent_id'], ['id']
    )

def downgrade():
    op.drop_constraint('fk_child_parent_id', 'child_table')
```

---

**End of Migration Guide**
