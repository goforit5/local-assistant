#!/bin/bash
#
# Database Backup Script for Local Assistant (Life Graph Integration)
#
# Purpose:
#   Create a timestamped backup of the PostgreSQL database
#   Saves to data/backups/ directory with automatic retention policy
#
# Usage:
#   ./scripts/backup_database.sh
#
# Environment Variables:
#   DATABASE_URL - PostgreSQL connection string (default: postgresql://assistant:assistant@localhost:5433/assistant)
#   BACKUP_DIR - Backup directory (default: ./data/backups)
#   BACKUP_RETENTION_DAYS - How many days to keep backups (default: 30)
#

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# ========== Configuration ==========

# Get database connection details from environment or use defaults
DB_URL="${DATABASE_URL:-postgresql://assistant:assistant@localhost:5433/assistant}"

# Parse DATABASE_URL into components
# Format: postgresql://user:password@host:port/database
DB_USER=$(echo "$DB_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASSWORD=$(echo "$DB_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DB_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DB_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DB_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

# Backup configuration
BACKUP_DIR="${BACKUP_DIR:-./data/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/assistant_${TIMESTAMP}.sql.gz"

# ========== Functions ==========

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

# ========== Main Script ==========

log "Starting database backup..."
log "Database: ${DB_NAME} on ${DB_HOST}:${DB_PORT}"

# Create backup directory if it doesn't exist
if [ ! -d "$BACKUP_DIR" ]; then
    log "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
fi

# Check if pg_dump is available
if ! command -v pg_dump &> /dev/null; then
    error "pg_dump command not found. Please install PostgreSQL client tools."
    exit 1
fi

# Perform backup using pg_dump
# Options:
#   --clean: Add DROP commands before CREATE (clean restore)
#   --if-exists: Use IF EXISTS when dropping objects
#   --create: Include CREATE DATABASE command
#   --verbose: Show detailed progress
#   --format=custom: Use PostgreSQL custom format (faster restore, supports parallel restore)
log "Running pg_dump to ${BACKUP_FILE}..."

export PGPASSWORD="$DB_PASSWORD"

if pg_dump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --clean \
    --if-exists \
    --create \
    --verbose \
    --format=custom \
    --file="${BACKUP_FILE%.gz}" 2>&1 | tee -a "${BACKUP_DIR}/backup.log"; then

    # Compress the backup
    log "Compressing backup..."
    gzip -f "${BACKUP_FILE%.gz}"

    # Get backup file size
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup completed successfully: $BACKUP_FILE (${BACKUP_SIZE})"

else
    error "Backup failed. Check ${BACKUP_DIR}/backup.log for details."
    unset PGPASSWORD
    exit 1
fi

unset PGPASSWORD

# ========== Cleanup Old Backups ==========

log "Cleaning up backups older than ${BACKUP_RETENTION_DAYS} days..."

# Find and delete backups older than retention period
DELETED_COUNT=$(find "$BACKUP_DIR" -name "assistant_*.sql.gz" -type f -mtime +${BACKUP_RETENTION_DAYS} -delete -print | wc -l)

if [ "$DELETED_COUNT" -gt 0 ]; then
    log "Deleted ${DELETED_COUNT} old backup(s)"
else
    log "No old backups to delete"
fi

# ========== Summary ==========

log "Backup summary:"
log "  Backup file: $BACKUP_FILE"
log "  Backup size: ${BACKUP_SIZE}"
log "  Retention: ${BACKUP_RETENTION_DAYS} days"
log "  Total backups: $(find "$BACKUP_DIR" -name "assistant_*.sql.gz" -type f | wc -l)"

log "Database backup completed successfully!"

# ========== Example Usage ==========
#
# # Basic backup with defaults
# ./scripts/backup_database.sh
#
# # Backup with custom retention
# BACKUP_RETENTION_DAYS=7 ./scripts/backup_database.sh
#
# # Backup to custom directory
# BACKUP_DIR=/mnt/backups ./scripts/backup_database.sh
#
# # List all backups
# ls -lh ./data/backups/assistant_*.sql.gz
#
# # Restore from backup
# ./scripts/restore_database.sh ./data/backups/assistant_20251106_120000.sql.gz
