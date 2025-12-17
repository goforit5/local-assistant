#!/bin/bash
#
# Health Check Script for Local Assistant
#
# Purpose:
#   Comprehensive health check for all services in the Local Assistant stack
#   - Verifies Docker services are running and healthy
#   - Tests database connectivity and query execution
#   - Validates Redis cache functionality
#   - Checks ChromaDB vector store accessibility
#   - Tests observability stack (Prometheus, Grafana)
#   - Verifies API endpoints (if application is running)
#
# Usage:
#   ./scripts/health_check.sh
#
# Exit Codes:
#   0 - All checks passed
#   1 - One or more checks failed
#
# Environment Variables:
#   DATABASE_URL - PostgreSQL connection string (default: postgresql://assistant:assistant@localhost:5433/assistant)
#   REDIS_URL - Redis connection string (default: redis://localhost:6380/0)
#   CHROMA_HOST - ChromaDB host (default: localhost)
#   CHROMA_PORT - ChromaDB port (default: 8002)
#   PROMETHEUS_PORT - Prometheus port (default: 9091)
#   GRAFANA_PORT - Grafana port (default: 3001)
#

set -u  # Exit on undefined variables (but not on errors, we want to report them)

# ========== Configuration ==========

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Service configuration
DB_URL="${DATABASE_URL:-postgresql://assistant:assistant@localhost:5433/assistant}"
REDIS_HOST="${REDIS_URL:-redis://localhost:6380/0}"
CHROMA_HOST="${CHROMA_HOST:-localhost}"
CHROMA_PORT="${CHROMA_PORT:-8002}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9091}"
GRAFANA_PORT="${GRAFANA_PORT:-3001}"

# Parse DATABASE_URL
DB_USER=$(echo "$DB_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASSWORD=$(echo "$DB_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DB_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DB_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DB_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

# Parse REDIS_URL
REDIS_PARSED_HOST=$(echo "$REDIS_HOST" | sed -n 's|redis://\([^:]*\):.*|\1|p')
REDIS_PORT=$(echo "$REDIS_HOST" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')

# Exit code tracker
EXIT_CODE=0

# ========== Helper Functions ==========

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

success() {
    echo "✓ $1"
}

error() {
    echo "✗ $1"
    EXIT_CODE=1
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        error "Required command '$1' not found. Please install it."
        exit 1
    fi
}

measure_time() {
    local start=$1
    local end=$2
    echo $((end - start))
}

# ========== Dependency Checks ==========

check_dependencies() {
    log "Checking required dependencies..."

    local missing_deps=0

    # Check for required commands
    for cmd in docker curl psql redis-cli; do
        if ! command -v "$cmd" &> /dev/null; then
            error "Required command '$cmd' not found"
            missing_deps=1
        fi
    done

    if [ $missing_deps -eq 1 ]; then
        echo ""
        echo "Please install missing dependencies:"
        echo "  - docker: https://docs.docker.com/get-docker/"
        echo "  - curl: Usually pre-installed or via package manager"
        echo "  - psql: Install postgresql-client"
        echo "  - redis-cli: Install redis-tools"
        exit 1
    fi

    success "All dependencies present"
}

# ========== Docker Service Checks ==========

check_docker_services() {
    echo ""
    log "Checking Docker services..."

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running"
        return
    fi
    success "Docker daemon is running"

    # Define services to check
    local services=(
        "assistant-postgres:PostgreSQL"
        "assistant-redis:Redis"
        "assistant-chroma:ChromaDB"
        "assistant-prometheus:Prometheus"
        "assistant-grafana:Grafana"
    )

    for service_def in "${services[@]}"; do
        local container_name="${service_def%%:*}"
        local service_name="${service_def##*:}"

        # Check if container exists and is running
        if ! docker ps --filter "name=${container_name}" --filter "status=running" | grep -q "${container_name}"; then
            error "${service_name} container (${container_name}) is not running"
            continue
        fi

        # Check health status
        local health_status=$(docker inspect --format='{{.State.Health.Status}}' "${container_name}" 2>/dev/null || echo "none")

        if [ "$health_status" = "healthy" ]; then
            # Measure response time for healthy services
            local start=$(date +%s%3N)
            docker exec "${container_name}" echo "ping" &> /dev/null
            local end=$(date +%s%3N)
            local response_time=$((end - start))
            success "${service_name} is healthy (response time: ${response_time}ms)"
        elif [ "$health_status" = "none" ]; then
            # No health check defined, just check if running
            success "${service_name} is running (no health check defined)"
        else
            error "${service_name} health status: ${health_status}"
        fi
    done

    # Check optional Jaeger service (might not be running)
    if docker ps --filter "name=assistant-jaeger" --filter "status=running" | grep -q "assistant-jaeger"; then
        success "Jaeger (optional) is running"
    fi
}

# ========== Database Connectivity Checks ==========

check_database() {
    echo ""
    log "Checking database connectivity..."

    # Test connection via Docker
    if docker exec assistant-postgres pg_isready -U "${DB_USER}" &> /dev/null; then
        success "Database accepts connections (via Docker)"
    else
        error "Database not accepting connections (via Docker)"
    fi

    # Test connection via external port
    local start=$(date +%s%3N)
    if PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1;" &> /dev/null; then
        local end=$(date +%s%3N)
        local query_time=$((end - start))
        success "Database connection successful (query time: ${query_time}ms)"
    else
        error "Cannot connect to database at ${DB_HOST}:${DB_PORT}"
        return
    fi

    # Count tables
    local table_count=$(PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')

    if [ -n "$table_count" ] && [ "$table_count" -gt 0 ]; then
        success "Can execute queries (${table_count} tables found)"
    else
        error "Cannot execute queries or no tables found"
    fi

    # Check migration status
    local migration_version=$(PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1;" 2>/dev/null | tr -d ' ')

    if [ -n "$migration_version" ]; then
        success "Database migrations current (version: ${migration_version})"
    else
        error "Cannot read migration version (alembic_version table missing?)"
    fi
}

# ========== Redis Checks ==========

check_redis() {
    echo ""
    log "Checking Redis connectivity..."

    # Test connection via Docker
    if docker exec assistant-redis redis-cli ping | grep -q "PONG"; then
        success "Redis responds to PING (via Docker)"
    else
        error "Redis not responding (via Docker)"
    fi

    # Test connection via external port
    local start=$(date +%s%3N)
    if redis-cli -h "${REDIS_PARSED_HOST}" -p "${REDIS_PORT}" ping | grep -q "PONG"; then
        local end=$(date +%s%3N)
        local ping_time=$((end - start))
        success "Redis connection successful (ping time: ${ping_time}ms)"
    else
        error "Cannot connect to Redis at ${REDIS_PARSED_HOST}:${REDIS_PORT}"
        return
    fi

    # Test write/read operation
    local test_key="health_check_$(date +%s)"
    local test_value="ok"

    if redis-cli -h "${REDIS_PARSED_HOST}" -p "${REDIS_PORT}" SET "$test_key" "$test_value" EX 10 &> /dev/null; then
        local retrieved_value=$(redis-cli -h "${REDIS_PARSED_HOST}" -p "${REDIS_PORT}" GET "$test_key" 2>/dev/null)
        if [ "$retrieved_value" = "$test_value" ]; then
            success "Redis read/write operations working"
            redis-cli -h "${REDIS_PARSED_HOST}" -p "${REDIS_PORT}" DEL "$test_key" &> /dev/null
        else
            error "Redis write succeeded but read failed"
        fi
    else
        error "Cannot write to Redis"
    fi

    # Check memory usage
    local memory_used=$(redis-cli -h "${REDIS_PARSED_HOST}" -p "${REDIS_PORT}" INFO memory | grep "used_memory_human:" | cut -d: -f2 | tr -d '\r')
    if [ -n "$memory_used" ]; then
        success "Redis memory usage: ${memory_used}"
    fi
}

# ========== ChromaDB Checks ==========

check_chromadb() {
    echo ""
    log "Checking ChromaDB connectivity..."

    # Test heartbeat endpoint
    local start=$(date +%s%3N)
    if curl -f -s -m 5 "http://${CHROMA_HOST}:${CHROMA_PORT}/api/v1/heartbeat" > /dev/null 2>&1; then
        local end=$(date +%s%3N)
        local response_time=$((end - start))
        success "ChromaDB heartbeat successful (response time: ${response_time}ms)"
    else
        error "ChromaDB heartbeat failed at ${CHROMA_HOST}:${CHROMA_PORT}"
        return
    fi

    # List collections
    local collections=$(curl -s -m 5 "http://${CHROMA_HOST}:${CHROMA_PORT}/api/v1/collections" 2>/dev/null)
    if [ -n "$collections" ]; then
        local collection_count=$(echo "$collections" | grep -o '"name"' | wc -l | tr -d ' ')
        success "ChromaDB API accessible (${collection_count} collections)"
    else
        error "Cannot access ChromaDB collections API"
    fi

    # Check version
    local version=$(curl -s -m 5 "http://${CHROMA_HOST}:${CHROMA_PORT}/api/v1/version" 2>/dev/null)
    if [ -n "$version" ]; then
        success "ChromaDB version: ${version}"
    fi
}

# ========== Prometheus Checks ==========

check_prometheus() {
    echo ""
    log "Checking Prometheus..."

    # Test API endpoint
    local start=$(date +%s%3N)
    if curl -f -s -m 5 "http://localhost:${PROMETHEUS_PORT}/api/v1/query?query=up" > /dev/null 2>&1; then
        local end=$(date +%s%3N)
        local response_time=$((end - start))
        success "Prometheus API accessible (response time: ${response_time}ms)"
    else
        error "Prometheus API not accessible at localhost:${PROMETHEUS_PORT}"
        return
    fi

    # Check targets
    local targets=$(curl -s -m 5 "http://localhost:${PROMETHEUS_PORT}/api/v1/targets" 2>/dev/null)
    if [ -n "$targets" ]; then
        local active_targets=$(echo "$targets" | grep -o '"health":"up"' | wc -l | tr -d ' ')
        local total_targets=$(echo "$targets" | grep -o '"health"' | wc -l | tr -d ' ')
        success "Prometheus targets: ${active_targets}/${total_targets} up"
    else
        error "Cannot query Prometheus targets"
    fi
}

# ========== Grafana Checks ==========

check_grafana() {
    echo ""
    log "Checking Grafana..."

    # Test health endpoint
    local start=$(date +%s%3N)
    if curl -f -s -m 5 "http://localhost:${GRAFANA_PORT}/api/health" > /dev/null 2>&1; then
        local end=$(date +%s%3N)
        local response_time=$((end - start))
        success "Grafana health check passed (response time: ${response_time}ms)"
    else
        error "Grafana health check failed at localhost:${GRAFANA_PORT}"
        return
    fi

    # Check datasources (requires auth, optional)
    local datasources=$(curl -s -u admin:admin -m 5 "http://localhost:${GRAFANA_PORT}/api/datasources" 2>/dev/null)
    if [ -n "$datasources" ]; then
        local ds_count=$(echo "$datasources" | grep -o '"name"' | wc -l | tr -d ' ')
        success "Grafana datasources configured: ${ds_count}"
    fi
}

# ========== API Endpoint Checks (Optional) ==========

check_api_endpoints() {
    echo ""
    log "Checking API endpoints (if running)..."

    # Common API ports to check
    local api_ports=(8080 8000 5000 3000)
    local api_found=0

    for port in "${api_ports[@]}"; do
        if curl -f -s -m 2 "http://localhost:${port}/health" > /dev/null 2>&1; then
            success "API health endpoint accessible at localhost:${port}"
            api_found=1

            # Try to get version
            local version=$(curl -s -m 2 "http://localhost:${port}/version" 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
            if [ -n "$version" ]; then
                success "API version: ${version}"
            fi

            break
        fi
    done

    if [ $api_found -eq 0 ]; then
        echo "ℹ API endpoints not found (application may not be running)"
    fi
}

# ========== System Resource Checks ==========

check_system_resources() {
    echo ""
    log "Checking system resources..."

    # Check disk space
    local disk_usage=$(df -h ./data 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')
    if [ -n "$disk_usage" ]; then
        if [ "$disk_usage" -lt 80 ]; then
            success "Disk usage: ${disk_usage}% (healthy)"
        elif [ "$disk_usage" -lt 90 ]; then
            echo "⚠ Disk usage: ${disk_usage}% (warning)"
        else
            error "Disk usage: ${disk_usage}% (critical)"
        fi
    fi

    # Check Docker disk usage
    local docker_images=$(docker images -q | wc -l | tr -d ' ')
    local docker_containers=$(docker ps -aq | wc -l | tr -d ' ')
    success "Docker resources: ${docker_images} images, ${docker_containers} containers"

    # Check for stopped containers that should be running
    local stopped_containers=$(docker ps -a --filter "name=assistant-" --filter "status=exited" --format "{{.Names}}" | wc -l | tr -d ' ')
    if [ "$stopped_containers" -gt 0 ]; then
        error "${stopped_containers} assistant containers are stopped"
    fi
}

# ========== Main Execution ==========

main() {
    echo "================================"
    echo "Local Assistant Health Check"
    echo "================================"
    echo ""
    echo "Timestamp: $(date +'%Y-%m-%d %H:%M:%S')"
    echo ""

    # Run all checks
    check_dependencies
    check_docker_services
    check_database
    check_redis
    check_chromadb
    check_prometheus
    check_grafana
    check_api_endpoints
    check_system_resources

    # Summary
    echo ""
    echo "================================"
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✓ All checks passed!"
        echo "================================"
    else
        echo "✗ Some checks failed!"
        echo "================================"
        echo ""
        echo "Please review the errors above and take corrective action."
        echo "See DEPLOYMENT_RUNBOOK.md for troubleshooting guidance."
    fi
    echo ""

    exit $EXIT_CODE
}

# Run main function
main "$@"
