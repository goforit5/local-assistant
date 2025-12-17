"""Document caching with Redis and database persistence."""

import os
import hashlib
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from redis.asyncio import Redis as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.conversations import ConversationManager
from memory.models import Document


class DocumentCache:
    """Document caching with Redis L1 and PostgreSQL L2."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        conversation_manager: Optional[ConversationManager] = None,
        ttl_seconds: int = 3600
    ):
        """Initialize document cache.

        Args:
            redis_url: Redis connection string.
                      Defaults to REDIS_URL environment variable.
            conversation_manager: ConversationManager for database access.
                                 If None, creates its own instance.
            ttl_seconds: Redis cache TTL in seconds (default: 1 hour)
        """
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL",
            "redis://localhost:6379/0"
        )
        self.conversation_manager = conversation_manager or ConversationManager()
        self.ttl_seconds = ttl_seconds
        self.redis: Optional[aioredis.Redis] = None
        self._owns_manager = conversation_manager is None

    async def initialize(self) -> None:
        """Initialize Redis connection and database."""
        self.redis = await aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )

        if self._owns_manager:
            await self.conversation_manager.initialize()

    async def close(self) -> None:
        """Close Redis and database connections."""
        if self.redis:
            await self.redis.close()

        if self._owns_manager:
            await self.conversation_manager.close()

    @staticmethod
    def _compute_hash(content: str) -> str:
        """Compute SHA-256 hash of content.

        Args:
            content: Content to hash

        Returns:
            Hex-encoded hash string
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _cache_key(self, path: str) -> str:
        """Generate Redis cache key for document path.

        Args:
            path: Document path

        Returns:
            Cache key string
        """
        return f"doc:{path}"

    async def get(
        self,
        path: str,
        skip_cache: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get document from cache or database.

        Args:
            path: Document path
            skip_cache: If True, skip Redis cache and query database directly

        Returns:
            Document dictionary with keys: id, path, content, content_hash,
            created_at, updated_at, metadata. Returns None if not found.
        """
        # Try Redis L1 cache first
        if not skip_cache and self.redis:
            cache_key = self._cache_key(path)
            cached = await self.redis.get(cache_key)

            if cached:
                return json.loads(cached)

        # Query PostgreSQL L2
        async with self.conversation_manager.session_factory() as session:
            query = select(Document).where(Document.path == path)
            result = await session.execute(query)
            document = result.scalar_one_or_none()

            if not document:
                return None

            doc_dict = {
                "id": str(document.id),
                "path": document.path,
                "content": document.content,
                "content_hash": document.content_hash,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
                "metadata": document.metadata_
            }

            # Update Redis cache
            if self.redis:
                cache_key = self._cache_key(path)
                await self.redis.setex(
                    cache_key,
                    self.ttl_seconds,
                    json.dumps(doc_dict)
                )

            return doc_dict

    async def set(
        self,
        path: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Store or update document in cache and database.

        Args:
            path: Document path
            content: Document content
            metadata: Optional metadata dictionary

        Returns:
            Document dictionary with all fields
        """
        content_hash = self._compute_hash(content)

        async with self.conversation_manager.session_factory() as session:
            # Check if document exists
            query = select(Document).where(Document.path == path)
            result = await session.execute(query)
            document = result.scalar_one_or_none()

            if document:
                # Update existing document
                document.content = content
                document.content_hash = content_hash
                document.updated_at = datetime.utcnow()
                if metadata is not None:
                    document.metadata_ = metadata
            else:
                # Create new document
                document = Document(
                    path=path,
                    content=content,
                    content_hash=content_hash,
                    metadata_=metadata
                )
                session.add(document)

            await session.commit()
            await session.refresh(document)

            doc_dict = {
                "id": str(document.id),
                "path": document.path,
                "content": document.content,
                "content_hash": document.content_hash,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
                "metadata": document.metadata_
            }

            # Update Redis cache
            if self.redis:
                cache_key = self._cache_key(path)
                await self.redis.setex(
                    cache_key,
                    self.ttl_seconds,
                    json.dumps(doc_dict)
                )

            return doc_dict

    async def delete(self, path: str) -> bool:
        """Delete document from cache and database.

        Args:
            path: Document path

        Returns:
            True if deleted, False if not found
        """
        # Remove from Redis
        if self.redis:
            cache_key = self._cache_key(path)
            await self.redis.delete(cache_key)

        # Remove from database
        async with self.conversation_manager.session_factory() as session:
            query = select(Document).where(Document.path == path)
            result = await session.execute(query)
            document = result.scalar_one_or_none()

            if not document:
                return False

            await session.delete(document)
            await session.commit()
            return True

    async def invalidate(self, path: str) -> None:
        """Invalidate Redis cache for a document.

        Args:
            path: Document path
        """
        if self.redis:
            cache_key = self._cache_key(path)
            await self.redis.delete(cache_key)

    async def list_documents(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List all documents with pagination.

        Args:
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of document dictionaries (without content field for efficiency)
        """
        async with self.conversation_manager.session_factory() as session:
            query = (
                select(Document)
                .order_by(Document.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )

            result = await session.execute(query)
            documents = result.scalars().all()

            return [
                {
                    "id": str(doc.id),
                    "path": doc.path,
                    "content_hash": doc.content_hash,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat(),
                    "metadata": doc.metadata_
                }
                for doc in documents
            ]

    async def search_by_hash(self, content_hash: str) -> List[Dict[str, Any]]:
        """Find documents by content hash.

        Args:
            content_hash: SHA-256 hash of content

        Returns:
            List of matching document dictionaries
        """
        async with self.conversation_manager.session_factory() as session:
            query = select(Document).where(Document.content_hash == content_hash)
            result = await session.execute(query)
            documents = result.scalars().all()

            return [
                {
                    "id": str(doc.id),
                    "path": doc.path,
                    "content": doc.content,
                    "content_hash": doc.content_hash,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat(),
                    "metadata": doc.metadata_
                }
                for doc in documents
            ]

    async def clear_cache(self) -> None:
        """Clear all document entries from Redis cache."""
        if self.redis:
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(
                    cursor,
                    match="doc:*",
                    count=100
                )
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break
