"""
Content-Addressable Storage Service

Provides SHA-256 based content-addressable storage with automatic deduplication.
"""

from typing import Optional

from lib.shared.local_assistant_shared.utils.hash_utils import calculate_sha256
from services.document_intelligence.backends.base import StorageBackend, StorageResult
from services.document_intelligence.backends.local import LocalStorageBackend


class ContentAddressableStorage:
    """Content-addressable storage with SHA-256 hashing.

    Files are stored using their SHA-256 hash as the filename, which provides:
    - Automatic deduplication (same content = same hash = same file)
    - Content verification (hash proves file integrity)
    - Cache-friendly (same hash always returns same content)
    - Provenance tracking (hash in database links to exact file version)

    Example:
        storage = ContentAddressableStorage()
        result = await storage.store(file_bytes, "invoice.pdf", "application/pdf")
        print(f"Stored at: {result.storage_path}")
        print(f"Deduplicated: {result.deduplicated}")
    """

    def __init__(
        self,
        backend: Optional[StorageBackend] = None,
        base_path: str = "./data/documents"
    ):
        """Initialize content-addressable storage.

        Args:
            backend: Storage backend to use (default: LocalStorageBackend)
            base_path: Base path for storage (used if backend is None)
        """
        self.backend = backend or LocalStorageBackend(base_path=base_path)

    async def store(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str = "application/octet-stream"
    ) -> StorageResult:
        """Store a file using content-addressable storage.

        The file's SHA-256 hash is calculated and used as the storage key.
        If a file with the same hash already exists, deduplication is detected
        and the existing file is reused.

        Args:
            file_bytes: Raw bytes of the file
            filename: Original filename (used for extension)
            mime_type: MIME type of the file

        Returns:
            StorageResult with metadata including:
                - sha256: Content hash
                - storage_path: Where file is stored
                - deduplicated: True if file already existed

        Example:
            result = await storage.store(
                file_bytes=pdf_bytes,
                filename="invoice.pdf",
                mime_type="application/pdf"
            )
            if result.deduplicated:
                print("File already exists, reusing existing copy")
        """
        # Calculate SHA-256 hash
        sha256 = calculate_sha256(file_bytes)

        # Store file using backend
        result = await self.backend.store(
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
            sha256=sha256
        )

        return result

    async def retrieve(self, sha256: str) -> Optional[bytes]:
        """Retrieve a file by its SHA-256 hash.

        Args:
            sha256: SHA-256 hash of the file

        Returns:
            File bytes if found, None otherwise

        Example:
            file_bytes = await storage.retrieve(
                "a1b2c3d4e5f6...789"
            )
            if file_bytes:
                print(f"Retrieved {len(file_bytes)} bytes")
        """
        return await self.backend.retrieve(sha256)

    async def exists(self, sha256: str) -> bool:
        """Check if a file exists in storage.

        Args:
            sha256: SHA-256 hash of the file

        Returns:
            True if file exists, False otherwise

        Example:
            if await storage.exists("a1b2c3d4..."):
                print("File already stored")
        """
        return await self.backend.exists(sha256)

    async def delete(self, sha256: str) -> bool:
        """Delete a file from storage.

        Args:
            sha256: SHA-256 hash of the file

        Returns:
            True if file was deleted, False if file didn't exist

        Example:
            deleted = await storage.delete("a1b2c3d4...")
            if deleted:
                print("File deleted successfully")
        """
        return await self.backend.delete(sha256)

    async def calculate_hash(self, file_bytes: bytes) -> str:
        """Calculate SHA-256 hash of file bytes.

        This is a convenience method that wraps the shared utility.

        Args:
            file_bytes: Raw bytes of the file

        Returns:
            SHA-256 hash as hex string (64 characters)

        Example:
            hash_val = await storage.calculate_hash(file_bytes)
            print(f"Hash: {hash_val}")
        """
        return calculate_sha256(file_bytes)
