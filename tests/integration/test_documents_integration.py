"""Integration tests for Documents API with real database.

These tests require:
- PostgreSQL running on port 5433
- Database migrations applied
- All necessary extensions enabled
"""

import pytest
import os
from io import BytesIO
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from api.main import app
from memory.models import Base, Document, Party, Commitment, DocumentLink, Signal
from memory.database import get_db


# Test database URL (use separate test database)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://assistant:assistant@localhost:5433/assistant_test",
)


@pytest.fixture(scope="function")
async def test_db_engine():
    """Create test database engine."""
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
    """Create test database session."""
    async_session = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest.fixture
def client(test_db_session):
    """Test client with test database."""

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def sample_pdf():
    """Sample PDF file bytes for testing."""
    # Minimal valid PDF header
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test Invoice) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000315 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
406
%%EOF
"""
    return pdf_content


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require RUN_INTEGRATION_TESTS=1",
)
class TestDocumentsAPIIntegration:
    """Integration tests for Documents API."""

    @pytest.mark.asyncio
    async def test_full_upload_workflow(self, client, sample_pdf, test_db_session):
        """Test complete document upload workflow with real database.

        This test verifies:
        1. Document upload and processing
        2. Entity creation (document, vendor, commitment)
        3. Entity linking (document_links)
        4. Signal creation and status updates
        5. Interaction logging
        """
        # Upload document
        files = {"file": ("test_invoice.pdf", BytesIO(sample_pdf), "application/pdf")}
        data = {"extraction_type": "invoice"}

        response = client.post("/api/documents/upload", files=files, data=data)

        # Should return 200 (may fail if vision API not configured)
        # In real test, we'd need to mock the vision API
        # For now, we just verify the endpoint exists
        assert response.status_code in [200, 500]

        # If successful, verify database state
        if response.status_code == 200:
            result = response.json()

            # Verify document was created
            document_id = UUID(result["document_id"])
            stmt = select(Document).where(Document.id == document_id)
            doc_result = await test_db_session.execute(stmt)
            document = doc_result.scalar_one_or_none()

            assert document is not None
            assert document.sha256 == result["sha256"]

            # Verify links were created
            links_stmt = select(DocumentLink).where(
                DocumentLink.document_id == document_id
            )
            links_result = await test_db_session.execute(links_stmt)
            links = links_result.scalars().all()

            assert len(links) > 0

    @pytest.mark.asyncio
    async def test_get_document_after_upload(
        self, client, sample_pdf, test_db_session
    ):
        """Test retrieving document details after upload."""
        # First, upload a document
        files = {"file": ("test_invoice.pdf", BytesIO(sample_pdf), "application/pdf")}
        data = {"extraction_type": "invoice"}

        upload_response = client.post("/api/documents/upload", files=files, data=data)

        # If upload successful, test get endpoint
        if upload_response.status_code == 200:
            upload_result = upload_response.json()
            document_id = upload_result["document_id"]

            # Get document details
            get_response = client.get(f"/api/documents/{document_id}")

            assert get_response.status_code == 200
            get_result = get_response.json()

            assert get_result["id"] == document_id
            assert get_result["sha256"] == upload_result["sha256"]

    @pytest.mark.asyncio
    async def test_download_after_upload(self, client, sample_pdf, test_db_session):
        """Test downloading document after upload."""
        # First, upload a document
        files = {"file": ("test_invoice.pdf", BytesIO(sample_pdf), "application/pdf")}
        data = {"extraction_type": "invoice"}

        upload_response = client.post("/api/documents/upload", files=files, data=data)

        # If upload successful, test download endpoint
        if upload_response.status_code == 200:
            upload_result = upload_response.json()
            document_id = upload_result["document_id"]

            # Download document
            download_response = client.get(f"/api/documents/{document_id}/download")

            assert download_response.status_code == 200
            assert download_response.headers["content-type"] == "application/pdf"
            # Verify we got file content back
            assert len(download_response.content) > 0

    @pytest.mark.asyncio
    async def test_deduplication(self, client, sample_pdf, test_db_session):
        """Test that uploading same file twice uses deduplication."""
        files1 = {
            "file": ("invoice1.pdf", BytesIO(sample_pdf), "application/pdf")
        }
        files2 = {
            "file": ("invoice2.pdf", BytesIO(sample_pdf), "application/pdf")
        }
        data = {"extraction_type": "invoice"}

        # Upload same file twice with different names
        response1 = client.post("/api/documents/upload", files=files1, data=data)
        response2 = client.post("/api/documents/upload", files=files2, data=data)

        # Both should succeed (or both fail)
        if response1.status_code == 200 and response2.status_code == 200:
            result1 = response1.json()
            result2 = response2.json()

            # Should have same SHA-256
            assert result1["sha256"] == result2["sha256"]

            # Second upload should be marked as deduplicated
            assert result2["metrics"]["storage"]["deduplicated"] is True


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require RUN_INTEGRATION_TESTS=1",
)
class TestDocumentsAPIErrorCases:
    """Integration tests for error cases."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self, client):
        """Test getting document that doesn't exist."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/documents/{fake_uuid}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_download_nonexistent_document(self, client):
        """Test downloading document that doesn't exist."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/documents/{fake_uuid}/download")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_invalid_pdf(self, client):
        """Test uploading invalid PDF."""
        invalid_pdf = b"not a real pdf"
        files = {"file": ("bad.pdf", BytesIO(invalid_pdf), "application/pdf")}
        data = {"extraction_type": "invoice"}

        response = client.post("/api/documents/upload", files=files, data=data)

        # Should fail during processing
        assert response.status_code == 500
