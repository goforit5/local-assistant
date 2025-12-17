"""
Integration tests for content-addressable storage with real PDF files.
"""

import tempfile
from pathlib import Path

import pytest

from services.document_intelligence.storage import ContentAddressableStorage


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def storage(temp_storage_dir):
    """Create a ContentAddressableStorage for integration testing."""
    return ContentAddressableStorage(base_path=temp_storage_dir)


@pytest.fixture
def sample_pdf_bytes():
    """Create a minimal valid PDF file for testing.

    This is a minimal PDF that can be parsed by PDF readers.
    """
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
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000317 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF
"""
    return pdf_content


class TestStorageIntegration:
    """Integration tests for storage with real files."""

    async def test_store_and_retrieve_pdf(self, storage, sample_pdf_bytes):
        """Test storing and retrieving a real PDF file."""
        filename = "test_invoice.pdf"
        mime_type = "application/pdf"

        # Store PDF
        result = await storage.store(sample_pdf_bytes, filename, mime_type)

        assert result.sha256 is not None
        assert result.file_size == len(sample_pdf_bytes)
        assert result.mime_type == "application/pdf"
        assert result.deduplicated is False
        assert result.storage_path.endswith(".pdf")

        # Retrieve PDF
        retrieved = await storage.retrieve(result.sha256)
        assert retrieved == sample_pdf_bytes

    async def test_pdf_deduplication_across_uploads(
        self, storage, sample_pdf_bytes
    ):
        """Test that uploading the same PDF twice results in deduplication."""
        filename1 = "invoice_copy1.pdf"
        filename2 = "invoice_copy2.pdf"
        mime_type = "application/pdf"

        # Upload first time
        result1 = await storage.store(sample_pdf_bytes, filename1, mime_type)
        assert result1.deduplicated is False

        # Upload second time (same content, different filename)
        result2 = await storage.store(sample_pdf_bytes, filename2, mime_type)
        assert result2.deduplicated is True
        assert result2.sha256 == result1.sha256

        # Both should point to the same storage path
        assert result2.storage_path == result1.storage_path

    async def test_store_multiple_different_pdfs(self, storage, sample_pdf_bytes):
        """Test storing multiple different PDF files."""
        # Store first PDF
        result1 = await storage.store(sample_pdf_bytes, "pdf1.pdf", "application/pdf")

        # Modify PDF content slightly
        modified_pdf = sample_pdf_bytes.replace(b"Test PDF", b"Modified")

        # Store second PDF
        result2 = await storage.store(modified_pdf, "pdf2.pdf", "application/pdf")

        # Should have different hashes
        assert result1.sha256 != result2.sha256

        # Both should exist
        assert await storage.exists(result1.sha256) is True
        assert await storage.exists(result2.sha256) is True

        # Retrieve both
        retrieved1 = await storage.retrieve(result1.sha256)
        retrieved2 = await storage.retrieve(result2.sha256)

        assert retrieved1 == sample_pdf_bytes
        assert retrieved2 == modified_pdf

    async def test_store_large_pdf(self, storage):
        """Test storing a larger PDF file (simulated with repeated content)."""
        # Create a larger PDF by repeating content
        large_pdf = b"%PDF-1.4\n" + (b"0123456789" * 10000) + b"\n%%EOF"
        filename = "large_invoice.pdf"

        # Store large PDF
        result = await storage.store(large_pdf, filename, "application/pdf")

        assert result.file_size == len(large_pdf)
        assert result.sha256 is not None

        # Verify retrieval works
        retrieved = await storage.retrieve(result.sha256)
        assert len(retrieved) == len(large_pdf)
        assert retrieved == large_pdf

    async def test_delete_and_verify_removal(self, storage, sample_pdf_bytes):
        """Test deleting a PDF and verifying it's removed."""
        filename = "delete_me.pdf"

        # Store PDF
        result = await storage.store(sample_pdf_bytes, filename, "application/pdf")
        sha256 = result.sha256

        # Verify exists
        assert await storage.exists(sha256) is True

        # Delete
        deleted = await storage.delete(sha256)
        assert deleted is True

        # Verify no longer exists
        assert await storage.exists(sha256) is False

        # Verify retrieval returns None
        retrieved = await storage.retrieve(sha256)
        assert retrieved is None

    async def test_storage_path_is_accessible(self, storage, sample_pdf_bytes):
        """Test that the storage path is accessible from filesystem."""
        filename = "accessible.pdf"

        # Store PDF
        result = await storage.store(sample_pdf_bytes, filename, "application/pdf")

        # Verify file exists on filesystem
        storage_path = Path(result.storage_path)
        assert storage_path.exists()
        assert storage_path.is_file()

        # Verify file content matches
        with open(storage_path, "rb") as f:
            file_content = f.read()
        assert file_content == sample_pdf_bytes

    async def test_concurrent_uploads_same_file(self, storage, sample_pdf_bytes):
        """Test concurrent uploads of the same file (deduplication under load)."""
        import asyncio

        # Upload same file 10 times concurrently
        tasks = [
            storage.store(sample_pdf_bytes, f"concurrent_{i}.pdf", "application/pdf")
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # First one should not be deduplicated
        assert results[0].deduplicated is False

        # All should have the same SHA-256
        sha256 = results[0].sha256
        for result in results:
            assert result.sha256 == sha256

        # Most should be deduplicated (at least 8 out of 10)
        deduplicated_count = sum(1 for r in results if r.deduplicated)
        assert deduplicated_count >= 8
