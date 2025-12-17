"""Storage backend implementations for document intelligence."""

from services.document_intelligence.backends.base import StorageBackend, StorageResult
from services.document_intelligence.backends.local import LocalStorageBackend

__all__ = ["StorageBackend", "StorageResult", "LocalStorageBackend"]
