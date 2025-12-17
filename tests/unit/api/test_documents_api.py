"""Unit tests for Documents API endpoints."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import UUID, uuid4
from datetime import datetime
from io import BytesIO

from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.main import app
from services.document_intelligence.pipeline import PipelineResult


@pytest.fixture
def client():
    """Test client for API."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.begin = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_pipeline():
    """Mock document processing pipeline."""
    pipeline = AsyncMock()
    return pipeline


@pytest.fixture
def sample_pipeline_result():
    """Sample successful pipeline result."""
    document_id = uuid4()
    vendor_id = uuid4()
    commitment_id = uuid4()
    signal_id = uuid4()

    return PipelineResult(
        document_id=document_id,
        signal_id=signal_id,
        vendor_id=vendor_id,
        commitment_id=commitment_id,
        interaction_ids=[uuid4(), uuid4()],
        metrics={
            "storage": {
                "sha256": "a1b2c3d4e5f6",
                "deduplicated": False,
                "size_bytes": 524288,
            },
            "extraction": {
                "cost": 0.0048675,
                "model": "gpt-4o",
                "pages_processed": 3,
                "duration_seconds": 1.23,
            },
            "vendor_resolution": {
                "vendor_id": str(vendor_id),
                "vendor_name": "Clipboard Health",
                "created_new": False,
                "confidence": 0.95,
                "tier": "fuzzy",
            },
            "commitment": {
                "commitment_id": str(commitment_id),
                "title": "Pay Invoice #240470 - Clipboard Health",
                "priority": 85,
                "due_date": "2024-02-28",
            },
        },
        error=None,
    )


class TestDocumentUpload:
    """Tests for POST /api/documents/upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_success(
        self, client, mock_db, mock_pipeline, sample_pipeline_result
    ):
        """Test successful document upload."""
        # Mock file upload
        file_content = b"fake pdf content"
        files = {"file": ("test.pdf", BytesIO(file_content), "application/pdf")}
        data = {"extraction_type": "invoice"}

        # Mock pipeline processing
        with patch("api.routes.documents.get_pipeline", return_value=mock_pipeline):
            with patch("api.routes.documents.get_db", return_value=mock_db):
                mock_pipeline.process_document_upload.return_value = (
                    sample_pipeline_result
                )

                # Mock database queries for vendor and commitment
                mock_vendor = Mock()
                mock_vendor.id = sample_pipeline_result.vendor_id
                mock_vendor.name = "Clipboard Health"

                mock_commitment = Mock()
                mock_commitment.id = sample_pipeline_result.commitment_id
                mock_commitment.title = "Pay Invoice #240470 - Clipboard Health"
                mock_commitment.priority = 85
                mock_commitment.reason = "Due in 2 days, $12,419.83"
                mock_commitment.due_date = datetime(2024, 2, 28)
                mock_commitment.commitment_type = "obligation"
                mock_commitment.state = "active"

                # Mock db.execute for vendor query
                vendor_result = Mock()
                vendor_result.scalar_one_or_none.return_value = mock_vendor

                # Mock db.execute for commitment query
                commitment_result = Mock()
                commitment_result.scalar_one_or_none.return_value = mock_commitment

                # Return different results based on query
                mock_db.execute.side_effect = [vendor_result, commitment_result]

                response = client.post("/api/documents/upload", files=files, data=data)

        # Assertions
        assert response.status_code == 200
        data = response.json()

        assert "document_id" in data
        assert data["sha256"] == "a1b2c3d4e5f6"

        assert data["vendor"]["name"] == "Clipboard Health"
        assert data["vendor"]["matched"] is True
        assert data["vendor"]["confidence"] == 0.95

        assert data["commitment"]["title"] == "Pay Invoice #240470 - Clipboard Health"
        assert data["commitment"]["priority"] == 85

        assert data["extraction"]["cost"] == 0.0048675
        assert data["extraction"]["model"] == "gpt-4o"
        assert data["extraction"]["pages_processed"] == 3

        assert "/api/interactions/timeline" in data["links"]["timeline"]
        assert "/api/vendors/" in data["links"]["vendor"]
        assert "/api/documents/" in data["links"]["download"]

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self, client):
        """Test upload with invalid file type."""
        file_content = b"fake text content"
        files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}
        data = {"extraction_type": "invoice"}

        response = client.post("/api/documents/upload", files=files, data=data)

        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_empty_file(self, client):
        """Test upload with empty file."""
        files = {"file": ("test.pdf", BytesIO(b""), "application/pdf")}
        data = {"extraction_type": "invoice"}

        response = client.post("/api/documents/upload", files=files, data=data)

        assert response.status_code == 400
        assert "Empty file" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_pipeline_failure(
        self, client, mock_db, mock_pipeline
    ):
        """Test upload when pipeline processing fails."""
        file_content = b"fake pdf content"
        files = {"file": ("test.pdf", BytesIO(file_content), "application/pdf")}
        data = {"extraction_type": "invoice"}

        # Mock pipeline failure
        failed_result = PipelineResult(
            document_id=None,
            signal_id=None,
            vendor_id=None,
            commitment_id=None,
            interaction_ids=[],
            metrics={},
            error="Vision API failed",
        )

        with patch("api.routes.documents.get_pipeline", return_value=mock_pipeline):
            with patch("api.routes.documents.get_db", return_value=mock_db):
                mock_pipeline.process_document_upload.return_value = failed_result

                response = client.post("/api/documents/upload", files=files, data=data)

        assert response.status_code == 500
        assert "Vision API failed" in response.json()["detail"]


class TestGetDocument:
    """Tests for GET /api/documents/{document_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_document_success(self, client, mock_db):
        """Test successful document retrieval."""
        document_id = uuid4()

        # Mock document
        mock_document = Mock()
        mock_document.id = document_id
        mock_document.sha256 = "a1b2c3d4e5f6"
        mock_document.path = "data/documents/a1b2c3d4e5f6.pdf"
        mock_document.mime_type = "application/pdf"
        mock_document.file_size = 524288
        mock_document.extraction_type = "invoice"
        mock_document.extraction_cost = 0.0048675
        mock_document.extracted_at = datetime(2025, 11, 8, 12, 0, 0)
        mock_document.created_at = datetime(2025, 11, 8, 12, 0, 0)
        mock_document.content = "Sample extraction content..."

        # Mock document links
        mock_link_vendor = Mock()
        mock_link_vendor.entity_type = "party"
        mock_link_vendor.link_type = "vendor"
        mock_link_vendor.entity_id = uuid4()

        # Mock db queries
        doc_result = Mock()
        doc_result.scalar_one_or_none.return_value = mock_document

        links_result = Mock()
        links_result.scalars.return_value.all.return_value = [mock_link_vendor]

        vendor_result = Mock()
        mock_vendor = Mock()
        mock_vendor.id = mock_link_vendor.entity_id
        mock_vendor.name = "Clipboard Health"
        vendor_result.scalar_one_or_none.return_value = mock_vendor

        mock_db.execute.side_effect = [doc_result, links_result, vendor_result]

        with patch("api.routes.documents.get_db", return_value=mock_db):
            response = client.get(f"/api/documents/{document_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(document_id)
        assert data["sha256"] == "a1b2c3d4e5f6"
        assert data["extraction_type"] == "invoice"
        assert data["vendor"]["name"] == "Clipboard Health"

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, client, mock_db):
        """Test get document when document doesn't exist."""
        document_id = uuid4()

        doc_result = Mock()
        doc_result.scalar_one_or_none.return_value = None

        mock_db.execute.return_value = doc_result

        with patch("api.routes.documents.get_db", return_value=mock_db):
            response = client.get(f"/api/documents/{document_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestDownloadDocument:
    """Tests for GET /api/documents/{document_id}/download endpoint."""

    @pytest.mark.asyncio
    async def test_download_success(self, client, mock_db, tmp_path):
        """Test successful document download."""
        document_id = uuid4()

        # Create a temporary test file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock document
        mock_document = Mock()
        mock_document.id = document_id
        mock_document.path = str(test_file)
        mock_document.mime_type = "application/pdf"

        doc_result = Mock()
        doc_result.scalar_one_or_none.return_value = mock_document

        mock_db.execute.return_value = doc_result

        with patch("api.routes.documents.get_db", return_value=mock_db):
            response = client.get(f"/api/documents/{document_id}/download")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert b"fake pdf content" in response.content

    @pytest.mark.asyncio
    async def test_download_file_not_found(self, client, mock_db):
        """Test download when physical file doesn't exist."""
        document_id = uuid4()

        # Mock document with non-existent file path
        mock_document = Mock()
        mock_document.id = document_id
        mock_document.path = "/nonexistent/path/file.pdf"
        mock_document.mime_type = "application/pdf"

        doc_result = Mock()
        doc_result.scalar_one_or_none.return_value = mock_document

        mock_db.execute.return_value = doc_result

        with patch("api.routes.documents.get_db", return_value=mock_db):
            response = client.get(f"/api/documents/{document_id}/download")

        assert response.status_code == 404
        assert "file not found" in response.json()["detail"].lower()
