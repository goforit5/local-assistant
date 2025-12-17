#!/bin/bash
#
# Database Migration Health Check Script for Local Assistant
#
# Purpose:
#   Verify that database migrations are in sync with the codebase
#   Check for pending migrations, missing tables, and schema drift
#
# Usage:
#   ./scripts/check_migration_health.sh
#
# Exit Codes:
#   0 - All checks passed
#   1 - Health check failed
#

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# ========== Configuration ==========

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
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ❌ ERROR: $1" >&2
}

success() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1"
}

warning() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  WARNING: $1"
}

# ========== Health Checks ==========

FAILED_CHECKS=0

log "Starting migration health check..."
log "Database: ${DB_NAME} on ${DB_HOST}:${DB_PORT}"
echo ""

# ========== Check 1: Database Connection ==========

log "Check 1/7: Database connection..."

export PGPASSWORD="$DB_PASSWORD"

if psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --command="SELECT 1;" &> /dev/null; then
    success "Database connection successful"
else
    error "Cannot connect to database: ${DB_NAME}"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

# ========== Check 2: Alembic Version Table ==========

log "Check 2/7: Alembic version table..."

if psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --tuples-only --command="SELECT version_num FROM alembic_version LIMIT 1;" &> /dev/null; then
    CURRENT_VERSION=$(psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --tuples-only --command="SELECT version_num FROM alembic_version LIMIT 1;" | tr -d ' ')
    success "Alembic version table exists. Current version: ${CURRENT_VERSION}"
else
    error "Alembic version table not found. Run 'alembic upgrade head' to initialize."
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

# ========== Check 3: Required Extensions ==========

log "Check 3/7: PostgreSQL extensions..."

REQUIRED_EXTENSIONS=("pgcrypto" "pg_trgm" "btree_gist")
MISSING_EXTENSIONS=()

for ext in "${REQUIRED_EXTENSIONS[@]}"; do
    if psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --tuples-only --command="SELECT 1 FROM pg_extension WHERE extname = '${ext}';" | grep -q 1; then
        success "  Extension '${ext}' is installed"
    else
        error "  Extension '${ext}' is missing"
        MISSING_EXTENSIONS+=("$ext")
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
done

if [ ${#MISSING_EXTENSIONS[@]} -gt 0 ]; then
    echo "  Missing extensions: ${MISSING_EXTENSIONS[*]}"
    echo "  Run: alembic upgrade 001 (or upgrade head)"
fi

# ========== Check 4: Required Tables ==========

log "Check 4/7: Required tables..."

REQUIRED_TABLES=(
    "alembic_version"
    "parties"
    "roles"
    "commitments"
    "documents"
    "signals"
    "document_links"
    "interactions"
)

MISSING_TABLES=()

for table in "${REQUIRED_TABLES[@]}"; do
    if psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --tuples-only --command="SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '${table}';" | grep -q 1; then
        success "  Table '${table}' exists"
    else
        error "  Table '${table}' is missing"
        MISSING_TABLES+=("$table")
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
done

if [ ${#MISSING_TABLES[@]} -gt 0 ]; then
    echo "  Missing tables: ${MISSING_TABLES[*]}"
    echo "  Run: alembic upgrade head"
fi

# ========== Check 5: Required Columns (documents table enhancements) ==========

log "Check 5/7: Documents table enhancements..."

REQUIRED_COLUMNS=(
    "sha256"
    "source"
    "mime_type"
    "file_size"
    "storage_uri"
    "extraction_type"
    "extraction_data"
    "extraction_cost"
    "extracted_at"
)

MISSING_COLUMNS=()

if psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --tuples-only --command="SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'documents';" | grep -q 1; then
    for column in "${REQUIRED_COLUMNS[@]}"; do
        if psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --tuples-only --command="SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'documents' AND column_name = '${column}';" | grep -q 1; then
            success "  Column 'documents.${column}' exists"
        else
            error "  Column 'documents.${column}' is missing"
            MISSING_COLUMNS+=("$column")
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
        fi
    done

    if [ ${#MISSING_COLUMNS[@]} -gt 0 ]; then
        echo "  Missing columns: ${MISSING_COLUMNS[*]}"
        echo "  Run: alembic upgrade 003 (or upgrade head)"
    fi
else
    warning "  Documents table does not exist, skipping column check"
fi

# ========== Check 6: Required Indexes ==========

log "Check 6/7: Critical indexes..."

REQUIRED_INDEXES=(
    "idx_parties_name_trigram"
    "idx_signals_dedupe_key_unique"
    "idx_documents_sha256_unique"
    "idx_commitments_state_due_date"
)

MISSING_INDEXES=()

for index in "${REQUIRED_INDEXES[@]}"; do
    if psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --tuples-only --command="SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = '${index}';" | grep -q 1; then
        success "  Index '${index}' exists"
    else
        error "  Index '${index}' is missing"
        MISSING_INDEXES+=("$index")
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
done

if [ ${#MISSING_INDEXES[@]} -gt 0 ]; then
    echo "  Missing indexes: ${MISSING_INDEXES[*]}"
    echo "  Run: alembic upgrade head"
fi

# ========== Check 7: Pending Migrations ==========

log "Check 7/7: Pending migrations..."

# Check if alembic command is available
if ! command -v alembic &> /dev/null; then
    warning "Alembic command not found, skipping pending migration check"
else
    # Get current version from Alembic
    ALEMBIC_CURRENT=$(alembic current 2>/dev/null | grep -oP '\(head\)' || echo "")

    if [ -n "$ALEMBIC_CURRENT" ]; then
        success "Database is up to date with latest migrations (at head)"
    else
        warning "Database may have pending migrations"
        echo "  Current version: $(alembic current 2>/dev/null || echo 'unknown')"
        echo "  Run: alembic upgrade head"
        # Don't fail on this - it's just a warning
    fi
fi

unset PGPASSWORD

# ========== Summary ==========

echo ""
log "Health check summary:"
echo "  Database: ${DB_NAME}"
echo "  Current migration: ${CURRENT_VERSION:-unknown}"
echo "  Failed checks: ${FAILED_CHECKS}"

if [ $FAILED_CHECKS -eq 0 ]; then
    echo ""
    success "All health checks passed! Database is healthy. ✅"
    exit 0
else
    echo ""
    error "Health check failed with ${FAILED_CHECKS} error(s). ❌"
    echo ""
    echo "Recommended actions:"
    echo "  1. Run: alembic upgrade head"
    echo "  2. If that fails, check migration files in migrations/versions/"
    echo "  3. If database is corrupted, restore from backup: ./scripts/restore_database.sh <backup_file>"
    exit 1
fi

# ========== Example Usage ==========
#
# # Run health check
# ./scripts/check_migration_health.sh
#
# # Run health check in CI/CD
# if ./scripts/check_migration_health.sh; then
#     echo "Database is healthy, deploying..."
# else
#     echo "Database health check failed, aborting deployment"
#     exit 1
# fi
#
# # Run health check before backup
# ./scripts/check_migration_health.sh && ./scripts/backup_database.sh
