# Testing Strategy: Life Graph Integration
**Version**: 1.0.0
**Date**: 2025-11-06
**Author**: AI Development Team
**Status**: Planning Phase

---

## Table of Contents
1. [Testing Philosophy](#testing-philosophy)
2. [Test Pyramid](#test-pyramid)
3. [Unit Testing](#unit-testing)
4. [Integration Testing](#integration-testing)
5. [End-to-End Testing](#end-to-end-testing)
6. [Performance Testing](#performance-testing)
7. [Security Testing](#security-testing)
8. [Test Data Management](#test-data-management)
9. [CI/CD Integration](#cicd-integration)
10. [Coverage Requirements](#coverage-requirements)

---

## Testing Philosophy

### Core Principles
1. **Test Behavior, Not Implementation**: Focus on public APIs and contracts
2. **Fast Feedback Loop**: Unit tests run in < 5s, full suite in < 2min
3. **Deterministic**: No flaky tests, use fixtures for time/randomness
4. **Isolated**: Tests don't depend on each other or external state
5. **Readable**: Test names describe what they test and why
6. **Maintainable**: DRY fixtures, clear arrange-act-assert pattern

### Testing Pyramid (FAANG Standard)
```
       /\
      /E2E\      10% - End-to-End (slow, brittle, high value)
     /------\
    /Integr.\   20% - Integration (medium speed, medium value)
   /----------\
  /   Unit     \ 70% - Unit (fast, reliable, foundational)
 /--------------\
```

**Why This Distribution?**
- **70% Unit**: Fast, isolated, test business logic exhaustively
- **20% Integration**: Verify components work together (DB, API, services)
- **10% E2E**: Validate critical user journeys end-to-end

---

## Test Pyramid

### 1. Unit Tests (70% of tests)

**Purpose**: Test individual functions, classes, methods in isolation

**Target Coverage**: 90%+ for:
- Service layer (`api/services/`)
- Business logic (`api/core/`)
- Utility functions (`api/utils/`)
- Pydantic models (`api/models/`)

**Technologies**:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking/patching
- `hypothesis` - Property-based testing
- `faker` - Test data generation

**File Naming Convention**:
```
tests/unit/
├── services/
│   ├── test_document_storage_service.py
│   ├── test_entity_resolver_service.py
│   └── test_commitment_manager_service.py
├── core/
│   ├── test_priority_calculator.py
│   └── test_fuzzy_matcher.py
├── models/
│   ├── test_document_models.py
│   └── test_party_models.py
└── utils/
    ├── test_hash_utils.py
    └── test_config_loader.py
```

**Example Test Structure**:
```python
"""Unit tests for EntityResolverService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from api.services.entity_resolver import EntityResolverService
from api.models.party import Party


class TestEntityResolverService:
    """Test suite for entity resolution service."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def resolver_service(self, mock_db_session):
        """Create EntityResolverService instance."""
        return EntityResolverService(session=mock_db_session)

    @pytest.mark.asyncio
    async def test_resolve_vendor_exact_match(self, resolver_service, mock_db_session):
        """Test exact match resolution returns existing vendor."""
        # Arrange
        existing_vendor = Party(
            party_id="party_123",
            name="Clipboard Health",
            legal_name="Twomagnets Inc.",
            tax_id="12-3456789"
        )
        mock_db_session.execute = AsyncMock(
            return_value=MagicMock(scalars=lambda: MagicMock(first=lambda: existing_vendor))
        )

        # Act
        result = await resolver_service.resolve_vendor(
            name="Clipboard Health",
            legal_name="Twomagnets Inc.",
            tax_id="12-3456789"
        )

        # Assert
        assert result.action == "matched"
        assert result.party_id == "party_123"
        assert result.confidence_score == 1.0
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_vendor_fuzzy_match_high_confidence(self, resolver_service):
        """Test fuzzy match with >90% confidence returns existing vendor."""
        # Arrange
        with patch.object(resolver_service, '_fuzzy_search_parties') as mock_fuzzy:
            mock_fuzzy.return_value = [
                {
                    "party_id": "party_456",
                    "name": "Clipboard Hlth",
                    "confidence_score": 0.92
                }
            ]

        # Act
        result = await resolver_service.resolve_vendor(
            name="Clipboard Health",
            similarity_threshold=0.90
        )

        # Assert
        assert result.action == "matched"
        assert result.confidence_score == 0.92

    @pytest.mark.asyncio
    async def test_resolve_vendor_no_match_creates_new(self, resolver_service, mock_db_session):
        """Test no match creates new vendor."""
        # Arrange
        mock_db_session.execute = AsyncMock(
            return_value=MagicMock(scalars=lambda: MagicMock(first=lambda: None))
        )

        # Act
        result = await resolver_service.resolve_vendor(
            name="New Vendor Inc",
            party_type="vendor"
        )

        # Assert
        assert result.action == "created"
        assert result.party_id is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_vendor_database_error_raises(self, resolver_service, mock_db_session):
        """Test database error is properly raised."""
        # Arrange
        mock_db_session.execute = AsyncMock(side_effect=Exception("DB Error"))

        # Act & Assert
        with pytest.raises(Exception, match="DB Error"):
            await resolver_service.resolve_vendor(name="Test")
```

**Property-Based Testing Example** (using Hypothesis):
```python
from hypothesis import given, strategies as st
from api.core.priority_calculator import calculate_priority


class TestPriorityCalculator:
    """Property-based tests for priority calculation."""

    @given(
        days_until_due=st.integers(min_value=0, max_value=365),
        amount=st.floats(min_value=0, max_value=1_000_000)
    )
    def test_priority_always_between_0_and_100(self, days_until_due, amount):
        """Priority score must always be in [0, 100] range."""
        priority = calculate_priority(
            commitment_type="obligation",
            days_until_due=days_until_due,
            amount=amount
        )
        assert 0 <= priority <= 100

    @given(
        days_until_due=st.integers(min_value=1, max_value=365)
    )
    def test_priority_decreases_with_time(self, days_until_due):
        """Priority should decrease as due date gets further away."""
        priority_soon = calculate_priority(
            commitment_type="obligation",
            days_until_due=days_until_due
        )
        priority_later = calculate_priority(
            commitment_type="obligation",
            days_until_due=days_until_due + 10
        )
        assert priority_soon >= priority_later
```

---

### 2. Integration Tests (20% of tests)

**Purpose**: Test interactions between components (DB, APIs, services)

**Target Coverage**: Critical paths:
- Document upload → entity creation → commitment creation
- Database queries with real PostgreSQL
- API endpoints with FastAPI TestClient
- Config loading from YAML files
- Prompt loading with PromptManager

**Technologies**:
- `pytest-postgresql` - Temporary PostgreSQL instances
- `httpx` - Async HTTP client for FastAPI testing
- `testcontainers` - Docker containers for integration tests
- `factory_boy` - Test data factories

**File Naming Convention**:
```
tests/integration/
├── api/
│   ├── test_document_upload_flow.py
│   ├── test_party_resolution_api.py
│   └── test_commitment_api.py
├── database/
│   ├── test_party_queries.py
│   ├── test_document_queries.py
│   └── test_fuzzy_matching.py
├── services/
│   ├── test_pipeline_integration.py
│   └── test_entity_linking.py
└── config/
    ├── test_config_loading.py
    └── test_prompt_manager.py
```

**Example Integration Test**:
```python
"""Integration tests for document upload flow."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from api.main import app
from api.database import engine, Base
from tests.fixtures import create_test_database


@pytest.fixture
async def test_db():
    """Create temporary test database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def async_client():
    """Create async HTTP client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.integration
@pytest.mark.asyncio
async def test_document_upload_creates_vendor_and_commitment(
    async_client, test_db
):
    """Test complete document upload flow."""
    # Arrange
    with open("tests/fixtures/invoice_sample.pdf", "rb") as f:
        files = {"file": ("invoice.pdf", f, "application/pdf")}
        data = {"detail_level": "high"}

        # Act
        response = await async_client.post(
            "/api/documents/upload",
            files=files,
            data=data
        )

    # Assert
    assert response.status_code == 201
    result = response.json()

    # Verify document created
    assert result["document_id"].startswith("doc_")
    assert result["sha256"] is not None

    # Verify vendor created/matched
    assert result["extraction"]["vendor"]["party_id"].startswith("party_")
    assert result["extraction"]["vendor"]["name"] == "Clipboard Health"

    # Verify commitment created
    assert result["extraction"]["commitment"]["commitment_id"].startswith("commit_")
    assert result["extraction"]["commitment"]["priority"] > 0

    # Verify database state
    async with AsyncSession(engine) as session:
        # Check party exists
        party_result = await session.execute(
            select(Party).where(Party.party_id == result["extraction"]["vendor"]["party_id"])
        )
        party = party_result.scalar_one()
        assert party.name == "Clipboard Health"

        # Check commitment exists
        commitment_result = await session.execute(
            select(Commitment).where(
                Commitment.commitment_id == result["extraction"]["commitment"]["commitment_id"]
            )
        )
        commitment = commitment_result.scalar_one()
        assert commitment.state == "pending"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_upload_detected(async_client, test_db):
    """Test uploading same file twice detects duplicate."""
    # Arrange
    with open("tests/fixtures/invoice_sample.pdf", "rb") as f:
        files1 = {"file": ("invoice.pdf", f, "application/pdf")}
        response1 = await async_client.post("/api/documents/upload", files=files1)

    # Act - upload same file again
    with open("tests/fixtures/invoice_sample.pdf", "rb") as f:
        files2 = {"file": ("invoice.pdf", f, "application/pdf")}
        response2 = await async_client.post("/api/documents/upload", files=files2)

    # Assert
    assert response1.status_code == 201
    assert response2.status_code == 201
    assert response2.json()["deduplicated"] is True
    assert response1.json()["sha256"] == response2.json()["sha256"]
```

**Database Integration Test Example**:
```python
"""Integration tests for fuzzy party matching."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import engine
from api.models.party import Party


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fuzzy_matching_with_pg_trgm():
    """Test PostgreSQL trigram fuzzy matching."""
    # Arrange
    async with AsyncSession(engine) as session:
        # Create test parties
        parties = [
            Party(name="Clipboard Health", legal_name="Twomagnets Inc."),
            Party(name="Clipboard Hlth", legal_name="Twomagnets"),
            Party(name="Acme Corporation", legal_name="Acme Corp LLC")
        ]
        for party in parties:
            session.add(party)
        await session.commit()

        # Act - fuzzy search
        query = text("""
            SELECT party_id, name, legal_name,
                   similarity(name, :search_name) as name_score,
                   similarity(legal_name, :search_legal) as legal_score
            FROM party
            WHERE name % :search_name OR legal_name % :search_legal
            ORDER BY GREATEST(name_score, legal_score) DESC
            LIMIT 5
        """)
        result = await session.execute(
            query,
            {"search_name": "Clipboard Health", "search_legal": "Twomagnets Inc"}
        )
        matches = result.fetchall()

    # Assert
    assert len(matches) >= 2
    assert matches[0].name_score > 0.9  # Exact match first
    assert matches[1].name_score > 0.7  # Close match second
```

---

### 3. End-to-End Tests (10% of tests)

**Purpose**: Validate complete user journeys from UI to database

**Target Coverage**: Critical user stories:
- US-001: Upload invoice and auto-create vendor
- US-002: Auto-create "Pay Invoice" commitment
- US-003: View document with full entity graph
- US-004: Search all vendor invoices
- US-005: View commitment dashboard

**Technologies**:
- `playwright` - Browser automation
- `pytest-playwright` - Playwright pytest plugin
- `testcontainers` - Full stack in Docker

**File Naming Convention**:
```
tests/e2e/
├── test_invoice_upload_journey.py
├── test_vendor_history_journey.py
├── test_commitment_fulfillment_journey.py
└── test_search_journey.py
```

**Example E2E Test**:
```python
"""E2E tests for invoice upload user journey."""

import pytest
from playwright.async_api import async_playwright, Page


@pytest.fixture
async def browser_page():
    """Launch browser and navigate to app."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://localhost:5173")
        yield page
        await browser.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_upload_invoice_creates_vendor_and_commitment(browser_page: Page):
    """Test US-001 and US-002: Upload invoice → create vendor → create commitment."""
    # Arrange
    page = browser_page

    # Act - Navigate to vision service
    await page.click("text=Vision Service")
    await page.wait_for_selector("h1:has-text('Vision Service')")

    # Upload file
    await page.set_input_files(
        'input[type="file"]',
        'tests/fixtures/invoice_sample.pdf'
    )

    # Wait for processing
    await page.wait_for_selector("text=Document Processed", timeout=10000)

    # Assert - Check vendor identified
    vendor_section = page.locator("text=Vendor Identified")
    await expect(vendor_section).to_be_visible()

    vendor_name = page.locator("text=Clipboard Health")
    await expect(vendor_name).to_be_visible()

    # Assert - Check commitment created
    commitment_section = page.locator("text=Commitment Created")
    await expect(commitment_section).to_be_visible()

    commitment_title = page.locator("text=Pay Invoice #240470")
    await expect(commitment_title).to_be_visible()

    # Assert - Check priority displayed
    priority_badge = page.locator("text=/Priority: \\d+/")
    await expect(priority_badge).to_be_visible()

    # Act - Click view vendor history
    await page.click("text=View vendor history")

    # Assert - Vendor page loads
    await page.wait_for_selector("h1:has-text('Clipboard Health')")

    # Assert - Document appears in vendor history
    document_row = page.locator("text=invoice_240470.pdf")
    await expect(document_row).to_be_visible()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_commitment_dashboard_shows_high_priority(browser_page: Page):
    """Test US-005: View commitment dashboard with high priority items."""
    # Arrange
    page = browser_page

    # Act - Navigate to commitments
    await page.click("text=Commitments")
    await page.wait_for_selector("h1:has-text('Your Focus')")

    # Assert - High priority commitments visible
    commitment_cards = page.locator('[data-testid="commitment-card"]')
    count = await commitment_cards.count()
    assert count > 0

    # Assert - Sorted by priority
    priorities = []
    for i in range(count):
        card = commitment_cards.nth(i)
        priority_text = await card.locator('[data-testid="priority"]').text_content()
        priority = int(priority_text.replace("Priority: ", ""))
        priorities.append(priority)

    assert priorities == sorted(priorities, reverse=True)

    # Act - Mark commitment as complete
    first_card = commitment_cards.first
    await first_card.locator("button:has-text('Mark Complete')").click()

    # Assert - Commitment disappears from list
    await page.wait_for_timeout(500)
    new_count = await commitment_cards.count()
    assert new_count == count - 1
```

---

## Performance Testing

### Load Testing

**Purpose**: Verify system handles expected traffic

**Tools**:
- `locust` - Load testing framework
- `pytest-benchmark` - Micro-benchmarking

**Target Metrics**:
| Endpoint | P50 | P95 | P99 | RPS |
|----------|-----|-----|-----|-----|
| GET /api/documents | < 50ms | < 150ms | < 300ms | 100 |
| POST /api/documents/upload | < 1.5s | < 3.5s | < 5s | 10 |
| POST /api/parties/resolve | < 300ms | < 800ms | < 1.5s | 50 |

**Example Load Test**:
```python
"""Load tests for document upload endpoint."""

from locust import HttpUser, task, between


class DocumentUploadUser(HttpUser):
    """Simulate user uploading documents."""

    wait_time = between(1, 5)

    @task
    def upload_document(self):
        """Upload test document."""
        with open("tests/fixtures/invoice_sample.pdf", "rb") as f:
            files = {"file": ("invoice.pdf", f, "application/pdf")}
            self.client.post("/api/documents/upload", files=files)

    @task(3)
    def list_documents(self):
        """List documents (more frequent)."""
        self.client.get("/api/documents?limit=50")

    @task(2)
    def get_party(self):
        """Get party details."""
        self.client.get("/api/parties/party_xyz789")
```

**Run Load Test**:
```bash
locust -f tests/load/test_document_upload.py --host http://localhost:8765 --users 100 --spawn-rate 10
```

### Database Performance Testing

**Example Benchmark Test**:
```python
"""Benchmark tests for database queries."""

import pytest
from sqlalchemy import select
from api.models.party import Party


@pytest.mark.benchmark
def test_fuzzy_party_search_performance(benchmark, db_session):
    """Benchmark fuzzy party search with 10,000 parties."""
    # Arrange - create 10,000 test parties
    parties = [
        Party(name=f"Company {i}", legal_name=f"Company {i} LLC")
        for i in range(10000)
    ]
    db_session.bulk_save_objects(parties)
    db_session.commit()

    # Act & Assert
    def search():
        query = text("""
            SELECT party_id, name, similarity(name, :search) as score
            FROM party
            WHERE name % :search
            ORDER BY score DESC
            LIMIT 10
        """)
        result = db_session.execute(query, {"search": "Company 5000"})
        return result.fetchall()

    result = benchmark(search)

    # Assert - query completes in < 100ms
    assert benchmark.stats.mean < 0.1
```

---

## Security Testing

### Vulnerability Scanning

**Tools**:
- `bandit` - Python security linter
- `safety` - Dependency vulnerability scanner
- `semgrep` - Static analysis

**Example Security Tests**:
```python
"""Security tests for API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.security
@pytest.mark.asyncio
async def test_sql_injection_protection(async_client):
    """Test SQL injection is prevented."""
    # Arrange - malicious input
    malicious_search = "'; DROP TABLE party; --"

    # Act
    response = await async_client.get(
        f"/api/parties?search={malicious_search}"
    )

    # Assert - request handled safely
    assert response.status_code in [200, 400]  # Not 500

    # Verify table still exists
    response = await async_client.get("/api/parties")
    assert response.status_code == 200


@pytest.mark.security
@pytest.mark.asyncio
async def test_file_upload_validates_mime_type(async_client):
    """Test malicious file upload is rejected."""
    # Arrange - executable disguised as PDF
    malicious_file = b"\x7fELF"  # ELF header
    files = {"file": ("malware.pdf", malicious_file, "application/pdf")}

    # Act
    response = await async_client.post("/api/documents/upload", files=files)

    # Assert - rejected
    assert response.status_code == 400
    assert "invalid" in response.json()["error"]["message"].lower()
```

---

## Test Data Management

### Fixtures

**Shared Fixtures** (`tests/fixtures/conftest.py`):
```python
"""Shared pytest fixtures."""

import pytest
from faker import Faker
from api.models.party import Party
from api.models.commitment import Commitment


@pytest.fixture
def faker_seed():
    """Fixed seed for reproducible fake data."""
    return 12345


@pytest.fixture
def fake(faker_seed):
    """Faker instance with fixed seed."""
    return Faker()


@pytest.fixture
def sample_party(fake):
    """Create sample party."""
    return Party(
        name=fake.company(),
        legal_name=f"{fake.company()} LLC",
        party_type="vendor",
        tax_id=fake.ssn()
    )


@pytest.fixture
def sample_invoice_data():
    """Sample invoice extraction data."""
    return {
        "vendor_name": "Clipboard Health",
        "legal_name": "Twomagnets Inc.",
        "invoice_id": "240470",
        "invoice_date": "2024-02-14",
        "due_date": "2024-02-28",
        "total_amount": 12419.83,
        "currency": "USD"
    }
```

### Factory Pattern

**Example Factory** (`tests/factories/party_factory.py`):
```python
"""Factory for creating test parties."""

import factory
from factory.alchemy import SQLAlchemyModelFactory
from api.models.party import Party
from api.database import SessionLocal


class PartyFactory(SQLAlchemyModelFactory):
    """Factory for Party model."""

    class Meta:
        model = Party
        sqlalchemy_session = SessionLocal

    party_id = factory.Sequence(lambda n: f"party_test_{n}")
    name = factory.Faker("company")
    legal_name = factory.LazyAttribute(lambda obj: f"{obj.name} LLC")
    party_type = "vendor"
    tax_id = factory.Faker("ssn")
    contact_json = factory.LazyFunction(
        lambda: {
            "email": factory.Faker("email").generate(),
            "phone": factory.Faker("phone_number").generate()
        }
    )


# Usage:
party = PartyFactory.create()  # Saves to DB
party = PartyFactory.build()   # Doesn't save
parties = PartyFactory.create_batch(10)  # Create 10
```

---

## CI/CD Integration

### GitHub Actions Workflow

**File**: `.github/workflows/test.yml`
```yaml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=api --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5433:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run migrations
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5433/testdb

      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5433/testdb

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install playwright
          playwright install chromium

      - name: Start application
        run: |
          uvicorn api.main:app --host 0.0.0.0 --port 8765 &
          cd ui && npm install && npm run dev &
          sleep 10

      - name: Run E2E tests
        run: pytest tests/e2e/ -v

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run bandit
        run: |
          pip install bandit
          bandit -r api/ -f json -o bandit-report.json

      - name: Run safety
        run: |
          pip install safety
          safety check --json > safety-report.json
```

### Pre-commit Hooks

**File**: `.pre-commit-config.yaml`
```yaml
repos:
  - repo: local
    hooks:
      - id: pytest-unit
        name: pytest unit tests
        entry: pytest tests/unit/ -v --tb=short
        language: system
        pass_filenames: false
        always_run: true

      - id: pytest-quick
        name: pytest quick tests
        entry: pytest -m "not slow" tests/
        language: system
        pass_filenames: false
        always_run: true
```

---

## Coverage Requirements

### Coverage Targets

| Category | Target | Enforcement |
|----------|--------|-------------|
| Overall | 85% | CI blocks < 80% |
| Service Layer | 90% | CI blocks < 85% |
| Business Logic | 95% | CI blocks < 90% |
| Models | 80% | CI blocks < 75% |
| API Routes | 75% | Warning only |

### Coverage Configuration

**File**: `.coveragerc`
```ini
[run]
source = api
omit =
    */tests/*
    */migrations/*
    */__pycache__/*
    */venv/*

[report]
precision = 2
skip_empty = True
skip_covered = False
sort = Cover

exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod

[html]
directory = htmlcov
```

### Running Coverage

```bash
# Run all tests with coverage
pytest --cov=api --cov-report=html --cov-report=term

# Run specific test type
pytest tests/unit/ --cov=api/services --cov-report=term-missing

# Generate coverage badge
coverage-badge -o coverage.svg -f
```

---

## Test Execution

### Running Tests

```bash
# Run all tests
pytest

# Run specific test type
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run specific test file
pytest tests/unit/services/test_entity_resolver.py

# Run specific test
pytest tests/unit/services/test_entity_resolver.py::TestEntityResolverService::test_resolve_vendor_exact_match

# Run with markers
pytest -m "not slow"  # Skip slow tests
pytest -m "integration"  # Only integration tests
pytest -m "security"  # Only security tests

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=api --cov-report=html

# Run in parallel (requires pytest-xdist)
pytest -n auto
```

### Test Markers

**File**: `pytest.ini`
```ini
[pytest]
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (require DB)
    e2e: End-to-end tests (require full stack)
    slow: Slow tests (> 1s)
    security: Security tests
    benchmark: Performance benchmark tests
    smoke: Smoke tests (critical path)

testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

asyncio_mode = auto

addopts =
    -ra
    --strict-markers
    --strict-config
    --tb=short
```

---

## Test Maintenance

### Flaky Test Detection

**Strategy**:
1. Run tests 10 times in CI: `pytest --count=10`
2. Flag tests that fail 1-9 times as flaky
3. Fix or quarantine flaky tests

**Quarantine Pattern**:
```python
@pytest.mark.skip(reason="Flaky test - tracked in issue #123")
def test_flaky_behavior():
    pass
```

### Test Speed Monitoring

**File**: `tests/conftest.py`
```python
"""Global pytest configuration."""

import pytest
import time


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Track test duration and flag slow tests."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        duration = report.duration
        if duration > 1.0 and "slow" not in item.keywords:
            pytest.warns(
                UserWarning,
                f"Test {item.nodeid} took {duration:.2f}s but not marked as slow"
            )
```

---

## Appendix: Test Checklist

### Before Commit
- [ ] All tests pass locally: `pytest`
- [ ] Coverage meets threshold: `pytest --cov=api`
- [ ] No new security warnings: `bandit -r api/`
- [ ] Type checks pass: `mypy api/`
- [ ] Linting passes: `ruff check api/`

### Before Pull Request
- [ ] All CI checks pass
- [ ] New code has 90%+ test coverage
- [ ] Integration tests for new endpoints
- [ ] E2E tests for new user journeys (if applicable)
- [ ] Performance tests for critical paths (if applicable)
- [ ] Security tests for new input handling (if applicable)

### Before Release
- [ ] Full test suite passes: `pytest tests/`
- [ ] Load tests meet targets: `locust`
- [ ] Security scan clean: `bandit`, `safety`
- [ ] E2E smoke tests pass: `pytest -m smoke`
- [ ] Database migrations tested: upgrade + downgrade
- [ ] Rollback plan tested

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-06 | Initial testing strategy |

---

**Next Steps**: Review WORKFLOWS.md for development and operational workflows including how testing integrates with the development lifecycle.
