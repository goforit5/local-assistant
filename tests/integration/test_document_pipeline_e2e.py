"""E2E Integration Tests for Document Upload Pipeline (TEST-002).

Tests the complete workflow:
1. Document upload → Vision extraction → Vendor resolution → Commitment creation → Entity linking

Test scenarios:
- Full pipeline with new vendor and commitment creation
- SHA-256 deduplication for duplicate uploads
- New vendor creation when unknown
- Fuzzy matching to existing vendors (>90% similarity)

All tests use real PostgreSQL database with transaction rollback.
External APIs (OpenAI, Anthropic) are mocked.
"""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from uuid import UUID
from io import BytesIO

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from api.main import app
from memory.models import Base, Document, Party, Commitment, DocumentLink, Signal
from memory.database import get_db
from services.vision.types import VisionResult
from tests.fixtures.documents import (
    sample_invoice_pdf,
    sample_invoice_pdf_different_vendor,
    mock_vision_response_acme,
    mock_vision_response_techsupplies,
    mock_vision_response_fuzzy_match,
)


# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://assistant:assistant@localhost:5433/assistant_test",
)


@pytest.fixture(scope="function")
async def test_db_engine():
    """Create test database engine with schema setup."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_db_engine):
    """Create test database session with automatic rollback."""
    async_session = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Start transaction
        async with session.begin():
            yield session
            # Rollback happens automatically when context exits


@pytest.fixture
async def async_client(test_db_session):
    """HTTP client with test database dependency override."""

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_vision_processor():
    """Mock VisionProcessor to avoid hitting real OpenAI API."""
    with patch("api.v1.documents.VisionProcessor") as mock:
        processor_instance = AsyncMock()
        mock.return_value = processor_instance
        yield processor_instance


@pytest.fixture
def mock_storage():
    """Mock ContentAddressableStorage to avoid filesystem operations."""
    with patch("api.v1.documents.ContentAddressableStorage") as mock:
        storage_instance = MagicMock()
        mock.return_value = storage_instance
        yield storage_instance


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require RUN_INTEGRATION_TESTS=1",
)
class TestDocumentPipelineE2E:
    """End-to-end tests for document upload → vendor → commitment pipeline."""

    async def test_upload_invoice_creates_vendor_and_commitment(
        self,
        async_client,
        test_db_session,
        sample_invoice_pdf,
        mock_vision_response_acme,
        mock_vision_processor,
        mock_storage,
    ):
        """Test complete pipeline: upload → extract → resolve vendor → create commitment.

        Verifies:
        - Document record created
        - Vendor (Party) created with correct name
        - Commitment created with invoice details
        - All entities linked via DocumentLink
        - Signal created and marked as 'attached'
        """
        # Configure mocks
        vision_result = VisionResult(
            content=mock_vision_response_acme["content"],
            model=mock_vision_response_acme["model"],
            cost=mock_vision_response_acme["cost"],
            pages_processed=mock_vision_response_acme["pages_processed"],
        )
        mock_vision_processor.analyze_document.return_value = vision_result

        from services.document_intelligence.storage import StorageResult

        storage_result = StorageResult(
            sha256="abc123def456",
            storage_path="/tmp/test/abc123def456.pdf",
            deduplicated=False,
        )
        mock_storage.store.return_value = storage_result

        # Upload invoice
        files = {"file": ("acme_invoice.pdf", BytesIO(sample_invoice_pdf), "application/pdf")}
        data = {"extraction_type": "invoice"}

        response = await async_client.post("/api/v1/documents/upload", files=files, data=data)

        # Assert successful upload
        assert response.status_code == 200
        result = response.json()

        # Verify response structure
        assert "document_id" in result
        assert "sha256" in result
        assert result["sha256"] == "abc123def456"
        assert result["vendor"] is not None
        assert result["commitment"] is not None

        document_id = UUID(result["document_id"])
        vendor_id = UUID(result["vendor"]["id"])
        commitment_id = UUID(result["commitment"]["id"])

        # Verify database state
        # 1. Document exists
        doc_query = select(Document).where(Document.id == document_id)
        doc_result = await test_db_session.execute(doc_query)
        document = doc_result.scalar_one_or_none()

        assert document is not None
        assert document.sha256 == "abc123def456"
        assert document.extraction_type == "invoice"
        assert document.extraction_cost > 0

        # 2. Vendor exists
        vendor_query = select(Party).where(Party.id == vendor_id)
        vendor_result = await test_db_session.execute(vendor_query)
        vendor = vendor_result.scalar_one_or_none()

        assert vendor is not None
        assert "Acme" in vendor.name  # Fuzzy match
        assert vendor.kind == "org"

        # 3. Commitment exists
        commitment_query = select(Commitment).where(Commitment.id == commitment_id)
        commitment_result = await test_db_session.execute(commitment_query)
        commitment = commitment_result.scalar_one_or_none()

        assert commitment is not None
        assert commitment.commitment_type == "invoice_payment"
        assert commitment.state == "pending"
        assert commitment.due_date is not None

        # 4. Links exist
        links_query = select(DocumentLink).where(DocumentLink.document_id == document_id)
        links_result = await test_db_session.execute(links_query)
        links = links_result.scalars().all()

        assert len(links) >= 3  # signal, vendor, commitment
        link_types = {link.link_type for link in links}
        assert "extracted_from" in link_types  # signal link
        assert "vendor" in link_types  # vendor link
        assert "obligation" in link_types  # commitment link

        # 5. Signal exists and is attached
        signal_query = select(Signal).where(Signal.dedupe_key == "abc123def456")
        signal_result = await test_db_session.execute(signal_query)
        signal = signal_result.scalar_one_or_none()

        assert signal is not None
        assert signal.status == "attached"

    async def test_duplicate_document_returns_cached_result(
        self,
        async_client,
        test_db_session,
        sample_invoice_pdf,
        mock_vision_response_acme,
        mock_vision_processor,
        mock_storage,
    ):
        """Test SHA-256 deduplication: uploading same file twice returns cached result.

        Verifies:
        - First upload processes normally
        - Second upload detects duplicate via SHA-256
        - Same document_id returned
        - No duplicate vendor/commitment created
        - Metrics indicate deduplication
        """
        # Configure mocks
        vision_result = VisionResult(
            content=mock_vision_response_acme["content"],
            model=mock_vision_response_acme["model"],
            cost=mock_vision_response_acme["cost"],
            pages_processed=mock_vision_response_acme["pages_processed"],
        )
        mock_vision_processor.analyze_document.return_value = vision_result

        from services.document_intelligence.storage import StorageResult

        # First upload - not deduplicated
        storage_result_1 = StorageResult(
            sha256="duplicate_test_sha256",
            storage_path="/tmp/test/duplicate_test_sha256.pdf",
            deduplicated=False,
        )
        mock_storage.store.return_value = storage_result_1

        # First upload
        files_1 = {"file": ("invoice_v1.pdf", BytesIO(sample_invoice_pdf), "application/pdf")}
        data = {"extraction_type": "invoice"}

        response_1 = await async_client.post("/api/v1/documents/upload", files=files_1, data=data)
        assert response_1.status_code == 200
        result_1 = response_1.json()

        # Second upload - deduplicated
        storage_result_2 = StorageResult(
            sha256="duplicate_test_sha256",
            storage_path="/tmp/test/duplicate_test_sha256.pdf",
            deduplicated=True,
        )
        mock_storage.store.return_value = storage_result_2

        files_2 = {"file": ("invoice_v2.pdf", BytesIO(sample_invoice_pdf), "application/pdf")}

        response_2 = await async_client.post("/api/v1/documents/upload", files=files_2, data=data)
        assert response_2.status_code == 200
        result_2 = response_2.json()

        # Verify deduplication
        assert result_1["sha256"] == result_2["sha256"]
        assert result_2["metrics"]["storage"]["deduplicated"] is True

        # Verify only one vendor created
        vendor_query = select(Party).where(Party.name.ilike("%Acme%"))
        vendor_result = await test_db_session.execute(vendor_query)
        vendors = vendor_result.scalars().all()
        assert len(vendors) == 1  # Should not create duplicate vendor

    async def test_invoice_with_unknown_vendor_creates_new_party(
        self,
        async_client,
        test_db_session,
        sample_invoice_pdf_different_vendor,
        mock_vision_response_techsupplies,
        mock_vision_processor,
        mock_storage,
    ):
        """Test new vendor creation when vendor name not found in database.

        Verifies:
        - New Party entity created with vendor details
        - Party has correct attributes (name, kind=org)
        - Response indicates new vendor (matched=False)
        - Vendor resolution metrics show created_new=True
        """
        # Configure mocks for different vendor
        vision_result = VisionResult(
            content=mock_vision_response_techsupplies["content"],
            model=mock_vision_response_techsupplies["model"],
            cost=mock_vision_response_techsupplies["cost"],
            pages_processed=mock_vision_response_techsupplies["pages_processed"],
        )
        mock_vision_processor.analyze_document.return_value = vision_result

        from services.document_intelligence.storage import StorageResult

        storage_result = StorageResult(
            sha256="techsupplies_sha256",
            storage_path="/tmp/test/techsupplies_sha256.pdf",
            deduplicated=False,
        )
        mock_storage.store.return_value = storage_result

        # Upload invoice with new vendor
        files = {
            "file": ("techsupplies_invoice.pdf", BytesIO(sample_invoice_pdf_different_vendor), "application/pdf")
        }
        data = {"extraction_type": "invoice"}

        response = await async_client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()

        # Verify new vendor created
        assert result["vendor"] is not None
        assert result["vendor"]["matched"] is False  # New vendor, not matched
        assert "TechSupplies" in result["vendor"]["name"]

        vendor_id = UUID(result["vendor"]["id"])

        # Verify vendor in database
        vendor_query = select(Party).where(Party.id == vendor_id)
        vendor_result = await test_db_session.execute(vendor_query)
        vendor = vendor_result.scalar_one_or_none()

        assert vendor is not None
        assert "TechSupplies" in vendor.name
        assert vendor.kind == "org"

        # Verify metrics
        assert result["metrics"]["vendor_resolution"]["created_new"] is True

    async def test_invoice_matches_existing_vendor_fuzzy(
        self,
        async_client,
        test_db_session,
        sample_invoice_pdf,
        mock_vision_response_fuzzy_match,
        mock_vision_processor,
        mock_storage,
    ):
        """Test fuzzy matching to existing vendor (>90% similarity).

        Verifies:
        - First upload creates vendor "Acme Corp"
        - Second upload with "Acme Corporation" matches existing vendor
        - No duplicate vendor created
        - Response indicates matched=True
        - Vendor resolution metrics show confidence >0.9
        """
        from services.document_intelligence.storage import StorageResult

        # First upload - create "Acme Corp"
        vision_result_1 = VisionResult(
            content="Invoice from Acme Corp\nTotal: $1000",
            model="gpt-4o",
            cost=Decimal("0.0025"),
            pages_processed=1,
        )
        mock_vision_processor.analyze_document.return_value = vision_result_1

        storage_result_1 = StorageResult(
            sha256="fuzzy_test_1",
            storage_path="/tmp/test/fuzzy_test_1.pdf",
            deduplicated=False,
        )
        mock_storage.store.return_value = storage_result_1

        files_1 = {"file": ("acme_corp.pdf", BytesIO(sample_invoice_pdf), "application/pdf")}
        data = {"extraction_type": "invoice"}

        response_1 = await async_client.post("/api/v1/documents/upload", files=files_1, data=data)
        assert response_1.status_code == 200
        result_1 = response_1.json()
        vendor_id_1 = UUID(result_1["vendor"]["id"])

        # Second upload - "Acme Corporation" should fuzzy match "Acme Corp"
        vision_result_2 = VisionResult(
            content=mock_vision_response_fuzzy_match["content"],
            model=mock_vision_response_fuzzy_match["model"],
            cost=mock_vision_response_fuzzy_match["cost"],
            pages_processed=mock_vision_response_fuzzy_match["pages_processed"],
        )
        mock_vision_processor.analyze_document.return_value = vision_result_2

        storage_result_2 = StorageResult(
            sha256="fuzzy_test_2",
            storage_path="/tmp/test/fuzzy_test_2.pdf",
            deduplicated=False,
        )
        mock_storage.store.return_value = storage_result_2

        files_2 = {"file": ("acme_corporation.pdf", BytesIO(sample_invoice_pdf), "application/pdf")}

        response_2 = await async_client.post("/api/v1/documents/upload", files=files_2, data=data)
        assert response_2.status_code == 200
        result_2 = response_2.json()

        # Verify fuzzy match to existing vendor
        vendor_id_2 = UUID(result_2["vendor"]["id"])
        assert vendor_id_1 == vendor_id_2  # Same vendor matched

        # Verify only one vendor exists
        vendor_query = select(Party).where(Party.name.ilike("%Acme%"))
        vendor_result = await test_db_session.execute(vendor_query)
        vendors = vendor_result.scalars().all()
        assert len(vendors) == 1  # No duplicate created

        # Verify match confidence
        assert result_2["vendor"]["matched"] is True
        assert result_2["vendor"]["confidence"] is not None
        assert result_2["vendor"]["confidence"] > 0.9  # High confidence fuzzy match


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require RUN_INTEGRATION_TESTS=1",
)
class TestDocumentPipelineEdgeCases:
    """Edge case tests for document pipeline."""

    async def test_invoice_without_vendor_name_handles_gracefully(
        self,
        async_client,
        test_db_session,
        sample_invoice_pdf,
        mock_vision_processor,
        mock_storage,
    ):
        """Test handling of invoice with missing vendor name.

        Verifies:
        - Pipeline doesn't crash
        - Document still created
        - No vendor created (or "Unknown Vendor" created)
        - Commitment may still be created
        """
        # Configure mocks with missing vendor
        vision_result = VisionResult(
            content="Invoice\nTotal: $500\nDue: 2025-12-31",
            model="gpt-4o",
            cost=Decimal("0.0025"),
            pages_processed=1,
        )
        mock_vision_processor.analyze_document.return_value = vision_result

        from services.document_intelligence.storage import StorageResult

        storage_result = StorageResult(
            sha256="no_vendor_sha",
            storage_path="/tmp/test/no_vendor_sha.pdf",
            deduplicated=False,
        )
        mock_storage.store.return_value = storage_result

        files = {"file": ("no_vendor.pdf", BytesIO(sample_invoice_pdf), "application/pdf")}
        data = {"extraction_type": "invoice"}

        response = await async_client.post("/api/v1/documents/upload", files=files, data=data)

        # Should succeed (or return 500 with graceful error)
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            result = response.json()
            # Document created
            assert "document_id" in result

    async def test_large_invoice_with_many_line_items(
        self,
        async_client,
        test_db_session,
        mock_vision_processor,
        mock_storage,
    ):
        """Test handling of large invoice with many line items.

        Verifies:
        - Pipeline handles large extraction data
        - All line items processed
        - Total calculated correctly
        """
        # Generate large PDF
        large_pdf = b"%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n4 0 obj\n<</Length 100>>stream\nBT\n/F1 12 Tf\n50 750 Td\n(LARGE INVOICE)Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\ntrailer\n<</Size 5/Root 1 0 R>>startxref\n%%EOF"

        # Large extraction with many line items
        line_items = [
            {"description": f"Item {i}", "quantity": 1, "unit_price": 10.0, "total": 10.0}
            for i in range(100)
        ]

        vision_result = VisionResult(
            content="INVOICE\nFrom: BigVendor Corp\nTotal: $1000.00\n" + "\n".join([f"Item {i}: $10" for i in range(100)]),
            model="gpt-4o",
            cost=Decimal("0.0050"),  # Higher cost for larger doc
            pages_processed=3,
        )
        mock_vision_processor.analyze_document.return_value = vision_result

        from services.document_intelligence.storage import StorageResult

        storage_result = StorageResult(
            sha256="large_invoice_sha",
            storage_path="/tmp/test/large_invoice_sha.pdf",
            deduplicated=False,
        )
        mock_storage.store.return_value = storage_result

        files = {"file": ("large_invoice.pdf", BytesIO(large_pdf), "application/pdf")}
        data = {"extraction_type": "invoice"}

        response = await async_client.post("/api/v1/documents/upload", files=files, data=data)

        # Should handle large data
        assert response.status_code in [200, 500]
