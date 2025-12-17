"""
Local filesystem storage backend.

Stores files on local disk with SHA-256 hash as filename for content-addressable storage.
"""

import aiofiles
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from services.document_intelligence.backends.base import StorageBackend, StorageResult


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend.

    Files are stored as: {base_path}/{sha256}.{extension}

    Example:
        base_path = "./data/documents"
        sha256 = "a1b2c3d4..."
        extension = "pdf"
        -> "./data/documents/a1b2c3d4....pdf"
    """

    def __init__(self, base_path: str = "./data/documents"):
        """Initialize local storage backend.

        Args:
            base_path: Base directory for storing files (default: ./data/documents)
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def store(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        sha256: str
    ) -> StorageResult:
        """Store a file on local filesystem.

        Args:
            file_bytes: Raw bytes of the file
            filename: Original filename (used to extract extension)
            mime_type: MIME type of the file
            sha256: SHA-256 hash of the file (pre-calculated)

        Returns:
            StorageResult with metadata about stored file
        """
        # Extract extension from filename
        extension = Path(filename).suffix.lstrip(".")
        if not extension:
            # Default to txt if no extension
            extension = "txt"

        # Get storage path
        storage_path = await self.get_storage_path(sha256, extension)

        # Check if file already exists (deduplication)
        file_path = Path(storage_path)
        deduplicated = file_path.exists()

        # Store file if it doesn't exist
        if not deduplicated:
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file_bytes)

        return StorageResult(
            sha256=sha256,
            storage_path=str(file_path),
            file_size=len(file_bytes),
            mime_type=mime_type,
            deduplicated=deduplicated,
            created_at=datetime.utcnow(),
            original_filename=filename
        )

    async def retrieve(self, sha256: str) -> Optional[bytes]:
        """Retrieve a file by its SHA-256 hash.

        Note: Since we don't store the extension separately, we need to
        search for files matching the SHA-256 prefix.

        Args:
            sha256: SHA-256 hash of the file

        Returns:
            File bytes if found, None otherwise
        """
        # Find file matching SHA-256 (any extension)
        matching_files = list(self.base_path.glob(f"{sha256}.*"))

        if not matching_files:
            return None

        # Read the first matching file
        file_path = matching_files[0]
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def exists(self, sha256: str) -> bool:
        """Check if a file exists in storage.

        Args:
            sha256: SHA-256 hash of the file

        Returns:
            True if file exists, False otherwise
        """
        # Find any file matching SHA-256 prefix
        matching_files = list(self.base_path.glob(f"{sha256}.*"))
        return len(matching_files) > 0

    async def delete(self, sha256: str) -> bool:
        """Delete a file from storage.

        Args:
            sha256: SHA-256 hash of the file

        Returns:
            True if file was deleted, False if file didn't exist
        """
        # Find file matching SHA-256
        matching_files = list(self.base_path.glob(f"{sha256}.*"))

        if not matching_files:
            return False

        # Delete the file
        matching_files[0].unlink()
        return True

    async def get_storage_path(self, sha256: str, extension: str) -> str:
        """Get the storage path for a file.

        Args:
            sha256: SHA-256 hash of the file
            extension: File extension (e.g., 'pdf', 'jpg')

        Returns:
            Full storage path as string
        """
        return str(self.base_path / f"{sha256}.{extension}")
