#!/bin/bash
#
# Database Restore Script for Local Assistant (Life Graph Integration)
#
# Purpose:
#   Restore PostgreSQL database from a backup file created by backup_database.sh
#   CAUTION: This will DROP the existing database and recreate it from backup!
#
# Usage:
#   ./scripts/restore_database.sh <backup_file>
#
# Example:
#   ./scripts/restore_database.sh ./data/backups/assistant_20251106_120000.sql.gz
#
# Environment Variables:
#   DATABASE_URL - PostgreSQL connection string (default: postgresql://assistant:assistant@localhost:5433/assistant)
#

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# ========== Configuration ==========

# Check if backup file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Example:"
    echo "  $0 ./data/backups/assistant_20251106_120000.sql.gz"
    echo ""
    echo "Available backups:"
    ls -lh ./data/backups/assistant_*.sql.gz 2>/dev/null || echo "  No backups found in ./data/backups/"
    exit 1
fi

BACKUP_FILE="$1"

# Get database connection details from environment or use defaults
DB_URL="${DATABASE_URL:-postgresql://assistant:assistant@localhost:5433/assistant}"

# Parse DATABASE_URL into components
DB_USER=$(echo "$DB_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASSWORD=$(echo "$DB_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DB_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DB_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DB_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

# ========== Functions ==========

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

confirm() {
    read -p "$1 [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        return 1
    fi
    return 0
}

# ========== Validation ==========

log "Starting database restore..."
log "Database: ${DB_NAME} on ${DB_HOST}:${DB_PORT}"
log "Backup file: ${BACKUP_FILE}"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Check if pg_restore is available
if ! command -v pg_restore &> /dev/null; then
    error "pg_restore command not found. Please install PostgreSQL client tools."
    exit 1
fi

# Get backup file info
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Backup file size: ${BACKUP_SIZE}"

# ========== Confirmation ==========

echo ""
echo "⚠️  WARNING: This will DESTROY the existing database and restore from backup!"
echo ""
echo "Database to restore: ${DB_NAME}"
echo "Backup file: ${BACKUP_FILE}"
echo "Backup size: ${BACKUP_SIZE}"
echo ""

if ! confirm "Are you sure you want to restore from this backup?"; then
    log "Restore cancelled by user."
    exit 0
fi

# ========== Pre-Restore Backup (Safety) ==========

log "Creating safety backup of current database before restore..."

SAFETY_BACKUP_DIR="./data/backups/pre_restore"
mkdir -p "$SAFETY_BACKUP_DIR"

SAFETY_BACKUP="${SAFETY_BACKUP_DIR}/assistant_pre_restore_$(date +%Y%m%d_%H%M%S).sql.gz"

export PGPASSWORD="$DB_PASSWORD"

if pg_dump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --format=custom \
    --file="${SAFETY_BACKUP%.gz}" 2>&1 | grep -v "NOTICE" || true; then

    gzip -f "${SAFETY_BACKUP%.gz}"
    log "Safety backup created: $SAFETY_BACKUP"
else
    error "Failed to create safety backup. Aborting restore."
    unset PGPASSWORD
    exit 1
fi

# ========== Restore Process ==========

log "Decompressing backup file..."

# Decompress backup if it's gzipped
if [[ "$BACKUP_FILE" == *.gz ]]; then
    DECOMPRESSED_FILE="${BACKUP_FILE%.gz}"
    gunzip -c "$BACKUP_FILE" > "$DECOMPRESSED_FILE"
else
    DECOMPRESSED_FILE="$BACKUP_FILE"
fi

log "Restoring database from backup..."

# Drop all connections to the database
log "Terminating active connections to database..."
psql \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="postgres" \
    --command="SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '${DB_NAME}' AND pid <> pg_backend_pid();" \
    2>&1 | grep -v "NOTICE" || true

# Restore using pg_restore
# Options:
#   --clean: Drop database objects before recreating (from backup --clean option)
#   --if-exists: Use IF EXISTS when dropping (from backup --if-exists option)
#   --create: Create the database (from backup --create option)
#   --verbose: Show detailed progress
#   --no-owner: Skip restoration of ownership (use current user)
#   --no-acl: Skip restoration of access privileges

if pg_restore \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="postgres" \
    --clean \
    --if-exists \
    --create \
    --verbose \
    --no-owner \
    --no-acl \
    "$DECOMPRESSED_FILE" 2>&1 | tee -a "${SAFETY_BACKUP_DIR}/restore.log"; then

    log "Database restored successfully!"

else
    error "Restore failed. Check ${SAFETY_BACKUP_DIR}/restore.log for details."
    error "You can restore the pre-restore backup from: $SAFETY_BACKUP"
    unset PGPASSWORD

    # Cleanup decompressed file if we created it
    if [[ "$BACKUP_FILE" == *.gz ]]; then
        rm -f "$DECOMPRESSED_FILE"
    fi

    exit 1
fi

unset PGPASSWORD

# Cleanup decompressed file if we created it
if [[ "$BACKUP_FILE" == *.gz ]]; then
    rm -f "$DECOMPRESSED_FILE"
fi

# ========== Verification ==========

log "Verifying database restore..."

export PGPASSWORD="$DB_PASSWORD"

# Check if database exists
if psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --command="\dt" &> /dev/null; then
    log "Database connection successful"

    # Count tables
    TABLE_COUNT=$(psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --tuples-only --command="SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
    log "Tables in database: ${TABLE_COUNT}"

    # Check Alembic version
    ALEMBIC_VERSION=$(psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --tuples-only --command="SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | tr -d ' ' || echo "none")
    log "Alembic migration version: ${ALEMBIC_VERSION}"

else
    error "Database connection failed after restore"
    unset PGPASSWORD
    exit 1
fi

unset PGPASSWORD

# ========== Summary ==========

log "Restore summary:"
log "  Restored from: $BACKUP_FILE"
log "  Backup size: ${BACKUP_SIZE}"
log "  Safety backup: $SAFETY_BACKUP"
log "  Tables restored: ${TABLE_COUNT}"
log "  Migration version: ${ALEMBIC_VERSION}"

log "Database restore completed successfully!"

# ========== Example Usage ==========
#
# # Restore from specific backup
# ./scripts/restore_database.sh ./data/backups/assistant_20251106_120000.sql.gz
#
# # List available backups
# ls -lh ./data/backups/assistant_*.sql.gz
#
# # After restore, check migration status
# alembic current
#
# # If needed, run migrations
# alembic upgrade head
