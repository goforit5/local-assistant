"""
Unit tests for content-addressable storage.
"""

import os
import tempfile
from pathlib import Path

import pytest

from services.document_intelligence.backends.local import LocalStorageBackend
from services.document_intelligence.storage import ContentAddressableStorage


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for storage tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def local_backend(temp_storage_dir):
    """Create a LocalStorageBackend for testing."""
    return LocalStorageBackend(base_path=temp_storage_dir)


@pytest.fixture
def storage(local_backend):
    """Create a ContentAddressableStorage for testing."""
    return ContentAddressableStorage(backend=local_backend)


class TestLocalStorageBackend:
    """Tests for LocalStorageBackend."""

    async def test_store_new_file(self, local_backend, temp_storage_dir):
        """Test storing a new file."""
        file_bytes = b"test content"
        filename = "test.txt"
        mime_type = "text/plain"
        sha256 = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"

        result = await local_backend.store(file_bytes, filename, mime_type, sha256)

        assert result.sha256 == sha256
        assert result.file_size == len(file_bytes)
        assert result.mime_type == mime_type
        assert result.deduplicated is False
        assert result.original_filename == filename
        assert Path(result.storage_path).exists()

    async def test_store_duplicate_file(self, local_backend):
        """Test storing a duplicate file (deduplication)."""
        file_bytes = b"duplicate content"
        filename = "test.txt"
        mime_type = "text/plain"
        sha256 = "8c6744c9d42ec2cb9e8885b54ff744d0821cf8443fd0612c4e935e3b8f5c1a3e"

        # Store first time
        result1 = await local_backend.store(file_bytes, filename, mime_type, sha256)
        assert result1.deduplicated is False

        # Store second time (should detect duplicate)
        result2 = await local_backend.store(file_bytes, filename, mime_type, sha256)
        assert result2.deduplicated is True
        assert result2.sha256 == result1.sha256
        assert result2.storage_path == result1.storage_path

    async def test_retrieve_existing_file(self, local_backend):
        """Test retrieving an existing file."""
        file_bytes = b"retrieve me"
        filename = "test.txt"
        mime_type = "text/plain"
        sha256 = "b8e7ae12e33ee4c87e789c13e876ab7f2c9ef6c3a45a2c30e9f44ad0b18b7f89"

        # Store file
        await local_backend.store(file_bytes, filename, mime_type, sha256)

        # Retrieve file
        retrieved = await local_backend.retrieve(sha256)
        assert retrieved == file_bytes

    async def test_retrieve_nonexistent_file(self, local_backend):
        """Test retrieving a file that doesn't exist."""
        sha256 = "nonexistent123456789"
        retrieved = await local_backend.retrieve(sha256)
        assert retrieved is None

    async def test_exists_returns_true_for_existing_file(self, local_backend):
        """Test exists() returns True for existing file."""
        file_bytes = b"exists test"
        filename = "test.txt"
        mime_type = "text/plain"
        sha256 = "c5f1b8f0e9b3a4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9"

        await local_backend.store(file_bytes, filename, mime_type, sha256)

        exists = await local_backend.exists(sha256)
        assert exists is True

    async def test_exists_returns_false_for_nonexistent_file(self, local_backend):
        """Test exists() returns False for nonexistent file."""
        sha256 = "nonexistent987654321"
        exists = await local_backend.exists(sha256)
        assert exists is False

    async def test_delete_existing_file(self, local_backend):
        """Test deleting an existing file."""
        file_bytes = b"delete me"
        filename = "test.txt"
        mime_type = "text/plain"
        sha256 = "d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8"

        # Store file
        await local_backend.store(file_bytes, filename, mime_type, sha256)

        # Verify exists
        assert await local_backend.exists(sha256) is True

        # Delete file
        deleted = await local_backend.delete(sha256)
        assert deleted is True

        # Verify no longer exists
        assert await local_backend.exists(sha256) is False

    async def test_delete_nonexistent_file(self, local_backend):
        """Test deleting a file that doesn't exist."""
        sha256 = "nonexistent111222333"
        deleted = await local_backend.delete(sha256)
        assert deleted is False

    async def test_get_storage_path(self, local_backend, temp_storage_dir):
        """Test getting storage path for a file."""
        sha256 = "abc123"
        extension = "pdf"

        path = await local_backend.get_storage_path(sha256, extension)

        expected_path = str(Path(temp_storage_dir) / f"{sha256}.{extension}")
        assert path == expected_path

    async def test_store_file_without_extension(self, local_backend):
        """Test storing a file without extension (defaults to .txt)."""
        file_bytes = b"no extension"
        filename = "noext"
        mime_type = "text/plain"
        sha256 = "f0e1d2c3b4a59687706050403020100f0e1d2c3b4a59687706050403020100"

        result = await local_backend.store(file_bytes, filename, mime_type, sha256)

        assert result.storage_path.endswith(".txt")


class TestContentAddressableStorage:
    """Tests for ContentAddressableStorage."""

    async def test_store_calculates_sha256(self, storage):
        """Test that store() calculates SHA-256 hash automatically."""
        file_bytes = b"test content"
        filename = "test.txt"
        mime_type = "text/plain"

        result = await storage.store(file_bytes, filename, mime_type)

        # Verify SHA-256 was calculated
        expected_sha256 = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
        assert result.sha256 == expected_sha256
        assert len(result.sha256) == 64  # SHA-256 is 64 hex characters

    async def test_store_deduplication(self, storage):
        """Test automatic deduplication of identical files."""
        file_bytes = b"duplicate content"
        filename = "test.txt"

        # Store first time
        result1 = await storage.store(file_bytes, filename)
        assert result1.deduplicated is False

        # Store second time with same content
        result2 = await storage.store(file_bytes, filename)
        assert result2.deduplicated is True
        assert result2.sha256 == result1.sha256

    async def test_store_different_files_get_different_hashes(self, storage):
        """Test that different files get different SHA-256 hashes."""
        file1_bytes = b"content 1"
        file2_bytes = b"content 2"

        result1 = await storage.store(file1_bytes, "file1.txt")
        result2 = await storage.store(file2_bytes, "file2.txt")

        assert result1.sha256 != result2.sha256

    async def test_retrieve_by_sha256(self, storage):
        """Test retrieving a file by its SHA-256 hash."""
        file_bytes = b"retrieve this"
        filename = "test.txt"

        # Store file
        result = await storage.store(file_bytes, filename)

        # Retrieve file
        retrieved = await storage.retrieve(result.sha256)
        assert retrieved == file_bytes

    async def test_exists_after_store(self, storage):
        """Test that exists() returns True after storing a file."""
        file_bytes = b"exists test"
        filename = "test.txt"

        result = await storage.store(file_bytes, filename)

        exists = await storage.exists(result.sha256)
        assert exists is True

    async def test_delete_removes_file(self, storage):
        """Test that delete() removes the file."""
        file_bytes = b"delete this"
        filename = "test.txt"

        # Store file
        result = await storage.store(file_bytes, filename)
        assert await storage.exists(result.sha256) is True

        # Delete file
        deleted = await storage.delete(result.sha256)
        assert deleted is True

        # Verify no longer exists
        assert await storage.exists(result.sha256) is False

    async def test_calculate_hash(self, storage):
        """Test calculate_hash() convenience method."""
        file_bytes = b"hash me"

        hash_val = await storage.calculate_hash(file_bytes)

        # Verify it's a valid SHA-256 hash
        assert len(hash_val) == 64
        assert all(c in "0123456789abcdef" for c in hash_val)

    async def test_store_pdf_file(self, storage):
        """Test storing a PDF file."""
        # Minimal PDF file (simplified)
        file_bytes = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
        filename = "test.pdf"
        mime_type = "application/pdf"

        result = await storage.store(file_bytes, filename, mime_type)

        assert result.mime_type == "application/pdf"
        assert result.storage_path.endswith(".pdf")
        assert result.sha256 is not None
