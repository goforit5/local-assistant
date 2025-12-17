"""
Abstract base class for storage backends.

Defines the interface that all storage backends (local, S3, Azure) must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class StorageResult:
    """Result of a storage operation.

    Attributes:
        sha256: SHA-256 hash of the stored file
        storage_path: Full path where file is stored
        file_size: Size of file in bytes
        mime_type: MIME type of the file
        deduplicated: True if file already existed (was not newly stored)
        created_at: Timestamp when file was stored
        original_filename: Original filename provided by user
    """
    sha256: str
    storage_path: str
    file_size: int
    mime_type: str
    deduplicated: bool
    created_at: datetime
    original_filename: str


class StorageBackend(ABC):
    """Abstract base class for storage backends.

    All storage backends must implement these methods to provide
    consistent interface for storing, retrieving, and managing files.
    """

    @abstractmethod
    async def store(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        sha256: str
    ) -> StorageResult:
        """Store a file in the backend.

        Args:
            file_bytes: Raw bytes of the file
            filename: Original filename
            mime_type: MIME type of the file
            sha256: SHA-256 hash of the file (pre-calculated)

        Returns:
            StorageResult with metadata about stored file

        Raises:
            IOError: If storage operation fails
        """
        pass

    @abstractmethod
    async def retrieve(self, sha256: str) -> Optional[bytes]:
        """Retrieve a file by its SHA-256 hash.

        Args:
            sha256: SHA-256 hash of the file

        Returns:
            File bytes if found, None otherwise
        """
        pass

    @abstractmethod
    async def exists(self, sha256: str) -> bool:
        """Check if a file exists in storage.

        Args:
            sha256: SHA-256 hash of the file

        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    async def delete(self, sha256: str) -> bool:
        """Delete a file from storage.

        Args:
            sha256: SHA-256 hash of the file

        Returns:
            True if file was deleted, False if file didn't exist
        """
        pass

    @abstractmethod
    async def get_storage_path(self, sha256: str, extension: str) -> str:
        """Get the storage path for a file.

        Args:
            sha256: SHA-256 hash of the file
            extension: File extension (e.g., 'pdf', 'jpg')

        Returns:
            Full storage path as string
        """
        pass
